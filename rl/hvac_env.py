from __future__ import annotations

from datetime import datetime
from typing import Any

import gymnasium as gym
import numpy as np

from .hvac_controller import calculate_hvac_action

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
    Gymnasium environment for HVAC control.

    The environment wraps a configurable RoomTwin.

    The RoomTwin is responsible for:
        - room thermal properties
        - initial indoor conditions
        - weather
        - occupancy
        - humidity
        - CO2
        - HVAC capacity
        - HVAC efficiency

    The RL agent is responsible for:
        - selecting the next thermostat setpoint adjustment

    PPO action space:

        0 -> -1.0 °C
        1 -> -0.5 °C
        2 ->  0.0 °C
        3 -> +0.5 °C
        4 -> +1.0 °C

    One RL step represents one configurable simulation interval.
    """

    metadata = {
        "render_modes": []
    }

    # =========================================================
    # ACTION CONFIGURATION
    # =========================================================

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

    # A 15-minute control interval keeps explicit Euler integration
    # numerically stable for small configurable room capacitances.
    DEFAULT_SIMULATION_DT_SECONDS = 900.0
    DEFAULT_TIMESTEP_SECONDS = DEFAULT_SIMULATION_DT_SECONDS

    # =========================================================
    # INITIALIZATION
    # =========================================================

    def __init__(
        self,
        twin: Any,
        constraint: dict | None = None,
        max_steps: int = 24,
        reward_weights: RewardWeights | None = None,
        occupancy_schedule: Any = None,
        timestep_seconds: float | None = None,
        simulation_dt_seconds: float | None = None,
    ):
        """
        Parameters
        ----------
        twin:
            Configured RoomTwin instance.

        constraint:
            Human comfort constraint produced by the NLP layer.

        max_steps:
            Maximum number of RL decisions in one episode.

        reward_weights:
            Weights for comfort, energy, human constraint,
            and setpoint movement.

        occupancy_schedule:
            Optional callable:

                occupancy_schedule(hour) -> int

            If omitted, the occupancy already present in
            RoomTwin is preserved.

        timestep_seconds:
            Backward-compatible name for the simulation timestep.

        simulation_dt_seconds:
            Simulation timestep in seconds. Each RL action advances
            the twin by exactly this duration. Defaults to 900 seconds.
        """

        super().__init__()

        if twin is None:
            raise ValueError(
                "twin must be a configured RoomTwin instance."
            )

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

        self.occupancy_schedule = (
            occupancy_schedule
        )

        self.current_step = 0

        if (
            timestep_seconds is not None
            and simulation_dt_seconds is not None
        ):
            raise ValueError(
                "Provide only one timestep argument."
            )

        configured_dt = (
            simulation_dt_seconds
            if simulation_dt_seconds is not None
            else timestep_seconds
        )

        self.simulation_dt_seconds = float(
            configured_dt
            if configured_dt is not None
            else self.DEFAULT_SIMULATION_DT_SECONDS
        )

        if self.simulation_dt_seconds <= 0:
            raise ValueError(
                "simulation_dt_seconds must be greater than zero."
            )

        # Keep the existing attribute available to callers.
        self.timestep_seconds = self.simulation_dt_seconds

        # -----------------------------------------------------
        # Gymnasium spaces
        # -----------------------------------------------------

        self.action_space = gym.spaces.Discrete(
            len(self.ACTION_DELTAS)
        )

        self.observation_space = (
            get_observation_space()
        )

    # =========================================================
    # STATE HELPERS
    # =========================================================

    def _get_state(self) -> Any:
        """
        Return the current state of the Digital Twin.
        """

        return self.twin.get_state()

    # =========================================================
    # ACTION
    # =========================================================

    def _decode_action(
        self,
        action: int,
    ) -> float:
        """
        Convert PPO's discrete action into
        a thermostat setpoint delta.
        """

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

    def _apply_setpoint_bounds(
        self,
        current_setpoint: float,
        requested_delta: float,
    ) -> tuple[float, float]:
        """
        Apply the safe thermostat range.

        Returns
        -------
        actual_delta:
            Delta that was actually applied.

        new_setpoint:
            Resulting setpoint.
        """

        current_setpoint = float(
            current_setpoint
        )

        requested_delta = float(
            requested_delta
        )

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

        return (
            float(actual_delta),
            float(new_setpoint),
        )

    # =========================================================
    # CONSTRAINT
    # =========================================================

    def set_constraint(
        self,
        constraint: dict | None,
    ) -> None:
        """
        Replace the active human comfort constraint.

        This allows the NLP module to update the desired
        comfort preference during a simulation.
        """

        self.current_constraint = (
            constraint or {}
        )

    # =========================================================
    # OCCUPANCY
    # =========================================================

    def _get_current_hour(
        self,
        state: Any,
    ) -> int:
        """
        Extract the simulated hour from TwinState.
        """

        timestamp = get_state_value(
            state,
            "timestamp",
            None,
        )

        if timestamp is None:
            return 12

        if hasattr(timestamp, "hour"):
            return int(timestamp.hour)

        try:
            return int(
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
            return 12

    def _get_occupancy(
        self,
        state: Any,
    ) -> int:
        """
        Determine occupancy for the next simulation step.

        Priority:

        1. User-provided occupancy schedule
        2. Existing TwinState occupancy

        This is important because the new Digital Twin
        supports arbitrary room occupancy instead of assuming
        four occupants during working hours.
        """

        current_hour = self._get_current_hour(
            state
        )

        if self.occupancy_schedule is not None:

            occupancy = self.occupancy_schedule(
                current_hour
            )

            occupancy = int(
                max(
                    0,
                    occupancy,
                )
            )

            return occupancy

        return int(
            max(
                0,
                get_state_value(
                    state,
                    "occupancy_count",
                    0,
                ),
            )
        )

    # =========================================================
    # STEP
    # =========================================================

    def step(
        self,
        action: int,
    ):
        """
        Execute one RL decision.

        Flow:

            PPO action
                ↓
            setpoint delta
                ↓
            safety bounds
                ↓
            HVAC thermal power
                ↓
            RoomTwin
                ↓
            next state
                ↓
            reward
                ↓
            next observation
        """

        # =====================================================
        # 1. Current state
        # =====================================================

        previous_state = self._get_state()

        current_setpoint = float(
            get_state_value(
                previous_state,
                "current_setpoint_c",
                24.0,
            )
        )

        indoor_temp_before = float(
            get_state_value(
                previous_state,
                "indoor_temp_c",
                24.0,
            )
        )

        # =====================================================
        # 2. Decode PPO action
        # =====================================================

        requested_delta = (
            self._decode_action(action)
        )

        # =====================================================
        # 3. Apply thermostat safety bounds
        # =====================================================

        (
            actual_delta,
            new_setpoint,
        ) = self._apply_setpoint_bounds(
            current_setpoint,
            requested_delta,
        )

        # =====================================================
        # 4. Determine HVAC thermal power
        # =====================================================

        # RoomTwin's HVAC capacity is used when available.
        # Otherwise use the established 2000 W default.

        max_hvac_power_w = float(
            getattr(
                self.twin,
                "hvac_capacity_w",
                2000.0,
            )
        )

        # If RoomTwin exposes its configuration,
        # obtain the capacity from it.
        twin_config = getattr(
            self.twin,
            "config",
            None,
        )

        if twin_config is not None:
            max_hvac_power_w = float(
                getattr(
                    twin_config,
                    "hvac_capacity_w",
                    max_hvac_power_w,
                )
            )

        # -----------------------------------------------------
        # Controller converts temperature error to thermal
        # HVAC power.
        # -----------------------------------------------------

        hvac_power_w = calculate_hvac_action(
            indoor_temp_c=indoor_temp_before,
            target_setpoint_c=new_setpoint,
            max_hvac_power_w=max_hvac_power_w,
        )

        # Enforce the room-specific limit at the environment boundary too.
        hvac_power_w = float(
            np.clip(
                hvac_power_w,
                -max_hvac_power_w,
                max_hvac_power_w,
            )
        )

        # =====================================================
        # 5. Occupancy
        # =====================================================

        occupancy = self._get_occupancy(
            previous_state
        )

        # =====================================================
        # 6. Apply action to Digital Twin
        # =====================================================

        self.twin.current_setpoint_c = (
            new_setpoint
        )

        state = self.twin.step(
            dt=self.simulation_dt_seconds,
            hvac_action=hvac_power_w,
            occupancy_count=occupancy,
        )

        # =====================================================
        # 7. Validate Digital Twin output
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

        # =====================================================
        # 8. Calculate reward
        # =====================================================

        electrical_power_kw = float(
            get_state_value(
                state,
                "energy_draw_kw",
                0.0,
            )
        )

        energy_draw_kwh = (
            electrical_power_kw
            * self.simulation_dt_seconds
            / 3600.0
        )

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
                energy_draw_kwh=energy_draw_kwh,
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
        # 10. Next observation
        # =====================================================

        observation = (
            state_to_observation(
                state,
                self.current_constraint,
            )
        )

        # =====================================================
        # 11. Diagnostic information
        # =====================================================

        info = {
            # RL action
            "action": int(action),

            "requested_delta_c": (
                requested_delta
            ),

            "setpoint_delta_c": (
                actual_delta
            ),

            "new_setpoint_c": (
                new_setpoint
            ),

            # HVAC
            "hvac_power_w": (
                hvac_power_w
            ),

            "hvac_capacity_w": (
                max_hvac_power_w
            ),

            # Thermal state
            "indoor_temp_before_c": (
                indoor_temp_before
            ),

            "indoor_temp_after_c": (
                indoor_temp_after
            ),

            # Environment
            "occupancy_count": (
                occupancy
            ),

            "energy_draw_kw": float(
                get_state_value(
                    state,
                    "energy_draw_kw",
                    0.0,
                )
            ),

            "energy_draw_kwh": energy_draw_kwh,

            # Simulation
            "simulated_step": (
                self.current_step
            ),

            "simulation_dt_seconds": (
                self.simulation_dt_seconds
            ),

            "simulated_time": (
                get_state_value(
                    state,
                    "timestamp",
                    None,
                )
            ),

            # Human constraint
            "constraint": (
                self.current_constraint
            ),

            # Reward diagnostics
            **reward_info,
        }

        return (
            observation,
            float(reward),
            terminated,
            truncated,
            info,
        )

    # =========================================================
    # RESET
    # =========================================================

    def reset(
        self,
        *,
        seed: int | None = None,
        options: dict | None = None,
    ):
        """
        Reset the Digital Twin and RL episode.
        """

        super().reset(
            seed=seed
        )

        self.current_step = 0

        # -----------------------------------------------------
        # Optional reset configuration
        # -----------------------------------------------------
        #
        # This allows the frontend/backend to provide
        # custom initial conditions when creating an episode.
        #
        # Example:
        #
        # env.reset(
        #     options={
        #         "initial_temp_c": 29,
        #         "initial_rh_pct": 70,
        #         "initial_co2_ppm": 1200,
        #         "initial_occupancy": 8,
        #     }
        # )
        #
        # RoomTwin remains the source of truth for actually
        # applying these values.

        options = options or {}

        configurable_attributes = (
            "initial_temp_c",
            "initial_indoor_rh_pct",
            "initial_co2_ppm",
            "initial_occupancy",
            "initial_setpoint_c",
            "start_hour",
        )

        for attribute in configurable_attributes:

            if attribute in options and hasattr(
                self.twin,
                attribute,
            ):
                setattr(
                    self.twin,
                    attribute,
                    options[attribute],
                )

        # -----------------------------------------------------
        # Reset Digital Twin
        # -----------------------------------------------------

        if hasattr(
            self.twin,
            "reset",
        ):
            self.twin.reset()

        # -----------------------------------------------------
        # Get initial state
        # -----------------------------------------------------

        state = self._get_state()

        # -----------------------------------------------------
        # Build observation
        # -----------------------------------------------------

        observation = (
            state_to_observation(
                state,
                self.current_constraint,
            )
        )

        # -----------------------------------------------------
        # Reset diagnostics
        # -----------------------------------------------------

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

            "initial_temp_c": float(
                get_state_value(
                    state,
                    "indoor_temp_c",
                    24.0,
                )
            ),

            "initial_rh_pct": float(
                get_state_value(
                    state,
                    "indoor_rh_pct",
                    50.0,
                )
            ),

            "initial_co2_ppm": float(
                get_state_value(
                    state,
                    "co2_ppm",
                    420.0,
                )
            ),

            "initial_occupancy": int(
                get_state_value(
                    state,
                    "occupancy_count",
                    0,
                )
            ),

            "initial_setpoint_c": float(
                get_state_value(
                    state,
                    "current_setpoint_c",
                    24.0,
                )
            ),

            "constraint": (
                self.current_constraint
            ),
        }

        return (
            observation,
            info,
        )

    # =========================================================
    # RENDER
    # =========================================================

    def render(self):
        """
        Return the current Digital Twin state.

        This intentionally returns structured data instead
        of printing so the backend/dashboard can consume it.
        """

        state = self._get_state()

        return {
            "zone_id": get_state_value(
                state,
                "zone_id",
            ),

            "indoor_temp_c": get_state_value(
                state,
                "indoor_temp_c",
            ),

            "indoor_rh_pct": get_state_value(
                state,
                "indoor_rh_pct",
            ),

            "co2_ppm": get_state_value(
                state,
                "co2_ppm",
            ),

            "outdoor_temp_c": get_state_value(
                state,
                "outdoor_temp_c",
            ),

            "outdoor_rh_pct": get_state_value(
                state,
                "outdoor_rh_pct",
            ),

            "occupancy_count": get_state_value(
                state,
                "occupancy_count",
            ),

            "current_setpoint_c": get_state_value(
                state,
                "current_setpoint_c",
            ),

            "energy_draw_kw": get_state_value(
                state,
                "energy_draw_kw",
            ),

            "timestamp": get_state_value(
                state,
                "timestamp",
            )
        }
