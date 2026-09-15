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