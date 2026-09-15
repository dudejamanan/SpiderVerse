"""
Static HVAC baseline schedule.

Person 01: Twin Engineer
"""


def get_baseline_setpoint(
    hour: int,
    occupancy_count: int,
) -> float:
    """
    Return the HVAC setpoint for the static baseline schedule.

    Occupied hours:
        09:00 - 18:00 -> 24°C

    Unoccupied hours:
        -> 28°C
    """

    occupied_hours = 9 <= hour < 18

    if occupied_hours and occupancy_count > 0:
        return 24.0

    return 28.0