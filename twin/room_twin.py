"""
Room-level Digital Twin.

Person 01 owns this module.
"""

from datetime import datetime, timezone

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
        latitude: float,
        longitude: float,
        initial_temp_c: float = 24.0,
    ):
        self.zone_id = zone_id

        self.latitude = latitude
        self.longitude = longitude

        self.thermal_params = ThermalParameters(
            R=R,
            C=C,
            window_area_m2=window_area,
        )

        self.indoor_temp_c = initial_temp_c

        # Temporary values for the temperature-only model.
        # These will be replaced by the weather client later.
        self.outdoor_temp_c = 35.0
        self.solar_radiation_w_m2 = 0.0

        self.occupancy_count = 0
        self.hvac_action_w = 0.0

        self.energy_draw_kw = 0.0
        self.current_setpoint_c = 24.0

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

        # Simple energy representation for the current prototype.
        self.energy_draw_kw = abs(hvac_action) / 1000.0

        return self.get_state()

    def get_state(self) -> dict:
        """
        Return the current state of the room.
        """

        return {
            "zone_id": self.zone_id,
            "indoor_temp_c": self.indoor_temp_c,
            "indoor_rh_pct": 50.0,
            "co2_ppm": 420.0,
            "outdoor_temp_c": self.outdoor_temp_c,
            "outdoor_rh_pct": 50.0,
            "occupancy_count": self.occupancy_count,
            "current_setpoint_c": self.current_setpoint_c,
            "energy_draw_kw": self.energy_draw_kw,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }