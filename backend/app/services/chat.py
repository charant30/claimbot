"""
Chat Service - Integrates LangGraph with chat API
"""
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from app.orchestration import (
    supervisor_graph,
    create_initial_state,
    ConversationState,
)
from app.core.logging import logger


# Module-level session store to persist state across requests
# In production, use Redis or database for persistence
_conversation_states: Dict[str, ConversationState] = {}


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
        global _conversation_states
        if thread_id not in _conversation_states:
            _conversation_states[thread_id] = create_initial_state(
                thread_id=thread_id,
                user_id=user_id,
                policy_id=policy_id,
            )
            logger.info(f"Created new conversation state for thread {thread_id}")
        else:
            logger.info(f"Retrieved existing conversation state for thread {thread_id}")
        return _conversation_states[thread_id]
    
    def process_message(
        self,
        thread_id: str,
        user_id: str,
        message: str,
        policy_id: Optional[str] = None,
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
        
        # Update state with current input
        state["current_input"] = message
        
        logger.info(f"Processing message in thread {thread_id}")
        
        try:
            # Run through supervisor graph
            result = supervisor_graph.invoke(state)
            
            # Update session state
            global _conversation_states
            _conversation_states[thread_id] = result
            
            # Prepare response
            response = {
                "thread_id": thread_id,
                "response": result.get("ai_response", "I'm sorry, I couldn't process that."),
                "intent": result.get("intent"),
                "product_line": result.get("product_line"),
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
        global _conversation_states
        if thread_id in _conversation_states:
            del _conversation_states[thread_id]


# Factory function for dependency injection
def get_chat_service(db: Session) -> ChatService:
    """Get chat service instance."""
    return ChatService(db)
