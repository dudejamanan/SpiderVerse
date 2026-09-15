from __future__ import annotations

from rl.reward import calculate_pmv
from twin.room_twin import RoomTwin
from twin.baseline_schedule import get_baseline_setpoint

from rl.reward import calculate_pmv
from rl.hvac_controller import calculate_hvac_action


# WATTS_PER_DEGREE = 50.0
TIMESTEP_SECONDS = 3600.0


def get_evaluation_occupancy(hour: int) -> int:
    """
    Deterministic occupancy schedule used for RL-vs-baseline evaluation.

    Occupied:
        09:00 - 18:00 -> 4 people

    Unoccupied:
        all other hours -> 0 people
    """
    if 9 <= hour < 18:
        return 4

    return 0


def evaluate_baseline():
    twin = RoomTwin(
        zone_id="room_b",
        region_id="chennai",
        initial_temp_c=26.0,
        start_hour=8,
    )

    total_energy_kwh = 0.0
    total_abs_pmv = 0.0

    print("=" * 100)
    print("BASELINE HVAC EVALUATION")
    print("=" * 100)
    print(
        f"{'Hr':>3} "
        f"{'Occup.':>7} "
        f"{'Setpoint':>10} "
        f"{'Temp':>9} "
        f"{'PMV':>8} "
        f"{'HVAC W':>9} "
        f"{'Energy kWh':>11}"
    )
    print("-" * 100)

    for hour in range(24):
        state_before = twin.get_state()

        current_hour = int(state_before.timestamp.hour)

        occupancy = get_evaluation_occupancy(current_hour)

        baseline_setpoint = float(
            get_baseline_setpoint(
                hour=current_hour,
                occupancy_count=occupancy,
            )
        )

        current_setpoint = float(twin.current_setpoint_c)

        hvac_action_w = calculate_hvac_action(
            indoor_temp_c=float(state_before.indoor_temp_c),
            target_setpoint_c=baseline_setpoint,
        )

        twin.current_setpoint_c = baseline_setpoint

        state = twin.step(
            dt=TIMESTEP_SECONDS,
            hvac_action=hvac_action_w,
            occupancy_count=occupancy,
        )

        energy_draw_kw = float(state.energy_draw_kw)

        # One simulation step = one hour.
        energy_kwh = energy_draw_kw

        pmv = calculate_pmv(
            indoor_temp_c=float(state.indoor_temp_c),
            indoor_rh_pct=float(state.indoor_rh_pct),
        )

        total_energy_kwh += energy_kwh
        total_abs_pmv += abs(pmv)

        print(
            f"{hour + 1:3d} "
            f"{occupancy:7d} "
            f"{baseline_setpoint:10.2f} "
            f"{state.indoor_temp_c:9.2f} "
            f"{pmv:8.3f} "
            f"{hvac_action_w:9.1f} "
            f"{energy_kwh:11.3f}"
        )

    average_abs_pmv = total_abs_pmv / 24.0

    print("-" * 100)
    print(f"Total baseline energy: {total_energy_kwh:.3f} kWh")
    print(f"Average |PMV|:         {average_abs_pmv:.3f}")
    print("=" * 100)


if __name__ == "__main__":
    evaluate_baseline()