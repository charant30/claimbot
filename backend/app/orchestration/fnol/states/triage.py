"""
TRIAGE State Handler

Calculates routing decision based on collected claim data:
- STP (Straight-Through Processing): Simple claims that can be auto-approved
- ADJUSTER: Claims requiring human adjuster review
- SIU_REVIEW: Claims flagged for Special Investigations Unit
- EMERGENCY: Urgent claims requiring immediate escalation
"""
from typing import Dict, List, Tuple, Optional
from datetime import datetime

from app.orchestration.fnol.state import FNOLConversationState, TriageResult
from app.orchestration.fnol.states.base import (
    add_audit_event,
    transition_state,
    set_response,
)


# Triage rule version for auditability
TRIAGE_RULE_VERSION = "1.0.0"


# Hard rules that immediately determine routing
HARD_RULES = {
    "fatal_injury": {
        "route": "emergency",
        "reason": "Fatal injury reported",
        "check": lambda s: any(
            i.get("severity") == "fatal" for i in s.get("injuries", [])
        ),
    },
    "hospitalized": {
        "route": "emergency",
        "reason": "Hospitalization required",
        "check": lambda s: any(
            i.get("treatment_level") == "admitted" for i in s.get("injuries", [])
        ),
    },
    "severe_injury": {
        "route": "adjuster",
        "reason": "Severe injury reported",
        "check": lambda s: any(
            i.get("severity") == "severe" for i in s.get("injuries", [])
        ),
    },
    "any_injury": {
        "route": "adjuster",
        "reason": "Injury reported",
        "check": lambda s: any(
            i.get("severity") not in [None, "none"] for i in s.get("injuries", [])
        ),
    },
}


# Scoring rules that accumulate points
SCORING_RULES = {
    "vehicle_not_drivable": {
        "points": 60,
        "flag": "vehicle_not_drivable",
        "check": lambda s: any(
            v.get("is_drivable") == False for v in s.get("vehicles", [])
        ),
    },
    "multiple_vehicles": {
        "points": 80,
        "flag": "multi_vehicle",
        "check": lambda s: len(s.get("vehicles", [])) >= 3,
    },
    "hit_and_run": {
        "points": 50,
        "flag": "hit_and_run",
        "check": lambda s: "hit_and_run" in s.get("active_playbooks", []),
    },
    "commercial_rideshare": {
        "points": 50,
        "flag": "commercial_use",
        "check": lambda s: "commercial_rideshare" in s.get("active_playbooks", []),
    },
    "cross_border": {
        "points": 40,
        "flag": "cross_border",
        "check": lambda s: s.get("incident", {}).get("cross_border", False),
    },
    "guest_mode": {
        "points": 30,
        "flag": "guest_mode",
        "check": lambda s: s.get("policy_match", {}).get("status") == "guest",
    },
    "theft_claim": {
        "points": 40,
        "flag": "theft",
        "check": lambda s: s.get("incident", {}).get("loss_type") == "theft",
    },
    "high_damage_estimate": {
        "points": 70,
        "flag": "high_value",
        "check": lambda s: any(
            d.get("estimated_amount", 0) > 15000 for d in s.get("damages", [])
        ),
    },
    "total_loss_indicated": {
        "points": 80,
        "flag": "total_loss",
        "check": lambda s: any(
            d.get("damage_area") == "total" for d in s.get("damages", [])
        ),
    },
    "police_dui": {
        "points": 100,
        "flag": "dui_suspected",
        "check": lambda s: s.get("police_info", {}).get("dui_suspected", False),
    },
    "no_police_report": {
        "points": 20,
        "flag": "no_police_report",
        "check": lambda s: not s.get("police_info", {}).get("report_filed", False)
        and s.get("incident", {}).get("loss_type") == "collision",
    },
}


# STP bonus rules (negative points for simple claims)
STP_BONUS_RULES = {
    "glass_only_with_photo": {
        "points": -50,
        "flag": "stp_candidate_glass",
        "check": lambda s: (
            "glass_only" in s.get("active_playbooks", [])
            and any(
                e.get("evidence_type") == "photo" for e in s.get("evidence", [])
            )
        ),
    },
    "parking_lot_minor": {
        "points": -30,
        "flag": "stp_candidate_parking",
        "check": lambda s: (
            "parking_lot" in s.get("active_playbooks", [])
            and all(
                d.get("estimated_amount", 0) < 2000 for d in s.get("damages", [])
            )
        ),
    },
    "single_vehicle_minor": {
        "points": -40,
        "flag": "stp_candidate_single",
        "check": lambda s: (
            len(s.get("vehicles", [])) == 1
            and all(v.get("is_drivable") for v in s.get("vehicles", []))
            and all(
                d.get("estimated_amount", 0) < 3000 for d in s.get("damages", [])
            )
        ),
    },
}


# SIU (Special Investigations Unit) red flags
SIU_FLAGS = {
    "recent_policy": {
        "flag": "siu_recent_policy",
        "check": lambda s: _is_recent_policy(s),
    },
    "prior_claims_pattern": {
        "flag": "siu_prior_claims",
        "check": lambda s: _has_prior_claims_pattern(s),
    },
    "inconsistent_narrative": {
        "flag": "siu_inconsistent",
        "check": lambda s: s.get("state_data", {}).get("narrative_flags", []),
    },
    "staged_accident_indicators": {
        "flag": "siu_staged",
        "check": lambda s: _has_staged_indicators(s),
    },
}


def _is_recent_policy(state: FNOLConversationState) -> bool:
    """Check if policy was created within last 30 days."""
    policy_match = state.get("policy_match", {})
    effective_date = policy_match.get("effective_date")
    if not effective_date:
        return False
    try:
        eff = datetime.fromisoformat(effective_date.replace("Z", "+00:00"))
        days_active = (datetime.now(eff.tzinfo) - eff).days
        return days_active < 30
    except (ValueError, TypeError):
        return False


def _has_prior_claims_pattern(state: FNOLConversationState) -> bool:
    """Check for suspicious prior claims pattern."""
    # In real implementation, this would check claims history
    # For now, return False
    return False


def _has_staged_indicators(state: FNOLConversationState) -> bool:
    """Check for indicators of a staged accident."""
    indicators = 0
    incident = state.get("incident", {})

    # Late night claim
    time_str = incident.get("time", "")
    if time_str:
        try:
            hour = int(time_str.split(":")[0])
            if 1 <= hour <= 5:
                indicators += 1
        except (ValueError, IndexError):
            pass

    # Multiple passengers with injuries
    injuries = state.get("injuries", [])
    if len([i for i in injuries if i.get("severity") not in [None, "none"]]) >= 3:
        indicators += 1

    # Specific injury pattern (soft tissue only)
    soft_tissue_keywords = ["neck", "back", "whiplash", "soreness", "strain"]
    descriptions = [i.get("description", "").lower() for i in injuries]
    if all(
        any(kw in d for kw in soft_tissue_keywords)
        for d in descriptions
        if d
    ):
        if len(descriptions) >= 2:
            indicators += 1

    return indicators >= 2


def triage_node(state: FNOLConversationState) -> FNOLConversationState:
    """Process the TRIAGE state."""
    step = state.get("state_step", "initial")

    # Step 1: Calculate triage
    if step == "initial":
        triage_result = calculate_triage(state)
        state["triage_result"] = triage_result

        state = add_audit_event(
            state,
            action="triage_calculated",
            actor="system",
            field_changed="triage_result",
            data_after=triage_result,
        )

        # Route based on triage result
        route = triage_result.get("route", "adjuster")

        if route == "emergency":
            state["should_escalate"] = True
            state["escalation_reason"] = triage_result.get("reason", "Emergency triage")
            state["state_step"] = "complete"
            return transition_state(state, "HANDOFF_ESCALATION", "emergency")

        if route == "siu_review":
            state["should_escalate"] = True
            state["escalation_reason"] = "Claim flagged for review"
            state["state_step"] = "complete"
            return transition_state(state, "HANDOFF_ESCALATION", "siu_review")

        # STP or ADJUSTER route - proceed to claim creation
        state["state_step"] = "complete"
        return transition_state(state, "CLAIM_CREATE", "initial")

    # Default transition
    return transition_state(state, "CLAIM_CREATE", "initial")


def calculate_triage(state: FNOLConversationState) -> TriageResult:
    """
    Calculate triage routing based on claim data.

    Returns:
        TriageResult with route, score, flags, and reasoning
    """
    flags: List[str] = []
    reasons: List[str] = []
    score = 0

    # Check hard rules first (immediate routing)
    for rule_name, rule in HARD_RULES.items():
        if rule["check"](state):
            return TriageResult(
                route=rule["route"],
                score=1000,
                flags=[rule_name],
                reason=rule["reason"],
                rule_version=TRIAGE_RULE_VERSION,
            )

    # Check SIU flags
    siu_flag_count = 0
    for rule_name, rule in SIU_FLAGS.items():
        if rule["check"](state):
            flags.append(rule["flag"])
            siu_flag_count += 1

    # If multiple SIU flags, route to SIU review
    if siu_flag_count >= 2:
        return TriageResult(
            route="siu_review",
            score=500,
            flags=flags,
            reason="Multiple SIU indicators detected",
            rule_version=TRIAGE_RULE_VERSION,
        )

    # Calculate scoring rules
    for rule_name, rule in SCORING_RULES.items():
        if rule["check"](state):
            score += rule["points"]
            flags.append(rule["flag"])
            reasons.append(f"+{rule['points']} ({rule['flag']})")

    # Apply STP bonus rules
    for rule_name, rule in STP_BONUS_RULES.items():
        if rule["check"](state):
            score += rule["points"]
            flags.append(rule["flag"])
            reasons.append(f"{rule['points']} ({rule['flag']})")

    # Determine route based on score
    if score > 200:
        route = "adjuster"
        reason = f"Score {score} exceeds STP threshold (200)"
    elif score < 0:
        route = "stp"
        reason = f"Score {score} qualifies for straight-through processing"
    else:
        route = "stp"
        reason = f"Score {score} within STP range"

    return TriageResult(
        route=route,
        score=score,
        flags=flags,
        reason=reason,
        rule_version=TRIAGE_RULE_VERSION,
    )


def get_triage_summary(triage_result: TriageResult) -> str:
    """Generate human-readable triage summary."""
    route = triage_result.get("route", "unknown")
    score = triage_result.get("score", 0)
    flags = triage_result.get("flags", [])

    route_descriptions = {
        "stp": "This claim qualifies for expedited processing.",
        "adjuster": "This claim will be reviewed by an adjuster.",
        "siu_review": "This claim requires additional review.",
        "emergency": "This claim requires immediate attention.",
    }

    summary = route_descriptions.get(route, "Claim routing determined.")

    if flags:
        flag_desc = ", ".join(f.replace("_", " ") for f in flags[:3])
        summary += f" Factors considered: {flag_desc}."

    return summary
