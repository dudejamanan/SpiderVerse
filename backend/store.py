from typing import Dict, List, Optional

from contracts import TwinState, LLMConstraint, RLAction


class SimulationStore:
    def __init__(self):
        # Latest constraint for each zone
        self.constraints: Dict[str, LLMConstraint] = {}

        # Latest twin state for each zone
        self.twin_states: Dict[str, TwinState] = {}

        # Latest RL action for each zone
        self.actions: Dict[str, RLAction] = {}

        # Historical simulation data
        self.history: List[dict] = []

        # Current selected region
        self.region: str = "Chennai"

    # --------------------------------------------------------
    # CONSTRAINTS
    # --------------------------------------------------------

    def save_constraint(self, constraint: LLMConstraint):
        self.constraints[constraint.zone_id] = constraint

    def get_constraint(self, zone_id: str) -> Optional[LLMConstraint]:
        return self.constraints.get(zone_id)

    # --------------------------------------------------------
    # TWIN STATE
    # --------------------------------------------------------

    def save_twin_state(self, state: TwinState):
        self.twin_states[state.zone_id] = state

    def get_twin_state(self, zone_id: str) -> Optional[TwinState]:
        return self.twin_states.get(zone_id)

    # --------------------------------------------------------
    # RL ACTION
    # --------------------------------------------------------

    def save_action(self, action: RLAction):
        self.actions[action.zone_id] = action

    def get_action(self, zone_id: str) -> Optional[RLAction]:
        return self.actions.get(zone_id)

    # --------------------------------------------------------
    # SIMULATION HISTORY
    # --------------------------------------------------------

    def add_history(self, record: dict):
        self.history.append(record)

    def get_history(self) -> List[dict]:
        return self.history

    # --------------------------------------------------------
    # REGION
    # --------------------------------------------------------

    def set_region(self, region: str):
        self.region = region

    def get_region(self) -> str:
        return self.region


# One shared store for the entire backend
store = SimulationStore()