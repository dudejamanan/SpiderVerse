"""
Room-level Digital Twin.

Person 01: Twin Engineer
"""

from datetime import datetime, timezone

from contracts import TwinState

from twin.baseline_schedule import get_baseline_setpoint
from twin.regions import get_region
from twin.thermal_model import (
    ThermalParameters,
    calculate_next_temperature,
    calculate_occupancy_heat_gain,
    calculate_solar_heat_gain,
)
from twin.weather_client import get_current_weather
from twin.zone_config import get_zone_config


class RoomTwin:
    """
    Digital twin representing one HVAC zone.

    The twin combines:
    - RC thermal dynamics
    - solar heat gain
    - occupancy heat gain
    - HVAC thermal power
    - indoor humidity dynamics
    - indoor CO2 dynamics
    - real outdoor weather
    - baseline HVAC scheduling
    """

    def __init__(
        self,
        zone_id: str,
        region_id: str,
        initial_temp_c: float = 24.0,
    ):
        self.zone_id = zone_id

        region = get_region(region_id)

        self.region_id = region_id
        self.latitude = region.latitude
        self.longitude = region.longitude

        zone_config = get_zone_config(zone_id)
        self.zone_config = zone_config

        self.thermal_params = ThermalParameters(
            R=zone_config.R,
            C=zone_config.C,
            window_area_m2=zone_config.window_area_m2,
            shading_coefficient=zone_config.shading_coefficient,
        )

        self.indoor_temp_c = initial_temp_c

        self.outdoor_temp_c = 35.0
        self.outdoor_rh_pct = 50.0
        self.solar_radiation_w_m2 = 0.0

        self.indoor_rh_pct = 50.0
        self.co2_ppm = 420.0

        self.occupancy_count = 0
        self.hvac_action_w = 0.0

        self.energy_draw_kw = 0.0
        self.current_setpoint_c = 24.0

    def apply_baseline_schedule(
        self,
        hour: int,
        occupancy_count: int,
    ) -> float:
        """Apply the static baseline schedule."""

        self.current_setpoint_c = get_baseline_setpoint(
            hour=hour,
            occupancy_count=occupancy_count,
        )

        return self.current_setpoint_c

    def update_weather(self) -> None:
        """Fetch and apply current outdoor weather."""

        weather = get_current_weather(
            latitude=self.latitude,
            longitude=self.longitude,
        )

        self.set_weather(
            outdoor_temp_c=weather["outdoor_temp_c"],
            outdoor_rh_pct=weather["outdoor_rh_pct"],
            solar_radiation_w_m2=weather["solar_radiation_w_m2"],
        )

    def set_weather(
        self,
        outdoor_temp_c: float,
        outdoor_rh_pct: float,
        solar_radiation_w_m2: float,
    ) -> None:
        """Set weather directly for deterministic simulation/testing."""

        self.outdoor_temp_c = outdoor_temp_c
        self.outdoor_rh_pct = outdoor_rh_pct
        self.solar_radiation_w_m2 = solar_radiation_w_m2

    def step(
        self,
        dt: float,
        hvac_action: float,
        occupancy_count: int,
    ) -> TwinState:
        """
        Advance the digital twin by one timestep.

        hvac_action:
            Thermal HVAC power in watts.
            Negative = cooling.
            Positive = heating.
        """

        if dt <= 0:
            raise ValueError("dt must be greater than zero.")

        if occupancy_count < 0:
            raise ValueError("occupancy_count cannot be negative.")

        self.hvac_action_w = hvac_action
        self.occupancy_count = occupancy_count

        q_solar = calculate_solar_heat_gain(
            solar_radiation_w_m2=self.solar_radiation_w_m2,
            window_area_m2=self.thermal_params.window_area_m2,
            shading_coefficient=self.thermal_params.shading_coefficient,
        )

        q_occupancy = calculate_occupancy_heat_gain(
            occupancy_count=occupancy_count,
        )

        self.indoor_temp_c = calculate_next_temperature(
            indoor_temp_c=self.indoor_temp_c,
            outdoor_temp_c=self.outdoor_temp_c,
            R=self.thermal_params.R,
            C=self.thermal_params.C,
            dt=dt,
            q_solar_w=q_solar,
            q_occupancy_w=q_occupancy,
            q_hvac_w=hvac_action,
        )

        self.update_humidity(dt)
        self.update_co2(dt)

        # hvac_action represents thermal power.
        # Electrical power = thermal power / COP.
        self.energy_draw_kw = (
            abs(hvac_action)
            / self.zone_config.cop
            / 1000.0
        )

        return self.get_state()

    def update_humidity(self, dt: float) -> None:
        """
        Update indoor relative humidity using a simple
        ventilation/dehumidification response.

        Cooling introduces additional moisture removal.
        """

        ventilation_rate = (
            self.zone_config.ventilation_ach / 3600.0
        )

        humidity_exchange = (
            self.outdoor_rh_pct - self.indoor_rh_pct
        )

        self.indoor_rh_pct += (
            humidity_exchange
            * ventilation_rate
            * dt
        )

        # Cooling produces dehumidification.
        if self.hvac_action_w < 0:
            cooling_magnitude = abs(self.hvac_action_w)

            dehumidification = (
                cooling_magnitude
                / 10000.0
                * 0.5
                * dt
            )

            self.indoor_rh_pct -= dehumidification

        self.indoor_rh_pct = max(
            20.0,
            min(80.0, self.indoor_rh_pct),
        )

    def update_co2(self, dt: float) -> None:
        """
        Update indoor CO2 using a room-volume and ventilation model.
        """

        room_volume = self.zone_config.volume_m3

        ventilation_rate = (
            self.zone_config.ventilation_ach
            * room_volume
            / 3600.0
        )

        outdoor_co2_ppm = 420.0

        # Approximate CO2 generation by occupants.
        co2_generation_lps = (
            self.occupancy_count * 0.005
        )

        co2_generation_ppm_per_second = (
            co2_generation_lps
            / (room_volume * 1000.0)
            * 1_000_000.0
        )

        ventilation_removal = (
            self.co2_ppm - outdoor_co2_ppm
        ) * (
            ventilation_rate / room_volume
        )

        self.co2_ppm += (
            co2_generation_ppm_per_second
            - ventilation_removal
        ) * dt

        self.co2_ppm = max(
            outdoor_co2_ppm,
            self.co2_ppm,
        )

    def simulate(
        self,
        steps: int,
        dt: float,
        hvac_action: float,
        occupancy_count: int,
    ) -> list[TwinState]:
        """Run the twin for multiple timesteps."""

        if steps < 0:
            raise ValueError("steps cannot be negative.")

        states = []

        for _ in range(steps):
            states.append(
                self.step(
                    dt=dt,
                    hvac_action=hvac_action,
                    occupancy_count=occupancy_count,
                )
            )

        return states

    def get_state(self) -> TwinState:
        """Return the current digital-twin state."""

        return TwinState(
            zone_id=self.zone_id,
            indoor_temp_c=self.indoor_temp_c,
            indoor_rh_pct=self.indoor_rh_pct,
            co2_ppm=self.co2_ppm,
            outdoor_temp_c=self.outdoor_temp_c,
            outdoor_rh_pct=self.outdoor_rh_pct,
            occupancy_count=self.occupancy_count,
            current_setpoint_c=self.current_setpoint_c,
            energy_draw_kw=self.energy_draw_kw,
            timestamp=datetime.now(timezone.utc),
        )