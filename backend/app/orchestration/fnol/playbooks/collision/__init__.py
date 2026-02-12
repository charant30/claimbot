"""
Collision Playbooks

Handles various collision scenarios:
- Two-vehicle collision
- Single-vehicle collision
- Multi-vehicle collision (3+)
- Hit and run
- Uninsured motorist
- Parking lot incident
- Animal strike
"""
from app.orchestration.fnol.playbooks.collision.two_vehicle import TwoVehiclePlaybook
from app.orchestration.fnol.playbooks.collision.single_vehicle import SingleVehiclePlaybook
from app.orchestration.fnol.playbooks.collision.multi_vehicle import MultiVehiclePlaybook
from app.orchestration.fnol.playbooks.collision.hit_and_run import HitAndRunPlaybook
from app.orchestration.fnol.playbooks.collision.uninsured import UninsuredPlaybook
from app.orchestration.fnol.playbooks.collision.parking_lot import ParkingLotPlaybook
from app.orchestration.fnol.playbooks.collision.animal_strike import AnimalStrikePlaybook

__all__ = [
    "TwoVehiclePlaybook",
    "SingleVehiclePlaybook",
    "MultiVehiclePlaybook",
    "HitAndRunPlaybook",
    "UninsuredPlaybook",
    "ParkingLotPlaybook",
    "AnimalStrikePlaybook",
]
