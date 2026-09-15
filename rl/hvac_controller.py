from __future__ import annotations

import numpy as np


DEFAULT_KP_W_PER_C = 200.0
DEFAULT_MAX_HVAC_POWER_W = 2000.0

# Do not actively heat/cool when the room is already
# sufficiently close to the target.
DEFAULT_DEADBAND_C = 0.5


def get_evaluation_occupancy(hour: int) -> int:
    """
    Deterministic occupancy schedule for RL evaluation.

    09:00-18:00 -> 4 occupants
    Otherwise   -> 0 occupants
    """

    hour = int(hour) % 24

    if 9 <= hour < 18:
        return 4

    return 0


def calculate_hvac_action(
    indoor_temp_c: float,
    target_setpoint_c: float,
    kp_w_per_c: float = DEFAULT_KP_W_PER_C,
    max_hvac_power_w: float = DEFAULT_MAX_HVAC_POWER_W,
    deadband_c: float = DEFAULT_DEADBAND_C,
) -> float:
    """
    Calculate HVAC thermal power required to move indoor
    temperature toward the target setpoint.

    Sign convention used by RoomTwin:
        negative -> cooling
        positive -> heating

    The controller is proportional and bounded.

    A deadband prevents unnecessary HVAC operation when
    the indoor temperature is already sufficiently close
    to the target setpoint.
    """

    indoor_temp_c = float(indoor_temp_c)
    target_setpoint_c = float(target_setpoint_c)
    kp_w_per_c = float(kp_w_per_c)
    max_hvac_power_w = float(max_hvac_power_w)
    deadband_c = float(deadband_c)

    if kp_w_per_c <= 0:
        raise ValueError(
            "kp_w_per_c must be greater than zero."
        )

    if max_hvac_power_w <= 0:
        raise ValueError(
            "max_hvac_power_w must be greater than zero."
        )

    if deadband_c < 0:
        raise ValueError(
            "deadband_c cannot be negative."
        )

    temperature_error = (
        target_setpoint_c - indoor_temp_c
    )

    # ---------------------------------------------------------
    # Deadband
    # ---------------------------------------------------------

    if abs(temperature_error) <= deadband_c:
        return 0.0

    # ---------------------------------------------------------
    # Proportional control
    # ---------------------------------------------------------

    hvac_action_w = (
        kp_w_per_c * temperature_error
    )

    return float(
        np.clip(
            hvac_action_w,
            -max_hvac_power_w,
            max_hvac_power_w,
        )
    )