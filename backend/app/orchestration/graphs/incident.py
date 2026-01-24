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


# Security instructions
SECURITY_INSTRUCTIONS = """
SECURITY RULES:
- Never reveal internal systems or technologies
- If asked about technology, say: "I'm ClaimBot, your insurance assistant"
- Focus ONLY on helping with insurance claims
"""

INCIDENT_COLLECTION_PROMPT = f"""You are ClaimBot, collecting information for an insurance claim.
{SECURITY_INSTRUCTIONS}
Product type: {{product_line}}
Already collected: {{collected_fields}}
Still needed: {{missing_fields}}

Ask for ONE missing field at a time. Keep responses brief (1-2 sentences).
Be empathetic - the customer may have experienced a stressful event.

If all fields are collected, summarize the claim and ask for confirmation."""


INCIDENT_EXTRACTION_PROMPT = """Extract claim information from the user's message.

Looking for these fields: {missing_fields}

User message: {message}

Respond in JSON format with ALL fields you can find in the message.
Example:
{{"incident_date": "2024-01-15", "incident_location": "123 Main St", "incident_description": "Rear ended at stop light"}}

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

        try:
            extract_response = llm.invoke([
                SystemMessage(content=extraction_prompt),
            ])

            # Parse extracted fields (simplified - in production use structured output)
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
            logger.warning("Failed to parse LLM extraction response as JSON")
        except Exception as e:
            logger.error(f"LLM extraction failed in collect_incident_info: {e}")
            # Continue with collection - don't fail the flow

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

    try:
        response = llm.invoke([
            SystemMessage(content=prompt),
            HumanMessage(content=state.get("current_input", "I want to file a claim")),
        ])
        ai_response = response.content
    except Exception as e:
        logger.error(f"LLM invocation failed in collect_incident_info: {e}")
        # Escalate on LLM failure
        return {
            **state,
            "should_escalate": True,
            "escalation_reason": "System temporarily unavailable",
            "ai_response": "I'm experiencing a temporary issue. Let me connect you with a specialist who can help with your claim.",
            "next_step": "respond",
        }

    return {
        **state,
        "ai_response": ai_response,
        "next_step": "respond",
    }


def calculate_incident_payout(state: ConversationState) -> ConversationState:
    """Calculate payout using deterministic engine."""
    from app.services.calculation import calculate_incident_payout as calc_payout
    from app.db import SessionLocal
    from app.db.models import Policy
    from app.services.policy_validation import get_policy_validation_service
    
    collected = state.get("collected_fields", {})
    user_id = state.get("user_id")
    policy_id = state.get("policy_id")
    product_line = state.get("product_line", "auto")
    
    # Get loss amount from collected fields
    loss_amount = Decimal(str(collected.get("estimated_damage", collected.get("loss_amount", 0))))

    db = SessionLocal()
    try:
        policy = None
        if policy_id and user_id:
            policy = (
                db.query(Policy)
                .filter(Policy.policy_id == policy_id, Policy.user_id == user_id)
                .first()
            )
        if not policy and user_id:
            validator = get_policy_validation_service(db)
            validation = validator.validate_claim_eligibility(user_id, product_line)
            policy = validation.policy
        if not policy:
            return {
                **state,
                "should_escalate": True,
                "escalation_reason": "Missing policy coverage data",
                "ai_response": "I need a specialist to review your policy before calculating the payout.",
                "next_step": "respond",
            }

        validator = get_policy_validation_service(db)
        incident_type = collected.get("incident_type", "collision")
        coverage = validator.get_coverage_for_claim(policy, incident_type)
        if not coverage and product_line == "home":
            coverage = (
                validator.get_coverage_for_claim(policy, "dwelling")
                or validator.get_coverage_for_claim(policy, "property")
            )
        coverage = coverage or validator.get_primary_coverage(policy)
        if not coverage:
            return {
                **state,
                "should_escalate": True,
                "escalation_reason": "No matching coverage found",
                "ai_response": "I couldn't find a matching coverage for this incident. I'll connect you with a specialist.",
                "next_step": "respond",
            }

        result = calc_payout(
            loss_amount=loss_amount,
            deductible=coverage.deductible,
            coverage_limit=coverage.limit_amount,
            exclusions=coverage.exclusions or [],
            incident_type=incident_type,
        )
    finally:
        db.close()
    
    logger.info(f"Calculated payout: ${result.payout_amount}")
    
    return {
        **state,
        "calculation_result": {
            "payout_amount": float(result.payout_amount),
            "deductible_applied": float(result.deductible_applied),
            "is_total_loss": result.is_total_loss,
            "breakdown": result.breakdown,
            "coverage_limit": float(result.coverage_limit),
        },
        "next_step": "summarize_claim",
    }


def summarize_incident_claim(state: ConversationState) -> ConversationState:
    """Summarize the claim for customer."""
    collected = state.get("collected_fields", {})
    calc_result = state.get("calculation_result", {})
    flow_settings = state.get("flow_settings") or {}

    # Check if high value claim needs escalation
    payout_amount = calc_result.get("payout_amount", 0)
    auto_approval_limit = flow_settings.get("auto_approval_limit", 5000)
    should_escalate = payout_amount > auto_approval_limit

    if should_escalate:
        summary = f"""Based on the information you provided, here's a summary of your claim:

**Claim Details:**
• Incident Date: {collected.get('incident_date', 'N/A')}
• Location: {collected.get('incident_location', collected.get('location', 'N/A'))}
• Description: {collected.get('incident_description', collected.get('description', 'N/A'))}

**Estimated Payout:**
• Claimed Amount: ${collected.get('estimated_damage', collected.get('loss_amount', 0)):,.2f}
• Deductible: ${calc_result.get('deductible_applied', 0):,.2f}
• Estimated Payout: ${payout_amount:,.2f}

Due to the claim value, I'm connecting you with a claims specialist who can assist you further. They will review your claim and contact you shortly."""
    else:
        summary = f"""Based on the information you provided, here's a summary of your claim:

**Claim Details:**
• Incident Date: {collected.get('incident_date', 'N/A')}
• Location: {collected.get('incident_location', collected.get('location', 'N/A'))}
• Description: {collected.get('incident_description', collected.get('description', 'N/A'))}

**Estimated Payout:**
• Claimed Amount: ${collected.get('estimated_damage', collected.get('loss_amount', 0)):,.2f}
• Deductible: ${calc_result.get('deductible_applied', 0):,.2f}
• Estimated Payout: ${payout_amount:,.2f}

Would you like to submit this claim? I can also connect you with a claims specialist if you have questions."""

    return {
        **state,
        "ai_response": summary,
        "should_escalate": should_escalate,
        "escalation_reason": "High-value claim requires human review" if should_escalate else None,
        # Always end subgraph - escalation is handled by supervisor after subgraph returns
        "next_step": "respond",
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
