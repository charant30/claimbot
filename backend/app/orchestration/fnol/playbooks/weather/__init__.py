"""
Weather Playbooks

Handles weather-related damage scenarios:
- Hail damage
- Flood damage
- Wind/Tree damage
"""
from app.orchestration.fnol.playbooks.weather.hail import HailPlaybook
from app.orchestration.fnol.playbooks.weather.flood import FloodPlaybook
from app.orchestration.fnol.playbooks.weather.wind_tree import WindTreePlaybook

__all__ = [
    "HailPlaybook",
    "FloodPlaybook",
    "WindTreePlaybook",
]
