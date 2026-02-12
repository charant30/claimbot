"""
FNOL State Handlers

Each state in the FNOL flow has a corresponding handler that:
1. Processes user input
2. Updates the conversation state
3. Generates the next question/response
4. Determines when to transition to the next state
"""
from app.orchestration.fnol.states.safety_check import safety_check_node
from app.orchestration.fnol.states.identity_match import identity_match_node
from app.orchestration.fnol.states.incident_core import incident_core_node
from app.orchestration.fnol.states.loss_module import loss_module_node
from app.orchestration.fnol.states.vehicle_driver import vehicle_driver_node
from app.orchestration.fnol.states.third_parties import third_parties_node
from app.orchestration.fnol.states.injuries import injuries_node
from app.orchestration.fnol.states.damage_evidence import damage_evidence_node
from app.orchestration.fnol.states.triage import triage_node
from app.orchestration.fnol.states.claim_create import claim_create_node
from app.orchestration.fnol.states.next_steps import next_steps_node
from app.orchestration.fnol.states.handoff_escalation import handoff_escalation_node

__all__ = [
    "safety_check_node",
    "identity_match_node",
    "incident_core_node",
    "loss_module_node",
    "vehicle_driver_node",
    "third_parties_node",
    "injuries_node",
    "damage_evidence_node",
    "triage_node",
    "claim_create_node",
    "next_steps_node",
    "handoff_escalation_node",
]
