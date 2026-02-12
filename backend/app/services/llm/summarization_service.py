"""
Summarization Service

Generates human-readable summaries of claim data for confirmation screens.
This is a bounded AI task - no coverage/liability language, factual only.

Generates:
- Incident summary
- Vehicle summary
- Party summary
- Damage summary
- Full claim summary
"""
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import date
import os


@dataclass
class ClaimSummary:
    """Structured claim summary."""
    incident_summary: str
    vehicle_summary: str
    party_summary: str
    damage_summary: str
    full_summary: str
    word_count: int

    def to_dict(self) -> dict:
        return {
            "incident_summary": self.incident_summary,
            "vehicle_summary": self.vehicle_summary,
            "party_summary": self.party_summary,
            "damage_summary": self.damage_summary,
            "full_summary": self.full_summary,
            "word_count": self.word_count,
        }


class SummarizationService:
    """
    Service for generating claim summaries.

    Uses templates for deterministic summaries and optionally
    LLM for natural language enhancement.
    """

    # Loss type descriptions
    LOSS_TYPE_DESCRIPTIONS = {
        "collision": "vehicle collision",
        "theft": "vehicle theft",
        "weather": "weather-related damage",
        "glass": "glass damage",
        "fire": "fire damage",
        "vandalism": "vandalism",
    }

    # Impact type descriptions
    IMPACT_DESCRIPTIONS = {
        "rear_end": "rear-ended",
        "front_end": "front collision",
        "sideswipe": "sideswiped",
        "t_bone": "T-bone collision",
        "head_on": "head-on collision",
        "rollover": "vehicle rollover",
    }

    # Severity descriptions
    SEVERITY_DESCRIPTIONS = {
        "none": "no injuries",
        "minor": "minor injuries",
        "moderate": "moderate injuries",
        "severe": "severe injuries",
        "fatal": "fatal injuries",
    }

    def __init__(self, use_llm: bool = False):
        """Initialize summarization service."""
        self.use_llm = use_llm
        self._llm_client = None

    def summarize(self, state: Dict[str, Any]) -> ClaimSummary:
        """
        Generate a complete claim summary.

        Args:
            state: FNOL conversation state with collected data

        Returns:
            ClaimSummary with all summary sections
        """
        incident_summary = self._summarize_incident(state)
        vehicle_summary = self._summarize_vehicles(state)
        party_summary = self._summarize_parties(state)
        damage_summary = self._summarize_damages(state)

        full_summary = self._generate_full_summary(
            incident_summary,
            vehicle_summary,
            party_summary,
            damage_summary,
        )

        return ClaimSummary(
            incident_summary=incident_summary,
            vehicle_summary=vehicle_summary,
            party_summary=party_summary,
            damage_summary=damage_summary,
            full_summary=full_summary,
            word_count=len(full_summary.split()),
        )

    def _summarize_incident(self, state: Dict[str, Any]) -> str:
        """Generate incident summary."""
        incident = state.get("incident", {})

        loss_type = incident.get("loss_type", "incident")
        loss_desc = self.LOSS_TYPE_DESCRIPTIONS.get(loss_type, loss_type)

        incident_date = incident.get("date")
        incident_time = incident.get("time")
        location = incident.get("location_raw") or incident.get("location_normalized")

        parts = [f"A {loss_desc} occurred"]

        # Date/time
        if incident_date:
            try:
                d = date.fromisoformat(incident_date)
                parts.append(f"on {d.strftime('%B %d, %Y')}")
            except (ValueError, TypeError):
                parts.append(f"on {incident_date}")

        if incident_time:
            parts.append(f"at approximately {incident_time}")

        # Location
        if location:
            parts.append(f"at {location}")

        summary = " ".join(parts) + "."

        # Add description if provided
        description = incident.get("description")
        if description:
            summary += f" {description}"

        return summary

    def _summarize_vehicles(self, state: Dict[str, Any]) -> str:
        """Generate vehicle summary."""
        vehicles = state.get("vehicles", [])

        if not vehicles:
            return "No vehicle information provided."

        summaries = []
        for v in vehicles:
            role = v.get("role", "")
            role_label = "Insured vehicle" if role == "insured" else "Other vehicle"

            parts = [role_label + ":"]

            year = v.get("year")
            make = v.get("make")
            model = v.get("model")
            color = v.get("color")

            vehicle_desc = []
            if year:
                vehicle_desc.append(str(year))
            if make:
                vehicle_desc.append(make)
            if model:
                vehicle_desc.append(model)
            if color:
                vehicle_desc.append(f"({color})")

            if vehicle_desc:
                parts.append(" ".join(vehicle_desc))
            else:
                parts.append("details not provided")

            # Drivable status
            drivable = v.get("drivable")
            if drivable == "no":
                parts.append("- not drivable")
            elif drivable == "yes":
                parts.append("- drivable")

            # Tow needed
            if v.get("tow_needed"):
                parts.append("(tow required)")

            summaries.append(" ".join(parts))

        return " ".join(summaries)

    def _summarize_parties(self, state: Dict[str, Any]) -> str:
        """Generate party summary."""
        parties = state.get("parties", [])
        injuries = state.get("injuries", [])

        if not parties:
            return "No party information provided."

        # Count by role
        insured_drivers = []
        third_party_drivers = []
        passengers = []
        witnesses = []

        for p in parties:
            role = p.get("role", "")
            name = f"{p.get('first_name', '')} {p.get('last_name', '')}".strip() or "Unknown"

            if p.get("is_unknown"):
                name = "Unknown party"

            if role in ["insured", "insured_driver"]:
                insured_drivers.append(name)
            elif role == "third_party_driver":
                third_party_drivers.append(name)
            elif "passenger" in role:
                passengers.append(name)
            elif role == "witness":
                witnesses.append(name)

        parts = []

        if insured_drivers:
            parts.append(f"Driver: {', '.join(insured_drivers)}")

        if third_party_drivers:
            label = "Other driver" if len(third_party_drivers) == 1 else "Other drivers"
            parts.append(f"{label}: {', '.join(third_party_drivers)}")

        if passengers:
            parts.append(f"{len(passengers)} passenger(s)")

        if witnesses:
            parts.append(f"{len(witnesses)} witness(es)")

        # Injury summary
        injury_count = len([i for i in injuries if i.get("severity") not in [None, "none"]])
        if injury_count > 0:
            parts.append(f"Injuries reported: {injury_count}")
        else:
            parts.append("No injuries reported")

        return ". ".join(parts) + "."

    def _summarize_damages(self, state: Dict[str, Any]) -> str:
        """Generate damage summary."""
        damages = state.get("damages", [])

        if not damages:
            return "Damage details pending assessment."

        vehicle_damages = [d for d in damages if d.get("damage_type") == "vehicle"]
        property_damages = [d for d in damages if d.get("damage_type") == "property"]

        parts = []

        if vehicle_damages:
            areas = set(d.get("damage_area") for d in vehicle_damages if d.get("damage_area"))
            if areas:
                area_list = ", ".join(a.replace("_", " ") for a in areas)
                parts.append(f"Vehicle damage areas: {area_list}")

            # Estimated amount
            total_estimate = sum(
                d.get("estimated_amount", 0) or 0
                for d in vehicle_damages
                if d.get("estimated_amount")
            )
            if total_estimate > 0:
                parts.append(f"Estimated damage: ${total_estimate:,.2f}")

        if property_damages:
            parts.append(f"Third-party property damage reported")

        return ". ".join(parts) + "." if parts else "Damage details pending."

    def _generate_full_summary(
        self,
        incident: str,
        vehicles: str,
        parties: str,
        damages: str,
    ) -> str:
        """Combine summaries into full summary."""
        sections = [
            "**Incident:**",
            incident,
            "",
            "**Vehicles Involved:**",
            vehicles,
            "",
            "**Parties:**",
            parties,
            "",
            "**Damages:**",
            damages,
        ]

        return "\n".join(sections)

    def generate_confirmation_text(self, state: Dict[str, Any]) -> str:
        """
        Generate confirmation text for user review.

        This is a simplified summary for the confirmation screen.
        """
        incident = state.get("incident", {})
        vehicles = state.get("vehicles", [])
        injuries = state.get("injuries", [])

        # Build confirmation
        lines = ["Please review and confirm your claim details:"]
        lines.append("")

        # Date and type
        loss_type = incident.get("loss_type", "incident")
        loss_desc = self.LOSS_TYPE_DESCRIPTIONS.get(loss_type, loss_type)
        incident_date = incident.get("date", "Not specified")
        lines.append(f"- Type: {loss_desc.title()}")
        lines.append(f"- Date: {incident_date}")

        # Location
        location = incident.get("location_raw")
        if location:
            lines.append(f"- Location: {location}")

        # Vehicles
        if vehicles:
            insured = [v for v in vehicles if v.get("role") == "insured"]
            if insured:
                v = insured[0]
                vehicle_str = f"{v.get('year', '')} {v.get('make', '')} {v.get('model', '')}".strip()
                if vehicle_str:
                    lines.append(f"- Your vehicle: {vehicle_str}")

            others = len([v for v in vehicles if v.get("role") != "insured"])
            if others:
                lines.append(f"- Other vehicles involved: {others}")

        # Injuries
        injury_count = len([i for i in injuries if i.get("severity") not in [None, "none"]])
        lines.append(f"- Injuries reported: {'Yes' if injury_count > 0 else 'No'}")

        lines.append("")
        lines.append("Is this information correct?")

        return "\n".join(lines)


# Singleton instance
_summarization_service: Optional[SummarizationService] = None


def get_summarization_service(use_llm: bool = False) -> SummarizationService:
    """Get or create summarization service singleton."""
    global _summarization_service
    if _summarization_service is None:
        _summarization_service = SummarizationService(use_llm=use_llm)
    return _summarization_service
