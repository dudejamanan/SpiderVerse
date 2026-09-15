from __future__ import annotations

from stable_baselines3 import PPO

from rl.train import make_environment


MODEL_PATH = (
    "rl/models/hvac_policy"
)


def evaluate() -> None:

    env = make_environment()

    model = PPO.load(
        MODEL_PATH
    )

    obs, reset_info = env.reset(
        seed=42
    )

    total_reward = 0.0
    total_energy_kwh = 0.0
    total_abs_pmv = 0.0

    steps = 0

    print(
        "=" * 100
    )

    print(
        "RL POLICY EVALUATION"
    )

    print(
        "=" * 100
    )

    print(
        f"Initial temperature: "
        f"{reset_info['initial_temp_c']:.2f}°C"
    )

    print(
        f"Start hour: "
        f"{reset_info['start_hour']:02d}:00"
    )

    print(
        f"Constraint: "
        f"{reset_info['constraint']['intensity']}"
    )

    print()

    print(
        f"{'Hr':>3} "
        f"{'Action':>6} "
        f"{'Setpoint':>10} "
        f"{'Temp':>8} "
        f"{'PMV':>8} "
        f"{'HVAC W':>9} "
        f"{'Energy kWh':>11} "
        f"{'Reward':>9}"
    )

    print(
        "-" * 100
    )

    for _ in range(24):

        action, _ = model.predict(
            obs,
            deterministic=True,
        )

        action = int(action)

        (
            obs,
            reward,
            terminated,
            truncated,
            info,
        ) = env.step(action)

        hvac_power_w = float(
            info["hvac_power_w"]
        )

        pmv = float(
            info["pmv"]
        )

        energy_draw_kw = float(
            info.get(
                "energy_draw_kw",
                0.0,
            )
        )

        # One environment step =
        # one simulated hour.
        energy_kwh = (
            energy_draw_kw
            * (
                env.TIMESTEP_SECONDS
                / 3600.0
            )
        )

        total_reward += float(
            reward
        )

        total_energy_kwh += (
            energy_kwh
        )

        total_abs_pmv += abs(
            pmv
        )

        steps += 1

        simulated_time = (
            info.get(
                "simulated_time"
            )
        )

        if simulated_time is not None:
            hour_label = (
                simulated_time.hour
            )
        else:
            hour_label = (
                steps - 1
            )

        print(
            f"{hour_label:3d} "
            f"{action:6d} "
            f"{info['new_setpoint_c']:10.2f} "
            f"{env.twin.indoor_temp_c:8.2f} "
            f"{pmv:8.3f} "
            f"{hvac_power_w:9.1f} "
            f"{energy_kwh:11.3f} "
            f"{reward:9.3f}"
        )

        if terminated or truncated:
            break

    average_abs_pmv = (
        total_abs_pmv / steps
        if steps
        else 0.0
    )

    print(
        "-" * 100
    )

    print(
        f"Total reward:       "
        f"{total_reward:.3f}"
    )

    print(
        f"Total HVAC energy:  "
        f"{total_energy_kwh:.3f} kWh"
    )

    print(
        f"Average |PMV|:      "
        f"{average_abs_pmv:.3f}"
    )

    print(
        "=" * 100
    )

    env.close()


if __name__ == "__main__":
    evaluate()