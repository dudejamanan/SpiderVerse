"""Backward-compatible region access backed by location metadata."""

from dataclasses import dataclass

from .location_config import LOCATIONS, LocationConfig, get_location


@dataclass(frozen=True)
class Region:
    """Legacy geographic shape retained for existing callers."""

    name: str
    latitude: float
    longitude: float


REGIONS = {
    location_id: Region(
        name=location.name,
        latitude=location.latitude,
        longitude=location.longitude,
    )
    for location_id, location in LOCATIONS.items()
}


def get_region(region_id: str) -> Region:
    """
    Get a region by its ID.
    """

    location = get_location(region_id)
    return REGIONS[location.location_id]