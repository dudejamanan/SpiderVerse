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


def calculate_pmv(
    indoor_temp_c: float,
    indoor_rh_pct: float,
    clo: float = 0.5,
    met: float = 1.2,
) -> float:
    """
    Calculate Predicted Mean Vote (PMV).

    Uses pythermalcomfort's ISO 7730 implementation.

    Parameters
    ----------
    indoor_temp_c:
        Indoor air temperature in Celsius.

    indoor_rh_pct:
        Indoor relative humidity in percent.

    clo:
        Clothing insulation.
        0.5 is a reasonable summer-office assumption.

    met:
        Metabolic rate.
        1.2 is a reasonable seated-office assumption.
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

    indoor_temp = float(state.indoor_temp_c)

    # Initial comfort target.
    target_temp = 24.0

    # Small tolerance so that the agent isn't forced
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
        indoor_temp_c=float(state.indoor_temp_c),
        indoor_rh_pct=float(state.indoor_rh_pct),
        clo=0.5,
        met=1.2,
    )

    comfort_penalty = -abs(pmv)

    # ---------------------------------------------------------
    # ENERGY
    # ---------------------------------------------------------

    energy_penalty = -float(state.energy_draw_kw)

    # ---------------------------------------------------------
    # HUMAN CONSTRAINT
    # ---------------------------------------------------------

    satisfied = constraint_is_satisfied(
        state,
        constraint or {},
    )

    constraint_bonus = (
        weights.gamma
        if satisfied
        else 0.0
    )

    # ---------------------------------------------------------
    # TOTAL REWARD
    # ---------------------------------------------------------

    reward = (
        weights.alpha * comfort_penalty
        + weights.beta * energy_penalty
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