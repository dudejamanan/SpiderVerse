from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from stable_baselines3 import PPO

from rl.hvac_env import HVACEnv
from twin.room_twin import RoomTwin


DEFAULT_TOTAL_TIMESTEPS = 50_000

MODEL_DIR = Path(
    "rl/models"
)

MODEL_PATH = (
    MODEL_DIR
    / "hvac_policy"
)


CONSTRAINTS = [
    {
        "zone_id": "room_b",
        "parameter": "temperature",
        "direction": "decrease",
        "intensity": "slight",
        "confidence": 0.85,
        "raw_text": (
            "Room B is slightly warm"
        ),
    },

    {
        "zone_id": "room_b",
        "parameter": "temperature",
        "direction": "decrease",
        "intensity": "moderate",
        "confidence": 0.85,
        "raw_text": (
            "it's stuffy in Room B"
        ),
    },

    {
        "zone_id": "room_b",
        "parameter": "temperature",
        "direction": "decrease",
        "intensity": "strong",
        "confidence": 0.85,
        "raw_text": (
            "Room B is too hot"
        ),
    },
]


class RandomizedHVACEnv(HVACEnv):
    """
    HVAC environment with randomized starting conditions.

    Each episode gets:
        - a different starting indoor temperature
        - a different starting hour
        - a different constraint intensity
    """

    def __init__(self):

        self._initial_temp_c = 26.0
        self._start_hour = 8
        self._constraint = CONSTRAINTS[1]

        twin = RoomTwin(
            zone_id="room_b",
            region_id="chennai",
            initial_temp_c=(
                self._initial_temp_c
            ),
            start_hour=(
                self._start_hour
            ),
        )

        super().__init__(
            twin=twin,
            constraint=self._constraint,
            max_steps=24,
        )


    def reset(
        self,
        *,
        seed: int | None = None,
        options: dict | None = None,
    ):
        # Always initialize Gymnasium's random-number generator.
        # This makes seeded and unseeded resets behave consistently.
        super().reset(seed=seed)

        self._initial_temp_c = float(
            self.np_random.uniform(
                24.0,
                29.0,
            )
        )

        self._start_hour = int(
            self.np_random.integers(
                0,
                24,
            )
        )

        constraint_index = int(
            self.np_random.integers(
                0,
                len(CONSTRAINTS),
            )
        )

        self._constraint = CONSTRAINTS[
            constraint_index
        ]

        self.twin.initial_temp_c = (
            self._initial_temp_c
        )

        self.twin.initial_indoor_rh_pct = 58.0
        self.twin.initial_co2_ppm = 720.0
        self.twin.initial_setpoint_c = 24.0

        self.twin.start_hour = self._start_hour

        self.twin.simulation_time = datetime(
            2026,
            1,
            1,
            self._start_hour,
            0,
            tzinfo=timezone.utc,
        )

        self.set_constraint(
            self._constraint
        )

        self.current_step = 0

        self.twin.reset()

        state = self._get_state()

        from rl.observation import (
            state_to_observation,
            get_state_value,
        )

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
            "simulated_time": get_state_value(
                state,
                "timestamp",
                None,
            ),
            "initial_temp_c": self._initial_temp_c,
            "start_hour": self._start_hour,
            "constraint": self._constraint,
        }

        return observation, info

def make_environment() -> HVACEnv:
    """
    Create the randomized training environment.
    """

    return RandomizedHVACEnv()


def train(
    total_timesteps: int = (
        DEFAULT_TOTAL_TIMESTEPS
    ),
) -> Path:
    """
    Train a PPO agent and save the
    resulting policy.
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
        total_timesteps=(
            total_timesteps
        )
    )

    model.save(
        str(MODEL_PATH)
    )

    env.close()

    return MODEL_PATH.with_suffix(
        ".zip"
    )


if __name__ == "__main__":

    saved_model = train()

    print()
    print(
        "Training complete."
    )
    print(
        f"Model saved to: "
        f"{saved_model}"
    )