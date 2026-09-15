from twin.room_twin import RoomTwin


def test_room_twin_initial_state():
    twin = RoomTwin(
        zone_id="room_a",
        R=2.0,
        C=10000.0,
        window_area=5.0,
        region_id="chennai",
    )

    state = twin.get_state()

    assert state.zone_id == "room_a"
    assert state.indoor_temp_c == 24.0
    assert state.indoor_rh_pct == 50.0
    assert state.co2_ppm == 420.0


def test_room_twin_step_changes_state():
    twin = RoomTwin(
        zone_id="room_a",
        R=2.0,
        C=10000.0,
        window_area=5.0,
        region_id="chennai",
    )

    initial_temp = twin.indoor_temp_c

    state = twin.step(
        dt=1.0,
        hvac_action=-2000.0,
        occupancy_count=2,
    )

    assert state.indoor_temp_c < initial_temp
    assert state.occupancy_count == 2
    assert state.co2_ppm > 420.0
    assert state.energy_draw_kw == 2.0


def test_room_twin_accepts_manual_weather():
    twin = RoomTwin(
        zone_id="room_a",
        R=2.0,
        C=10000.0,
        window_area=5.0,
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
        R=2.0,
        C=10000.0,
        window_area=5.0,
        region_id="chennai",
    )

    states = twin.simulate(
        steps=5,
        dt=1.0,
        hvac_action=0.0,
        occupancy_count=4,
    )

    assert len(states) == 5
    assert all(isinstance(state, type(twin.get_state())) for state in states)
    assert states[-1].co2_ppm > states[0].co2_ppm