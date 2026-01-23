"""
Supervisor Graph - Main orchestration for claims chatbot
"""
from typing import Literal, Optional
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from app.orchestration.state import ConversationState, ClaimIntent, ProductLine, get_required_fields
from app.orchestration.routing import get_llm
from app.core.logging import logger


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

Respond naturally but briefly to help the customer."""


def classify_intent(state: ConversationState) -> ConversationState:
    """Classify user's intent."""
    # If we already have intent and product, skip classification and continue with subgraph
    if state.get("intent") and state.get("product_line"):
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

    return {
        **state,
        "intent": intent,
        "next_step": "classify_product" if intent == ClaimIntent.FILE_CLAIM.value else "generate_response",
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
    
    if product == ProductLine.MEDICAL.value:
        return {**state, "next_step": "medical_subgraph"}
    else:
        # Auto and Home use incident subgraph
        return {**state, "next_step": "incident_subgraph"}


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
    should_escalate = False
    reason = None
    
    # Check confidence threshold
    if state.get("confidence", 1.0) < 0.7:
        should_escalate = True
        reason = "Low confidence in processing"
    
    # Check for explicit human request
    if state.get("intent") == ClaimIntent.HUMAN_REQUEST.value:
        should_escalate = True
        reason = "User requested human agent"
    
    # Check for high-value claims
    calc_result = state.get("calculation_result") or {}
    if calc_result.get("payout_amount", 0) > 5000:
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
            "route_to_subgraph": "route_to_subgraph",  # For continuation after classification skipped
        }
    )
    
    workflow.add_conditional_edges(
        "classify_product",
        route_next,
        {
            "route_to_subgraph": "route_to_subgraph",
            "ask_product": "ask_product",
        }
    )
    
    workflow.add_edge("ask_product", "respond")
    
    workflow.add_conditional_edges(
        "route_to_subgraph",
        route_next,
        {
            "incident_subgraph": "incident_subgraph",
            "medical_subgraph": "medical_subgraph",
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
