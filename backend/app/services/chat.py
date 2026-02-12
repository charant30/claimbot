"""
Chat Service - Integrates LangGraph with chat API
"""
from typing import Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session

from app.orchestration import (
    supervisor_graph,
    create_initial_state,
    ConversationState,
    get_required_fields,
)
from app.db.models import SystemSettings, Case, CaseStatus
from app.core.logging import logger
from app.services.session_store import get_session_store


STATE_KEY_PREFIX = "conversation_state:"


class ChatService:
    """Service for processing chat messages through LangGraph."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_or_create_session(
        self,
        thread_id: str,
        user_id: str,
        policy_id: Optional[str] = None,
    ) -> ConversationState:
        """Get existing session or create new one."""
        session_store = get_session_store()
        state_key = f"{STATE_KEY_PREFIX}{thread_id}"
        state = session_store.get(state_key)
        if not state:
            state = create_initial_state(
                thread_id=thread_id,
                user_id=user_id,
                policy_id=policy_id,
            )
            logger.info(f"Created new conversation state for thread {thread_id}")
        else:
            logger.info(f"Retrieved existing conversation state for thread {thread_id}")
        session_store.set(state_key, state, ttl_hours=24)
        return state

    def _get_flow_settings(self) -> Dict[str, Any]:
        setting = (
            self.db.query(SystemSettings)
            .filter(SystemSettings.key == "flows")
            .first()
        )
        if setting and isinstance(setting.value, dict):
            return setting.value
        return {
            "confidence_threshold": 0.7,
            "auto_approval_limit": 5000,
            "escalation_triggers": [
                "low_confidence",
                "high_amount",
                "user_request",
                "coverage_ambiguity",
            ],
        }

    def _apply_metadata(
        self,
        state: ConversationState,
        metadata: Optional[Dict[str, Any]],
    ) -> ConversationState:
        if not metadata:
            return state

        intent = metadata.get("intent")
        product_line = metadata.get("product_line")
        claim_id = metadata.get("claim_id")
        policy_id = metadata.get("policy_id")
        claim_form = metadata.get("claim_form")
        claim_number = metadata.get("claim_number")

        if intent and not state.get("intent"):
            state["intent"] = intent

        if product_line and not state.get("product_line"):
            state["product_line"] = product_line

        if claim_id and not state.get("claim_id"):
            state["claim_id"] = claim_id

        if claim_number and not state.get("claim_number"):
            state["claim_number"] = claim_number

        if policy_id and not state.get("policy_id"):
            state["policy_id"] = policy_id

        # Extract claim form data into collected_fields
        if claim_form:
            collected = state.get("collected_fields") or {}
            # Map frontend form fields to backend field names
            field_mapping = {
                "incidentDate": "incident_date",
                "incidentType": "incident_type",
                "location": "incident_location",
                "description": "incident_description",
                "estimatedLoss": "estimated_damage",
                "policyNumber": "policy_number",
            }
            for frontend_key, backend_key in field_mapping.items():
                if frontend_key in claim_form and claim_form[frontend_key]:
                    collected[backend_key] = claim_form[frontend_key]
            state["collected_fields"] = collected
            logger.info(f"Applied form data to collected_fields: {list(collected.keys())}")

        if state.get("intent") and state.get("product_line") and not state.get("required_fields"):
            required = get_required_fields(state["intent"], state["product_line"])
            state["required_fields"] = required
            state["missing_fields"] = required.copy()

        # Update missing_fields based on what we've collected
        if state.get("required_fields") and state.get("collected_fields"):
            collected = state["collected_fields"]
            state["missing_fields"] = [f for f in state["required_fields"] if f not in collected]

        return state
    
    def process_message(
        self,
        thread_id: str,
        user_id: str,
        message: str,
        policy_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Process a user message through the LangGraph supervisor.
        
        Args:
            thread_id: Chat thread ID
            user_id: User's ID
            message: User's message
            policy_id: Optional policy context
            
        Returns:
            Response with AI message and metadata
        """
        # Get or create session state
        state = self.get_or_create_session(thread_id, user_id, policy_id)
        
        # Apply admin flow settings and any frontend metadata
        state["flow_settings"] = self._get_flow_settings()
        state = self._apply_metadata(state, metadata)

        # Check for active case (ESCALATED or AGENT_HANDLING)
        active_case = (
            self.db.query(Case)
            .filter(
                Case.chat_thread_id == thread_id,
                Case.status.in_([CaseStatus.ESCALATED, CaseStatus.AGENT_HANDLING])
            )
            .first()
        )
        
        if active_case:
            logger.info(f"Thread {thread_id} has active case {active_case.case_id} ({active_case.status}) - skipping AI")
            
            # Append user message to history so agent sees it
            current_messages = state.get("messages", [])
            new_msg = {
                "role": "user",
                "content": message,
                "created_at": datetime.utcnow().isoformat(),
                "metadata": {"actor_id": user_id}
            }
            current_messages.append(new_msg)
            state["messages"] = current_messages
            
            # Save updated state
            session_store = get_session_store()
            state_key = f"{STATE_KEY_PREFIX}{thread_id}"
            session_store.set(state_key, state, ttl_hours=24)
            
            return {
                "thread_id": thread_id,
                "response": "A specialist will be with you shortly." if active_case.status == CaseStatus.ESCALATED else "",
                "intent": "human_request",
                "should_escalate": True,
                "claim_id": str(active_case.claim_id) if active_case.claim_id else None,
            }

        # Update state with current input
        state["current_input"] = message
        
        logger.info(f"Processing message in thread {thread_id}")
        
        try:
            # Run through supervisor graph
            result = supervisor_graph.invoke(state)
            agent_trace = result.get("agent_trace") or []
            agent_trace.append({
                "agent": "supervisor_graph",
                "input": {"message": message, "thread_id": thread_id},
                "output": {
                    "intent": result.get("intent"),
                    "product_line": result.get("product_line"),
                    "should_escalate": result.get("should_escalate", False),
                },
                "timestamp": datetime.utcnow().isoformat(),
            })
            result["agent_trace"] = agent_trace
            
            # Update session state
            session_store = get_session_store()
            state_key = f"{STATE_KEY_PREFIX}{thread_id}"
            session_store.set(state_key, result, ttl_hours=24)
            
            # Prepare response
            response = {
                "thread_id": thread_id,
                "response": result.get("ai_response", "I'm sorry, I couldn't process that."),
                "intent": result.get("intent"),
                "product_line": result.get("product_line"),
                "claim_id": result.get("claim_id"),
                "should_escalate": result.get("should_escalate", False),
                "escalation_reason": result.get("escalation_reason"),
                "collected_fields": result.get("collected_fields", {}),
                "calculation_result": result.get("calculation_result"),
            }
            
            # If escalation needed, create case packet
            if result.get("should_escalate"):
                response["case_packet"] = result.get("case_packet")
            
            return response
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            return {
                "thread_id": thread_id,
                "response": "I'm having trouble processing your request. Let me connect you with a specialist.",
                "should_escalate": True,
                "escalation_reason": f"Processing error: {str(e)}",
            }
    
    def clear_session(self, thread_id: str) -> None:
        """Clear a chat session."""
        session_store = get_session_store()
        state_key = f"{STATE_KEY_PREFIX}{thread_id}"
        session_store.delete(state_key)


# Factory function for dependency injection
def get_chat_service(db: Session) -> ChatService:
    """Get chat service instance."""
    return ChatService(db)
