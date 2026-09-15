# rl/agent.py

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from stable_baselines3 import PPO

from contracts import RLAction

from .observation import state_to_observation


class HVACAgent:
    """
    Inference wrapper around the trained PPO HVAC policy.

    Input:
        TwinState-like dictionary/object

    Output:
        RLAction-compatible dictionary
    """

    ACTION_DELTAS = np.array(
        [-1.0, -0.5, 0.0, 0.5, 1.0],
        dtype=np.float32,
    )

    MIN_SETPOINT_C = 17.0
    MAX_SETPOINT_C = 29.0

    def __init__(
        self,
        model_path: str | Path,
    ):
        """
        Load a trained PPO model.

        Parameters
        ----------
        model_path:
            Path to the trained Stable-Baselines3
            PPO model.
        """

        self.model_path = Path(model_path)

        if not self.model_path.exists():
            raise FileNotFoundError(
                f"RL model not found: {self.model_path}"
            )

        self.model = PPO.load(
            str(self.model_path)
        )

    @staticmethod
    def _get_state_value(
        state: Any,
        key: str,
        default: Any = None,
    ) -> Any:
        """
        Read a value from either a dictionary
        or an object/dataclass/Pydantic model.
        """

        if isinstance(state, dict):
            return state.get(key, default)

        return getattr(
            state,
            key,
            default,
        )

    @classmethod
    def _decode_action(
        cls,
        action: int,
    ) -> float:
        """
        Convert PPO's discrete action into
        a setpoint delta in Celsius.
        """

        action = int(action)

        if action < 0 or action >= len(
            cls.ACTION_DELTAS
        ):
            raise ValueError(
                f"Invalid PPO action: {action}"
            )

        return float(
            cls.ACTION_DELTAS[action]
        )

    @classmethod
    def _apply_setpoint_bounds(
        cls,
        current_setpoint: float,
        requested_delta: float,
    ) -> tuple[float, float]:
        """
        Apply the 17-29 C safety bounds.

        Returns:
            actual_delta, new_setpoint
        """

        new_setpoint = float(
            np.clip(
                current_setpoint
                + requested_delta,
                cls.MIN_SETPOINT_C,
                cls.MAX_SETPOINT_C,
            )
        )

        actual_delta = (
            new_setpoint
            - current_setpoint
        )

        return (
            float(actual_delta),
            new_setpoint,
        )

    def predict(
        self,
        state: Any,
        constraint: dict | None = None,
    ) -> dict:
        """
        Predict the next HVAC setpoint action.

        Parameters
        ----------
        state:
            TwinState object or dictionary.

        constraint:
            Human comfort constraint.

        Returns
        -------
        dict
            RLAction-compatible action.
        """

        # ----------------------------------------------
        # 1. Convert TwinState into RL observation
        # ----------------------------------------------

        observation = state_to_observation(
            state,
            constraint,
        )

        # ----------------------------------------------
        # 2. Ask PPO for an action
        # ----------------------------------------------

        action, _ = self.model.predict(
            observation,
            deterministic=True,
        )

        # ----------------------------------------------
        # 3. Convert discrete action into Celsius
        # ----------------------------------------------

        requested_delta = (
            self._decode_action(action)
        )

        # ----------------------------------------------
        # 4. Read current setpoint
        # ----------------------------------------------

        current_setpoint = float(
            self._get_state_value(
                state,
                "current_setpoint_c",
                24.0,
            )
        )

        # ----------------------------------------------
        # 5. Enforce 17-29 C safety range
        # ----------------------------------------------

        actual_delta, new_setpoint = (
            self._apply_setpoint_bounds(
                current_setpoint,
                requested_delta,
            )
        )

        # ----------------------------------------------
        # 6. Create shared RL action contract
        # ----------------------------------------------

        result = RLAction(
            zone_id=str(
                self._get_state_value(
                    state,
                    "zone_id",
                )
            ),
            setpoint_delta_c=actual_delta,
            new_setpoint_c=new_setpoint,
        )

        # Return a dictionary because the rest
        # of the system uses JSON-like action data.
        return result.model_dump()