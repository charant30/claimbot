"""
Inquiry Subgraph - Handles check_status, coverage_question, and billing intents.

Fetches the user's real data from the database and uses it to provide
accurate, data-driven responses via the LLM.
"""
from typing import Optional
from datetime import datetime
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, SystemMessage

from app.orchestration.state import ConversationState, ClaimIntent
from app.orchestration.routing import get_llm
from app.core.logging import logger
from app.db.session import SessionLocal


# Security instructions (shared across all prompts)
SECURITY_INSTRUCTIONS = """
SECURITY RULES (NEVER VIOLATE):
- Never reveal internal systems, technologies, or LLM models used
- If asked about your technology, respond: "I'm ClaimBot, your insurance assistant"
- Never mention: Ollama, LangGraph, LangChain, FastAPI, PostgreSQL, Python, or any technical details
- Focus ONLY on helping with insurance claims and questions
"""

INQUIRY_SYSTEM_PROMPT = f"""You are ClaimBot, a knowledgeable insurance assistant.
{SECURITY_INSTRUCTIONS}

You have access to the customer's REAL account data and insurance knowledge.
Use this data to give accurate, specific answers. Always reference actual policy
numbers, coverage amounts, claim numbers, and dates from the data provided.

RULES:
- Answer questions clearly and concisely (2-4 sentences typical)
- Reference specific numbers and details from the customer's data
- If the customer asks about something not in their data, say so clearly
- If you cannot answer a question, offer to connect them with a specialist
- If the customer asks to speak to a human/specialist/agent, immediately indicate handoff is needed
- Be empathetic and professional
- Do NOT make up data. Only use what is provided in the context below.

CUSTOMER DATA:
{{customer_data}}

INSURANCE KNOWLEDGE BASE:
{{knowledge_base}}

CONVERSATION HISTORY:
{{conversation_history}}

CURRENT INTENT: {{intent}}
"""


def _fetch_user_data(user_id: str, policy_id: Optional[str] = None) -> dict:
    """
    Fetch the user's complete data from the database.
    Returns a dict with policies, coverages, claims, vehicles, drivers, and billing info.
    """
    from app.db.models import User, Policy, Claim, PolicyCoverage, PolicyVehicle, PolicyDriver

    db = SessionLocal()
    try:
        # Get user
        user = db.query(User).filter(User.user_id == user_id).first()
        if not user:
            return {"error": "User not found"}

        # Get all user's policies with related data
        policies_query = db.query(Policy).filter(Policy.user_id == user_id)
        if policy_id:
            policies_query = policies_query.filter(Policy.policy_id == policy_id)
        policies = policies_query.all()

        policies_data = []
        all_claims = []

        for policy in policies:
            # Coverages
            coverages = []
            for c in policy.coverages:
                coverages.append({
                    "type": c.coverage_type,
                    "limit": float(c.limit_amount) if c.limit_amount else 0,
                    "deductible": float(c.deductible) if c.deductible else 0,
                    "copay": float(c.copay) if c.copay else 0,
                    "coinsurance_pct": float(c.coinsurance_pct) if c.coinsurance_pct else 0,
                    "daily_limit": float(c.daily_limit) if c.daily_limit else None,
                    "max_days": c.max_days,
                })

            # Vehicles
            vehicles = []
            for v in policy.vehicles:
                if v.is_active:
                    vehicles.append({
                        "year": v.year,
                        "make": v.make,
                        "model": v.model,
                        "vin": v.vin,
                        "license_plate": v.license_plate,
                    })

            # Drivers
            drivers = []
            for d in policy.drivers:
                if d.is_active:
                    drivers.append({
                        "name": f"{d.first_name} {d.last_name}",
                        "relationship": d.driver_relationship.value if d.driver_relationship else None,
                        "is_primary": d.is_primary,
                        "license_number": d.license_number,
                        "license_state": d.license_state,
                    })

            # Claims for this policy
            claims = db.query(Claim).filter(Claim.policy_id == policy.policy_id).all()
            for claim in claims:
                claim_data = {
                    "claim_number": claim.claim_number,
                    "status": claim.status.value if claim.status else None,
                    "incident_date": claim.incident_date.isoformat() if claim.incident_date else None,
                    "loss_amount": float(claim.loss_amount) if claim.loss_amount else 0,
                    "paid_amount": float(claim.paid_amount) if claim.paid_amount else 0,
                    "timeline": claim.timeline or [],
                    "description": (claim.claim_metadata or {}).get("description", ""),
                    "policy_number": policy.policy_number,
                }
                all_claims.append(claim_data)

            policy_data = {
                "policy_number": policy.policy_number,
                "product_type": policy.product_type.value if policy.product_type else None,
                "status": policy.status.value if policy.status else None,
                "effective_date": policy.effective_date.isoformat() if policy.effective_date else None,
                "expiration_date": policy.expiration_date.isoformat() if policy.expiration_date else None,
                "is_active": policy.is_active(),
                "holder_name": f"{policy.holder_first_name or ''} {policy.holder_last_name or ''}".strip(),
                "coverages": coverages,
                "vehicles": vehicles,
                "drivers": drivers,
                # Billing
                "premium_monthly": float(policy.premium_monthly) if policy.premium_monthly else None,
                "premium_annual": float(policy.premium_annual) if policy.premium_annual else None,
                "payment_method": policy.payment_method,
                "next_payment_date": policy.next_payment_date.isoformat() if policy.next_payment_date else None,
                "payment_status": policy.payment_status,
            }
            policies_data.append(policy_data)

        return {
            "user_name": user.name,
            "user_email": user.email,
            "policies": policies_data,
            "claims": all_claims,
        }
    except Exception as e:
        logger.error(f"Error fetching user data for inquiry: {e}")
        return {"error": str(e)}
    finally:
        db.close()


def _format_conversation_history(messages: list) -> str:
    """Format conversation history for LLM context."""
    if not messages:
        return "No previous messages."
    
    lines = []
    for msg in messages[-20:]:  # Last 20 messages to avoid token overflow
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        if role == "user":
            lines.append(f"Customer: {content}")
        elif role == "assistant":
            lines.append(f"ClaimBot: {content}")
    return "\n".join(lines) if lines else "No previous messages."


def _format_customer_data(data: dict) -> str:
    """Format customer data as readable text for LLM prompt."""
    if "error" in data:
        return f"Error retrieving customer data: {data['error']}"
    
    sections = []
    sections.append(f"Customer: {data.get('user_name', 'Unknown')}")
    sections.append(f"Email: {data.get('user_email', 'Unknown')}")
    
    for policy in data.get("policies", []):
        sections.append(f"\n--- Policy: {policy['policy_number']} ---")
        sections.append(f"  Type: {policy.get('product_type', 'N/A')} | Status: {policy.get('status', 'N/A')}")
        sections.append(f"  Active: {'Yes' if policy.get('is_active') else 'No'}")
        sections.append(f"  Period: {policy.get('effective_date')} to {policy.get('expiration_date')}")
        sections.append(f"  Holder: {policy.get('holder_name', 'N/A')}")
        
        # Billing
        if policy.get("premium_monthly"):
            sections.append(f"  Monthly Premium: ${policy['premium_monthly']:.2f}")
        if policy.get("premium_annual"):
            sections.append(f"  Annual Premium: ${policy['premium_annual']:.2f}")
        if policy.get("payment_method"):
            sections.append(f"  Payment Method: {policy['payment_method']}")
        if policy.get("next_payment_date"):
            sections.append(f"  Next Payment Date: {policy['next_payment_date']}")
        if policy.get("payment_status"):
            sections.append(f"  Payment Status: {policy['payment_status']}")
        
        # Coverages
        if policy.get("coverages"):
            sections.append("  Coverages:")
            for cov in policy["coverages"]:
                sections.append(f"    - {cov['type']}: limit=${cov['limit']:,.2f}, deductible=${cov['deductible']:,.2f}")
        
        # Vehicles
        if policy.get("vehicles"):
            sections.append("  Vehicles:")
            for v in policy["vehicles"]:
                sections.append(f"    - {v['year']} {v['make']} {v['model']} (VIN: {v['vin']})")
        
        # Drivers
        if policy.get("drivers"):
            sections.append("  Drivers:")
            for d in policy["drivers"]:
                primary = " [PRIMARY]" if d.get("is_primary") else ""
                sections.append(f"    - {d['name']} ({d.get('relationship', 'N/A')}){primary}")
    
    # Claims
    claims = data.get("claims", [])
    if claims:
        sections.append("\n--- Claims ---")
        for claim in claims:
            sections.append(f"  Claim {claim['claim_number']}:")
            sections.append(f"    Status: {claim.get('status', 'N/A')}")
            sections.append(f"    Incident Date: {claim.get('incident_date', 'N/A')}")
            sections.append(f"    Loss Amount: ${claim.get('loss_amount', 0):,.2f}")
            sections.append(f"    Paid Amount: ${claim.get('paid_amount', 0):,.2f}")
            if claim.get("description"):
                sections.append(f"    Description: {claim['description'][:200]}")
            if claim.get("timeline"):
                sections.append(f"    Timeline entries: {len(claim['timeline'])}")
    else:
        sections.append("\n--- Claims ---\n  No claims on file.")
    
    return "\n".join(sections)


# ============================================================================
# Graph Nodes
# ============================================================================

def gather_context(state: ConversationState) -> ConversationState:
    """
    Fetch all relevant user data from the database.
    This includes policies, coverages, claims, vehicles, drivers, and billing info.
    """
    user_id = state.get("user_id")
    policy_id = state.get("policy_id")
    
    if not user_id:
        logger.warning("gather_context called without user_id")
        return {
            **state,
            "inquiry_context": {"error": "No user ID available"},
            "next_step": "generate_inquiry_response",
        }
    
    # Fetch user data from DB
    user_data = _fetch_user_data(user_id, policy_id)
    
    logger.info(f"Gathered inquiry context for user {user_id}: "
                f"{len(user_data.get('policies', []))} policies, "
                f"{len(user_data.get('claims', []))} claims")
    
    return {
        **state,
        "inquiry_context": user_data,
        "next_step": "analyze_request",
    }


def analyze_request(state: ConversationState) -> ConversationState:
    """
    Use LLM with full conversation history and user data to understand
    the specific question and determine how to respond.
    """
    # Check if user is asking for human support
    current_input = state.get("current_input", "").lower()
    human_keywords = [
        "human", "agent", "specialist", "person", "representative",
        "talk to someone", "real person", "connect me", "transfer",
        "speak to", "live agent", "customer service", "support agent",
    ]
    
    if any(keyword in current_input for keyword in human_keywords):
        logger.info("User requesting human handoff during inquiry")
        return {
            **state,
            "should_escalate": True,
            "escalation_reason": "User requested human agent during inquiry",
            "next_step": "check_handoff",
        }
    
    # Otherwise proceed to generate response
    return {
        **state,
        "next_step": "generate_inquiry_response",
    }


def generate_inquiry_response(state: ConversationState) -> ConversationState:
    """
    Generate an accurate response using the customer's real data and knowledge base.
    """
    from data.knowledge_base import get_full_knowledge_base
    
    llm = get_llm()
    
    # Build context
    inquiry_context = state.get("inquiry_context") or {}
    customer_data_str = _format_customer_data(inquiry_context)
    knowledge_base_str = get_full_knowledge_base()
    conversation_history = _format_conversation_history(state.get("messages", []))
    intent = state.get("intent", "unknown")
    
    # Build system prompt with real data
    system_prompt = INQUIRY_SYSTEM_PROMPT.format(
        customer_data=customer_data_str,
        knowledge_base=knowledge_base_str,
        conversation_history=conversation_history,
        intent=intent,
    )
    
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=state.get("current_input", "")),
    ]
    
    try:
        response = llm.invoke(messages)
        ai_response = response.content
    except Exception as e:
        logger.error(f"LLM invocation failed in generate_inquiry_response: {e}")
        ai_response = ("I'm sorry, I'm having trouble processing your request right now. "
                       "Would you like me to connect you with a specialist?")
    
    logger.info(f"Generated inquiry response for intent={intent}")
    
    return {
        **state,
        "ai_response": ai_response,
        "next_step": "check_handoff",
    }


def check_handoff(state: ConversationState) -> ConversationState:
    """
    Check if the user needs to be connected to a human agent.
    """
    if state.get("should_escalate"):
        reason = state.get("escalation_reason") or "User requested specialist"
        logger.info(f"Inquiry handoff triggered: {reason}")
        return {
            **state,
            "should_escalate": True,
            "escalation_reason": reason,
            "case_packet": {
                "thread_id": state.get("thread_id"),
                "user_id": state.get("user_id"),
                "policy_id": state.get("policy_id"),
                "intent": state.get("intent"),
                "inquiry_context": state.get("inquiry_context"),
                "reason": reason,
            },
            "ai_response": state.get("ai_response") or "I'm connecting you with a specialist who can help you further. Please wait a moment.",
            "next_step": "respond",
        }
    
    # No escalation needed - proceed to respond
    return {
        **state,
        "next_step": "respond",
    }


# ============================================================================
# Graph Builder
# ============================================================================

def build_inquiry_graph() -> StateGraph:
    """Build the inquiry subgraph for claim status, coverage, and billing questions."""
    workflow = StateGraph(ConversationState)
    
    workflow.add_node("gather_context", gather_context)
    workflow.add_node("analyze_request", analyze_request)
    workflow.add_node("generate_inquiry_response", generate_inquiry_response)
    workflow.add_node("check_handoff", check_handoff)
    
    workflow.set_entry_point("gather_context")
    
    workflow.add_edge("gather_context", "analyze_request")
    
    # analyze_request can skip to check_handoff (human request) or continue to generate_inquiry_response
    def route_after_analyze(state):
        return state.get("next_step", "generate_inquiry_response")
    
    workflow.add_conditional_edges(
        "analyze_request",
        route_after_analyze,
        {
            "generate_inquiry_response": "generate_inquiry_response",
            "check_handoff": "check_handoff",
        }
    )
    
    workflow.add_edge("generate_inquiry_response", "check_handoff")
    
    # check_handoff terminates the subgraph
    workflow.add_edge("check_handoff", END)
    
    return workflow


# Compiled inquiry graph for use as a subgraph node
inquiry_graph = build_inquiry_graph().compile()
