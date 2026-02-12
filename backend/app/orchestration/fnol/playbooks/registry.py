"""
Playbook Registry

Manages all FNOL playbooks and provides detection/lookup functionality.
"""
from typing import Dict, List, Optional, Type, Tuple, Any
from app.orchestration.fnol.playbooks.base import BasePlaybook, PlaybookQuestion


class PlaybookRegistry:
    """
    Registry for managing FNOL playbooks.

    Provides:
    - Playbook registration
    - Scenario detection
    - Question aggregation
    - Validation coordination
    """

    def __init__(self):
        self._playbooks: Dict[str, Type[BasePlaybook]] = {}
        self._by_category: Dict[str, List[str]] = {
            "collision": [],
            "weather": [],
            "theft": [],
            "other": [],
        }

    def register(self, playbook_class: Type[BasePlaybook]) -> None:
        """
        Register a playbook class.

        Args:
            playbook_class: The playbook class to register
        """
        playbook_id = playbook_class.playbook_id
        if not playbook_id:
            raise ValueError(f"Playbook {playbook_class.__name__} has no playbook_id")

        self._playbooks[playbook_id] = playbook_class

        # Add to category index
        category = playbook_class.category or "other"
        if category not in self._by_category:
            self._by_category[category] = []
        if playbook_id not in self._by_category[category]:
            self._by_category[category].append(playbook_id)

    def get(self, playbook_id: str) -> Optional[Type[BasePlaybook]]:
        """Get a playbook by ID."""
        return self._playbooks.get(playbook_id)

    def get_all(self) -> List[Type[BasePlaybook]]:
        """Get all registered playbooks."""
        return list(self._playbooks.values())

    def get_by_category(self, category: str) -> List[Type[BasePlaybook]]:
        """Get all playbooks in a category."""
        playbook_ids = self._by_category.get(category, [])
        return [self._playbooks[pid] for pid in playbook_ids if pid in self._playbooks]

    def detect_applicable(
        self,
        state: Dict[str, Any],
        threshold: float = 0.3,
    ) -> List[Tuple[str, float]]:
        """
        Detect which playbooks apply to the current state.

        Args:
            state: Current FNOL conversation state
            threshold: Minimum confidence score to include

        Returns:
            List of (playbook_id, confidence) tuples, sorted by confidence descending
        """
        results = []

        for playbook_id, playbook_class in self._playbooks.items():
            try:
                confidence = playbook_class.detect(state)
                if confidence >= threshold:
                    results.append((playbook_id, confidence))
            except Exception as e:
                # Log error but continue with other playbooks
                print(f"Error detecting playbook {playbook_id}: {e}")
                continue

        # Sort by confidence descending, then by priority ascending
        results.sort(
            key=lambda x: (-x[1], self._playbooks[x[0]].priority)
        )

        return results

    def get_questions_for_state(
        self,
        active_playbooks: List[str],
        current_state: str,
        state: Dict[str, Any],
    ) -> List[PlaybookQuestion]:
        """
        Get all questions from active playbooks for the current state.

        Args:
            active_playbooks: List of active playbook IDs
            current_state: Current state in the flow
            state: Current FNOL conversation state

        Returns:
            List of questions, sorted by priority
        """
        questions = []

        for playbook_id in active_playbooks:
            playbook_class = self._playbooks.get(playbook_id)
            if not playbook_class:
                continue

            playbook_questions = playbook_class.get_questions(current_state, state)
            for q in playbook_questions:
                q["playbook_id"] = playbook_id
                questions.append(q)

        # Sort by priority
        questions.sort(key=lambda x: x.get("priority", 100))

        return questions

    def validate_all(
        self,
        active_playbooks: List[str],
        state: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Run validation for all active playbooks.

        Args:
            active_playbooks: List of active playbook IDs
            state: Current FNOL conversation state

        Returns:
            Combined validation result
        """
        all_errors = []
        all_warnings = []

        for playbook_id in active_playbooks:
            playbook_class = self._playbooks.get(playbook_id)
            if not playbook_class:
                continue

            result = playbook_class.validate(state)
            for error in result.get("errors", []):
                all_errors.append(f"[{playbook_id}] {error}")
            for warning in result.get("warnings", []):
                all_warnings.append(f"[{playbook_id}] {warning}")

        return {
            "valid": len(all_errors) == 0,
            "errors": all_errors,
            "warnings": all_warnings,
        }

    def get_all_triage_flags(
        self,
        active_playbooks: List[str],
        state: Dict[str, Any],
    ) -> List[str]:
        """
        Get all triage flags from active playbooks.

        Args:
            active_playbooks: List of active playbook IDs
            state: Current FNOL conversation state

        Returns:
            Deduplicated list of triage flags
        """
        flags = set()

        for playbook_id in active_playbooks:
            playbook_class = self._playbooks.get(playbook_id)
            if not playbook_class:
                continue

            playbook_flags = playbook_class.get_triage_flags(state)
            flags.update(playbook_flags)

        return list(flags)

    def get_required_evidence(
        self,
        active_playbooks: List[str],
        state: Dict[str, Any],
    ) -> List[Dict[str, str]]:
        """
        Get all required evidence from active playbooks.

        Args:
            active_playbooks: List of active playbook IDs
            state: Current FNOL conversation state

        Returns:
            List of evidence requirements
        """
        evidence = []
        seen = set()

        for playbook_id in active_playbooks:
            playbook_class = self._playbooks.get(playbook_id)
            if not playbook_class:
                continue

            for ev in playbook_class.get_required_evidence(state):
                key = f"{ev.get('evidence_type')}:{ev.get('description', '')}"
                if key not in seen:
                    seen.add(key)
                    evidence.append(ev)

        return evidence


# Global registry instance
_registry: Optional[PlaybookRegistry] = None


def get_playbook_registry() -> PlaybookRegistry:
    """Get or create the global playbook registry."""
    global _registry
    if _registry is None:
        _registry = PlaybookRegistry()
        _register_all_playbooks(_registry)
    return _registry


def _register_all_playbooks(registry: PlaybookRegistry) -> None:
    """Register all playbooks with the registry."""
    # Import and register collision playbooks
    from app.orchestration.fnol.playbooks.collision import (
        TwoVehiclePlaybook,
        SingleVehiclePlaybook,
        MultiVehiclePlaybook,
        HitAndRunPlaybook,
        UninsuredPlaybook,
        ParkingLotPlaybook,
        AnimalStrikePlaybook,
    )
    registry.register(TwoVehiclePlaybook)
    registry.register(SingleVehiclePlaybook)
    registry.register(MultiVehiclePlaybook)
    registry.register(HitAndRunPlaybook)
    registry.register(UninsuredPlaybook)
    registry.register(ParkingLotPlaybook)
    registry.register(AnimalStrikePlaybook)

    # Import and register weather playbooks
    from app.orchestration.fnol.playbooks.weather import (
        HailPlaybook,
        FloodPlaybook,
        WindTreePlaybook,
    )
    registry.register(HailPlaybook)
    registry.register(FloodPlaybook)
    registry.register(WindTreePlaybook)

    # Import and register theft playbooks
    from app.orchestration.fnol.playbooks.theft import (
        VehicleTheftPlaybook,
        AttemptedTheftPlaybook,
    )
    registry.register(VehicleTheftPlaybook)
    registry.register(AttemptedTheftPlaybook)

    # Import and register other playbooks
    from app.orchestration.fnol.playbooks.other import (
        VandalismPlaybook,
        GlassOnlyPlaybook,
        FirePlaybook,
        TowingPlaybook,
        CommercialRidesharePlaybook,
        RentalPlaybook,
        OutOfStatePlaybook,
        InjuryPlaybook,
        SevereInjuryPlaybook,
        PoliceDuiPlaybook,
    )
    registry.register(VandalismPlaybook)
    registry.register(GlassOnlyPlaybook)
    registry.register(FirePlaybook)
    registry.register(TowingPlaybook)
    registry.register(CommercialRidesharePlaybook)
    registry.register(RentalPlaybook)
    registry.register(OutOfStatePlaybook)
    registry.register(InjuryPlaybook)
    registry.register(SevereInjuryPlaybook)
    registry.register(PoliceDuiPlaybook)


def detect_playbooks(
    state: Dict[str, Any],
    threshold: float = 0.3,
) -> List[Tuple[str, float]]:
    """
    Convenience function to detect applicable playbooks.

    Args:
        state: Current FNOL conversation state
        threshold: Minimum confidence score

    Returns:
        List of (playbook_id, confidence) tuples
    """
    registry = get_playbook_registry()
    return registry.detect_applicable(state, threshold)
