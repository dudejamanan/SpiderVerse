from dataclasses import dataclass

import numpy as np

from rl.hvac_env import HVACEnv
from gymnasium.utils.env_checker import check_env


@dataclass
class MockState:
    zone_id: str = "room_b"

    indoor_temp_c: float = 26.0
    indoor_rh_pct: float = 55.0
    co2_ppm: float = 700.0

    outdoor_temp_c: float = 34.0
    outdoor_rh_pct: float = 60.0

    occupancy_count: int = 4

    current_setpoint_c: float = 24.0

    energy_draw_kw: float = 1.5

    timestamp: str = "2026-09-15T12:00:00"


class MockTwin:
    def __init__(self):
        self.state = MockState()

    def get_state(self):
        return self.state

    def reset(self):
        self.state = MockState()

    def step(
        self,
        dt,
        hvac_action,
        occupancy_count,
    ):
        self.state.occupancy_count = occupancy_count

        self.state.current_setpoint_c = float(
            np.clip(
                self.state.current_setpoint_c + hvac_action,
                17.0,
                29.0,
            )
        )

        # Very simple fake physics:
        # lower setpoint -> cooler room.
        self.state.indoor_temp_c += (
            self.state.current_setpoint_c
            - self.state.indoor_temp_c
        ) * 0.15

        self.state.energy_draw_kw = (
            1.0 + abs(hvac_action) * 0.5
        )

        return self.state


def test_environment_reset():

    twin = MockTwin()

    constraint = {
        "zone_id": "room_b",
        "parameter": "temperature",
        "direction": "decrease",
        "intensity": "moderate",
        "confidence": 0.85,
    }

    env = HVACEnv(
        twin=twin,
        constraint=constraint,
    )

    observation, info = env.reset()

    assert observation.shape == (9,)
    assert observation.dtype == np.float32
    assert env.observation_space.contains(observation)


def test_environment_action():

    twin = MockTwin()

    constraint = {
        "zone_id": "room_b",
        "parameter": "temperature",
        "direction": "decrease",
        "intensity": "strong",
    }

    env = HVACEnv(
        twin=twin,
        constraint=constraint,
    )

    observation, _ = env.reset()

    next_obs, reward, terminated, truncated, info = env.step(0)

    assert next_obs.shape == (9,)
    assert isinstance(reward, float)

    assert "pmv" in info
    assert "constraint_satisfied" in info
    assert "setpoint_delta_c" in info


def test_action_space():

    twin = MockTwin()

    env = HVACEnv(twin=twin)

    assert env.action_space.n == 5

    for action in range(5):
        delta = env._decode_action(action)

        assert delta in [
            -1.0,
            -0.5,
            0.0,
            0.5,
            1.0,
        ]

def test_gymnasium_api():

    twin = MockTwin()

    env = HVACEnv(twin=twin)

    check_env(env)

def test_room_twin_reset_and_simulated_time():
    from twin.room_twin import RoomTwin

    twin = RoomTwin(
        zone_id="room_b",
        region_id="chennai",
        initial_temp_c=26.0,
        start_hour=8,
    )

    initial_state = twin.reset()

    assert initial_state.indoor_temp_c == 26.0
    assert initial_state.current_setpoint_c == 24.0
    assert initial_state.timestamp.hour == 8

    first_state = twin.step(
        dt=3600.0,
        hvac_action=0.0,
        occupancy_count=2,
    )

def test_env_advances_one_simulation_interval():
    from twin.room_twin import RoomTwin
    from rl.hvac_env import HVACEnv

    twin = RoomTwin(
        zone_id="room_b",
        region_id="chennai",
        initial_temp_c=26.0,
        start_hour=8,
    )

    env = HVACEnv(
        twin=twin,
        max_steps=24,
    )

    obs, info = env.reset()

    assert info["simulated_time"].hour == 8

    obs, reward, terminated, truncated, info = env.step(2)

    assert info["simulated_step"] == 1

    state = twin.get_state()

    assert state.timestamp.hour == 8
    assert state.timestamp.minute == 15