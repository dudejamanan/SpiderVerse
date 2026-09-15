"""
Regional configuration for the HVAC Digital Twin.

Person 01: Twin Engineer
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Region:
    """Geographic configuration for a simulation region."""

    name: str
    latitude: float
    longitude: float


REGIONS = {
    "chennai": Region(
        name="Chennai",
        latitude=13.0827,
        longitude=80.2707,
    ),
    "delhi": Region(
        name="Delhi",
        latitude=28.6139,
        longitude=77.2090,
    ),
}


def get_region(region_id: str) -> Region:
    """
    Get a region by its ID.
    """

    region_id = region_id.lower()

    if region_id not in REGIONS:
        raise ValueError(
            f"Unknown region: {region_id}. "
            f"Available regions: {list(REGIONS.keys())}"
        )

    return REGIONS[region_id]