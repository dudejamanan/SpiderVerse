
# rl/reward.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pythermalcomfort.models import pmv_ppd_iso


@dataclass
class RewardWeights:
    """
    Weights used by the HVAC RL reward.

    alpha -> thermal comfort importance
    beta  -> energy consumption importance
    gamma -> human constraint importance
    """

    alpha: float = 1.0
    beta: float = 1.0
    gamma: float = 1.0


def _get_state_value(state: Any, key: str) -> Any:
    """
    Read a value from either:

    1. A dictionary-based twin state
    2. An object/dataclass-based twin state

    This keeps the reward function independent
    of the final RoomTwin implementation.
    """

    if isinstance(state, dict):
        return state[key]

    return getattr(state, key)


def calculate_pmv(
    indoor_temp_c: float,
    indoor_rh_pct: float,
    clo: float = 0.5,
    met: float = 1.2,
) -> float:
    """
    Calculate Predicted Mean Vote (PMV).

    Uses pythermalcomfort's ISO 7730 implementation.
    """

    result = pmv_ppd_iso(
        tdb=indoor_temp_c,
        tr=indoor_temp_c,
        vr=0.1,
        rh=indoor_rh_pct,
        met=met,
        clo=clo,
    )

    return float(result.pmv)


def constraint_is_satisfied(
    state: Any,
    constraint: dict,
) -> bool:
    """
    Determine whether the current room state satisfies
    the human's temperature constraint.

    Currently supports:

        parameter = "temperature"
        direction = "increase"
        direction = "decrease"
    """

    if not constraint:
        return False

    parameter = constraint.get("parameter")
    direction = constraint.get("direction")

    if parameter != "temperature":
        return False

    indoor_temp = float(
        _get_state_value(state, "indoor_temp_c")
    )

    # Initial comfort target.
    target_temp = 24.0

    # Small tolerance so the agent does not need
    # to hit exactly 24.0 C.
    tolerance = 0.5

    if direction == "decrease":
        return indoor_temp <= target_temp + tolerance

    if direction == "increase":
        return indoor_temp >= target_temp - tolerance

    return False


def compute_reward(
    state: Any,
    constraint: dict | None,
    weights: RewardWeights | None = None,
) -> tuple[float, dict]:
    """
    Calculate the total RL reward.

    Reward:

        - alpha * |PMV|
        - beta  * energy
        + gamma * constraint_satisfied

    Returns
    -------
    reward:
        Scalar reward used by PPO.

    info:
        Diagnostic information useful for debugging
        and dashboard logging.
    """

    if weights is None:
        weights = RewardWeights()

    # ---------------------------------------------------------
    # COMFORT
    # ---------------------------------------------------------

    pmv = calculate_pmv(
        indoor_temp_c=float(
            _get_state_value(state, "indoor_temp_c")
        ),
        indoor_rh_pct=float(
            _get_state_value(state, "indoor_rh_pct")
        ),
    )

    comfort_penalty = -weights.alpha * abs(pmv)

    # ---------------------------------------------------------
    # ENERGY
    # ---------------------------------------------------------

    energy_draw_kw = float(
        _get_state_value(state, "energy_draw_kw")
    )

    energy_penalty = -weights.beta * energy_draw_kw

    # ---------------------------------------------------------
    # HUMAN CONSTRAINT
    # ---------------------------------------------------------

    satisfied = constraint_is_satisfied(
        state=state,
        constraint=constraint,
    )

    constraint_bonus = (
        weights.gamma
        if satisfied
        else 0.0
    )

    # ---------------------------------------------------------
    # TOTAL
    # ---------------------------------------------------------

    reward = (
        comfort_penalty
        + energy_penalty
        + constraint_bonus
    )

    info = {
        "pmv": pmv,
        "comfort_penalty": comfort_penalty,
        "energy_penalty": energy_penalty,
        "constraint_satisfied": satisfied,
        "constraint_bonus": constraint_bonus,
    }

    return float(reward), info
