from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from stable_baselines3 import PPO

from rl.hvac_env import HVACEnv
from twin.room_twin import RoomTwin
from twin.building_config import RoomConfig

# ============================================================
# CONFIGURATION
# ============================================================

DEFAULT_TOTAL_TIMESTEPS = 50_000

MODEL_DIR = Path("rl/models")
MODEL_PATH = MODEL_DIR / "hvac_policy"


# ============================================================
# HUMAN COMFORT CONSTRAINTS
# ============================================================
#
# These are generic constraints.
# They are NOT tied to Room A / Room B.
#
# The frontend/NLP layer can later generate these dynamically.
# ============================================================

CONSTRAINTS = [
    {
        "parameter": "temperature",
        "direction": "decrease",
        "intensity": "slight",
        "confidence": 0.85,
        "raw_text": "The room is slightly warm",
    },
    {
        "parameter": "temperature",
        "direction": "decrease",
        "intensity": "moderate",
        "confidence": 0.85,
        "raw_text": "The room feels stuffy",
    },
    {
        "parameter": "temperature",
        "direction": "decrease",
        "intensity": "strong",
        "confidence": 0.85,
        "raw_text": "The room is too hot",
    },
    {
        "parameter": "temperature",
        "direction": "increase",
        "intensity": "slight",
        "confidence": 0.85,
        "raw_text": "The room is slightly cold",
    },
    {
        "parameter": "temperature",
        "direction": "increase",
        "intensity": "moderate",
        "confidence": 0.85,
        "raw_text": "The room feels cold",
    },
]


# ============================================================
# RANDOMIZED TRAINING ENVIRONMENT
# ============================================================


class RandomizedHVACEnv(HVACEnv):
    """
    Generalized HVAC training environment.

    Each episode randomizes:

        - latitude/longitude (arbitrary global location)
        - room thermal properties (R, C, window_area, etc.)
        - room geometry (area, height)
        - HVAC capacity and efficiency
        - initial indoor temperature
        - indoor humidity
        - CO2
        - occupancy
        - starting hour
        - initial HVAC setpoint
        - human comfort constraint

    The purpose is to prevent PPO from learning a policy
    specifically tied to one room or one climate.
    """

    def __init__(self):

        # Initial placeholder values.
        # reset() replaces these before an episode starts.

        self._latitude = 13.0827
        self._longitude = 80.2707

        self._room_id = "room_0"

        self._initial_temp_c = 26.0
        self._initial_rh_pct = 58.0
        self._initial_co2_ppm = 720.0
        self._initial_occupancy = 4
        self._initial_setpoint_c = 24.0
        self._start_hour = 8

        self._constraint = CONSTRAINTS[1]

        # Create initial RoomConfig with placeholder values
        config = RoomConfig(
            room_id=self._room_id,
            area_m2=30.0,
            height_m=3.0,
            window_area_m2=5.0,
            R=2.0,
            C=156000.0,
            shading_coefficient=0.5,
            ventilation_ach=1.5,
            hvac_capacity_w=2000.0,
            cop=3.5,
            initial_temp_c=self._initial_temp_c,
            initial_rh_pct=self._initial_rh_pct,
            initial_co2_ppm=self._initial_co2_ppm,
            initial_occupancy=self._initial_occupancy,
        )

        twin = RoomTwin(
            config=config,
            latitude=self._latitude,
            longitude=self._longitude,
            start_hour=self._start_hour,
        )

        super().__init__(
            twin=twin,
            constraint=self._constraint,
            max_steps=24,
        )

    # ========================================================
    # RESET
    # ========================================================

    def reset(
        self,
        *,
        seed: int | None = None,
        options: dict | None = None,
    ):
        """
        Start a new randomized simulation episode.
        """

        # Initialize Gymnasium RNG.
        super().reset(seed=seed)

        # ----------------------------------------------------
        # Random latitude/longitude (temperate regions only for stability)
        # ----------------------------------------------------

        self._latitude = float(
            self.np_random.uniform(
                -45.0,
                45.0,
            )
        )

        self._longitude = float(
            self.np_random.uniform(
                -180.0,
                180.0,
            )
        )

        # ----------------------------------------------------
        # Random room thermal properties (physically consistent)
        # ----------------------------------------------------

        area_m2 = float(
            self.np_random.uniform(
                20.0,
                50.0,
            )
        )

        height_m = float(
            self.np_random.uniform(
                2.8,
                3.2,
            )
        )

        # Window area should be proportional to room area (10-20%)
        window_area_m2 = float(
            self.np_random.uniform(
                0.1 * area_m2,
                0.2 * area_m2,
            )
        )

        # Thermal resistance: 1.5 to 3.0 K/W
        R = float(
            self.np_random.uniform(
                1.5,
                3.0,
            )
        )

        # Thermal capacitance should scale with room volume
        # Approximate: air heat capacity ~ 1.2 kJ/m³K × volume
        volume_m3 = area_m2 * height_m
        C = float(
            self.np_random.uniform(
                1.0e6 * volume_m3,
                2.0e6 * volume_m3,
            )
        )

        shading_coefficient = float(
            self.np_random.uniform(
                0.4,
                0.8,
            )
        )

        ventilation_ach = float(
            self.np_random.uniform(
                0.5,
                1.5,
            )
        )

        # HVAC capacity should scale with room size (50-100 W/m²)
        hvac_capacity_w = float(
            self.np_random.uniform(
                50.0 * area_m2,
                100.0 * area_m2,
            )
        )

        cop = float(
            self.np_random.uniform(
                3.0,
                4.0,
            )
        )

        # ----------------------------------------------------
        # Random initial indoor conditions (constrained for stability)
        # ----------------------------------------------------

        self._initial_temp_c = float(
            self.np_random.uniform(
                22.0,
                30.0,
            )
        )

        self._initial_rh_pct = float(
            self.np_random.uniform(
                35.0,
                85.0,
            )
        )

        self._initial_co2_ppm = float(
            self.np_random.uniform(
                420.0,
                1200.0,
            )
        )

        self._initial_occupancy = int(
            self.np_random.integers(
                0,
                10,
            )
        )

        self._initial_setpoint_c = float(
            self.np_random.uniform(
                22.0,
                27.0,
            )
        )

        self._start_hour = int(
            self.np_random.integers(
                0,
                24,
            )
        )

        # ----------------------------------------------------
        # Random human constraint
        # ----------------------------------------------------

        constraint_index = int(
            self.np_random.integers(
                0,
                len(CONSTRAINTS),
            )
        )

        self._constraint = CONSTRAINTS[
            constraint_index
        ]

        # ----------------------------------------------------
        # Create new RoomConfig with randomized parameters
        # ----------------------------------------------------

        config = RoomConfig(
            room_id=self._room_id,
            area_m2=area_m2,
            height_m=height_m,
            window_area_m2=window_area_m2,
            R=R,
            C=C,
            shading_coefficient=shading_coefficient,
            ventilation_ach=ventilation_ach,
            hvac_capacity_w=hvac_capacity_w,
            cop=cop,
            initial_temp_c=self._initial_temp_c,
            initial_rh_pct=self._initial_rh_pct,
            initial_co2_ppm=self._initial_co2_ppm,
            initial_occupancy=self._initial_occupancy,
        )

        # ----------------------------------------------------
        # Replace the twin with a new randomized instance
        # ----------------------------------------------------

        self.twin = RoomTwin(
            config=config,
            latitude=self._latitude,
            longitude=self._longitude,
            start_hour=self._start_hour,
        )

        # ----------------------------------------------------
        # Apply constraint
        # ----------------------------------------------------

        self.set_constraint(
            self._constraint
        )

        self.current_step = 0

        # ----------------------------------------------------
        # Reset physical Twin
        # ----------------------------------------------------

        self.twin.reset()

        # ----------------------------------------------------
        # Generate observation
        # ----------------------------------------------------

        state = self._get_state()

        from rl.observation import (
            get_state_value,
            state_to_observation,
        )

        observation = state_to_observation(
            state,
            self.current_constraint,
        )

        # ----------------------------------------------------
        # Diagnostic information
        # ----------------------------------------------------

        info = {
            "zone_id": get_state_value(
                state,
                "zone_id",
                None,
            ),
            "latitude": self._latitude,
            "longitude": self._longitude,
            "simulated_time": get_state_value(
                state,
                "timestamp",
                None,
            ),
            "initial_temp_c": self._initial_temp_c,
            "initial_rh_pct": self._initial_rh_pct,
            "initial_co2_ppm": self._initial_co2_ppm,
            "initial_occupancy": self._initial_occupancy,
            "initial_setpoint_c": self._initial_setpoint_c,
            "start_hour": self._start_hour,
            "area_m2": area_m2,
            "R": R,
            "C": C,
            "hvac_capacity_w": hvac_capacity_w,
            "cop": cop,
            "constraint": self._constraint,
        }

        return observation, info


# ============================================================
# ENVIRONMENT FACTORY
# ============================================================


def make_environment() -> HVACEnv:
    """
    Create the generalized randomized HVAC environment.
    """

    return RandomizedHVACEnv()


# ============================================================
# PPO TRAINING
# ============================================================


def train(
    total_timesteps: int = DEFAULT_TOTAL_TIMESTEPS,
) -> Path:
    """
    Train PPO on randomized HVAC simulations.

    PPO sees different room/climate/occupancy conditions
    throughout training rather than one fixed scenario.
    """

    env = make_environment()

    MODEL_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    model = PPO(
        policy="MlpPolicy",
        env=env,
        verbose=1,

        # PPO hyperparameters
        learning_rate=3e-4,
        n_steps=256,
        batch_size=64,
        gamma=0.99,
        gae_lambda=0.95,
        ent_coef=0.01,
        max_grad_norm=0.5,
        clip_range=0.2,

        seed=42,
    )

    model.learn(
        total_timesteps=total_timesteps,
    )

    model.save(
        str(MODEL_PATH)
    )

    env.close()

    return MODEL_PATH.with_suffix(
        ".zip"
    )


# ============================================================
# MAIN
# ============================================================


if __name__ == "__main__":

    saved_model = train()

    print()
    print("Training complete.")
    print(
        f"Model saved to: {saved_model}"
    )
