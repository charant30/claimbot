"""
Medical Subgraph - Handles Medical/Health claims
"""
from typing import Optional
from decimal import Decimal
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, SystemMessage

from app.orchestration.state import ConversationState, get_required_fields
from app.orchestration.routing import get_llm
from app.core.logging import logger


MEDICAL_COLLECTION_PROMPT = """You are helping a member submit a medical claim.

Already collected: {collected_fields}
Still needed: {missing_fields}

Ask for ONE missing item at a time. Be patient and helpful.
For provider NPI, explain they can find it on their receipt or EOB.
For diagnosis/procedure codes, offer to help look them up.

If all fields collected, summarize and provide the Explanation of Benefits."""


MEDICAL_EXTRACTION_PROMPT = """Extract medical claim information from the member's message.

Looking for: {missing_fields}

Message: {message}

Respond in JSON format. Example:
{{"service_date": "2024-01-15", "provider_name": "Dr. Smith", "billed_amount": 250.00}}

Only include fields you can confidently extract."""


def collect_medical_info(state: ConversationState) -> ConversationState:
    """Collect medical claim information."""
    llm = get_llm()
    
    # Try to extract fields from current input
    if state.get("current_input"):
        extraction_prompt = MEDICAL_EXTRACTION_PROMPT.format(
            missing_fields=state.get("missing_fields", []),
            message=state["current_input"],
        )
        
        extract_response = llm.invoke([
            SystemMessage(content=extraction_prompt),
        ])
        
        try:
            import json
            extracted = json.loads(extract_response.content)
            if isinstance(extracted, dict) and extracted:
                collected = {**state.get("collected_fields", {}), **extracted}
                missing = [f for f in state.get("missing_fields", []) if f not in collected]
                
                logger.info(f"Extracted medical fields: {list(extracted.keys())}")
                
                state = {
                    **state,
                    "collected_fields": collected,
                    "missing_fields": missing,
                }
        except json.JSONDecodeError:
            pass
    
    # Check if all fields collected
    if not state.get("missing_fields"):
        return {
            **state,
            "next_step": "check_eligibility",
        }
    
    # Generate collection prompt
    prompt = MEDICAL_COLLECTION_PROMPT.format(
        collected_fields=state.get("collected_fields", {}),
        missing_fields=state.get("missing_fields", []),
    )
    
    response = llm.invoke([
        SystemMessage(content=prompt),
        HumanMessage(content=state.get("current_input", "I want to submit a medical claim")),
    ])
    
    return {
        **state,
        "ai_response": response.content,
        "next_step": "respond",
    }


def check_eligibility(state: ConversationState) -> ConversationState:
    """Check member eligibility and coverage."""
    collected = state.get("collected_fields", {})
    
    # Simplified eligibility check - in production, verify against policy
    is_eligible = True
    eligibility_message = "Coverage verified and active."
    
    if not is_eligible:
        return {
            **state,
            "ai_response": f"I'm sorry, but there's an issue with coverage: {eligibility_message}. Let me connect you with a specialist.",
            "should_escalate": True,
            "escalation_reason": "Eligibility issue",
            "next_step": "respond",
        }
    
    return {
        **state,
        "next_step": "check_provider_network",
    }


def check_provider_network_status(state: ConversationState) -> ConversationState:
    """Check if provider is in-network."""
    collected = state.get("collected_fields", {})
    provider_npi = collected.get("provider_npi", "")
    
    # Simplified - in production, lookup in Provider table
    is_in_network = True  # Default to in-network for demo
    
    return {
        **state,
        "collected_fields": {
            **collected,
            "is_in_network": is_in_network,
        },
        "next_step": "adjudicate_claim",
    }


def adjudicate_medical_claim(state: ConversationState) -> ConversationState:
    """Adjudicate the medical claim using deterministic engine."""
    from app.services.calculation import adjudicate_medical_claim as adjudicate
    
    collected = state.get("collected_fields", {})
    
    billed_amount = Decimal(str(collected.get("billed_amount", 0)))
    is_in_network = collected.get("is_in_network", True)
    
    # Simplified - in production, lookup from Provider and Policy
    allowed_amount = billed_amount * Decimal("0.80") if is_in_network else Decimal("0")
    copay = Decimal("40")
    deductible_remaining = Decimal("500")
    coinsurance_pct = Decimal("20")
    coverage_limit = Decimal("100000")
    
    result = adjudicate(
        billed_amount=billed_amount,
        allowed_amount=allowed_amount,
        copay=copay,
        deductible_remaining=deductible_remaining,
        coinsurance_pct=coinsurance_pct,
        coverage_limit=coverage_limit,
        is_in_network=is_in_network,
    )
    
    logger.info(f"Medical adjudication: member=${result.member_responsibility}, payer=${result.payer_responsibility}")
    
    return {
        **state,
        "calculation_result": {
            "billed_amount": float(result.billed_amount),
            "allowed_amount": float(result.allowed_amount),
            "copay": float(result.copay),
            "deductible_applied": float(result.deductible_applied),
            "coinsurance_amount": float(result.coinsurance_amount),
            "member_responsibility": float(result.member_responsibility),
            "payer_responsibility": float(result.payer_responsibility),
            "is_in_network": result.is_in_network,
            "breakdown": result.breakdown,
        },
        "next_step": "generate_eob",
    }


def generate_eob(state: ConversationState) -> ConversationState:
    """Generate Explanation of Benefits."""
    collected = state.get("collected_fields", {})
    calc_result = state.get("calculation_result", {})
    
    network_status = "In-Network" if calc_result.get("is_in_network") else "Out-of-Network"
    
    eob = f"""**Explanation of Benefits (EOB)**

**Service Information:**
• Date of Service: {collected.get('service_date', 'N/A')}
• Provider: {collected.get('provider_name', 'N/A')}
• Network Status: {network_status}

**Claim Breakdown:**
| Description | Amount |
|-------------|--------|
| Billed Amount | ${calc_result.get('billed_amount', 0):,.2f} |
| Allowed Amount | ${calc_result.get('allowed_amount', 0):,.2f} |
| Copay | ${calc_result.get('copay', 0):,.2f} |
| Deductible Applied | ${calc_result.get('deductible_applied', 0):,.2f} |
| Coinsurance ({int(calc_result.get('breakdown', {}).get('coinsurance_pct', 20))}%) | ${calc_result.get('coinsurance_amount', 0):,.2f} |

**Your Responsibility: ${calc_result.get('member_responsibility', 0):,.2f}**
**Plan Pays: ${calc_result.get('payer_responsibility', 0):,.2f}**

This is an estimate. Your actual responsibility may vary based on remaining deductible and other factors.

Would you like me to submit this claim, or do you have any questions?"""

    return {
        **state,
        "ai_response": eob,
        "next_step": "respond",
    }


def route_medical(state: ConversationState) -> str:
    """Route to next step in medical flow."""
    return state.get("next_step", END)


def build_medical_graph() -> StateGraph:
    """Build the medical claims subgraph."""
    workflow = StateGraph(ConversationState)
    
    # Add nodes
    workflow.add_node("collect_info", collect_medical_info)
    workflow.add_node("check_eligibility", check_eligibility)
    workflow.add_node("check_provider_network", check_provider_network_status)
    workflow.add_node("adjudicate_claim", adjudicate_medical_claim)
    workflow.add_node("generate_eob", generate_eob)
    
    # Set entry point
    workflow.set_entry_point("collect_info")
    
    # Add conditional edges
    workflow.add_conditional_edges(
        "collect_info",
        route_medical,
        {
            "check_eligibility": "check_eligibility",
            "respond": END,
        }
    )
    
    workflow.add_conditional_edges(
        "check_eligibility",
        route_medical,
        {
            "check_provider_network": "check_provider_network",
            "respond": END,
        }
    )
    
    workflow.add_edge("check_provider_network", "adjudicate_claim")
    workflow.add_edge("adjudicate_claim", "generate_eob")
    workflow.add_edge("generate_eob", END)
    
    return workflow.compile()


# Compiled graph instance
medical_graph = build_medical_graph()
