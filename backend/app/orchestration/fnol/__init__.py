"""
FNOL (First Notice of Loss) Orchestration Module

This module implements a deterministic state machine for auto insurance
claim intake, with bounded AI for intent detection, entity extraction,
and summarization only.
"""
from app.orchestration.fnol.state import FNOLConversationState, create_initial_fnol_state
from app.orchestration.fnol.machine import build_fnol_graph, FNOLStateMachine

__all__ = [
    "FNOLConversationState",
    "create_initial_fnol_state",
    "build_fnol_graph",
    "FNOLStateMachine",
]
