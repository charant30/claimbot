"""
FNOL State Machine

Implements the deterministic state machine for FNOL claim intake
using LangGraph. The machine has 12 states and routes based on
collected data and business rules.
"""
from typing import Optional, Callable, Dict, Any
from datetime import datetime
from langgraph.graph import StateGraph, END

from app.orchestration.fnol.state import (
    FNOLConversationState,
    create_initial_fnol_state,
    STATE_ORDER,
    calculate_progress,
    get_next_states,
)


class FNOLStateMachine:
    """
    FNOL State Machine controller.

    This class wraps the LangGraph state machine and provides
    methods for processing messages and managing state.
    """

    def __init__(self):
        """Initialize the state machine."""
        from app.orchestration.fnol.states import (
            safety_check_node,
            identity_match_node,
            incident_core_node,
            loss_module_node,
            vehicle_driver_node,
            third_parties_node,
            injuries_node,
            damage_evidence_node,
            triage_node,
            claim_create_node,
            next_steps_node,
            handoff_escalation_node,
        )

        self.node_map = {
            "SAFETY_CHECK": safety_check_node,
            "IDENTITY_MATCH": identity_match_node,
            "INCIDENT_CORE": incident_core_node,
            "LOSS_MODULE": loss_module_node,
            "VEHICLE_DRIVER": vehicle_driver_node,
            "THIRD_PARTIES": third_parties_node,
            "INJURIES": injuries_node,
            "DAMAGE_EVIDENCE": damage_evidence_node,
            "TRIAGE": triage_node,
            "CLAIM_CREATE": claim_create_node,
            "NEXT_STEPS": next_steps_node,
            "HANDOFF_ESCALATION": handoff_escalation_node,
        }

    async def process_message(
        self,
        state: FNOLConversationState,
        message: str,
    ) -> FNOLConversationState:
        """
        Process a user message through the state machine.

        Executes the current state's node function and continues advancing
        through states until user input is needed or a terminal state is
        reached. This replaces LangGraph's ainvoke() which ran the entire
        graph from entry to END, causing infinite loops on self-referencing
        edges.

        Args:
            state: Current conversation state
            message: User's input message

        Returns:
            Updated conversation state
        """
        # Update state with new input
        state["current_input"] = message
        state["updated_at"] = datetime.utcnow().isoformat()
        
        # Clear previous AI response to prevent loops
        state["ai_response"] = None

        # Add message to history
        state["messages"] = state.get("messages", []) + [{
            "role": "user",
            "content": message,
            "timestamp": datetime.utcnow().isoformat(),
        }]

        # Reset input flag before processing
        state["needs_user_input"] = False

        # Execute nodes until user input is needed or we reach a terminal state
        max_iterations = 20  # Safety limit to prevent runaway loops
        for _ in range(max_iterations):
            current_state = state.get("current_state")
            node_fn = self.node_map.get(current_state)

            if node_fn is None:
                break

            state = node_fn(state)

            # Stop if this node needs user input
            if state.get("needs_user_input"):
                break

            # Stop if the flow is complete
            if state.get("is_complete"):
                break

        # Add AI response to message history if present
        if state.get("ai_response"):
            state["messages"] = state.get("messages", []) + [{
                "role": "assistant",
                "content": state["ai_response"],
                "timestamp": datetime.utcnow().isoformat(),
            }]

        # Update progress
        state["progress_percent"] = calculate_progress(
            state.get("completed_states", []),
            state.get("current_state", "SAFETY_CHECK"),
        )

        return state

    def create_session(
        self,
        thread_id: str,
        user_id: Optional[str] = None,
        policy_id: Optional[str] = None,
    ) -> FNOLConversationState:
        """
        Create a new FNOL session.

        Args:
            thread_id: Unique thread identifier
            user_id: Optional authenticated user ID
            policy_id: Optional policy ID if known

        Returns:
            Initial conversation state with welcome message
        """
        state = create_initial_fnol_state(thread_id, user_id, policy_id)

        # Set initial welcome message
        state["ai_response"] = (
            "I'm here to help you report an auto insurance claim. "
            "Before we begin, I need to make sure everyone is safe.\n\n"
            "Are you and everyone involved currently in a safe location?"
        )
        state["pending_question"] = "safety_confirmation"
        state["pending_question_field"] = "safety_confirmed"
        state["ui_hints"] = {
            "input_type": "yesno",
            "options": [
                {"value": "yes", "label": "Yes, we're safe"},
                {"value": "no", "label": "No, I need help"},
            ],
            "show_progress": True,
            "show_summary": False,
            "allow_skip": False,
        }

        # Add welcome message to history
        state["messages"] = [{
            "role": "assistant",
            "content": state["ai_response"],
            "timestamp": datetime.utcnow().isoformat(),
        }]

        return state


def build_fnol_graph() -> StateGraph:
    """
    Build the FNOL state machine graph.

    The graph has 12 nodes corresponding to the top-level states:
    1. SAFETY_CHECK - Ensure caller safety, detect emergencies
    2. IDENTITY_MATCH - Verify policy and identity
    3. INCIDENT_CORE - Collect basic incident information
    4. LOSS_MODULE - Detect and activate scenario playbooks
    5. VEHICLE_DRIVER - Collect insured vehicle and driver info
    6. THIRD_PARTIES - Collect other party information
    7. INJURIES - Collect injury information
    8. DAMAGE_EVIDENCE - Collect damage details and evidence
    9. TRIAGE - Calculate routing decision
    10. CLAIM_CREATE - Create the claim in the system
    11. NEXT_STEPS - Provide confirmation and next steps
    12. HANDOFF_ESCALATION - Transfer to human agent

    Returns:
        Configured StateGraph
    """
    workflow = StateGraph(FNOLConversationState)

    # Import state handlers (will be implemented in states/ directory)
    from app.orchestration.fnol.states import (
        safety_check_node,
        identity_match_node,
        incident_core_node,
        loss_module_node,
        vehicle_driver_node,
        third_parties_node,
        injuries_node,
        damage_evidence_node,
        triage_node,
        claim_create_node,
        next_steps_node,
        handoff_escalation_node,
    )

    # Add state nodes
    workflow.add_node("SAFETY_CHECK", safety_check_node)
    workflow.add_node("IDENTITY_MATCH", identity_match_node)
    workflow.add_node("INCIDENT_CORE", incident_core_node)
    workflow.add_node("LOSS_MODULE", loss_module_node)
    workflow.add_node("VEHICLE_DRIVER", vehicle_driver_node)
    workflow.add_node("THIRD_PARTIES", third_parties_node)
    workflow.add_node("INJURIES", injuries_node)
    workflow.add_node("DAMAGE_EVIDENCE", damage_evidence_node)
    workflow.add_node("TRIAGE", triage_node)
    workflow.add_node("CLAIM_CREATE", claim_create_node)
    workflow.add_node("NEXT_STEPS", next_steps_node)
    workflow.add_node("HANDOFF_ESCALATION", handoff_escalation_node)

    # Set entry point
    workflow.set_entry_point("SAFETY_CHECK")

    # Define routing functions
    def route_from_safety_check(state: FNOLConversationState) -> str:
        """Route from SAFETY_CHECK state."""
        if state.get("emergency_detected"):
            return "HANDOFF_ESCALATION"
        if state.get("safety_confirmed"):
            return "IDENTITY_MATCH"
        # Stay in current state if not confirmed
        return "SAFETY_CHECK"

    def route_from_identity_match(state: FNOLConversationState) -> str:
        """Route from IDENTITY_MATCH state."""
        if state.get("should_escalate"):
            return "HANDOFF_ESCALATION"
        policy_status = state.get("policy_match", {}).get("status")
        if policy_status in ["matched", "guest"]:
            return "INCIDENT_CORE"
        # Stay in current state if still pending
        return "IDENTITY_MATCH"

    def route_from_incident_core(state: FNOLConversationState) -> str:
        """Route from INCIDENT_CORE state."""
        incident = state.get("incident", {})
        # Check if minimum incident data collected
        if incident.get("loss_type") and incident.get("date") and incident.get("location_raw"):
            return "LOSS_MODULE"
        return "INCIDENT_CORE"

    def route_from_loss_module(state: FNOLConversationState) -> str:
        """Route from LOSS_MODULE state."""
        # Loss module activates playbooks and routes to vehicle collection
        if state.get("active_playbooks"):
            return "VEHICLE_DRIVER"
        return "LOSS_MODULE"

    def route_from_vehicle_driver(state: FNOLConversationState) -> str:
        """Route from VEHICLE_DRIVER state."""
        vehicles = state.get("vehicles", [])
        # Check if at least insured vehicle captured
        insured_vehicles = [v for v in vehicles if v.get("role") == "insured"]
        if insured_vehicles:
            return "THIRD_PARTIES"
        return "VEHICLE_DRIVER"

    def route_from_third_parties(state: FNOLConversationState) -> str:
        """Route from THIRD_PARTIES state."""
        # Third parties are optional for some scenarios
        # Move to injuries after collecting or skipping
        state_step = state.get("state_step", "")
        if state_step == "complete" or state_step == "skipped":
            return "INJURIES"
        return "THIRD_PARTIES"

    def route_from_injuries(state: FNOLConversationState) -> str:
        """Route from INJURIES state."""
        injuries = state.get("injuries", [])
        # Check for severe/fatal injuries requiring immediate escalation
        severe_injuries = [i for i in injuries if i.get("severity") in ["severe", "fatal"]]
        if severe_injuries:
            return "HANDOFF_ESCALATION"
        # Move to damage evidence
        state_step = state.get("state_step", "")
        if state_step in ["complete", "no_injuries"]:
            return "DAMAGE_EVIDENCE"
        return "INJURIES"

    def route_from_damage_evidence(state: FNOLConversationState) -> str:
        """Route from DAMAGE_EVIDENCE state."""
        state_step = state.get("state_step", "")
        if state_step == "complete":
            return "TRIAGE"
        return "DAMAGE_EVIDENCE"

    def route_from_triage(state: FNOLConversationState) -> str:
        """Route from TRIAGE state."""
        triage = state.get("triage_result")
        if triage:
            route = triage.get("route")
            if route == "emergency":
                return "HANDOFF_ESCALATION"
            if route == "siu_review":
                return "HANDOFF_ESCALATION"
            # STP and ADJUSTER both go to claim create
            return "CLAIM_CREATE"
        return "TRIAGE"

    def route_from_claim_create(state: FNOLConversationState) -> str:
        """Route from CLAIM_CREATE state."""
        if state.get("should_escalate"):
            return "HANDOFF_ESCALATION"
        state_step = state.get("state_step", "")
        if state_step == "complete":
            return "NEXT_STEPS"
        return "CLAIM_CREATE"

    # Add conditional edges
    workflow.add_conditional_edges(
        "SAFETY_CHECK",
        route_from_safety_check,
        {
            "SAFETY_CHECK": "SAFETY_CHECK",
            "IDENTITY_MATCH": "IDENTITY_MATCH",
            "HANDOFF_ESCALATION": "HANDOFF_ESCALATION",
        }
    )

    workflow.add_conditional_edges(
        "IDENTITY_MATCH",
        route_from_identity_match,
        {
            "IDENTITY_MATCH": "IDENTITY_MATCH",
            "INCIDENT_CORE": "INCIDENT_CORE",
            "HANDOFF_ESCALATION": "HANDOFF_ESCALATION",
        }
    )

    workflow.add_conditional_edges(
        "INCIDENT_CORE",
        route_from_incident_core,
        {
            "INCIDENT_CORE": "INCIDENT_CORE",
            "LOSS_MODULE": "LOSS_MODULE",
        }
    )

    workflow.add_conditional_edges(
        "LOSS_MODULE",
        route_from_loss_module,
        {
            "LOSS_MODULE": "LOSS_MODULE",
            "VEHICLE_DRIVER": "VEHICLE_DRIVER",
        }
    )

    workflow.add_conditional_edges(
        "VEHICLE_DRIVER",
        route_from_vehicle_driver,
        {
            "VEHICLE_DRIVER": "VEHICLE_DRIVER",
            "THIRD_PARTIES": "THIRD_PARTIES",
        }
    )

    workflow.add_conditional_edges(
        "THIRD_PARTIES",
        route_from_third_parties,
        {
            "THIRD_PARTIES": "THIRD_PARTIES",
            "INJURIES": "INJURIES",
        }
    )

    workflow.add_conditional_edges(
        "INJURIES",
        route_from_injuries,
        {
            "INJURIES": "INJURIES",
            "DAMAGE_EVIDENCE": "DAMAGE_EVIDENCE",
            "HANDOFF_ESCALATION": "HANDOFF_ESCALATION",
        }
    )

    workflow.add_conditional_edges(
        "DAMAGE_EVIDENCE",
        route_from_damage_evidence,
        {
            "DAMAGE_EVIDENCE": "DAMAGE_EVIDENCE",
            "TRIAGE": "TRIAGE",
        }
    )

    workflow.add_conditional_edges(
        "TRIAGE",
        route_from_triage,
        {
            "TRIAGE": "TRIAGE",
            "CLAIM_CREATE": "CLAIM_CREATE",
            "HANDOFF_ESCALATION": "HANDOFF_ESCALATION",
        }
    )

    workflow.add_conditional_edges(
        "CLAIM_CREATE",
        route_from_claim_create,
        {
            "CLAIM_CREATE": "CLAIM_CREATE",
            "NEXT_STEPS": "NEXT_STEPS",
            "HANDOFF_ESCALATION": "HANDOFF_ESCALATION",
        }
    )

    # Terminal states
    workflow.add_edge("NEXT_STEPS", END)
    workflow.add_edge("HANDOFF_ESCALATION", END)

    return workflow


# Singleton instance
_fnol_machine: Optional[FNOLStateMachine] = None


def get_fnol_machine() -> FNOLStateMachine:
    """Get or create the FNOL state machine singleton."""
    global _fnol_machine
    if _fnol_machine is None:
        _fnol_machine = FNOLStateMachine()
    return _fnol_machine
