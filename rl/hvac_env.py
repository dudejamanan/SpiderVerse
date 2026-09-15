# rl/hvac_env.py

from __future__ import annotations

from typing import Any

import gymnasium as gym
import numpy as np

from .reward import RewardWeights, compute_reward


class HVACEnv(gym.Env):
    """
    Gymnasium environment wrapping the RoomTwin.

    The RL agent observes:
        indoor temperature
        indoor humidity
        CO2
        outdoor temperature
        outdoor humidity
        time of day
        occupancy
        human constraint direction
        human constraint intensity

    The agent chooses:
        -1.0 C
        -0.5 C
         0.0 C
        +0.5 C
        +1.0 C

    The action modifies the current HVAC setpoint.
    """

    metadata = {"render_modes": []}

    ACTION_DELTAS = np.array(
        [-1.0, -0.5, 0.0, 0.5, 1.0],
        dtype=np.float32,
    )

    MIN_SETPOINT_C = 17.0
    MAX_SETPOINT_C = 29.0

    MAX_OCCUPANCY = 20.0

    def __init__(
        self,
        twin: Any,
        constraint: dict | None = None,
        max_steps: int = 24,
        reward_weights: RewardWeights | None = None,
    ):
        super().__init__()

        self.twin = twin
        self.current_constraint = constraint or {}
        self.max_steps = max_steps
        self.reward_weights = reward_weights or RewardWeights()

        self.current_step = 0

        # Five discrete actions:
        #
        # 0 -> -1.0 C
        # 1 -> -0.5 C
        # 2 ->  0.0 C
        # 3 -> +0.5 C
        # 4 -> +1.0 C
        self.action_space = gym.spaces.Discrete(5)

        # 9 normalized observations.
        self.observation_space = gym.spaces.Box(
            low=-1.0,
            high=1.0,
            shape=(9,),
            dtype=np.float32,
        )

    # ---------------------------------------------------------
    # ACTION
    # ---------------------------------------------------------

    def _decode_action(self, action: int) -> float:
        """
        Convert discrete action into setpoint delta.
        """

        action = int(action)

        if not self.action_space.contains(action):
            raise ValueError(f"Invalid action: {action}")

        return float(self.ACTION_DELTAS[action])

    # ---------------------------------------------------------
    # NORMALIZATION
    # ---------------------------------------------------------

    @staticmethod
    def _normalize(
        value: float,
        minimum: float,
        maximum: float,
    ) -> float:
        """
        Map value from [minimum, maximum] to [-1, 1].
        """

        if maximum <= minimum:
            raise ValueError("maximum must be greater than minimum")

        normalized = (
            2.0 * (value - minimum) / (maximum - minimum)
            - 1.0
        )

        return float(np.clip(normalized, -1.0, 1.0))

    def _encode_direction(self, direction: str | None) -> float:
        """
        Encode human temperature direction.

        decrease -> -1
        increase -> +1
        anything else -> 0
        """

        if direction == "decrease":
            return -1.0

        if direction == "increase":
            return 1.0

        return 0.0

    def _encode_intensity(self, intensity: str | float | None) -> float:
        """
        Encode complaint intensity.

        slight    -> -0.5
        moderate  ->  0
        strong    -> +1
        """

        if isinstance(intensity, (int, float)):
            return float(np.clip(intensity, -1.0, 1.0))

        mapping = {
            "slight": -0.5,
            "moderate": 0.0,
            "strong": 1.0,
        }

        return mapping.get(intensity, 0.0)

    # ---------------------------------------------------------
    # STATE -> OBSERVATION
    # ---------------------------------------------------------

    def _state_to_obs(self, state: Any) -> np.ndarray:
        """
        Convert RoomTwin state into normalized observation vector.
        """

        indoor_temp = self._normalize(
            float(state.indoor_temp_c),
            10.0,
            40.0,
        )

        indoor_rh = self._normalize(
            float(state.indoor_rh_pct),
            0.0,
            100.0,
        )

        co2 = self._normalize(
            float(state.co2_ppm),
            400.0,
            2000.0,
        )

        outdoor_temp = self._normalize(
            float(state.outdoor_temp_c),
            0.0,
            50.0,
        )

        outdoor_rh = self._normalize(
            float(state.outdoor_rh_pct),
            0.0,
            100.0,
        )

        # Simulated time in hours.
        hour = self._get_hour(state)

        time_of_day = self._normalize(
            hour,
            0.0,
            24.0,
        )

        occupancy = self._normalize(
            float(state.occupancy_count),
            0.0,
            self.MAX_OCCUPANCY,
        )

        direction = self._encode_direction(
            self.current_constraint.get("direction")
        )

        intensity = self._encode_intensity(
            self.current_constraint.get("intensity")
        )

        obs = np.array(
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

        return obs

    @staticmethod
    def _get_hour(state: Any) -> float:
        """
        Extract hour from timestamp.

        Supports:
            datetime
            ISO timestamp string
        """

        timestamp = getattr(state, "timestamp", None)

        if timestamp is None:
            return 12.0

        if hasattr(timestamp, "hour"):
            return float(timestamp.hour)

        try:
            from datetime import datetime

            parsed = datetime.fromisoformat(
                str(timestamp).replace("Z", "+00:00")
            )

            return float(parsed.hour)

        except (ValueError, TypeError):
            return 12.0

    # ---------------------------------------------------------
    # CONSTRAINT
    # ---------------------------------------------------------

    def set_constraint(self, constraint: dict | None) -> None:
        """
        Update the active human constraint.

        Person 3 / Person 4 can call this between episodes.
        """

        self.current_constraint = constraint or {}

    # ---------------------------------------------------------
    # STEP
    # ---------------------------------------------------------

    def step(self, action: int):
        """
        Execute one simulation step.
        """

        hvac_delta = self._decode_action(action)

        # Clamp the new setpoint to the safety range.
        current_setpoint = float(
            self.twin.state.current_setpoint_c
        )

        new_setpoint = float(
            np.clip(
                current_setpoint + hvac_delta,
                self.MIN_SETPOINT_C,
                self.MAX_SETPOINT_C,
            )
        )

        actual_delta = new_setpoint - current_setpoint

        # RoomTwin is expected to expose step().
        state = self.twin.step(
            dt=1,
            hvac_action=actual_delta,
            occupancy_count=self._get_occupancy(),
        )

        reward, reward_info = compute_reward(
            state,
            self.current_constraint,
            self.reward_weights,
        )

        self.current_step += 1

        terminated = False

        truncated = self.current_step >= self.max_steps

        observation = self._state_to_obs(state)

        info = {
            "setpoint_delta_c": actual_delta,
            "new_setpoint_c": new_setpoint,
            **reward_info,
        }

        return (
            observation,
            reward,
            terminated,
            truncated,
            info,
        )

    def _get_occupancy(self) -> int:
        """
        Read occupancy from the current twin state.
        """

        state = getattr(self.twin, "state", None)

        if state is None:
            return 0

        return int(getattr(state, "occupancy_count", 0))

    # ---------------------------------------------------------
    # RESET
    # ---------------------------------------------------------

    def reset(
        self,
        *,
        seed: int | None = None,
        options: dict | None = None,
    ):
        """
        Reset the environment.

        The exact reset behavior depends on Person 1's RoomTwin
        implementation. We support a standard reset() if available.
        """

        super().reset(seed=seed)

        self.current_step = 0

        if hasattr(self.twin, "reset"):
            self.twin.reset()

        state = self.twin.get_state()

        observation = self._state_to_obs(state)

        info = {
            "zone_id": getattr(state, "zone_id", None),
        }

        return observation, info