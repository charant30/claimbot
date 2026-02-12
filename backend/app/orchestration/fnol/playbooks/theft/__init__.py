"""
Theft Playbooks

Handles theft-related scenarios:
- Vehicle theft (complete)
- Attempted theft (partial damage)
"""
from app.orchestration.fnol.playbooks.theft.vehicle_theft import VehicleTheftPlaybook
from app.orchestration.fnol.playbooks.theft.attempted_theft import AttemptedTheftPlaybook

__all__ = [
    "VehicleTheftPlaybook",
    "AttemptedTheftPlaybook",
]
