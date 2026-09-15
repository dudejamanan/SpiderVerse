from __future__ import annotations

import numpy as np
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
    delta -> setpoint movement penalty
    """

    alpha: float = 0.9
    beta: float = 2.5
    gamma: float = 0.5
    delta: float = 0.05


def _get_state_value(
    state: Any,
    key: str,
    default: Any = None,
) -> Any:
    if isinstance(state, dict):
        return state.get(key, default)

    return getattr(state, key, default)


def calculate_pmv(
    indoor_temp_c: float,
    indoor_rh_pct: float,
    clo: float = 0.5,
    met: float = 1.2,
) -> float:
    """
    Calculate PMV using pythermalcomfort.

    Temperature and PMV are protected from NaN/extreme
    values that could destabilize PPO.
    """

    safe_temp_c = float(
        max(10.0, min(30.0, indoor_temp_c))
    )

    safe_rh_pct = float(
        max(0.0, min(100.0, indoor_rh_pct))
    )

    result = pmv_ppd_iso(
        tdb=safe_temp_c,
        tr=safe_temp_c,
        vr=0.1,
        rh=safe_rh_pct,
        met=met,
        clo=clo,
    )

    pmv = float(result.pmv)

    if not np.isfinite(pmv):
        if indoor_temp_c > 30.0:
            pmv = 2.0

        elif indoor_temp_c < 10.0:
            pmv = -2.0

        else:
            raise RuntimeError(
                f"PMV calculation produced invalid value: {pmv}"
            )

    return float(
        np.clip(
            pmv,
            -2.0,
            2.0,
        )
    )


def constraint_is_satisfied(
    state: Any,
    constraint: dict,
) -> bool:
    """
    Determine whether the current room state is reasonably
    aligned with the human temperature constraint.

    This is retained as a diagnostic signal for logging/tests.
    """

    if not constraint:
        return False

    parameter = constraint.get("parameter")
    direction = constraint.get("direction")

    if parameter != "temperature":
        return False

    indoor_temp = float(
        _get_state_value(
            state,
            "indoor_temp_c",
        )
    )

    target_temp = 24.0
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
    setpoint_delta_c: float = 0.0,
) -> tuple[float, dict]:
    """
    Calculate the total RL reward.

    Reward components:

        1. Thermal comfort
        2. Energy consumption
        3. Human temperature constraint
        4. Setpoint movement

    Comfort uses a PMV deadband of +/-0.5.

    The human constraint uses a target temperature band:

        23.5°C <= temperature <= 24.5°C

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

    # =========================================================
    # COMFORT
    # =========================================================

    pmv = calculate_pmv(
        indoor_temp_c=float(
            _get_state_value(
                state,
                "indoor_temp_c",
            )
        ),
        indoor_rh_pct=float(
            _get_state_value(
                state,
                "indoor_rh_pct",
            )
        ),
    )

    comfort_error = abs(pmv)

    if comfort_error <= 0.5:
        comfort_penalty = 0.0
    else:
        comfort_penalty = (
            -weights.alpha
            * (comfort_error - 0.5)
        )

    # =========================================================
    # ENERGY
    # =========================================================

    energy_draw_kw = float(
        _get_state_value(
            state,
            "energy_draw_kw",
        )
    )

    energy_penalty = (
        -weights.beta * energy_draw_kw
    )

    # =========================================================
    # HUMAN CONSTRAINT
    # =========================================================

    constraint = constraint or {}

    direction = constraint.get("direction")

    lower_bound = 23.5
    upper_bound = 24.5

    indoor_temp = float(
        _get_state_value(
            state,
            "indoor_temp_c",
        )
    )

    constraint_error = 0.0

    if direction == "decrease":

        if indoor_temp > upper_bound:
            constraint_error = (
                indoor_temp - upper_bound
            )

        elif indoor_temp < lower_bound:
            constraint_error = (
                lower_bound - indoor_temp
            )

    elif direction == "increase":

        if indoor_temp < lower_bound:
            constraint_error = (
                lower_bound - indoor_temp
            )

        elif indoor_temp > upper_bound:
            constraint_error = (
                indoor_temp - upper_bound
            )

    constraint_penalty = (
        -weights.gamma * constraint_error
    )

    # =========================================================
    # SETPOINT MOVEMENT
    # =========================================================

    setpoint_delta_c = float(
        setpoint_delta_c
    )

    action_penalty = (
        -weights.delta
        * abs(setpoint_delta_c)
    )

    # =========================================================
    # TOTAL REWARD
    # =========================================================

    reward = (
        comfort_penalty
        + energy_penalty
        + constraint_penalty
        + action_penalty
    )

    # =========================================================
    # DIAGNOSTICS
    # =========================================================

    info = {
        "pmv": pmv,

        "comfort_penalty": (
            comfort_penalty
        ),

        "energy_penalty": (
            energy_penalty
        ),

        "constraint_satisfied": (
            constraint_is_satisfied(
                state=state,
                constraint=constraint,
            )
        ),

        "constraint_error": (
            constraint_error
        ),

        "constraint_penalty": (
            constraint_penalty
        ),

        "action_penalty": (
            action_penalty
        ),

        "setpoint_delta_c": (
            setpoint_delta_c
        ),
    }

    return float(reward), info