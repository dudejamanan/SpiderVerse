import pytest

from twin.building_config import BuildingConfig, RoomConfig
from twin.building_twin import BuildingTwin
from twin.location_config import LOCATIONS, get_location, list_locations
from twin.regions import get_region


def test_configured_locations_are_complete_and_unique():
    expected = {
        "chennai",
        "delhi",
        "mumbai",
        "dubai",
        "singapore",
        "london",
    }

    assert set(LOCATIONS) == expected
    assert len({location.location_id for location in LOCATIONS.values()}) == 6

    for location in LOCATIONS.values():
        assert -90.0 <= location.latitude <= 90.0
        assert -180.0 <= location.longitude <= 180.0


def test_locations_are_grouped_for_frontend():
    grouped = list_locations()

    assert [item["location_id"] for item in grouped["india"]] == [
        "chennai",
        "delhi",
        "mumbai",
    ]
    assert [item["location_id"] for item in grouped["outside_india"]] == [
        "dubai",
        "singapore",
        "london",
    ]


def test_unknown_location_raises_clear_error():
    with pytest.raises(ValueError, match="Unknown location: nowhere"):
        get_location("nowhere")


def test_region_compatibility_uses_location_source_of_truth():
    assert get_region("mumbai").name == get_location("mumbai").name
    assert get_region("chennai").latitude == 13.0827


def test_building_config_uses_selected_location_coordinates():
    location = get_location("london")
    building = BuildingTwin(
        BuildingConfig(
            building_id="london_building",
            latitude=location.latitude,
            longitude=location.longitude,
            rooms=[RoomConfig(room_id="office_1")],
        )
    )

    room = building.get_room("office_1")

    assert building.latitude == location.latitude
    assert building.longitude == location.longitude
    assert room.zone_id == "office_1"
