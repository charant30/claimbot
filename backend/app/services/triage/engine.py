"""
Triage Engine

Implements deterministic scoring and routing rules for FNOL claims.
The engine evaluates claim data and determines the appropriate routing:
- STP (Straight-Through Processing): Automated processing
- ADJUSTER: Route to human adjuster
- SIU_REVIEW: Special Investigations Unit review
- EMERGENCY: Priority/emergency handling
"""
from typing import Dict, Any, List, Optional, TypedDict
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime


class TriageRoute(str, Enum):
    """Possible routing decisions."""
    STP = "stp"
    ADJUSTER = "adjuster"
    SIU_REVIEW = "siu_review"
    EMERGENCY = "emergency"


class TriageResult(TypedDict):
    """Result of triage evaluation."""
    route: str
    score: int
    reasons: List[str]
    flags: List[str]
    rule_version: str
    evaluated_at: str


@dataclass
class TriageRule:
    """A single triage rule."""
    rule_id: str
    description: str
    points: int
    is_hard_rule: bool = False
    hard_route: Optional[TriageRoute] = None

    def evaluate(self, state: Dict[str, Any]) -> tuple[bool, List[str]]:
        """Evaluate if this rule applies. Returns (applies, reasons)."""
        raise NotImplementedError


class InjuryHardRule(TriageRule):
    """Any injury present requires adjuster."""

    def __init__(self):
        super().__init__(
            rule_id="injury_any",
            description="Injury reported - requires adjuster review",
            points=0,
            is_hard_rule=True,
            hard_route=TriageRoute.ADJUSTER,
        )

    def evaluate(self, state: Dict[str, Any]) -> tuple[bool, List[str]]:
        injuries = state.get("injuries", [])
        for injury in injuries:
            severity = injury.get("severity", "none")
            if severity != "none":
                return True, [f"Injury reported: {severity}"]
        return False, []


class SevereInjuryEmergencyRule(TriageRule):
    """Severe/fatal injury requires emergency handling."""

    def __init__(self):
        super().__init__(
            rule_id="severe_injury",
            description="Severe or fatal injury - emergency handling",
            points=0,
            is_hard_rule=True,
            hard_route=TriageRoute.EMERGENCY,
        )

    def evaluate(self, state: Dict[str, Any]) -> tuple[bool, List[str]]:
        injuries = state.get("injuries", [])
        for injury in injuries:
            severity = injury.get("severity", "none")
            if severity in ["severe", "fatal"]:
                return True, [f"Severe injury: {severity}"]
            if injury.get("hospitalized"):
                return True, ["Hospitalization required"]
        return False, []


class VehicleNotDrivableRule(TriageRule):
    """Non-drivable vehicle adds points."""

    def __init__(self):
        super().__init__(
            rule_id="vehicle_not_drivable",
            description="Vehicle is not drivable",
            points=60,
        )

    def evaluate(self, state: Dict[str, Any]) -> tuple[bool, List[str]]:
        vehicles = state.get("vehicles", [])
        reasons = []
        for vehicle in vehicles:
            if vehicle.get("role") == "insured":
                drivable = vehicle.get("drivable", "unknown")
                if drivable == "no":
                    reasons.append("Insured vehicle not drivable")
                    return True, reasons
        return False, []


class MultiVehicleRule(TriageRule):
    """Three or more vehicles involved adds points."""

    def __init__(self):
        super().__init__(
            rule_id="multi_vehicle",
            description="Multi-vehicle accident (3+)",
            points=80,
        )

    def evaluate(self, state: Dict[str, Any]) -> tuple[bool, List[str]]:
        vehicles = state.get("vehicles", [])
        if len(vehicles) >= 3:
            return True, [f"Multi-vehicle accident: {len(vehicles)} vehicles"]
        return False, []


class HitAndRunRule(TriageRule):
    """Hit-and-run adds points."""

    def __init__(self):
        super().__init__(
            rule_id="hit_and_run",
            description="Hit-and-run incident",
            points=50,
        )

    def evaluate(self, state: Dict[str, Any]) -> tuple[bool, List[str]]:
        incident = state.get("incident", {})
        if incident.get("loss_subtype") == "hit_and_run":
            return True, ["Hit-and-run incident"]

        # Check for unknown third party
        parties = state.get("parties", [])
        for party in parties:
            if party.get("is_unknown") and party.get("role") in ["third_party_driver"]:
                return True, ["Unknown third party (possible hit-and-run)"]

        # Check playbook data
        playbook_data = state.get("playbook_data", {})
        if "hit_and_run" in state.get("active_playbooks", []):
            return True, ["Hit-and-run playbook active"]

        return False, []


class CommercialUseRule(TriageRule):
    """Commercial/rideshare use adds points."""

    def __init__(self):
        super().__init__(
            rule_id="commercial_use",
            description="Commercial or rideshare use",
            points=50,
        )

    def evaluate(self, state: Dict[str, Any]) -> tuple[bool, List[str]]:
        playbook_data = state.get("playbook_data", {})
        use_type = playbook_data.get("use_type")

        if use_type in ["commercial", "rideshare", "delivery"]:
            return True, [f"Vehicle use: {use_type}"]

        if "commercial_rideshare" in state.get("active_playbooks", []):
            return True, ["Commercial/rideshare playbook active"]

        return False, []


class CrossBorderRule(TriageRule):
    """Cross-state/cross-border incidents add points."""

    def __init__(self):
        super().__init__(
            rule_id="cross_border",
            description="Cross-state or cross-border incident",
            points=40,
        )

    def evaluate(self, state: Dict[str, Any]) -> tuple[bool, List[str]]:
        if "out_of_state" in state.get("active_playbooks", []):
            return True, ["Out-of-state incident"]

        # Check if incident location state differs from policy state
        incident = state.get("incident", {})
        policy_match = state.get("policy_match", {})

        # Would need actual location data to implement fully
        return False, []


class GlassOnlyRule(TriageRule):
    """Glass-only damage with photo is STP candidate (negative points)."""

    def __init__(self):
        super().__init__(
            rule_id="glass_only",
            description="Glass-only damage with photo evidence",
            points=-50,
        )

    def evaluate(self, state: Dict[str, Any]) -> tuple[bool, List[str]]:
        incident = state.get("incident", {})
        if incident.get("loss_type") == "glass":
            # Check for photo evidence
            evidence = state.get("evidence", [])
            has_photo = any(e.get("evidence_type") == "photo" for e in evidence)
            if has_photo:
                return True, ["Glass-only claim with photo - STP candidate"]
        return False, []


class GuestModeRule(TriageRule):
    """Guest mode (no policy match) adds points."""

    def __init__(self):
        super().__init__(
            rule_id="guest_mode",
            description="Filing as guest (no policy matched)",
            points=30,
        )

    def evaluate(self, state: Dict[str, Any]) -> tuple[bool, List[str]]:
        policy_match = state.get("policy_match", {})
        if policy_match.get("status") == "guest":
            return True, ["Guest mode - policy verification needed"]
        return False, []


class TowRequiredRule(TriageRule):
    """Tow required adds points."""

    def __init__(self):
        super().__init__(
            rule_id="tow_required",
            description="Towing required",
            points=20,
        )

    def evaluate(self, state: Dict[str, Any]) -> tuple[bool, List[str]]:
        vehicles = state.get("vehicles", [])
        for vehicle in vehicles:
            if vehicle.get("role") == "insured" and vehicle.get("tow_needed"):
                return True, ["Towing required"]
        return False, []


class PoliceInvolvementRule(TriageRule):
    """Police involvement adds points."""

    def __init__(self):
        super().__init__(
            rule_id="police_involved",
            description="Police involvement",
            points=15,
        )

    def evaluate(self, state: Dict[str, Any]) -> tuple[bool, List[str]]:
        police = state.get("police", {})
        if police.get("contacted") == "yes":
            return True, ["Police contacted"]
        return False, []


class DUIFraudRule(TriageRule):
    """DUI suspected requires SIU review."""

    def __init__(self):
        super().__init__(
            rule_id="dui_suspected",
            description="DUI/DWI suspected",
            points=0,
            is_hard_rule=True,
            hard_route=TriageRoute.SIU_REVIEW,
        )

    def evaluate(self, state: Dict[str, Any]) -> tuple[bool, List[str]]:
        police = state.get("police", {})
        if police.get("dui_suspected"):
            return True, ["DUI/DWI suspected - SIU review required"]

        if "police_dui" in state.get("active_playbooks", []):
            return True, ["DUI playbook active"]

        return False, []


class TheftRule(TriageRule):
    """Vehicle theft adds significant points."""

    def __init__(self):
        super().__init__(
            rule_id="theft",
            description="Vehicle theft reported",
            points=100,
        )

    def evaluate(self, state: Dict[str, Any]) -> tuple[bool, List[str]]:
        incident = state.get("incident", {})
        if incident.get("loss_type") == "theft":
            return True, ["Vehicle theft reported"]
        return False, []


class PropertyDamageRule(TriageRule):
    """Third-party property damage adds points."""

    def __init__(self):
        super().__init__(
            rule_id="property_damage",
            description="Third-party property damage",
            points=40,
        )

    def evaluate(self, state: Dict[str, Any]) -> tuple[bool, List[str]]:
        damages = state.get("damages", [])
        for damage in damages:
            if damage.get("damage_type") == "property":
                return True, ["Third-party property damage"]
        return False, []


class TriageEngine:
    """
    FNOL Triage Engine

    Evaluates claims using a set of deterministic rules to determine
    the appropriate routing decision.
    """

    RULE_VERSION = "v1.0"
    ADJUSTER_THRESHOLD = 200

    def __init__(self):
        """Initialize with default rule set."""
        self.rules: List[TriageRule] = [
            # Hard rules (checked first, in order of priority)
            SevereInjuryEmergencyRule(),
            DUIFraudRule(),
            InjuryHardRule(),
            # Scoring rules
            TheftRule(),
            MultiVehicleRule(),
            VehicleNotDrivableRule(),
            HitAndRunRule(),
            CommercialUseRule(),
            PropertyDamageRule(),
            CrossBorderRule(),
            GuestModeRule(),
            TowRequiredRule(),
            PoliceInvolvementRule(),
            GlassOnlyRule(),  # Negative points for STP
        ]

    def evaluate(self, state: Dict[str, Any]) -> TriageResult:
        """
        Evaluate a claim and determine routing.

        Args:
            state: FNOL conversation state

        Returns:
            TriageResult with route, score, reasons, and flags
        """
        score = 0
        reasons: List[str] = []
        flags: List[str] = []
        final_route: Optional[TriageRoute] = None

        # Evaluate all rules
        for rule in self.rules:
            applies, rule_reasons = rule.evaluate(state)

            if applies:
                flags.append(rule.rule_id)
                reasons.extend(rule_reasons)

                # Check for hard rules first
                if rule.is_hard_rule and rule.hard_route:
                    if final_route is None or self._route_priority(rule.hard_route) > self._route_priority(final_route):
                        final_route = rule.hard_route
                else:
                    score += rule.points

        # Determine route based on score if no hard rule triggered
        if final_route is None:
            if score >= self.ADJUSTER_THRESHOLD:
                final_route = TriageRoute.ADJUSTER
            else:
                final_route = TriageRoute.STP

        return TriageResult(
            route=final_route.value,
            score=score,
            reasons=reasons,
            flags=flags,
            rule_version=self.RULE_VERSION,
            evaluated_at=datetime.utcnow().isoformat(),
        )

    def _route_priority(self, route: TriageRoute) -> int:
        """Get priority of a route (higher = more urgent)."""
        priorities = {
            TriageRoute.STP: 0,
            TriageRoute.ADJUSTER: 1,
            TriageRoute.SIU_REVIEW: 2,
            TriageRoute.EMERGENCY: 3,
        }
        return priorities.get(route, 0)

    def get_rule_descriptions(self) -> List[Dict[str, Any]]:
        """Get descriptions of all rules for documentation."""
        return [
            {
                "rule_id": rule.rule_id,
                "description": rule.description,
                "points": rule.points,
                "is_hard_rule": rule.is_hard_rule,
                "hard_route": rule.hard_route.value if rule.hard_route else None,
            }
            for rule in self.rules
        ]


# Singleton instance
_triage_engine: Optional[TriageEngine] = None


def get_triage_engine() -> TriageEngine:
    """Get or create the triage engine singleton."""
    global _triage_engine
    if _triage_engine is None:
        _triage_engine = TriageEngine()
    return _triage_engine
