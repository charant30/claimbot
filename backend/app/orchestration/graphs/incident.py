"""
Incident Subgraph - Handles Auto and Home claims
"""
from typing import Optional
from decimal import Decimal
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, SystemMessage

from app.orchestration.state import ConversationState, get_required_fields
from app.orchestration.routing import get_llm
from app.core.logging import logger


INCIDENT_COLLECTION_PROMPT = """You are collecting information for an insurance claim.

Product type: {product_line}
Already collected: {collected_fields}
Still needed: {missing_fields}

Ask for ONE missing field at a time in a natural, conversational way.
Be empathetic - the customer may have experienced a stressful event.

If all fields are collected, summarize the claim and ask for confirmation."""


INCIDENT_EXTRACTION_PROMPT = """Extract claim information from the user's message.

Looking for these fields: {missing_fields}

User message: {message}

Respond in JSON format with any fields you can extract. Example:
{{"incident_date": "2024-01-15", "incident_location": "123 Main St"}}

Only include fields you can confidently extract. If none, respond with {{}}."""


def collect_incident_info(state: ConversationState) -> ConversationState:
    """Collect incident claim information."""
    llm = get_llm()
    
    # Try to extract fields from current input
    if state.get("current_input"):
        extraction_prompt = INCIDENT_EXTRACTION_PROMPT.format(
            missing_fields=state.get("missing_fields", []),
            message=state["current_input"],
        )
        
        extract_response = llm.invoke([
            SystemMessage(content=extraction_prompt),
        ])
        
        # Parse extracted fields (simplified - in production use structured output)
        try:
            import json
            extracted = json.loads(extract_response.content)
            if isinstance(extracted, dict) and extracted:
                # Update collected fields
                collected = {**state.get("collected_fields", {}), **extracted}
                missing = [f for f in state.get("missing_fields", []) if f not in collected]
                
                logger.info(f"Extracted fields: {list(extracted.keys())}")
                
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
            "next_step": "calculate_payout",
        }
    
    # Generate collection prompt
    prompt = INCIDENT_COLLECTION_PROMPT.format(
        product_line=state.get("product_line", "auto"),
        collected_fields=state.get("collected_fields", {}),
        missing_fields=state.get("missing_fields", []),
    )
    
    response = llm.invoke([
        SystemMessage(content=prompt),
        HumanMessage(content=state.get("current_input", "I want to file a claim")),
    ])
    
    return {
        **state,
        "ai_response": response.content,
        "next_step": "respond",
    }


def calculate_incident_payout(state: ConversationState) -> ConversationState:
    """Calculate payout using deterministic engine."""
    from app.services.calculation import calculate_incident_payout as calc_payout
    
    collected = state.get("collected_fields", {})
    
    # Get loss amount from collected fields
    loss_amount = Decimal(str(collected.get("estimated_damage", collected.get("loss_amount", 0))))
    
    # Simplified - in production, lookup policy coverages
    deductible = Decimal("500")
    coverage_limit = Decimal("50000")
    
    result = calc_payout(
        loss_amount=loss_amount,
        deductible=deductible,
        coverage_limit=coverage_limit,
        exclusions=[],
        incident_type=collected.get("incident_type", "collision"),
    )
    
    logger.info(f"Calculated payout: ${result.payout_amount}")
    
    return {
        **state,
        "calculation_result": {
            "payout_amount": float(result.payout_amount),
            "deductible_applied": float(result.deductible_applied),
            "is_total_loss": result.is_total_loss,
            "breakdown": result.breakdown,
        },
        "next_step": "summarize_claim",
    }


def summarize_incident_claim(state: ConversationState) -> ConversationState:
    """Summarize the claim for customer."""
    collected = state.get("collected_fields", {})
    calc_result = state.get("calculation_result", {})
    
    summary = f"""Based on the information you provided, here's a summary of your claim:

**Claim Details:**
• Incident Date: {collected.get('incident_date', 'N/A')}
• Location: {collected.get('incident_location', collected.get('location', 'N/A'))}
• Description: {collected.get('incident_description', collected.get('description', 'N/A'))}

**Estimated Payout:**
• Claimed Amount: ${collected.get('estimated_damage', collected.get('loss_amount', 0)):,.2f}
• Deductible: ${calc_result.get('deductible_applied', 0):,.2f}
• Estimated Payout: ${calc_result.get('payout_amount', 0):,.2f}

Would you like to submit this claim? I can also connect you with a claims specialist if you have questions."""

    # Check if high value claim needs escalation
    should_escalate = calc_result.get("payout_amount", 0) > 5000
    
    return {
        **state,
        "ai_response": summary,
        "should_escalate": should_escalate,
        "escalation_reason": "High-value claim requires human review" if should_escalate else None,
        "next_step": "check_escalation" if should_escalate else "respond",
    }


def route_incident(state: ConversationState) -> str:
    """Route to next step in incident flow."""
    return state.get("next_step", END)


def build_incident_graph() -> StateGraph:
    """Build the incident claims subgraph."""
    workflow = StateGraph(ConversationState)
    
    # Add nodes
    workflow.add_node("collect_info", collect_incident_info)
    workflow.add_node("calculate_payout", calculate_incident_payout)
    workflow.add_node("summarize_claim", summarize_incident_claim)
    
    # Set entry point
    workflow.set_entry_point("collect_info")
    
    # Add conditional edges
    workflow.add_conditional_edges(
        "collect_info",
        route_incident,
        {
            "calculate_payout": "calculate_payout",
            "respond": END,
        }
    )
    
    workflow.add_edge("calculate_payout", "summarize_claim")
    workflow.add_edge("summarize_claim", END)
    
    return workflow.compile()


# Compiled graph instance
incident_graph = build_incident_graph()
