# rl/hvac_env.py

from __future__ import annotations

from typing import Any

import gymnasium as gym
import numpy as np

from .observation import (
    get_observation_space,
    get_state_value,
    state_to_observation,
)
from .reward import (
    RewardWeights,
    compute_reward,
)


class HVACEnv(gym.Env):
    """
    Gymnasium environment wrapping the RoomTwin.

    Observation:
        1. indoor temperature
        2. indoor humidity
        3. CO2
        4. outdoor temperature
        5. outdoor humidity
        6. time of day
        7. occupancy
        8. human constraint direction
        9. human constraint intensity

    Actions:
        0 -> -1.0 C
        1 -> -0.5 C
        2 ->  0.0 C
        3 -> +0.5 C
        4 -> +1.0 C
    """

    metadata = {"render_modes": []}

    ACTION_DELTAS = np.array(
        [-1.0, -0.5, 0.0, 0.5, 1.0],
        dtype=np.float32,
    )

    MIN_SETPOINT_C = 17.0
    MAX_SETPOINT_C = 29.0

    # Temporary actuator mapping.
    #
    # The current RoomTwin expects HVAC power in watts,
    # while the RL action is a setpoint change in Celsius.
    #
    # Therefore:
    #
    #   -1.0 C -> -1000 W
    #   -0.5 C ->  -500 W
    #    0.0 C ->     0 W
    #   +0.5 C ->  +500 W
    #   +1.0 C -> +1000 W
    #
    # This is a prototype bridge and can be calibrated later.
    WATTS_PER_DEGREE = 1000.0

    def __init__(
        self,
        twin: Any,
        constraint: dict | None = None,
        max_steps: int = 24,
        reward_weights: RewardWeights | None = None,
    ):
        super().__init__()

        self.twin = twin

        self.current_constraint = (
            constraint or {}
        )

        self.max_steps = max_steps

        self.reward_weights = (
            reward_weights or RewardWeights()
        )

        self.current_step = 0

        # Five discrete RL actions.
        self.action_space = gym.spaces.Discrete(5)

        # Nine normalized observations.
        self.observation_space = (
            get_observation_space()
        )

    def _get_state(self) -> Any:
        """Get the current state from RoomTwin."""
        return self.twin.get_state()

    def _decode_action(
        self,
        action: int,
    ) -> float:
        """
        Convert a discrete action into
        a setpoint delta in Celsius.
        """

        action = int(action)

        if not self.action_space.contains(action):
            raise ValueError(
                f"Invalid action: {action}"
            )

        return float(
            self.ACTION_DELTAS[action]
        )

    @classmethod
    def _delta_to_hvac_power(
        cls,
        delta_c: float,
    ) -> float:
        """
        Convert setpoint delta into temporary
        HVAC thermal power.

        Negative -> cooling
        Positive -> heating
        """

        return float(
            delta_c * cls.WATTS_PER_DEGREE
        )

    def set_constraint(
        self,
        constraint: dict | None,
    ) -> None:
        """
        Update the active human constraint.
        """

        self.current_constraint = (
            constraint or {}
        )

    def _get_occupancy(self) -> int:
        """
        Read occupancy from the current
        TwinState.
        """

        state = self._get_state()

        return int(
            get_state_value(
                state,
                "occupancy_count",
                0,
            )
        )

    def step(self, action: int):
        """
        Execute one simulation step.
        """

        # --------------------------------------------------
        # 1. Decode RL action
        # --------------------------------------------------

        requested_delta = (
            self._decode_action(action)
        )

        # --------------------------------------------------
        # 2. Read current twin state
        # --------------------------------------------------

        current_state = self._get_state()

        current_setpoint = float(
            get_state_value(
                current_state,
                "current_setpoint_c",
                24.0,
            )
        )

        # --------------------------------------------------
        # 3. Calculate new setpoint
        # --------------------------------------------------

        new_setpoint = float(
            np.clip(
                current_setpoint
                + requested_delta,
                self.MIN_SETPOINT_C,
                self.MAX_SETPOINT_C,
            )
        )

        # Because of the 17-29 C safety bounds,
        # the actual change may be smaller than
        # the requested change.
        actual_delta = (
            new_setpoint
            - current_setpoint
        )

        # --------------------------------------------------
        # 4. Convert RL action to HVAC power
        # --------------------------------------------------

        hvac_power_w = (
            self._delta_to_hvac_power(
                actual_delta
            )
        )

        # --------------------------------------------------
        # 5. Get occupancy
        # --------------------------------------------------

        occupancy = self._get_occupancy()

        # --------------------------------------------------
        # 6. Update twin setpoint
        # --------------------------------------------------

        self.twin.current_setpoint_c = (
            new_setpoint
        )

        # --------------------------------------------------
        # 7. Advance digital twin
        # --------------------------------------------------

        state = self.twin.step(
            dt=1.0,
            hvac_action=hvac_power_w,
            occupancy_count=occupancy,
        )

        # --------------------------------------------------
        # 8. Calculate reward
        # --------------------------------------------------

        reward, reward_info = compute_reward(
            state,
            self.current_constraint,
            self.reward_weights,
        )

        # --------------------------------------------------
        # 9. Advance RL episode
        # --------------------------------------------------

        self.current_step += 1

        terminated = False

        truncated = (
            self.current_step
            >= self.max_steps
        )

        # --------------------------------------------------
        # 10. Convert state into observation
        # --------------------------------------------------

        observation = state_to_observation(
            state,
            self.current_constraint,
        )

        # --------------------------------------------------
        # 11. Diagnostic information
        # --------------------------------------------------

        info = {
            "setpoint_delta_c": actual_delta,
            "new_setpoint_c": new_setpoint,
            "hvac_power_w": hvac_power_w,
            **reward_info,
        }

        return (
            observation,
            reward,
            terminated,
            truncated,
            info,
        )

    def reset(
        self,
        *,
        seed: int | None = None,
        options: dict | None = None,
    ):
        """
        Reset the RL episode.

        The current RoomTwin does not yet provide
        a reset() method, so this currently resets
        the RL episode counter while retaining the
        twin's current state.
        """

        super().reset(seed=seed)

        self.current_step = 0

        # Use RoomTwin.reset() if Person 1 adds it later.
        if hasattr(self.twin, "reset"):
            self.twin.reset()

        state = self._get_state()

        observation = state_to_observation(
            state,
            self.current_constraint,
        )

        info = {
            "zone_id": get_state_value(
                state,
                "zone_id",
                None,
            ),
        }

        return (
            observation,
            info,
        )