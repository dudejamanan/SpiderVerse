from rl.train import make_environment


def test_24_hour_episode_stays_stable():
    env = make_environment()

    try:
        obs, info = env.reset()

        for step in range(24):
            action = step % 5
            obs, reward, terminated, truncated, info = env.step(action)

            temp = env.twin.indoor_temp_c

            print(
                f"hour={step + 1:02d}, "
                f"temp={temp:.2f}°C, "
                f"reward={reward:.3f}, "
                f"pmv={info['pmv']:.3f}"
            )

            assert 10.0 <= temp <= 40.0
            assert reward == reward  # catches NaN

            if terminated or truncated:
                break

    finally:
        env.close()
