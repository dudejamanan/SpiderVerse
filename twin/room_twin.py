from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from .baseline_schedule import get_baseline_setpoint
from .building_config import RoomConfig
from .regions import get_region
from .thermal_model import (
    calculate_next_temperature,
    calculate_occupancy_heat_gain,
    calculate_solar_heat_gain,
)

from contracts import TwinState



class RoomTwin:
    """
    Customizable physics-based digital twin for one HVAC zone.

    The room can be created either using a complete RoomConfig:

        RoomTwin(
            config=RoomConfig(...),
            latitude=25.2048,
            longitude=55.2708,
        )

    or using the legacy/test interface:

        RoomTwin(
            zone_id="room_a",
            region_id="chennai",
        )

    The thermal physics itself remains in thermal_model.py.
    """

    DEFAULT_INDOOR_TEMP_C = 24.0
    DEFAULT_INDOOR_RH_PCT = 50.0
    DEFAULT_CO2_PPM = 420.0

    DEFAULT_OUTDOOR_TEMP_C = 30.0
    DEFAULT_OUTDOOR_RH_PCT = 70.0
    DEFAULT_SOLAR_RADIATION_W_M2 = 0.0

    DEFAULT_SETPOINT_C = 24.0

    CO2_OUTDOOR_PPM = 400.0

    # Approximate CO2 generation per person.
    CO2_GENERATION_PPM_PER_PERSON_STEP = 10.0

    def __init__(
        self,
        zone_id: Optional[str] = None,
        region_id: Optional[str] = None,
        *,
        config: Optional[RoomConfig] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        initial_temp_c: Optional[float] = None,
        initial_rh_pct: Optional[float] = None,
        initial_co2_ppm: Optional[float] = None,
        initial_occupancy: Optional[int] = None,
        start_hour: int = 12,
    ):
        # ---------------------------------------------------------
        # CONFIGURATION
        # ---------------------------------------------------------

        if config is not None:
            self.config = config

            self.zone_id = config.room_id

            if latitude is None:
                latitude = 0.0

            if longitude is None:
                longitude = 0.0

        else:
            if zone_id is None:
                raise ValueError(
                    "Either config or zone_id must be provided."
                )

            self.zone_id = zone_id

            # Preserve the old room_a / room_b configuration API.
            #
            # Import lazily so this remains compatible with the
            # customizable BuildingConfig implementation.
            try:
                from .zone_config import get_zone_config

                old_config = get_zone_config(zone_id)

                self.config = RoomConfig(
                    room_id=old_config.zone_id,
                    area_m2=(
                        old_config.volume_m3
                        / 3.0
                    ),
                    height_m=3.0,
                    window_area_m2=(
                        old_config.window_area_m2
                    ),
                    R=old_config.R,
                    C=old_config.C,
                    shading_coefficient=(
                        old_config.shading_coefficient
                    ),
                    ventilation_ach=(
                        old_config.ventilation_ach
                    ),
                    hvac_capacity_w=(
                        old_config.cop * 0.0
                        + 2000.0
                    ),
                    cop=old_config.cop,
                )

            except ImportError:
                raise ValueError(
                    "No RoomConfig supplied and legacy "
                    "zone configuration is unavailable."
                )

            if region_id is not None:
                region = get_region(region_id)

                latitude = region.latitude
                longitude = region.longitude

            else:
                latitude = 0.0
                longitude = 0.0

        self.latitude = float(latitude)
        self.longitude = float(longitude)

        # ---------------------------------------------------------
        # INITIAL CONDITIONS
        # ---------------------------------------------------------

        self.initial_temp_c = (
            float(initial_temp_c)
            if initial_temp_c is not None
            else float(
                getattr(
                    self.config,
                    "initial_temp_c",
                    self.DEFAULT_INDOOR_TEMP_C,
                )
            )
        )

        self.initial_indoor_rh_pct = (
            float(initial_rh_pct)
            if initial_rh_pct is not None
            else float(
                getattr(
                    self.config,
                    "initial_rh_pct",
                    self.DEFAULT_INDOOR_RH_PCT,
                )
            )
        )

        self.initial_co2_ppm = (
            float(initial_co2_ppm)
            if initial_co2_ppm is not None
            else float(
                getattr(
                    self.config,
                    "initial_co2_ppm",
                    self.DEFAULT_CO2_PPM,
                )
            )
        )

        self.initial_occupancy = (
            int(initial_occupancy)
            if initial_occupancy is not None
            else int(
                getattr(
                    self.config,
                    "initial_occupancy",
                    0,
                )
            )
        )

        self.initial_setpoint_c = float(
            getattr(
                self.config,
                "initial_setpoint_c",
                self.DEFAULT_SETPOINT_C,
            )
        )

        # ---------------------------------------------------------
        # SIMULATION CLOCK
        # ---------------------------------------------------------

        self.start_hour = int(start_hour) % 24

        self.simulation_time = datetime(
            2026,
            1,
            1,
            self.start_hour,
            0,
            tzinfo=timezone.utc,
        )

        # ---------------------------------------------------------
        # WEATHER
        # ---------------------------------------------------------

        self.outdoor_temp_c = (
            self.DEFAULT_OUTDOOR_TEMP_C
        )

        self.outdoor_rh_pct = (
            self.DEFAULT_OUTDOOR_RH_PCT
        )

        self.solar_radiation_w_m2 = (
            self.DEFAULT_SOLAR_RADIATION_W_M2
        )

        # ---------------------------------------------------------
        # DYNAMIC STATE
        # ---------------------------------------------------------

        self.indoor_temp_c = (
            self.initial_temp_c
        )

        self.indoor_rh_pct = (
            self.initial_indoor_rh_pct
        )

        self.co2_ppm = (
            self.initial_co2_ppm
        )

        self.occupancy_count = (
            self.initial_occupancy
        )

        self.current_setpoint_c = (
            self.initial_setpoint_c
        )

        self.energy_draw_kw = 0.0

    # =============================================================
    # WEATHER
    # =============================================================

    def set_weather(
        self,
        outdoor_temp_c: float,
        outdoor_rh_pct: float,
        solar_radiation_w_m2: float = 0.0,
    ) -> None:
        """
        Manually provide outdoor environmental conditions.

        This is the main interface for externally supplied
        weather/API data.
        """

        self.outdoor_temp_c = float(
            outdoor_temp_c
        )

        self.outdoor_rh_pct = float(
            outdoor_rh_pct
        )

        self.solar_radiation_w_m2 = float(
            solar_radiation_w_m2
        )

    def update_weather(self) -> None:
        """
        Update weather.

        Currently this provides a deterministic simulation
        fallback. An external weather API can later replace
        this method without changing the thermal model.
        """

        # Deterministic daily temperature profile.
        hour = self.simulation_time.hour

        if 6 <= hour < 12:
            outdoor_temp = 28.0 + (
                (hour - 6) * 0.4
            )

        elif 12 <= hour < 16:
            outdoor_temp = 30.0

        elif 16 <= hour < 21:
            outdoor_temp = 29.0

        else:
            outdoor_temp = 26.0

        self.outdoor_temp_c = outdoor_temp

        # Simple deterministic RH profile.
        self.outdoor_rh_pct = (
            85.0
            if hour < 7 or hour >= 20
            else 70.0
        )

        # Approximate solar radiation.
        if 6 <= hour < 18:
            self.solar_radiation_w_m2 = 500.0
        else:
            self.solar_radiation_w_m2 = 0.0

    # =============================================================
    # OCCUPANCY / HUMAN CONDITIONS
    # =============================================================

    def set_occupancy(
        self,
        occupancy_count: int,
    ) -> None:
        """Set the number of occupants in the room."""

        if occupancy_count < 0:
            raise ValueError(
                "occupancy_count cannot be negative."
            )

        self.occupancy_count = int(
            occupancy_count
        )

    # =============================================================
    # SETPOINT
    # =============================================================

    def set_setpoint(
        self,
        setpoint_c: float,
    ) -> None:
        """Set the desired HVAC temperature."""

        self.current_setpoint_c = float(
            max(
                17.0,
                min(
                    29.0,
                    setpoint_c,
                ),
            )
        )

    # =============================================================
    # BASELINE
    # =============================================================

    def apply_baseline_schedule(
        self,
        hour: int | None = None,
        occupancy_count: int | None = None,
    ) -> float:
        """
        Apply and return the baseline HVAC setpoint.

        Supports both:
            apply_baseline_schedule()
            apply_baseline_schedule(hour, occupancy_count)
        """

        if hour is None:
            hour = self.simulation_time.hour

        if occupancy_count is None:
            occupancy_count = self.occupancy_count

        setpoint = get_baseline_setpoint(
            hour=int(hour),
            occupancy_count=int(occupancy_count),
        )

        self.current_setpoint_c = setpoint

        return setpoint

    # =============================================================
    # RESET
    # =============================================================

    def reset(self) -> TwinState:
        """
        Reset the room to its configured initial state.
        """

        self.indoor_temp_c = (
            self.initial_temp_c
        )

        self.indoor_rh_pct = (
            self.initial_indoor_rh_pct
        )

        self.co2_ppm = (
            self.initial_co2_ppm
        )

        self.occupancy_count = (
            self.initial_occupancy
        )

        self.current_setpoint_c = (
            self.initial_setpoint_c
        )

        self.energy_draw_kw = 0.0

        self.simulation_time = datetime(
            2026,
            1,
            1,
            self.start_hour,
            0,
            tzinfo=timezone.utc,
        )

        return self.get_state()

    # =============================================================
    # THERMAL STEP
    # =============================================================

    def step(
        self,
        dt: float,
        hvac_action: float,
        occupancy_count: Optional[int] = None,
    ) -> TwinState:
        """
        Advance the digital twin by one timestep.

        Parameters
        ----------
        dt:
            Simulation timestep in seconds.

        hvac_action:
            HVAC thermal power in watts.

            Negative -> cooling
            Positive -> heating

        occupancy_count:
            Optional occupancy override.
        """

        if dt <= 0:
            raise ValueError(
                "dt must be greater than zero."
            )

        if occupancy_count is not None:
            self.set_occupancy(
                occupancy_count
            )

        # ---------------------------------------------------------
        # HVAC CAPACITY LIMIT
        # ---------------------------------------------------------

        hvac_capacity_w = float(
            getattr(
                self.config,
                "hvac_capacity_w",
                2000.0,
            )
        )

        hvac_action = max(
            -hvac_capacity_w,
            min(
                hvac_capacity_w,
                float(hvac_action),
            ),
        )

        # ---------------------------------------------------------
        # SOLAR HEAT
        # ---------------------------------------------------------

        q_solar = calculate_solar_heat_gain(
            solar_radiation_w_m2=(
                self.solar_radiation_w_m2
            ),
            window_area_m2=(
                self.config.window_area_m2
            ),
            shading_coefficient=(
                self.config.shading_coefficient
            ),
        )

        # ---------------------------------------------------------
        # OCCUPANCY HEAT
        # ---------------------------------------------------------

        q_occupancy = (
            calculate_occupancy_heat_gain(
                occupancy_count=(
                    self.occupancy_count
                )
            )
        )

        # ---------------------------------------------------------
        # THERMAL MODEL
        # ---------------------------------------------------------

        self.indoor_temp_c = (
            calculate_next_temperature(
                indoor_temp_c=(
                    self.indoor_temp_c
                ),
                outdoor_temp_c=(
                    self.outdoor_temp_c
                ),
                R=self.config.R,
                C=self.config.C,
                dt=dt,
                q_solar_w=q_solar,
                q_occupancy_w=q_occupancy,
                q_hvac_w=hvac_action,
            )
        )

        # ---------------------------------------------------------
        # HUMIDITY
        # ---------------------------------------------------------

        # Simple humidity response toward outdoor RH.
        #
        # Cooling/dehumidification lowers indoor RH.
        humidity_mix_rate = min(
            1.0,
            dt / 3600.0
            * self.config.ventilation_ach,
        )

        self.indoor_rh_pct += (
            (
                self.outdoor_rh_pct
                - self.indoor_rh_pct
            )
            * humidity_mix_rate
        )

        if hvac_action < 0:
            dehumidification = (
                abs(hvac_action)
                / max(
                    1.0,
                    hvac_capacity_w,
                )
            ) * 5.0 * (
                dt / 3600.0
            )

            self.indoor_rh_pct -= (
                dehumidification
            )

        self.indoor_rh_pct = max(
            0.0,
            min(
                100.0,
                self.indoor_rh_pct,
            ),
        )

        # ---------------------------------------------------------
        # CO2
        # ---------------------------------------------------------

        ventilation_rate = (
            self.config.ventilation_ach
            * self.config.volume_m3
            / 3600.0
        )

        co2_generation = (
            self.occupancy_count
            * 20.0
            * dt
        )

        co2_removal = (
            ventilation_rate
            * (
                self.co2_ppm
                - self.CO2_OUTDOOR_PPM
            )
            * dt
        )

        room_volume = max(
            1.0,
            self.config.volume_m3,
        )

        self.co2_ppm += (
            (
                co2_generation
                - co2_removal
            )
            / room_volume
        )

        self.co2_ppm = max(
            self.CO2_OUTDOOR_PPM,
            self.co2_ppm,
        )

        # ---------------------------------------------------------
        # ENERGY
        # ---------------------------------------------------------

        # Electrical power = thermal HVAC power / COP.
        thermal_power_w = abs(
            hvac_action
        )

        cop = max(
            1.0,
            float(
                getattr(
                    self.config,
                    "cop",
                    3.5,
                )
            ),
        )

        self.energy_draw_kw = (
            thermal_power_w
            / cop
            / 1000.0
        )

        # ---------------------------------------------------------
        # SIMULATION CLOCK
        # ---------------------------------------------------------

        self.simulation_time += (
            timedelta(
                seconds=dt
            )
        )

        return self.get_state()

    # =============================================================
    # MULTI-STEP SIMULATION
    # =============================================================

    def simulate(
        self,
        steps: int,
        dt: float,
        hvac_action: float = 0.0,
        occupancy_count: Optional[int] = None,
        update_weather: bool = False,
    ) -> list[TwinState]:
        """
        Run multiple simulation steps.

        Returns one TwinState per timestep.
        """

        if steps < 1:
            raise ValueError(
                "steps must be at least 1."
            )

        states: list[TwinState] = []

        for _ in range(steps):

            if update_weather:
                self.update_weather()

            state = self.step(
                dt=dt,
                hvac_action=hvac_action,
                occupancy_count=occupancy_count,
            )

            states.append(state)

        return states

    # =============================================================
    # STATE
    # =============================================================

    def get_state(self) -> TwinState:
        """Return the current digital-twin state."""

        return TwinState(
            zone_id=self.zone_id,

            indoor_temp_c=(
                self.indoor_temp_c
            ),

            indoor_rh_pct=(
                self.indoor_rh_pct
            ),

            co2_ppm=self.co2_ppm,

            outdoor_temp_c=(
                self.outdoor_temp_c
            ),

            outdoor_rh_pct=(
                self.outdoor_rh_pct
            ),

            occupancy_count=(
                self.occupancy_count
            ),

            current_setpoint_c=(
                self.current_setpoint_c
            ),

            energy_draw_kw=(
                self.energy_draw_kw
            ),

            timestamp=self.simulation_time,
        )