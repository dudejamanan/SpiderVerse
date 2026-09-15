from __future__ import annotations

import numpy as np
from stable_baselines3 import PPO

from rl.train import make_environment


MODEL_PATH = "rl/models/hvac_policy"


def main() -> None:
    model = PPO.load(MODEL_PATH)
    env = make_environment()

    energies = []
    pmvs = []

    print("=" * 70)
    print("RUNNING 10 RL EVALUATION EPISODES")
    print("=" * 70)

    for episode in range(10):

        obs, reset_info = env.reset(
            seed=100 + episode
        )

        energy_kwh = 0.0
        total_abs_pmv = 0.0
        steps = 0

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

            energy_kwh += float(
                info.get(
                    "energy_draw_kwh",
                    0.0,
                )
            )

            total_abs_pmv += abs(
                float(info["pmv"])
            )

            steps += 1

            if terminated or truncated:
                break

        average_abs_pmv = (
            total_abs_pmv / steps
            if steps
            else 0.0
        )

        energies.append(energy_kwh)
        pmvs.append(average_abs_pmv)

        print(
            f"Episode {episode + 1:2d}: "
            f"energy={energy_kwh:.3f} kWh, "
            f"avg_abs_pmv={average_abs_pmv:.3f}, "
            f"start_temp={reset_info['initial_temp_c']:.2f} C, "
            f"start_hour={reset_info['start_hour']:02d}:00"
        )

    print("-" * 70)

    print(
        f"Average energy:   "
        f"{np.mean(energies):.3f} kWh"
    )

    print(
        f"Average abs PMV:  "
        f"{np.mean(pmvs):.3f}"
    )

    print(
        f"Minimum energy:   "
        f"{np.min(energies):.3f} kWh"
    )

    print(
        f"Maximum energy:   "
        f"{np.max(energies):.3f} kWh"
    )

    print(
        f"Minimum abs PMV:  "
        f"{np.min(pmvs):.3f}"
    )

    print(
        f"Maximum abs PMV:  "
        f"{np.max(pmvs):.3f}"
    )

    print("=" * 70)

    env.close()


if __name__ == "__main__":
    main()