from contracts import TwinState
from twin.room_twin import RoomTwin
import pytest


def test_room_twin_initial_state():
    twin = RoomTwin(
        zone_id="room_a",
        region_id="chennai",
    )

    state = twin.get_state()

    assert isinstance(state, TwinState)
    assert state.zone_id == "room_a"
    assert state.indoor_temp_c == 24.0
    assert state.indoor_rh_pct == 50.0
    assert state.co2_ppm == 420.0
    assert state.occupancy_count == 0
    assert state.current_setpoint_c == 24.0
    assert state.energy_draw_kw == 0.0


def test_room_twin_step_changes_state():
    twin = RoomTwin(
        zone_id="room_a",
        region_id="chennai",
    )

    initial_temp = twin.indoor_temp_c

    state = twin.step(
        dt=1.0,
        hvac_action=-2000.0,
        occupancy_count=2,
    )

    assert isinstance(state, TwinState)
    assert state.indoor_temp_c < initial_temp
    assert state.occupancy_count == 2
    assert state.co2_ppm > 420.0
    assert state.energy_draw_kw == pytest.approx(2000.0 / 3.5 / 1000.0)


def test_room_twin_accepts_manual_weather():
    twin = RoomTwin(
        zone_id="room_a",
        region_id="chennai",
    )

    twin.set_weather(
        outdoor_temp_c=40.0,
        outdoor_rh_pct=70.0,
        solar_radiation_w_m2=500.0,
    )

    state = twin.get_state()

    assert state.outdoor_temp_c == 40.0
    assert state.outdoor_rh_pct == 70.0


def test_room_twin_simulate_returns_multiple_states():
    twin = RoomTwin(
        zone_id="room_a",
        region_id="chennai",
    )

    states = twin.simulate(
        steps=5,
        dt=1.0,
        hvac_action=0.0,
        occupancy_count=4,
    )

    assert len(states) == 5
    assert all(isinstance(state, TwinState) for state in states)
    assert states[-1].co2_ppm > states[0].co2_ppm


def test_room_twin_baseline_schedule():
    twin = RoomTwin(
        zone_id="room_a",
        region_id="chennai",
    )

    assert twin.apply_baseline_schedule(10, 4) == 24.0
    assert twin.apply_baseline_schedule(20, 0) == 28.0


def test_different_zones_have_different_thermal_response():
    room_a = RoomTwin(
        zone_id="room_a",
        region_id="chennai",
    )

    room_b = RoomTwin(
        zone_id="room_b",
        region_id="chennai",
    )

    weather = {
        "outdoor_temp_c": 35.0,
        "outdoor_rh_pct": 50.0,
        "solar_radiation_w_m2": 500.0,
    }

    room_a.set_weather(**weather)
    room_b.set_weather(**weather)

    state_a = room_a.step(
        dt=1.0,
        hvac_action=0.0,
        occupancy_count=4,
    )

    state_b = room_b.step(
        dt=1.0,
        hvac_action=0.0,
        occupancy_count=4,
    )

    assert state_a.indoor_temp_c != state_b.indoor_temp_c

# R = thermal resistance of the room envelope
# C = thermal capacitance
# window_area = area receiving solar gain