"""
Tests for supervisor graph routing and client inquiry (agent_status) behavior.

Verifies:
- Graph differentiates file_claim (subgraph/agents) vs check_status (inquiry agent).
- Route to subgraph by product (auto -> incident_subgraph).
- Agent_status (client inquiry) prompts for claim number when missing and
  returns claim_details when claim number is provided.
"""

import pytest
from unittest.mock import patch

from app.orchestration.state import create_initial_state
from app.orchestration.graphs.supervisor import (
    route_to_subgraph,
    route_agents,
    agent_status,
    classify_intent,
)
from app.orchestration.state import ClaimIntent, ProductLine


def _base_state(**overrides):
    s = create_initial_state(thread_id="test-thread", user_id="user-1", policy_id=None)
    s["current_input"] = overrides.get("current_input", "I want to check my claim status")
    return {**s, **overrides}


# --- route_to_subgraph: differentiate by product (auto -> incident) ---


def test_route_to_subgraph_auto_goes_to_incident_subgraph():
    state = _base_state(product_line=ProductLine.AUTO.value)
    out = route_to_subgraph(state)
    assert out["next_step"] == "incident_subgraph"


def test_route_to_subgraph_missing_product_asks_product():
    state = _base_state(product_line=None)
    out = route_to_subgraph(state)
    assert out["next_step"] == "ask_product"


# --- route_agents: file_claim -> agent_intake, else -> route_to_subgraph ---


def test_route_agents_file_claim_goes_to_agent_intake():
    state = _base_state(intent=ClaimIntent.FILE_CLAIM.value)
    out = route_agents(state)
    assert out["next_step"] == "agent_intake"


def test_route_agents_non_file_claim_goes_to_subgraph():
    state = _base_state(intent=ClaimIntent.CHECK_STATUS.value)
    out = route_agents(state)
    assert out["next_step"] == "route_to_subgraph"


# --- agent_status (client inquiry): no claim number -> generate_response ---


def test_agent_status_no_claim_number_prompts_for_it():
    state = _base_state(
        intent=ClaimIntent.CHECK_STATUS.value,
        claim_number=None,
        current_input="What is my claim status?",
    )
    out = agent_status(state)
    assert out["next_step"] == "generate_response"
    # No claim_details set when we didn't look up
    assert out.get("claim_details") is None or "error" not in str(out.get("claim_details", {})).lower()


# --- agent_status with claim number: uses lookup (integration with DB) ---


def test_agent_status_with_claim_number_lookup(db, test_claim):
    """When user provides claim number in message, agent_status extracts it and looks up."""
    state = _base_state(
        intent=ClaimIntent.CHECK_STATUS.value,
        claim_number=None,
        current_input=f"What is the status of {test_claim.claim_number}?",
    )
    with patch("app.orchestration.graphs.supervisor.SessionLocal", return_value=db):
        out = agent_status(state)
    assert out["next_step"] == "generate_response"
    assert out.get("claim_number") == test_claim.claim_number
    details = out.get("claim_details") or {}
    assert "error" not in details


# --- classify_intent: skip re-classification when already file_claim + product ---


def test_classify_intent_skips_when_file_claim_and_product_set():
    state = _base_state(
        intent=ClaimIntent.FILE_CLAIM.value,
        product_line=ProductLine.AUTO.value,
        current_input="yes",
    )
    out = classify_intent(state)
    assert out["next_step"] == "route_to_subgraph"
    assert out["intent"] == ClaimIntent.FILE_CLAIM.value
