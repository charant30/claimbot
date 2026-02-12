"""
Other Playbooks

Handles miscellaneous scenarios:
- Vandalism
- Glass only
- Fire damage
- Towing
- Commercial/Rideshare
- Rental vehicle
- Out of state incident
- Injury claims
- Severe injury
- Police/DUI involvement
"""
from app.orchestration.fnol.playbooks.other.vandalism import VandalismPlaybook
from app.orchestration.fnol.playbooks.other.glass_only import GlassOnlyPlaybook
from app.orchestration.fnol.playbooks.other.fire import FirePlaybook
from app.orchestration.fnol.playbooks.other.towing import TowingPlaybook
from app.orchestration.fnol.playbooks.other.commercial_rideshare import CommercialRidesharePlaybook
from app.orchestration.fnol.playbooks.other.rental import RentalPlaybook
from app.orchestration.fnol.playbooks.other.out_of_state import OutOfStatePlaybook
from app.orchestration.fnol.playbooks.other.injury import InjuryPlaybook
from app.orchestration.fnol.playbooks.other.severe_injury import SevereInjuryPlaybook
from app.orchestration.fnol.playbooks.other.police_dui import PoliceDuiPlaybook

__all__ = [
    "VandalismPlaybook",
    "GlassOnlyPlaybook",
    "FirePlaybook",
    "TowingPlaybook",
    "CommercialRidesharePlaybook",
    "RentalPlaybook",
    "OutOfStatePlaybook",
    "InjuryPlaybook",
    "SevereInjuryPlaybook",
    "PoliceDuiPlaybook",
]
