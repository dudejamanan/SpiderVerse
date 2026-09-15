"""
Room-level Digital Twin.

Person 01 owns this module.
"""

from datetime import datetime, timezone

from twin.weather_client import get_current_weather

from twin.baseline_schedule import get_baseline_setpoint

from twin.regions import get_region

from contracts import TwinState

from twin.thermal_model import (
    ThermalParameters,
    calculate_next_temperature,
    calculate_occupancy_heat_gain,
    calculate_solar_heat_gain,
)


class RoomTwin:
    """
    Digital twin representing one simulated room.

    The current version focuses on the temperature RC model.
    Humidity, CO2, weather API, and baseline control will be
    added in the following steps.
    """

    def __init__(
        self,
        zone_id: str,
        R: float,
        C: float,
        window_area: float,
        region_id: str,
        initial_temp_c: float = 24.0,
    ):
        self.zone_id = zone_id

        region = get_region(region_id)

        self.region_id = region_id
        self.latitude = region.latitude
        self.longitude = region.longitude

        self.thermal_params = ThermalParameters(
            R=R,
            C=C,
            window_area_m2=window_area,
        )

        self.indoor_temp_c = initial_temp_c

        # Temporary values for the temperature-only model.
        # These will be replaced by the weather client later.
        self.outdoor_temp_c = 35.0
        self.outdoor_rh_pct = 50.0
        self.solar_radiation_w_m2 = 0.0

        self.occupancy_count = 0    
        self.indoor_rh_pct = 50.0
        self.co2_ppm = 420.0    
        self.hvac_action_w = 0.0

        self.energy_draw_kw = 0.0
        self.current_setpoint_c = 24.0

    def apply_baseline_schedule(
        self,
        hour: int,
        occupancy_count: int,
    ) -> float:
        """
        Apply the static baseline schedule and return its setpoint.
        """

        self.current_setpoint_c = get_baseline_setpoint(
            hour=hour,
            occupancy_count=occupancy_count,
        )

        return self.current_setpoint_c

    def update_weather(self) -> None:
        """
        Update the twin's outdoor conditions using Open-Meteo.
        """

        weather = get_current_weather(
            latitude=self.latitude,
            longitude=self.longitude,
        )

        self.outdoor_temp_c = weather["outdoor_temp_c"]
        self.outdoor_rh_pct = weather["outdoor_rh_pct"]
        self.solar_radiation_w_m2 = weather["solar_radiation_w_m2"]

    def set_weather(
        self,
        outdoor_temp_c: float,
        outdoor_rh_pct: float,
        solar_radiation_w_m2: float,
    ) -> None:
        """
        Set weather conditions directly.

        Useful for deterministic simulations and tests.
        """

        self.outdoor_temp_c = outdoor_temp_c
        self.outdoor_rh_pct = outdoor_rh_pct
        self.solar_radiation_w_m2 = solar_radiation_w_m2


    def step(
        self,
        dt: float,
        hvac_action: float,
        occupancy_count: int,
    ) -> dict:
        """
        Advance the digital twin by one timestep.

        Parameters
        ----------
        dt:
            Simulation timestep.
        hvac_action:
            HVAC thermal power in watts.
            Negative = cooling.
            Positive = heating.
        occupancy_count:
            Number of people in the room.
        """

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

        self.update_humidity()
        self.update_co2(dt)

        # Simple energy representation for the current prototype.
        self.energy_draw_kw = abs(hvac_action) / 1000.0

        return self.get_state()


    def update_humidity(self) -> None:
        """
        Simple indoor humidity response toward outdoor humidity.
        """

        humidity_difference = (
            self.outdoor_rh_pct - self.indoor_rh_pct
        )

        self.indoor_rh_pct += 0.05 * humidity_difference

        self.indoor_rh_pct = max(
            20.0,
            min(80.0, self.indoor_rh_pct),
        )

    def update_co2(self, dt: float) -> None:
        """
        Update indoor CO2 based on occupancy and ventilation.

        Occupants add CO2 while ventilation removes some CO2.
        """

        co2_generation = self.occupancy_count * 20.0

        ventilation_decay = (
            self.co2_ppm - 420.0
        ) * 0.02

        self.co2_ppm += (
            co2_generation - ventilation_decay
        ) * dt

        self.co2_ppm = max(420.0, self.co2_ppm)


    def simulate(
        self,
        steps: int,
        dt: float,
        hvac_action: float,
        occupancy_count: int,
    ) -> list[TwinState]:
        """
        Run the twin for a number of timesteps.

        Returns the state after every timestep.
        """

        states = []

        for _ in range(steps):
            state = self.step(
                dt=dt,
                hvac_action=hvac_action,
                occupancy_count=occupancy_count,
            )

            states.append(state)

        return states

    def get_state(self) -> TwinState:
        """
        Return the current state of the room.
        """

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
        