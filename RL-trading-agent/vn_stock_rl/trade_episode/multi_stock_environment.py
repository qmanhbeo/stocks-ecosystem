"""One ticker-agnostic policy environment sampling ticker and start date per reset."""

from __future__ import annotations

from collections import Counter

import gymnasium as gym
import numpy as np

from vn_stock_rl.trade_episode.environment import TradeEpisodeEnv


class MultiStockEpisodeEnv(gym.Env):
    """Sample a stock and chronological start while exposing no ticker identity."""

    metadata: dict[str, list[str]] = {"render_modes": []}

    def __init__(
        self,
        environments: dict[str, TradeEpisodeEnv],
        *,
        eligible_start_indices: dict[str, np.ndarray] | None = None,
    ) -> None:
        super().__init__()
        if len(environments) < 2:
            raise ValueError("MultiStockEpisodeEnv requires at least two tickers")
        self.tickers = tuple(sorted(str(ticker).upper() for ticker in environments))
        self.environments = {str(ticker).upper(): env for ticker, env in environments.items()}
        first = self.environments[self.tickers[0]]
        shape = first.observation_space.shape
        if any(env.observation_space.shape != shape for env in self.environments.values()):
            raise ValueError("All stocks must have the same observation shape")
        if any(env.action_space != first.action_space for env in self.environments.values()):
            raise ValueError("All stocks must share one action space")
        self.observation_space = first.observation_space
        self.action_space = first.action_space
        self.observation_feature_names = list(first.observation_feature_names)
        if any(
            "ticker" in name.lower() or "symbol" in name.lower()
            for name in self.observation_feature_names
        ):
            raise ValueError("Ticker identity cannot appear in observations")

        starts = eligible_start_indices or {}
        self.eligible_start_indices: dict[str, np.ndarray] = {}
        for ticker in self.tickers:
            env = self.environments[ticker]
            values = np.asarray(starts.get(ticker, np.arange(env.n_rows - 1)), dtype=np.int64)
            values = values[(values >= 0) & (values < env.n_rows - 1)]
            if values.size == 0:
                raise ValueError(f"No eligible chronological starts for {ticker}")
            self.eligible_start_indices[ticker] = values

        self.current_ticker: str | None = None
        self.current_env: TradeEpisodeEnv | None = None
        self.sample_counts: Counter[str] = Counter()
        self.sampled_start_dates: dict[str, list[str]] = {ticker: [] for ticker in self.tickers}
        self._ticker_cycle: list[str] = []

    def action_masks(self) -> np.ndarray:
        if self.current_env is None:
            raise RuntimeError("Call reset() before requesting action masks")
        return self.current_env.action_masks()

    def reset(self, *, seed: int | None = None, options: dict | None = None):
        super().reset(seed=seed)
        if seed is not None:
            self._ticker_cycle = []
        if options:
            raise ValueError("Multi-stock training does not accept fixed ticker/start options")
        if not self._ticker_cycle:
            self._ticker_cycle = list(self.np_random.permutation(self.tickers))
        ticker = self._ticker_cycle.pop()
        starts = self.eligible_start_indices[ticker]
        start_index = int(starts[int(self.np_random.integers(0, len(starts)))])
        child_seed = int(self.np_random.integers(0, np.iinfo(np.uint32).max))
        self.current_ticker = ticker
        self.current_env = self.environments[ticker]
        observation, info = self.current_env.reset(
            seed=child_seed, options={"start_index": start_index}
        )
        self.sample_counts[ticker] += 1
        self.sampled_start_dates[ticker].append(str(info["episode_start_date"]))
        info["sampled_ticker"] = ticker
        info["sampled_start_date"] = info["episode_start_date"]
        info["sampled_start_index"] = start_index
        return observation, info

    def step(self, action):
        if self.current_env is None or self.current_ticker is None:
            raise RuntimeError("Call reset() before step()")
        observation, reward, terminated, truncated, info = self.current_env.step(action)
        info["sampled_ticker"] = self.current_ticker
        return observation, reward, terminated, truncated, info

    def close(self) -> None:
        for env in self.environments.values():
            env.close()
