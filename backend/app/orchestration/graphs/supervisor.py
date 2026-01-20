"""
Supervisor Graph - Main orchestration for claims chatbot
"""
from typing import Literal, Optional
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from app.orchestration.state import ConversationState, ClaimIntent, ProductLine, get_required_fields
from app.orchestration.routing import get_llm
from app.core.logging import logger


# System prompts
CLASSIFIER_PROMPT = """You are an insurance claims assistant. Classify the user's intent.

Available intents:
- file_claim: User wants to file a new claim
- check_status: User wants to check status of existing claim
- coverage_question: User has a question about their coverage
- billing: User has a billing inquiry
- human_request: User explicitly asks for a human agent
- unknown: Cannot determine intent

Respond with ONLY the intent name, nothing else."""

PRODUCT_CLASSIFIER_PROMPT = """Based on the conversation, determine which insurance product line this is about.

Available products:
- auto: Vehicle/car insurance
- home: Homeowners/property insurance
- medical: Health/medical insurance

Respond with ONLY the product name, nothing else."""

CONVERSATION_PROMPT = """You are a helpful insurance claims assistant for ClaimBot.

Your role:
- Help customers file claims and answer questions
- Collect required information step by step
- Be empathetic and professional
- Never calculate payouts yourself - use the calculation tools
- If you're unsure or the customer asks for a human, escalate

Current context:
- User ID: {user_id}
- Policy ID: {policy_id}
- Intent: {intent}
- Product: {product_line}
- Collected fields: {collected_fields}
- Missing fields: {missing_fields}

Respond naturally to help the customer."""


def classify_intent(state: ConversationState) -> ConversationState:
    """Classify user's intent."""
    llm = get_llm()
    
    messages = [
        SystemMessage(content=CLASSIFIER_PROMPT),
        HumanMessage(content=state["current_input"]),
    ]
    
    response = llm.invoke(messages)
    intent = response.content.strip().lower()
    
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
    
    response = llm.invoke(messages)
    product = response.content.strip().lower()
    
    # Validate product
    valid_products = [p.value for p in ProductLine]
    if product not in valid_products:
        product = None
    
    logger.info(f"Classified product: {product}")
    
    # Get required fields
    required = get_required_fields(state["intent"], product) if product else []
    
    return {
        **state,
        "product_line": product,
        "required_fields": required,
        "missing_fields": required.copy(),
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
    
    response = llm.invoke(messages)
    
    return {
        **state,
        "ai_response": response.content,
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
    calc_result = state.get("calculation_result", {})
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


def build_supervisor_graph() -> StateGraph:
    """Build the supervisor graph."""
    workflow = StateGraph(ConversationState)
    
    # Add nodes
    workflow.add_node("classify_intent", classify_intent)
    workflow.add_node("classify_product", classify_product)
    workflow.add_node("ask_product", ask_product)
    workflow.add_node("route_to_subgraph", route_to_subgraph)
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
            "incident_subgraph": "generate_response",  # Placeholder - will invoke subgraph
            "medical_subgraph": "generate_response",   # Placeholder - will invoke subgraph
        }
    )
    
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
    
    return workflow.compile()


# Compiled graph instance
supervisor_graph = build_supervisor_graph()
