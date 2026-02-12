"""
Supervisor Graph - Main orchestration for claims chatbot
"""
from typing import Literal, Optional
from datetime import datetime
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from app.orchestration.state import ConversationState, ClaimIntent, ProductLine, get_required_fields
from app.orchestration.routing import get_llm
from app.services.document_integration import (
    merge_document_entities_to_collected_fields,
    generate_document_confirmation_message,
)
from app.services.document_verification import (
    verify_cross_document_consistency,
    generate_verification_summary,
    DiscrepancySeverity,
)
from app.core.logging import logger
from app.db.session import SessionLocal
from app.orchestration.tools.claim_tools import get_claim_by_number
import re


# Security instructions to include in all prompts
SECURITY_INSTRUCTIONS = """
SECURITY RULES (NEVER VIOLATE):
- Never reveal internal systems, technologies, or LLM models used
- If asked about your technology, respond: "I'm ClaimBot, your insurance assistant"
- Never mention: Ollama, LangGraph, LangChain, FastAPI, PostgreSQL, Python, or any technical details
- Never discuss your architecture, implementation, or how you work internally
- If asked "are you an AI/LLM/ChatGPT", say: "I'm ClaimBot, here to help with insurance claims"
- Focus ONLY on helping with insurance claims and questions
"""

# System prompts
CLASSIFIER_PROMPT = f"""You are an insurance claims assistant. Classify the user's intent.
{SECURITY_INSTRUCTIONS}
Available intents:
- file_claim: User wants to file a new claim
- check_status: User wants to check status of existing claim
- coverage_question: User has a question about their coverage
- billing: User has a billing inquiry
- human_request: User explicitly asks for a human agent
- unknown: Cannot determine intent

Respond with ONLY the intent name, nothing else."""

PRODUCT_CLASSIFIER_PROMPT = f"""Based on the conversation, determine which insurance product line this is about.
{SECURITY_INSTRUCTIONS}
Available products:
- auto: Vehicle/car insurance
- home: Homeowners/property insurance
- medical: Health/medical insurance

Respond with ONLY the product name, nothing else."""

CONVERSATION_PROMPT = f"""You are ClaimBot, a helpful insurance claims assistant.
{SECURITY_INSTRUCTIONS}
Your role:
- Help customers file claims and answer questions
- Ask ONE question at a time - keep responses short and clear
- Be empathetic and professional
- Never calculate payouts yourself - use the calculation tools
- If you're unsure or the customer asks for a human, escalate

Current context:
- Intent: {{intent}}
- Product: {{product_line}}
- Collected fields: {{collected_fields}}
- Missing fields: {{missing_fields}}
- Claim Details: {{claim_details}}

Respond naturally but briefly to help the customer."""


def classify_intent(state: ConversationState) -> ConversationState:
    """Classify user's intent."""
    # If we already have intent and product, skip classification and continue with subgraph
    # ONLY for file_claim — other intents (check_status, coverage_question, billing) should
    # always re-classify so the user can change intent (e.g. "connect to specialist")
    if state.get("intent") == ClaimIntent.FILE_CLAIM.value and state.get("product_line"):
        logger.info(f"Skipping classification, continuing with intent={state['intent']}, product={state['product_line']}")
        return {
            **state,
            "next_step": "route_to_subgraph",
        }

    # If we have intent but no product (user is responding to product question), skip to product classification
    if state.get("intent") == ClaimIntent.FILE_CLAIM.value and not state.get("product_line"):
        logger.info(f"Intent already set to {state['intent']}, classifying product from user response")
        return {
            **state,
            "next_step": "classify_product",
        }

    llm = get_llm()

    messages = [
        SystemMessage(content=CLASSIFIER_PROMPT),
        HumanMessage(content=state["current_input"]),
    ]

    try:
        response = llm.invoke(messages)
        intent = response.content.strip().lower()
    except Exception as e:
        logger.error(f"LLM invocation failed in classify_intent: {e}")
        # Escalate on LLM failure - let human handle
        return {
            **state,
            "intent": ClaimIntent.UNKNOWN.value,
            "should_escalate": True,
            "escalation_reason": "System temporarily unavailable",
            "ai_response": "I'm experiencing a temporary issue. Let me connect you with a specialist who can help.",
            "next_step": "escalate",
        }

    # Validate intent
    valid_intents = [i.value for i in ClaimIntent]
    if intent not in valid_intents:
        intent = ClaimIntent.UNKNOWN.value

    logger.info(f"Classified intent: {intent}")

    # Check for human request
    if intent == ClaimIntent.HUMAN_REQUEST.value:
        return {
            **state,
            "intent": intent,
            "should_escalate": True,
            "escalation_reason": "User requested human agent",
            "next_step": "escalate",
        }

    next_step = "generate_response"
    if intent == ClaimIntent.FILE_CLAIM.value:
        next_step = "classify_product"
    elif intent == ClaimIntent.CHECK_STATUS.value:
        next_step = "agent_status"

    return {
        **state,
        "intent": intent,
        "next_step": next_step,
    }


def classify_product(state: ConversationState) -> ConversationState:
    """Classify product line for claim."""
    # If policy is already known, get product from policy
    if state.get("policy_id"):
        # In real implementation, lookup policy product type
        # For now, ask the LLM to classify
        pass

    llm = get_llm()

    messages = [
        SystemMessage(content=PRODUCT_CLASSIFIER_PROMPT),
        HumanMessage(content=state["current_input"]),
    ]

    try:
        response = llm.invoke(messages)
        product = response.content.strip().lower()
    except Exception as e:
        logger.error(f"LLM invocation failed in classify_product: {e}")
        # Fall back to asking user to specify product
        return {
            **state,
            "product_line": None,
            "next_step": "ask_product",
        }
    
    # Validate product
    valid_products = [p.value for p in ProductLine]
    if product not in valid_products:
        product = None
    
    logger.info(f"Classified product: {product}")
    
    # Only set required/missing fields if not already set (preserve progress)
    required = state.get("required_fields") or []
    missing = state.get("missing_fields") or []
    
    if not required and product:
        required = get_required_fields(state["intent"], product)
        missing = required.copy()
    
    return {
        **state,
        "product_line": product,
        "required_fields": required,
        "missing_fields": missing,
        "next_step": "route_to_subgraph" if product else "ask_product",
    }


def ask_product(state: ConversationState) -> ConversationState:
    """Ask user to specify product type."""
    return {
        **state,
        "ai_response": "I'd be happy to help you file a claim. Which type of insurance is this for?\n\n• **Auto** - Vehicle or car insurance\n• **Home** - Homeowners or property insurance\n• **Medical** - Health or medical insurance",
        "next_step": "respond",
    }


def route_to_subgraph(state: ConversationState) -> ConversationState:
    """Route to appropriate subgraph based on product line."""
    product = state.get("product_line")

    # Handle missing product - should not happen but fail gracefully
    if not product:
        logger.warning("route_to_subgraph called without product_line set")
        return {**state, "next_step": "ask_product"}

    if product == ProductLine.MEDICAL.value:
        return {**state, "next_step": "medical_subgraph"}
    elif product in (ProductLine.AUTO.value, ProductLine.HOME.value):
        return {**state, "next_step": "incident_subgraph"}
    else:
        # Unknown product type - ask user to clarify
        logger.warning(f"Unknown product_line: {product}")
        return {**state, "next_step": "ask_product"}


def route_agents(state: ConversationState) -> ConversationState:
    """Route to agent pipeline for multi-step validation."""
    if state.get("intent") == ClaimIntent.FILE_CLAIM.value:
        return {**state, "next_step": "agent_intake"}
    return {**state, "next_step": "route_to_subgraph"}


def _append_agent_trace(state: ConversationState, agent: str, output: dict = None) -> ConversationState:
    """Append an agent trace entry without mutating the original state."""
    existing_trace = state.get("agent_trace") or []
    new_entry = {
        "agent": agent,
        "input": {
            "intent": state.get("intent"),
            "product_line": state.get("product_line"),
            "current_input": state.get("current_input"),
        },
        "output": output or {},
        "timestamp": datetime.utcnow().isoformat(),
    }
    # Create new list to avoid mutating original state
    return {**state, "agent_trace": [*existing_trace, new_entry]}


def agent_intake(state: ConversationState) -> ConversationState:
    """Stub intake agent - validates and enriches intake data."""
    state = _append_agent_trace(state, "agent_intake", {"status": "ok"})
    return {**state, "next_step": "agent_documents"}


def agent_documents(state: ConversationState) -> ConversationState:
    """
    Document verification agent - processes uploaded documents and merges extracted data.

    Reads documents associated with the current claim/thread and merges
    OCR-extracted entities into the collected_fields. Also performs cross-document
    verification when multiple documents are present.
    """
    documents = state.get("uploaded_documents", [])

    if not documents:
        # No documents to process yet
        state = _append_agent_trace(state, "agent_documents", {"status": "no_documents"})
        return {**state, "next_step": "agent_policy"}

    # Merge document entities into collected fields
    collected = state.get("collected_fields", {})
    required = state.get("required_fields", [])

    merged_collected = merge_document_entities_to_collected_fields(
        collected_fields=collected,
        documents=documents,
        required_fields=required,
    )

    # Update missing fields
    missing = [f for f in required if f not in merged_collected]

    # Count how many fields were added from documents
    fields_added = len(merged_collected) - len(collected)

    # Check for any new documents that need confirmation
    pending_review = state.get("pending_document_review", False)
    ai_response = None

    if pending_review and documents:
        # Generate confirmation for the most recent document
        latest_doc = documents[-1]
        ai_response = generate_document_confirmation_message(
            doc_type=latest_doc.get("doc_type", "document"),
            extracted_entities=latest_doc.get("extracted_entities", {}),
        )

    # Run cross-document verification when we have multiple documents
    verification_result = None
    document_discrepancies = state.get("document_discrepancies", [])
    should_escalate = state.get("should_escalate", False)
    escalation_reason = state.get("escalation_reason")

    if len(documents) >= 2:
        verification_result = verify_cross_document_consistency(
            documents=documents,
            collected_fields=merged_collected,
            tolerance_days=7,
        )

        # Store discrepancies
        document_discrepancies = [d.to_dict() for d in verification_result.discrepancies]

        # Check for error-level discrepancies that require escalation
        error_discrepancies = [
            d for d in verification_result.discrepancies
            if d.severity == DiscrepancySeverity.ERROR
        ]

        if error_discrepancies:
            should_escalate = True
            escalation_reason = f"Document verification failed: {error_discrepancies[0].details}"
            logger.warning(f"Cross-document verification found {len(error_discrepancies)} error(s)")

        # Add verification summary to response if we have discrepancies
        if verification_result.discrepancies and ai_response:
            summary = generate_verification_summary(verification_result)
            ai_response = f"{ai_response}\n\n---\n**Verification Note:**\n{summary}"
        elif verification_result.discrepancies and not ai_response:
            ai_response = generate_verification_summary(verification_result)

        logger.info(f"Cross-document verification: valid={verification_result.is_valid}, "
                    f"confidence={verification_result.confidence_score:.2f}, "
                    f"discrepancies={len(verification_result.discrepancies)}")

    state = _append_agent_trace(state, "agent_documents", {
        "status": "processed",
        "documents_count": len(documents),
        "fields_added_from_documents": fields_added,
        "verification_valid": verification_result.is_valid if verification_result else None,
        "discrepancy_count": len(document_discrepancies),
    })

    logger.info(f"agent_documents: processed {len(documents)} documents, added {fields_added} fields")

    result = {
        **state,
        "collected_fields": merged_collected,
        "missing_fields": missing,
        "pending_document_review": False,
        "document_discrepancies": document_discrepancies,
        "verified_documents": verification_result.verified_fields if verification_result else {},
        "confidence": verification_result.confidence_score if verification_result else state.get("confidence", 1.0),
        "should_escalate": should_escalate,
        "escalation_reason": escalation_reason,
        "next_step": "agent_policy",
    }

    # If we have a confirmation message, return it to the user
    if ai_response:
        result["ai_response"] = ai_response
        result["next_step"] = "respond"

    # If escalation is needed due to verification errors, route to escalation
    if should_escalate and document_discrepancies:
        result["next_step"] = "escalate"

    return result


def agent_policy(state: ConversationState) -> ConversationState:
    """Stub policy agent - checks policy coverage and deductibles."""
    state = _append_agent_trace(state, "agent_policy", {"status": "policy_checked"})
    return {**state, "next_step": "agent_decision"}


def agent_decision(state: ConversationState) -> ConversationState:
    """Stub decision agent - reconciles findings and routes onward."""
    state = _append_agent_trace(state, "agent_decision", {"status": "decision_ready"})
    return {**state, "next_step": "route_to_subgraph"}


def agent_status(state: ConversationState) -> ConversationState:
    """Check claim status if intent is check_status."""
    claim_number = state.get("claim_number")
    current_input = state.get("current_input", "")
    
    # Try to extract claim number if not set (or if user provides a different one)
    # Regex for common formats (INC-*, CLM-*, AUT-*, etc.)
    match = re.search(r"([A-Z]{3,}-[A-Z0-9]+)", current_input, re.IGNORECASE)
    if match:
        extracted = match.group(0).upper()
        # If we found a new claim number, update it
        if extracted != claim_number:
            claim_number = extracted
            
    if not claim_number:
        # Prompt user for claim number
        return {
            **state,
            "next_step": "generate_response",
        }

    # Fetch claim details
    db = SessionLocal()
    try:
        result = get_claim_by_number(claim_number, db)
    finally:
        db.close()
        
    state = _append_agent_trace(state, "agent_status", {"found": "error" not in result})
    
    if "error" in result:
        # Claim not found
        return {
            **state,
            "claim_number": claim_number,
            "claim_details": {"error": result["error"]},
            "next_step": "generate_response", 
        }
        
    return {
        **state,
        "claim_number": claim_number,
        "claim_details": result,
        # Infer product line from claim product if not set
        "product_line": state.get("product_line") or (ProductLine.AUTO.value if "auto" in str(result.get("description", "")).lower() else None),
        "next_step": "generate_response",
    }


def generate_response(state: ConversationState) -> ConversationState:
    """Generate conversational response."""
    llm = get_llm()

    prompt = CONVERSATION_PROMPT.format(
        user_id=state.get("user_id", "unknown"),
        policy_id=state.get("policy_id", "not selected"),
        intent=state.get("intent", "unknown"),
        product_line=state.get("product_line", "not determined"),
        collected_fields=state.get("collected_fields", {}),
        missing_fields=state.get("missing_fields", []),
        claim_details=state.get("claim_details", "Not checked"),
    )

    messages = [
        SystemMessage(content=prompt),
        HumanMessage(content=state["current_input"]),
    ]

    try:
        response = llm.invoke(messages)
        ai_response = response.content
    except Exception as e:
        logger.error(f"LLM invocation failed in generate_response: {e}")
        # Escalate on LLM failure
        return {
            **state,
            "should_escalate": True,
            "escalation_reason": "System temporarily unavailable",
            "ai_response": "I'm experiencing a temporary issue. Let me connect you with a specialist who can help.",
            "next_step": "escalate",
        }

    return {
        **state,
        "ai_response": ai_response,
        "next_step": "respond",
    }


def check_escalation(state: ConversationState) -> ConversationState:
    """Check if escalation is needed."""
    if state.get("should_escalate"):
        reason = state.get("escalation_reason") or "Escalation requested"
        return {
            **state,
            "should_escalate": True,
            "escalation_reason": reason,
            "case_packet": {
                "thread_id": state.get("thread_id"),
                "user_id": state.get("user_id"),
                "policy_id": state.get("policy_id"),
                "intent": state.get("intent"),
                "collected_fields": state.get("collected_fields"),
                "calculation_result": state.get("calculation_result"),
                "reason": reason,
            },
            "next_step": "escalate",
        }

    flow_settings = state.get("flow_settings") or {}
    confidence_threshold = flow_settings.get("confidence_threshold", 0.7)
    auto_approval_limit = flow_settings.get("auto_approval_limit", 5000)
    should_escalate = False
    reason = None
    
    # Check confidence threshold
    if state.get("confidence", 1.0) < confidence_threshold:
        should_escalate = True
        reason = "Low confidence in processing"
    
    # Check for explicit human request
    if state.get("intent") == ClaimIntent.HUMAN_REQUEST.value:
        should_escalate = True
        reason = "User requested human agent"
    
    # Check for high-value claims
    calc_result = state.get("calculation_result") or {}
    if calc_result.get("payout_amount", 0) > auto_approval_limit:
        should_escalate = True
        reason = "High-value claim requires review"
    
    if should_escalate:
        return {
            **state,
            "should_escalate": True,
            "escalation_reason": reason,
            "case_packet": {
                "thread_id": state.get("thread_id"),
                "user_id": state.get("user_id"),
                "policy_id": state.get("policy_id"),
                "intent": state.get("intent"),
                "collected_fields": state.get("collected_fields"),
                "calculation_result": state.get("calculation_result"),
                "reason": reason,
            },
            "next_step": "escalate",
        }
    
    return {**state, "next_step": "respond"}


def escalate(state: ConversationState) -> ConversationState:
    """Escalate to human agent."""
    logger.info(f"Escalating case: {state.get('escalation_reason')}")
    
    return {
        **state,
        "ai_response": "I'm connecting you with a claims specialist who can help you further. Please wait a moment while I transfer you.",
        "next_step": "respond",
        "is_complete": True,
    }


def respond(state: ConversationState) -> ConversationState:
    """Final response step - adds message to history."""
    new_messages = [
        {"role": "user", "content": state["current_input"]},
        {"role": "assistant", "content": state["ai_response"]},
    ]
    
    return {
        **state,
        "messages": new_messages,
        "next_step": END,
    }


def route_next(state: ConversationState) -> str:
    """Determine next node based on state."""
    return state.get("next_step", END)


from app.orchestration.graphs.incident import incident_graph
from app.orchestration.graphs.medical import medical_graph

# ... existing code ...

def build_supervisor_graph() -> StateGraph:
    """Build the supervisor graph."""
    workflow = StateGraph(ConversationState)
    
    # Add nodes
    workflow.add_node("classify_intent", classify_intent)
    workflow.add_node("classify_product", classify_product)
    workflow.add_node("ask_product", ask_product)
    workflow.add_node("route_to_subgraph", route_to_subgraph)
    workflow.add_node("route_agents", route_agents)
    workflow.add_node("agent_intake", agent_intake)
    workflow.add_node("agent_documents", agent_documents)
    workflow.add_node("agent_policy", agent_policy)
    workflow.add_node("agent_decision", agent_decision)
    workflow.add_node("agent_status", agent_status)
    
    # Add subgraph nodes
    workflow.add_node("incident_subgraph", incident_graph)
    workflow.add_node("medical_subgraph", medical_graph)
    
    workflow.add_node("generate_response", generate_response)
    workflow.add_node("check_escalation", check_escalation)
    workflow.add_node("escalate", escalate)
    workflow.add_node("respond", respond)
    
    # Set entry point
    workflow.set_entry_point("classify_intent")
    
    # Add conditional edges
    workflow.add_conditional_edges(
        "classify_intent",
        route_next,
        {
            "classify_product": "classify_product",
            "generate_response": "generate_response",
            "escalate": "escalate",
            "route_to_subgraph": "route_to_subgraph",
            "agent_status": "agent_status",
        }
    )

    workflow.add_edge("agent_status", "generate_response")
    
    workflow.add_conditional_edges(
        "classify_product",
        route_next,
        {
            "route_to_subgraph": "route_agents",
            "ask_product": "ask_product",
        }
    )

    workflow.add_conditional_edges(
        "route_agents",
        route_next,
        {
            "agent_intake": "agent_intake",
            "route_to_subgraph": "route_to_subgraph",
        }
    )

    workflow.add_edge("agent_intake", "agent_documents")

    # agent_documents can route to respond (for confirmation), escalate (for errors), or continue
    workflow.add_conditional_edges(
        "agent_documents",
        route_next,
        {
            "agent_policy": "agent_policy",
            "respond": "respond",
            "escalate": "escalate",
        }
    )

    workflow.add_edge("agent_policy", "agent_decision")
    workflow.add_edge("agent_decision", "route_to_subgraph")
    
    workflow.add_edge("ask_product", "respond")
    
    workflow.add_conditional_edges(
        "route_to_subgraph",
        route_next,
        {
            "incident_subgraph": "incident_subgraph",
            "medical_subgraph": "medical_subgraph",
            "ask_product": "ask_product",  # Fallback for missing/invalid product
        }
    )
    
    # Route output of subgraphs
    workflow.add_edge("incident_subgraph", "check_escalation")
    workflow.add_edge("medical_subgraph", "check_escalation")
    
    workflow.add_edge("generate_response", "check_escalation")
    
    workflow.add_conditional_edges(
        "check_escalation",
        route_next,
        {
            "escalate": "escalate",
            "respond": "respond",
        }
    )
    
    workflow.add_edge("escalate", "respond")
    workflow.add_edge("respond", END)
    
    return workflow


def get_compiled_supervisor():
    """Get the compiled supervisor graph with checkpointer."""
    try:
        from app.core.checkpointer import get_checkpointer
        checkpointer = get_checkpointer()
        return build_supervisor_graph().compile(checkpointer=checkpointer)
    except Exception as e:
        logger.warning(f"Failed to initialize checkpointer, using in-memory: {e}")
        return build_supervisor_graph().compile()


# Compiled graph instance
supervisor_graph = build_supervisor_graph().compile()
