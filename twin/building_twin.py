"""
Building-level Digital Twin.

Person 01: Twin Engineer

A BuildingTwin manages any number of RoomTwin instances.

There is deliberately no fixed room_a / room_b assumption.

The frontend can construct a BuildingConfig containing:
    - any latitude/longitude
    - any number of rooms
    - arbitrary room geometry
    - arbitrary thermal parameters
    - arbitrary initial conditions
    - optional weather overrides
"""

from __future__ import annotations

from typing import Any

from twin.building_config import (
    BuildingConfig,
    RoomConfig,
)
from twin.room_twin import RoomTwin


class BuildingTwin:
    """
    Digital twin for an entire configurable building.

    Example:

        building = BuildingTwin(
            BuildingConfig(
                building_id="office",
                latitude=25.2048,
                longitude=55.2708,
                rooms=[
                    RoomConfig(
                        room_id="office_1",
                        initial_temp_c=29.0,
                        initial_rh_pct=70.0,
                        initial_occupancy=8,
                    ),
                    RoomConfig(
                        room_id="office_2",
                        initial_temp_c=25.0,
                        initial_rh_pct=55.0,
                        initial_occupancy=3,
                    ),
                ],
            )
        )
    """

    def __init__(
        self,
        config: BuildingConfig,
    ):
        self.config = config

        self.building_id = config.building_id
        self.latitude = float(config.latitude)
        self.longitude = float(config.longitude)

        self.rooms: dict[str, RoomTwin] = {}

        self._create_rooms()

        # ---------------------------------------------------------
        # Apply building-level weather override if supplied.
        # ---------------------------------------------------------

        if self._has_weather_override():
            self.set_weather(
                outdoor_temp_c=(
                    config.outdoor_temp_c
                ),
                outdoor_rh_pct=(
                    config.outdoor_rh_pct
                ),
                solar_radiation_w_m2=(
                    config.solar_radiation_w_m2
                ),
            )

    # ============================================================
    # ROOM MANAGEMENT
    # ============================================================

    def _create_rooms(self) -> None:
        """Create RoomTwin objects from BuildingConfig."""

        self.rooms.clear()

        for room_config in self.config.rooms:

            self.rooms[
                room_config.room_id
            ] = RoomTwin(
                config=room_config,
                latitude=self.latitude,
                longitude=self.longitude,
            )

    def add_room(
        self,
        room_config: RoomConfig,
    ) -> RoomTwin:
        """
        Add a room to the building.

        The new room immediately becomes part of the
        building simulation.
        """

        if room_config.room_id in self.rooms:
            raise ValueError(
                f"Room already exists: "
                f"{room_config.room_id}"
            )

        self.config.add_room(
            room_config
        )

        room = RoomTwin(
            config=room_config,
            latitude=self.latitude,
            longitude=self.longitude,
        )

        self.rooms[
            room_config.room_id
        ] = room

        # Apply current building weather if available.
        self._apply_weather_to_room(room)

        return room

    def remove_room(
        self,
        room_id: str,
    ) -> None:
        """Remove a room from the building."""

        if room_id not in self.rooms:
            raise ValueError(
                f"Unknown room: {room_id}"
            )

        self.config.remove_room(
            room_id
        )

        del self.rooms[room_id]

    def get_room(
        self,
        room_id: str,
    ) -> RoomTwin:
        """Return a room twin by ID."""

        if room_id not in self.rooms:
            raise ValueError(
                f"Unknown room: {room_id}. "
                f"Available rooms: "
                f"{list(self.rooms.keys())}"
            )

        return self.rooms[room_id]

    # ============================================================
    # WEATHER
    # ============================================================

    def _has_weather_override(self) -> bool:
        """
        Determine whether the building has manually supplied
        weather data.
        """

        return any(
            value is not None
            for value in (
                self.config.outdoor_temp_c,
                self.config.outdoor_rh_pct,
                self.config.solar_radiation_w_m2,
            )
        )

    def _apply_weather_to_room(
        self,
        room: RoomTwin,
    ) -> None:
        """
        Apply currently configured building weather to a room.

        Only non-None values are used.
        Existing values remain unchanged for fields that
        were not overridden.
        """

        outdoor_temp = (
            self.config.outdoor_temp_c
            if self.config.outdoor_temp_c
            is not None
            else room.outdoor_temp_c
        )

        outdoor_rh = (
            self.config.outdoor_rh_pct
            if self.config.outdoor_rh_pct
            is not None
            else room.outdoor_rh_pct
        )

        solar = (
            self.config.solar_radiation_w_m2
            if self.config.solar_radiation_w_m2
            is not None
            else room.solar_radiation_w_m2
        )

        room.set_weather(
            outdoor_temp_c=outdoor_temp,
            outdoor_rh_pct=outdoor_rh,
            solar_radiation_w_m2=solar,
        )

    def update_weather(self) -> None:
        """
        Fetch current weather using the building coordinates.

        The same outdoor conditions are then applied to all
        rooms because all rooms belong to the same building.
        """

        from twin.weather_client import (
            get_current_weather,
        )

        weather = get_current_weather(
            latitude=self.latitude,
            longitude=self.longitude,
        )

        self.config.update_weather_override(
            outdoor_temp_c=(
                weather["outdoor_temp_c"]
            ),
            outdoor_rh_pct=(
                weather["outdoor_rh_pct"]
            ),
            solar_radiation_w_m2=(
                weather[
                    "solar_radiation_w_m2"
                ]
            ),
        )

        self.set_weather(
            outdoor_temp_c=(
                weather["outdoor_temp_c"]
            ),
            outdoor_rh_pct=(
                weather["outdoor_rh_pct"]
            ),
            solar_radiation_w_m2=(
                weather[
                    "solar_radiation_w_m2"
                ]
            ),
        )

    def set_weather(
        self,
        outdoor_temp_c: float | None = None,
        outdoor_rh_pct: float | None = None,
        solar_radiation_w_m2: float | None = None,
    ) -> None:
        """
        Manually set weather for the entire building.

        This is the main interface for frontend-driven
        what-if weather simulation.
        """

        if outdoor_temp_c is not None:
            self.config.outdoor_temp_c = float(
                outdoor_temp_c
            )

        if outdoor_rh_pct is not None:
            self.config.outdoor_rh_pct = float(
                outdoor_rh_pct
            )

        if solar_radiation_w_m2 is not None:
            self.config.solar_radiation_w_m2 = float(
                solar_radiation_w_m2
            )

        for room in self.rooms.values():
            self._apply_weather_to_room(room)

    # ============================================================
    # ROOM INITIAL CONDITIONS
    # ============================================================

    def set_room_conditions(
        self,
        room_id: str,
        temperature_c: float | None = None,
        humidity_pct: float | None = None,
        co2_ppm: float | None = None,
        occupancy_count: int | None = None,
    ) -> None:
        """
        Dynamically modify one room's indoor state.
        """

        room = self.get_room(
            room_id
        )

        room.set_indoor_conditions(
            temperature_c=temperature_c,
            humidity_pct=humidity_pct,
            co2_ppm=co2_ppm,
            occupancy_count=occupancy_count,
        )

    # ============================================================
    # SIMULATION
    # ============================================================

    def step(
        self,
        dt: float,
        hvac_actions: dict[str, float] | None = None,
        occupancies: dict[str, int] | None = None,
    ) -> dict[str, Any]:
        """
        Advance every room by one timestep.

        Parameters
        ----------
        dt:
            Simulation timestep in seconds.

        hvac_actions:
            Dictionary:

                {
                    "room_1": -1500.0,
                    "room_2": 500.0
                }

            Negative -> cooling
            Positive -> heating

        occupancies:
            Dictionary:

                {
                    "room_1": 8,
                    "room_2": 3
                }

        Returns
        -------
        dict
            Room states keyed by room ID.
        """

        if dt <= 0:
            raise ValueError(
                "dt must be greater than zero."
            )

        hvac_actions = hvac_actions or {}
        occupancies = occupancies or {}

        states: dict[str, Any] = {}

        for room_id, room in self.rooms.items():

            hvac_action = float(
                hvac_actions.get(
                    room_id,
                    0.0,
                )
            )

            occupancy = occupancies.get(
                room_id,
                room.occupancy_count,
            )

            states[room_id] = room.step(
                dt=dt,
                hvac_action=hvac_action,
                occupancy_count=occupancy,
            )

        return states

    def simulate(
        self,
        steps: int,
        dt: float,
        hvac_actions: dict[str, float]
        | None = None,
        occupancies: dict[str, int]
        | None = None,
    ) -> list[dict[str, Any]]:
        """
        Run multiple building-level simulation steps.
        """

        if steps < 0:
            raise ValueError(
                "steps cannot be negative."
            )

        results: list[dict[str, Any]] = []

        for _ in range(steps):

            results.append(
                self.step(
                    dt=dt,
                    hvac_actions=hvac_actions,
                    occupancies=occupancies,
                )
            )

        return results

    # ============================================================
    # RESET
    # ============================================================

    def reset(self) -> dict[str, Any]:
        """Reset every room to its configured initial state."""

        states: dict[str, Any] = {}

        for room_id, room in self.rooms.items():
            states[room_id] = room.reset()

        # Reapply building weather after reset.
        if self._has_weather_override():
            for room in self.rooms.values():
                self._apply_weather_to_room(room)

        return states

    # ============================================================
    # STATE
    # ============================================================

    def get_state(
        self,
    ) -> dict[str, Any]:
        """
        Return the current state of every room.
        """

        return {
            room_id: room.get_state()
            for room_id, room in self.rooms.items()
        }

    # ============================================================
    # CONFIGURATION
    # ============================================================

    def get_config(
        self,
    ) -> dict[str, Any]:
        """
        Return frontend/API-friendly building configuration.
        """

        return self.config.to_dict()

    def summary(self) -> dict[str, Any]:
        """
        Return a compact building simulation summary.
        """

        states = self.get_state()

        total_energy_kw = sum(
            state.energy_draw_kw
            for state in states.values()
        )

        average_temperature = (
            sum(
                state.indoor_temp_c
                for state in states.values()
            )
            / len(states)
            if states
            else 0.0
        )

        total_occupancy = sum(
            state.occupancy_count
            for state in states.values()
        )

        return {
            "building_id": self.building_id,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "room_count": len(self.rooms),
            "total_occupancy": total_occupancy,
            "average_indoor_temperature_c": (
                average_temperature
            ),
            "total_energy_draw_kw": (
                total_energy_kw
            ),
            "rooms": {
                room_id: {
                    "temperature_c": (
                        state.indoor_temp_c
                    ),
                    "humidity_pct": (
                        state.indoor_rh_pct
                    ),
                    "co2_ppm": (
                        state.co2_ppm
                    ),
                    "occupancy": (
                        state.occupancy_count
                    ),
                    "energy_draw_kw": (
                        state.energy_draw_kw
                    ),
                }
                for room_id, state
                in states.items()
            },
        }