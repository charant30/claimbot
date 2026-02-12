"""
FNOL Playbooks

Playbooks are composable modules that handle specific claim scenarios.
Each playbook:
1. Detects when it applies based on collected data
2. Provides additional questions specific to the scenario
3. Validates scenario-specific data
4. Contributes triage flags for routing decisions

22 playbooks organized by category:
- Collision (7): two_vehicle, single_vehicle, multi_vehicle, hit_and_run,
  uninsured, parking_lot, animal_strike
- Weather (3): hail, flood, wind_tree
- Theft (2): vehicle_theft, attempted_theft
- Other (10): vandalism, glass_only, fire, towing, commercial_rideshare,
  rental, out_of_state, injury, severe_injury, police_dui
"""
from app.orchestration.fnol.playbooks.base import BasePlaybook
from app.orchestration.fnol.playbooks.registry import (
    PlaybookRegistry,
    get_playbook_registry,
    detect_playbooks,
)

__all__ = [
    "BasePlaybook",
    "PlaybookRegistry",
    "get_playbook_registry",
    "detect_playbooks",
]
