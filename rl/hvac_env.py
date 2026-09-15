from __future__ import annotations

from datetime import datetime
from typing import Any

import gymnasium as gym
import numpy as np

from .hvac_controller import (
    calculate_hvac_action,
    get_evaluation_occupancy,
)

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
    Gymnasium environment wrapping RoomTwin.

    One RL step represents one simulated hour.

    PPO action:
        0 -> -1.0°C
        1 -> -0.5°C
        2 ->  0.0°C
        3 -> +0.5°C
        4 -> +1.0°C
    """

    metadata = {"render_modes": []}

    ACTION_DELTAS = np.array(
        [
            -1.0,
            -0.5,
            0.0,
            0.5,
            1.0,
        ],
        dtype=np.float32,
    )

    MIN_SETPOINT_C = 17.0
    MAX_SETPOINT_C = 29.0

    TIMESTEP_SECONDS = 3600.0

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

        self.max_steps = int(max_steps)

        if self.max_steps <= 0:
            raise ValueError(
                "max_steps must be greater than zero."
            )

        self.reward_weights = (
            reward_weights
            or RewardWeights()
        )

        self.current_step = 0

        self.action_space = gym.spaces.Discrete(
            len(self.ACTION_DELTAS)
        )

        self.observation_space = (
            get_observation_space()
        )

    def _get_state(self) -> Any:
        return self.twin.get_state()

    def _decode_action(
        self,
        action: int,
    ) -> float:
        action = int(action)

        if not self.action_space.contains(
            action
        ):
            raise ValueError(
                f"Invalid action: {action}"
            )

        return float(
            self.ACTION_DELTAS[action]
        )

    def set_constraint(
        self,
        constraint: dict | None,
    ) -> None:
        self.current_constraint = (
            constraint or {}
        )

    def _get_occupancy_from_time(
        self,
        state: Any,
    ) -> int:
        """
        Determine deterministic evaluation occupancy
        from the simulated timestamp.

        Supports:
        - datetime timestamps
        - ISO timestamp strings
        """

        timestamp = get_state_value(
            state,
            "timestamp",
            None,
        )

        if timestamp is None:

            current_hour = 12

        elif hasattr(timestamp, "hour"):

            current_hour = int(
                timestamp.hour
            )

        else:

            try:
                current_hour = int(
                    datetime.fromisoformat(
                        str(timestamp).replace(
                            "Z",
                            "+00:00",
                        )
                    ).hour
                )

            except (
                ValueError,
                TypeError,
            ):

                current_hour = 12

        return get_evaluation_occupancy(
            current_hour
        )

    def step(
        self,
        action: int,
    ):

        # =====================================================
        # 1. Decode PPO action
        # =====================================================

        requested_delta = (
            self._decode_action(action)
        )

        # =====================================================
        # 2. Read current state
        # =====================================================

        current_state = self._get_state()

        current_setpoint = float(
            get_state_value(
                current_state,
                "current_setpoint_c",
                24.0,
            )
        )

        indoor_temp = float(
            get_state_value(
                current_state,
                "indoor_temp_c",
            )
        )

        # =====================================================
        # 3. Apply setpoint safety bounds
        # =====================================================

        new_setpoint = float(
            np.clip(
                current_setpoint
                + requested_delta,
                self.MIN_SETPOINT_C,
                self.MAX_SETPOINT_C,
            )
        )

        actual_delta = (
            new_setpoint
            - current_setpoint
        )

        # =====================================================
        # 4. Convert setpoint to HVAC thermal power
        # =====================================================

        hvac_power_w = calculate_hvac_action(
            indoor_temp_c=indoor_temp,
            target_setpoint_c=new_setpoint,
        )

        # =====================================================
        # 5. Determine occupancy
        # =====================================================

        occupancy = (
            self._get_occupancy_from_time(
                current_state
            )
        )

        # =====================================================
        # 6. Apply action to RoomTwin
        # =====================================================

        self.twin.current_setpoint_c = (
            new_setpoint
        )

        state = self.twin.step(
            dt=self.TIMESTEP_SECONDS,
            hvac_action=hvac_power_w,
            occupancy_count=occupancy,
        )

        # =====================================================
        # 7. Safety checks
        # =====================================================

        indoor_temp_after = float(
            get_state_value(
                state,
                "indoor_temp_c",
            )
        )

        if not np.isfinite(
            indoor_temp_after
        ):
            raise RuntimeError(
                "RoomTwin produced invalid "
                f"indoor temperature: "
                f"{indoor_temp_after}"
            )

        if (
            indoor_temp_after < 10.0
            or indoor_temp_after > 40.0
        ):
            raise RuntimeError(
                "RoomTwin temperature became "
                "physically unreasonable: "
                f"{indoor_temp_after:.2f}°C"
            )

        # =====================================================
        # 8. Calculate reward
        # =====================================================

        reward, reward_info = (
            compute_reward(
                state=state,
                constraint=(
                    self.current_constraint
                ),
                weights=(
                    self.reward_weights
                ),
                setpoint_delta_c=(
                    actual_delta
                ),
            )
        )

        # =====================================================
        # 9. Advance episode
        # =====================================================

        self.current_step += 1

        terminated = False

        truncated = (
            self.current_step
            >= self.max_steps
        )

        # =====================================================
        # 10. Build next observation
        # =====================================================

        observation = (
            state_to_observation(
                state,
                self.current_constraint,
            )
        )

        # =====================================================
        # 11. Build diagnostic info
        # =====================================================

        info = {
            "setpoint_delta_c": (
                actual_delta
            ),

            "new_setpoint_c": (
                new_setpoint
            ),

            "requested_delta_c": (
                requested_delta
            ),

            "hvac_power_w": (
                hvac_power_w
            ),

            "energy_draw_kw": float(
                get_state_value(
                    state,
                    "energy_draw_kw",
                    0.0,
                )
            ),

            "occupancy_count": (
                occupancy
            ),

            "simulated_step": (
                self.current_step
            ),

            "simulated_time": (
                get_state_value(
                    state,
                    "timestamp",
                    None,
                )
            ),

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
        super().reset(
            seed=seed
        )

        self.current_step = 0

        if hasattr(
            self.twin,
            "reset",
        ):
            self.twin.reset()

        state = self._get_state()

        observation = (
            state_to_observation(
                state,
                self.current_constraint,
            )
        )

        info = {
            "zone_id": get_state_value(
                state,
                "zone_id",
                None,
            ),

            "simulated_time": (
                get_state_value(
                    state,
                    "timestamp",
                    None,
                )
            ),
        }

        return (
            observation,
            info,
        )