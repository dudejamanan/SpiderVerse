# rl/observation.py

from __future__ import annotations

from datetime import datetime
from typing import Any

import gymnasium as gym
import numpy as np


MAX_OCCUPANCY = 20.0


def get_state_value(
    state: Any,
    key: str,
    default: Any = None,
) -> Any:
    """
    Read a value from either:

    1. A dictionary-based twin state
    2. An object/dataclass/Pydantic-based twin state
    """

    if isinstance(state, dict):
        return state.get(key, default)

    return getattr(state, key, default)


def normalize(
    value: float,
    minimum: float,
    maximum: float,
) -> float:
    """
    Map a value from [minimum, maximum] to [-1, 1].
    """

    if maximum <= minimum:
        raise ValueError(
            "maximum must be greater than minimum"
        )

    normalized = (
        2.0 * (value - minimum)
        / (maximum - minimum)
        - 1.0
    )

    return float(
        np.clip(normalized, -1.0, 1.0)
    )


def encode_direction(
    direction: str | None,
) -> float:
    """
    Encode human temperature constraint direction.

    decrease -> -1
    increase -> +1
    anything else -> 0
    """

    if direction == "decrease":
        return -1.0

    if direction == "increase":
        return 1.0

    return 0.0


def encode_intensity(
    intensity: str | float | None,
) -> float:
    """
    Encode complaint intensity.

    slight    -> -0.5
    moderate  ->  0
    strong    -> +1
    """

    if isinstance(intensity, (int, float)):
        return float(
            np.clip(intensity, -1.0, 1.0)
        )

    mapping = {
        "slight": -0.5,
        "moderate": 0.0,
        "strong": 1.0,
    }

    return mapping.get(intensity, 0.0)


def get_hour(state: Any) -> float:
    """
    Extract the hour from the TwinState timestamp.

    Supports:

    - datetime objects
    - ISO-format strings

    If timestamp is unavailable or invalid,
    defaults to 12:00.
    """

    timestamp = get_state_value(
        state,
        "timestamp",
        None,
    )

    if timestamp is None:
        return 12.0

    if hasattr(timestamp, "hour"):
        return float(timestamp.hour)

    try:
        parsed = datetime.fromisoformat(
            str(timestamp).replace(
                "Z",
                "+00:00",
            )
        )

        return float(parsed.hour)

    except (ValueError, TypeError):
        return 12.0


def state_to_observation(
    state: Any,
    constraint: dict | None = None,
) -> np.ndarray:
    """
    Convert a TwinState into the 9-element
    normalized RL observation.

    Observation order:

    1. indoor temperature
    2. indoor humidity
    3. CO2
    4. outdoor temperature
    5. outdoor humidity
    6. time of day
    7. occupancy
    8. constraint direction
    9. constraint intensity
    """

    constraint = constraint or {}

    indoor_temp = normalize(
        float(
            get_state_value(
                state,
                "indoor_temp_c",
            )
        ),
        10.0,
        40.0,
    )

    indoor_rh = normalize(
        float(
            get_state_value(
                state,
                "indoor_rh_pct",
            )
        ),
        0.0,
        100.0,
    )

    co2 = normalize(
        float(
            get_state_value(
                state,
                "co2_ppm",
            )
        ),
        400.0,
        2000.0,
    )

    outdoor_temp = normalize(
        float(
            get_state_value(
                state,
                "outdoor_temp_c",
            )
        ),
        0.0,
        50.0,
    )

    outdoor_rh = normalize(
        float(
            get_state_value(
                state,
                "outdoor_rh_pct",
            )
        ),
        0.0,
        100.0,
    )

    time_of_day = normalize(
        get_hour(state),
        0.0,
        24.0,
    )

    occupancy = normalize(
        float(
            get_state_value(
                state,
                "occupancy_count",
                0,
            )
        ),
        0.0,
        MAX_OCCUPANCY,
    )

    direction = encode_direction(
        constraint.get("direction")
    )

    intensity = encode_intensity(
        constraint.get("intensity")
    )

    observation = np.array(
        [
            indoor_temp,
            indoor_rh,
            co2,
            outdoor_temp,
            outdoor_rh,
            time_of_day,
            occupancy,
            direction,
            intensity,
        ],
        dtype=np.float32,
    )

    return observation


def get_observation_space() -> gym.spaces.Box:
    """
    Return the Gymnasium observation space
    used by HVACEnv and the PPO agent.
    """

    return gym.spaces.Box(
        low=-1.0,
        high=1.0,
        shape=(9,),
        dtype=np.float32,
    )