"""
Physical configuration for individual HVAC zones.

Person 01: Twin Engineer
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ZoneConfig:
    """Physical parameters describing one simulated room."""

    zone_id: str

    # Effective thermal resistance of the room envelope.
    # Units: K/W
    R: float

    # Effective thermal capacitance of the room.
    # Units: J/K
    C: float

    # Effective window area.
    # Units: m²
    window_area_m2: float

    # Effective solar transmission/shading factor.
    shading_coefficient: float = 0.5

    # Approximate room volume.
    # Units: m³
    volume_m3: float = 30.0

    # Mechanical ventilation rate.
    # Air changes per hour.
    ventilation_ach: float = 1.5

    # HVAC coefficient of performance.
    cop: float = 3.5


ZONE_CONFIGS = {
    "room_a": ZoneConfig(
        zone_id="room_a",
        R=2.0,
        C=156000.0,
        window_area_m2=5.0,
    ),
    "room_b": ZoneConfig(
        zone_id="room_b",
        R=0.02,
        C=3_000_000.0,
        window_area_m2=4.0,
    ),
}


def get_zone_config(zone_id: str) -> ZoneConfig:
    """Return the physical configuration for a zone."""

    if zone_id not in ZONE_CONFIGS:
        raise ValueError(
            f"Unknown zone: {zone_id}. "
            f"Available zones: {list(ZONE_CONFIGS.keys())}"
        )

    return ZONE_CONFIGS[zone_id]