import numpy as np
from rl.reward import calculate_pmv
from rl.train import make_environment

def test_pmv_stays_finite_outside_model_range():
    pmv_hot = calculate_pmv(
        indoor_temp_c=35.0,
        indoor_rh_pct=60.0,
    )

    pmv_cold = calculate_pmv(
        indoor_temp_c=5.0,
        indoor_rh_pct=60.0,
    )

    assert np.isfinite(pmv_hot)
    assert np.isfinite(pmv_cold)
    
def test_ppo_data_is_finite():
    env = make_environment()

    try:
        obs, _ = env.reset()

        for step in range(24):
            action = step % 5

            obs, reward, terminated, truncated, info = env.step(action)

            print(
                f"step={step + 1:02d} "
                f"action={action} "
                f"temp={env.twin.indoor_temp_c:.2f} "
                f"pmv={info['pmv']:.3f} "
                f"reward={reward:.3f}"
            )

            assert np.all(np.isfinite(obs)), (
                f"Observation contains NaN/Inf at step {step + 1}: {obs}"
            )

            assert np.isfinite(reward), (
                f"Reward is NaN/Inf at step {step + 1}: {reward}"
            )

            assert np.isfinite(info["pmv"]), (
                f"PMV is NaN/Inf at step {step + 1}: {info['pmv']}"
            )

    finally:
        env.close()