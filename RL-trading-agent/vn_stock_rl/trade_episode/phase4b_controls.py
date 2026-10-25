"""Feature-blind controls matched to frozen PPO validation behavior."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np


class ValidationScheduleRandomPolicy:
    """Sample validation wait/hold pairs; never inspect market feature values."""

    def __init__(
        self,
        duration_pairs: Sequence[tuple[int, int]],
        *,
        seed: int,
        max_wait_steps: int,
        max_holding_intervals: int,
        max_episode_steps: int,
    ) -> None:
        pairs = np.asarray(duration_pairs, dtype=np.int64)
        if pairs.ndim != 2 or pairs.shape[1] != 2 or pairs.shape[0] == 0:
            raise ValueError("duration_pairs must contain at least one (wait, hold) pair")
        if (pairs[:, 0] < 0).any() or (pairs[:, 1] < 3).any():
            raise ValueError("waiting durations must be non-negative and holding durations >= 3")
        if max_wait_steps < 1 or max_holding_intervals < 3 or max_episode_steps < 1:
            raise ValueError("control horizons must support the minimum holding duration")
        self.duration_pairs = pairs.copy()
        self.max_wait_steps = int(max_wait_steps)
        self.max_holding_intervals = int(max_holding_intervals)
        self.max_episode_steps = int(max_episode_steps)
        self.rng = np.random.default_rng(seed)
        self.sampled_pairs: list[tuple[int, int]] = []
        self._episode_active = False
        self._target_wait = 0
        self._target_hold = 3

    def _begin_episode(self) -> None:
        pair_index = int(self.rng.integers(0, len(self.duration_pairs)))
        wait, hold = self.duration_pairs[pair_index]
        self._target_wait = int(np.clip(wait, 0, self.max_wait_steps - 1))
        self._target_hold = int(np.clip(hold, 3, self.max_holding_intervals))
        self.sampled_pairs.append((self._target_wait, self._target_hold))
        self._episode_active = True

    def predict(
        self,
        observation,
        *,
        action_masks,
        deterministic: bool = True,
        **kwargs: Any,
    ):
        del deterministic, kwargs
        obs = np.asarray(observation, dtype=np.float32).reshape(-1)
        masks = np.asarray(action_masks, dtype=bool).reshape(-1)
        if obs.size < 5 or masks.shape != (2,):
            raise ValueError("Expected position-state observation and two target-action masks")

        # The final five state fields are position, holding, unrealized return,
        # waiting, and episode duration. Episode-start time is not a feature.
        in_position = bool(obs[-5] >= 0.5)
        episode_step = int(round(float(obs[-1]) * self.max_episode_steps))
        if episode_step == 0 or not self._episode_active:
            self._begin_episode()

        if in_position:
            holding = int(round(float(obs[-4]) * self.max_holding_intervals))
            action = 0 if masks[0] and holding + 1 >= self._target_hold else 1
        else:
            waiting = int(round(float(obs[-2]) * self.max_wait_steps))
            action = 1 if waiting >= self._target_wait and masks[1] else 0
        if not masks[action]:
            raise RuntimeError("Randomized control selected a masked action")
        return np.asarray([action], dtype=np.int64), None


class MechanicalThreeDayPolicy:
    """Enter at the first opportunity and sell at the first legal minimum hold."""

    def predict(self, observation, *, action_masks, deterministic=True, **kwargs):
        del deterministic, kwargs
        obs = np.asarray(observation, dtype=np.float32).reshape(-1)
        in_position = bool(obs[-5] >= 0.5)
        action = 0 if in_position and action_masks[0] else 1 if not in_position else 1
        if not action_masks[action]:
            action = 0
        return np.asarray([action], dtype=np.int64), None


class BuyAndHoldPolicy:
    """Buy at the first legal next-open fill and hold through data end."""

    def predict(self, observation, *, action_masks, deterministic=True, **kwargs):
        del observation, deterministic, kwargs
        action = 1 if action_masks[1] else 0
        return np.asarray([action], dtype=np.int64), None


def summarize_duration_matching(
    target: dict[str, float], observed: dict[str, float]
) -> dict[str, float]:
    """Report signed and scaled exposure/duration gaps without tuning outcomes."""

    target_exposure = float(target["exposure_percentage"])
    target_holding = float(target["average_holding_duration"])
    target_wait = float(target["average_waiting_duration"])
    observed_exposure = float(observed["exposure_percentage"])
    observed_holding = float(observed["average_holding_duration"])
    observed_wait = float(observed["average_waiting_duration"])
    if target_holding <= 0:
        raise ValueError("target holding duration must be positive")
    return {
        "exposure_error_percentage_points": observed_exposure - target_exposure,
        "holding_duration_relative_error": (observed_holding - target_holding) / target_holding,
        "waiting_duration_error_days": observed_wait - target_wait,
    }
