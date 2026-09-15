"""Centralized geographic metadata for configurable building locations."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class LocationConfig:
    location_id: str
    name: str
    country: str
    latitude: float
    longitude: float


LOCATIONS = {
    "chennai": LocationConfig(
        location_id="chennai",
        name="Chennai",
        country="India",
        latitude=13.0827,
        longitude=80.2707,
    ),
    "delhi": LocationConfig(
        location_id="delhi",
        name="Delhi",
        country="India",
        latitude=28.6139,
        longitude=77.2090,
    ),
    "mumbai": LocationConfig(
        location_id="mumbai",
        name="Mumbai",
        country="India",
        latitude=19.0760,
        longitude=72.8777,
    ),
    "dubai": LocationConfig(
        location_id="dubai",
        name="Dubai",
        country="United Arab Emirates",
        latitude=25.2048,
        longitude=55.2708,
    ),
    "singapore": LocationConfig(
        location_id="singapore",
        name="Singapore",
        country="Singapore",
        latitude=1.3521,
        longitude=103.8198,
    ),
    "london": LocationConfig(
        location_id="london",
        name="London",
        country="United Kingdom",
        latitude=51.5074,
        longitude=-0.1278,
    ),
}


def get_location(location_id: str) -> LocationConfig:
    """Resolve a location ID or raise a clear configuration error."""

    normalized_id = str(location_id).strip().lower()

    if normalized_id not in LOCATIONS:
        raise ValueError(
            f"Unknown location: {normalized_id}. "
            f"Available locations: {list(LOCATIONS)}"
        )

    return LOCATIONS[normalized_id]


def list_locations() -> dict[str, list[dict]]:
    """Return location metadata grouped for the frontend."""

    grouped: dict[str, list[dict]] = {}

    for location in LOCATIONS.values():
        group = "india" if location.country == "India" else "outside_india"
        grouped.setdefault(group, []).append(asdict(location))

    return grouped
