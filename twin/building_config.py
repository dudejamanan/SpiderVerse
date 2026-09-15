"""
Dynamic building configuration for the HVAC Digital Twin.

Person 01: Twin Engineer

This module defines user-configurable building and room
parameters. A building is no longer restricted to predefined
regions or a fixed number of rooms.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RoomConfig:
    """
    Physical and environmental configuration for one room.

    All values can be supplied by the frontend/user.
    """

    room_id: str

    # ---------------------------------------------------------
    # Geometry
    # ---------------------------------------------------------

    area_m2: float = 30.0
    height_m: float = 3.0
    window_area_m2: float = 5.0

    # ---------------------------------------------------------
    # Thermal properties
    # ---------------------------------------------------------

    # Effective thermal resistance.
    # Higher R -> better insulation.
    # Units: K/W
    R: float = 2.0

    # Effective thermal capacitance.
    # Higher C -> slower temperature changes.
    # Units: J/K
    C: float = 156_000.0

    # Fraction of incident solar radiation entering room.
    shading_coefficient: float = 0.5

    # ---------------------------------------------------------
    # Air / ventilation
    # ---------------------------------------------------------

    ventilation_ach: float = 1.5

    # ---------------------------------------------------------
    # HVAC
    # ---------------------------------------------------------

    hvac_capacity_w: float = 2000.0
    cop: float = 3.5

    # ---------------------------------------------------------
    # Initial indoor state
    # ---------------------------------------------------------

    initial_temp_c: float = 24.0
    initial_rh_pct: float = 50.0
    initial_co2_ppm: float = 420.0

    # Initial occupancy.
    initial_occupancy: int = 0

    def __post_init__(self) -> None:
        if not self.room_id:
            raise ValueError("room_id cannot be empty.")

        if self.area_m2 <= 0:
            raise ValueError("area_m2 must be greater than zero.")

        if self.height_m <= 0:
            raise ValueError("height_m must be greater than zero.")

        if self.window_area_m2 < 0:
            raise ValueError(
                "window_area_m2 cannot be negative."
            )

        if self.R <= 0:
            raise ValueError("R must be greater than zero.")

        if self.C <= 0:
            raise ValueError("C must be greater than zero.")

        if not 0.0 <= self.shading_coefficient <= 1.0:
            raise ValueError(
                "shading_coefficient must be between 0 and 1."
            )

        if self.ventilation_ach < 0:
            raise ValueError(
                "ventilation_ach cannot be negative."
            )

        if self.hvac_capacity_w <= 0:
            raise ValueError(
                "hvac_capacity_w must be greater than zero."
            )

        if self.cop <= 0:
            raise ValueError(
                "cop must be greater than zero."
            )

        if not 0.0 <= self.initial_rh_pct <= 100.0:
            raise ValueError(
                "initial_rh_pct must be between 0 and 100."
            )

        if self.initial_co2_ppm < 0:
            raise ValueError(
                "initial_co2_ppm cannot be negative."
            )

        if self.initial_occupancy < 0:
            raise ValueError(
                "initial_occupancy cannot be negative."
            )

    @property
    def volume_m3(self) -> float:
        """Calculate room volume from area and height."""

        return self.area_m2 * self.height_m


@dataclass
class BuildingConfig:
    """
    Complete configuration of a simulated building.

    Latitude and longitude can come directly from the
    frontend globe/map.

    Weather values are optional overrides. If they are None,
    the weather client can provide live/default values.
    """

    building_id: str

    latitude: float
    longitude: float

    rooms: list[RoomConfig] = field(
        default_factory=list
    )

    # ---------------------------------------------------------
    # Optional weather overrides
    # ---------------------------------------------------------

    outdoor_temp_c: float | None = None
    outdoor_rh_pct: float | None = None
    solar_radiation_w_m2: float | None = None

    def __post_init__(self) -> None:
        if not self.building_id:
            raise ValueError(
                "building_id cannot be empty."
            )

        if not -90.0 <= self.latitude <= 90.0:
            raise ValueError(
                "latitude must be between -90 and 90."
            )

        if not -180.0 <= self.longitude <= 180.0:
            raise ValueError(
                "longitude must be between -180 and 180."
            )

        if not self.rooms:
            raise ValueError(
                "Building must contain at least one room."
            )

        room_ids = [
            room.room_id
            for room in self.rooms
        ]

        if len(room_ids) != len(set(room_ids)):
            raise ValueError(
                "Room IDs must be unique."
            )

        if self.outdoor_rh_pct is not None:
            if not 0.0 <= self.outdoor_rh_pct <= 100.0:
                raise ValueError(
                    "outdoor_rh_pct must be between 0 and 100."
                )

        if self.solar_radiation_w_m2 is not None:
            if self.solar_radiation_w_m2 < 0:
                raise ValueError(
                    "solar_radiation_w_m2 cannot be negative."
                )

    def get_room(
        self,
        room_id: str,
    ) -> RoomConfig:
        """Return a room configuration by ID."""

        for room in self.rooms:
            if room.room_id == room_id:
                return room

        raise ValueError(
            f"Unknown room: {room_id}. "
            f"Available rooms: "
            f"{[room.room_id for room in self.rooms]}"
        )

    def add_room(
        self,
        room: RoomConfig,
    ) -> None:
        """Add a new room dynamically."""

        if any(
            existing.room_id == room.room_id
            for existing in self.rooms
        ):
            raise ValueError(
                f"Room already exists: {room.room_id}"
            )

        self.rooms.append(room)

    def remove_room(
        self,
        room_id: str,
    ) -> None:
        """Remove a room dynamically."""

        original_count = len(self.rooms)

        self.rooms = [
            room
            for room in self.rooms
            if room.room_id != room_id
        ]

        if len(self.rooms) == original_count:
            raise ValueError(
                f"Unknown room: {room_id}"
            )

        if not self.rooms:
            raise ValueError(
                "Building must contain at least one room."
            )

    def update_weather_override(
        self,
        outdoor_temp_c: float | None = None,
        outdoor_rh_pct: float | None = None,
        solar_radiation_w_m2: float | None = None,
    ) -> None:
        """
        Update manually supplied weather values.

        None means that particular variable should use the
        external weather source instead.
        """

        if outdoor_rh_pct is not None:
            if not 0.0 <= outdoor_rh_pct <= 100.0:
                raise ValueError(
                    "outdoor_rh_pct must be between 0 and 100."
                )

        if solar_radiation_w_m2 is not None:
            if solar_radiation_w_m2 < 0:
                raise ValueError(
                    "solar_radiation_w_m2 cannot be negative."
                )

        self.outdoor_temp_c = outdoor_temp_c
        self.outdoor_rh_pct = outdoor_rh_pct
        self.solar_radiation_w_m2 = solar_radiation_w_m2

    def to_dict(self) -> dict[str, Any]:
        """Return frontend/API-friendly configuration."""

        return {
            "building_id": self.building_id,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "weather": {
                "outdoor_temp_c": self.outdoor_temp_c,
                "outdoor_rh_pct": self.outdoor_rh_pct,
                "solar_radiation_w_m2": (
                    self.solar_radiation_w_m2
                ),
            },
            "rooms": [
                {
                    "room_id": room.room_id,
                    "area_m2": room.area_m2,
                    "height_m": room.height_m,
                    "volume_m3": room.volume_m3,
                    "window_area_m2": room.window_area_m2,
                    "R": room.R,
                    "C": room.C,
                    "shading_coefficient": (
                        room.shading_coefficient
                    ),
                    "ventilation_ach": (
                        room.ventilation_ach
                    ),
                    "hvac_capacity_w": (
                        room.hvac_capacity_w
                    ),
                    "cop": room.cop,
                    "initial_temp_c": (
                        room.initial_temp_c
                    ),
                    "initial_rh_pct": (
                        room.initial_rh_pct
                    ),
                    "initial_co2_ppm": (
                        room.initial_co2_ppm
                    ),
                    "initial_occupancy": (
                        room.initial_occupancy
                    ),
                }
                for room in self.rooms
            ],
        }