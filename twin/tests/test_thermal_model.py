from twin.thermal_model import calculate_next_temperature


def test_room_heats_when_outdoor_is_hot():
    indoor_temp = 24.0
    outdoor_temp = 35.0

    next_temp = calculate_next_temperature(
        indoor_temp_c=indoor_temp,
        outdoor_temp_c=outdoor_temp,
        R=2.0,
        C=10000.0,
        dt=1.0,
        q_hvac_w=0.0,
    )

    assert next_temp > indoor_temp


def test_room_cools_with_hvac():
    indoor_temp = 30.0
    outdoor_temp = 35.0

    next_temp = calculate_next_temperature(
        indoor_temp_c=indoor_temp,
        outdoor_temp_c=outdoor_temp,
        R=2.0,
        C=10000.0,
        dt=1.0,
        q_hvac_w=-2000.0,
    )

    assert next_temp < indoor_temp
