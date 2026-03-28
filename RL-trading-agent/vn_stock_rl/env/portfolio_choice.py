from __future__ import annotations

import glob
import os
from pathlib import Path
from typing import Optional

import gymnasium as gym
import numpy as np
import pandas as pd
from gymnasium import spaces

from vn_stock_rl.config import DEFAULT_CONFIG
from vn_stock_rl.env.execution_model import (
    apply_portfolio_execution_constraints,
    update_holding_ages,
)
from vn_stock_rl.env.market_rules import build_tradability_cache, resolve_required_holding_age
from vn_stock_rl.external_features import (
    default_lab_signal_prediction_dir,
    signal_fill_value_for_column,
)


class PortfolioChoiceEnv(gym.Env):
    """Daily top-K long-only portfolio environment for cross-sectional signal panels."""

    metadata = {"render_modes": ["human"]}

    def __init__(
        self,
        data_dir: str,
        mode: str = "train",
        train_split: float | None = None,
        val_split: float | None = None,
        buy_fee_rate: float | None = None,
        sell_fee_rate: float | None = None,
        capital_gains_tax_rate: float | None = None,
        drawdown_penalty_enabled: Optional[bool] = None,
        drawdown_penalty_lambda: Optional[float] = None,
        drawdown_penalty_train_only: Optional[bool] = None,
        reward_benchmark: Optional[str] = None,
        benchmark_weight: Optional[float] = None,
        benchmark_relative_reward: Optional[bool] = None,
        train_episode_sampling_enabled: Optional[bool] = None,
        train_episode_min_fraction: Optional[float] = None,
        train_episode_max_fraction: Optional[float] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        signal_feature_columns: Optional[list[str]] = None,
        signal_prediction_dir: Optional[str] = None,
        portfolio_universe_size: int = 20,
        portfolio_top_k: int = 3,
        portfolio_universe_tickers: Optional[list[str]] = None,
    ):
        super().__init__()

        if mode not in {"train", "val", "test"}:
            raise ValueError(f"Invalid mode {mode!r}; expected 'train', 'val', or 'test'")
        if not signal_feature_columns:
            raise ValueError("Portfolio mode requires explicit signal_feature_columns")
        if portfolio_universe_size <= 0:
            raise ValueError("portfolio_universe_size must be > 0")
        if portfolio_top_k <= 0:
            raise ValueError("portfolio_top_k must be > 0")

        self.portfolio_choice = True
        self.mode = mode
        self.data_dir = str(data_dir)
        self.train_split = (
            float(train_split) if train_split is not None else float(DEFAULT_CONFIG["train_split"])
        )
        self.val_split = float(val_split) if val_split is not None else float(DEFAULT_CONFIG["val_split"])
        if not (0.0 < self.train_split < 1.0):
            raise ValueError(f"train_split must be in (0,1), got {self.train_split}")
        if not (0.0 <= self.val_split < 1.0):
            raise ValueError(f"val_split must be in [0,1), got {self.val_split}")
        if self.train_split + self.val_split >= 1.0:
            raise ValueError("train_split + val_split must be < 1.0")

        self.buy_fee_rate = (
            float(buy_fee_rate) if buy_fee_rate is not None else float(DEFAULT_CONFIG["buy_fee_rate"])
        )
        self.sell_fee_rate = (
            float(sell_fee_rate) if sell_fee_rate is not None else float(DEFAULT_CONFIG["sell_fee_rate"])
        )
        self.capital_gains_tax_rate = (
            float(capital_gains_tax_rate)
            if capital_gains_tax_rate is not None
            else float(DEFAULT_CONFIG["capital_gains_tax_rate"])
        )

        reward_shaping_cfg = DEFAULT_CONFIG.get("reward_shaping", {}) or {}
        drawdown_cfg = reward_shaping_cfg.get("drawdown_penalty", {}) or {}
        benchmark_cfg = reward_shaping_cfg.get("benchmark_relative", {}) or {}
        self.drawdown_penalty_enabled = (
            bool(drawdown_penalty_enabled)
            if drawdown_penalty_enabled is not None
            else bool(drawdown_cfg.get("enabled", True))
        )
        self.drawdown_penalty_lambda = (
            float(drawdown_penalty_lambda)
            if drawdown_penalty_lambda is not None
            else float(drawdown_cfg.get("lambda", 0.05))
        )
        self.drawdown_penalty_train_only = (
            bool(drawdown_penalty_train_only)
            if drawdown_penalty_train_only is not None
            else bool(drawdown_cfg.get("train_only", True))
        )
        self.benchmark_relative_reward_enabled = (
            bool(benchmark_relative_reward)
            if benchmark_relative_reward is not None
            else bool(benchmark_cfg.get("enabled", False))
        )
        self.reward_benchmark = (
            str(reward_benchmark).strip().lower()
            if reward_benchmark is not None
            else str(benchmark_cfg.get("benchmark", "self_buy_hold")).strip().lower()
        )
        if self.reward_benchmark != "self_buy_hold":
            raise ValueError(
                f"Unsupported reward_benchmark for portfolio mode: {self.reward_benchmark!r}"
            )
        self.benchmark_weight = (
            float(benchmark_weight)
            if benchmark_weight is not None
            else float(benchmark_cfg.get("weight", 1.0))
        )

        train_episode_cfg = DEFAULT_CONFIG.get("train_episode_sampling", {}) or {}
        self.train_episode_sampling_enabled = (
            bool(train_episode_sampling_enabled)
            if train_episode_sampling_enabled is not None
            else bool(train_episode_cfg.get("enabled", True))
        )
        self.train_episode_min_fraction = (
            float(train_episode_min_fraction)
            if train_episode_min_fraction is not None
            else float(train_episode_cfg.get("min_fraction", 0.05))
        )
        self.train_episode_max_fraction = (
            float(train_episode_max_fraction)
            if train_episode_max_fraction is not None
            else float(train_episode_cfg.get("max_fraction", 0.25))
        )
        if not (0.0 < self.train_episode_min_fraction <= 1.0):
            raise ValueError("train_episode_min_fraction must be in (0,1]")
        if not (0.0 < self.train_episode_max_fraction <= 1.0):
            raise ValueError("train_episode_max_fraction must be in (0,1]")
        if self.train_episode_min_fraction > self.train_episode_max_fraction:
            raise ValueError("train_episode_min_fraction must be <= train_episode_max_fraction")

        self.sample_start_date = self._normalize_date_bound(start_date)
        self.sample_end_date = self._normalize_date_bound(end_date)
        if (
            self.sample_start_date is not None
            and self.sample_end_date is not None
            and self.sample_start_date > self.sample_end_date
        ):
            raise ValueError("start_date must be <= end_date")

        self.signal_feature_names = [str(column).strip() for column in signal_feature_columns]
        if not self.signal_feature_names:
            raise ValueError("Portfolio mode requires at least one signal feature column")
        self.signal_prediction_dir = str(
            Path(signal_prediction_dir or default_lab_signal_prediction_dir()).expanduser().resolve()
        )
        self.portfolio_universe_size = int(portfolio_universe_size)
        self.portfolio_top_k = int(portfolio_top_k)
        self.portfolio_universe_tickers = (
            [str(ticker).strip().upper() for ticker in portfolio_universe_tickers]
            if portfolio_universe_tickers
            else None
        )

        self.lookback_window = 0
        self.requested_min_hold_days = int(DEFAULT_CONFIG["min_hold_days"])
        self.min_hold_days = resolve_required_holding_age(self.requested_min_hold_days)
        self.required_holding_age = int(self.min_hold_days)
        self.normalize = False
        self.include_can_exit = False
        self.stop_loss = None
        self.source_mode = "portfolio_panel"
        self.ohlcv_fields: list[str] = []
        self.calendar_features: list[str] = []
        self.ma_windows: list[int] = []
        self.helpers_ma_windows_cfg: list[int] = []
        self.returns_windows: list[int] = []
        self.helpers_returns_windows_cfg: list[int] = []
        self.engineered_feature_families: list[str] = []
        self.engineered_window_policy = None
        self.engineered_feature_windows: list[int] = []
        self.rs_market_proxies: list[str] = []
        self.rs_include_long = False
        self.start_episode_position = 0.0
        self.train_episode_sampling_mode = "fraction"
        self.signal_feature_columns = list(self.signal_feature_names)
        self.reward_shaping = {
            "drawdown_penalty": {
                "enabled": bool(self.drawdown_penalty_enabled),
                "lambda": float(self.drawdown_penalty_lambda),
                "train_only": bool(self.drawdown_penalty_train_only),
            },
            "benchmark_relative": {
                "enabled": bool(self.benchmark_relative_reward_enabled),
                "benchmark": self.reward_benchmark,
                "weight": float(self.benchmark_weight),
            },
        }
        self.position = 0
        self.hold_count = 0
        self.num_holdings = 0
        self.avg_holding_age = 0.0

        self._setup_panel()

        self.n_features_per_stock = len(self.signal_feature_names) + 1
        self.n_features = self.portfolio_universe_size * self.n_features_per_stock
        obs_dim = self.n_features + 1
        self.observation_space = spaces.Box(
            low=-np.inf,
            high=np.inf,
            shape=(obs_dim,),
            dtype=np.float32,
        )
        self.action_space = spaces.MultiDiscrete(
            np.full(self.portfolio_top_k, self.portfolio_universe_size + 1, dtype=np.int64)
        )

        self.input_features = {
            "source_mode": self.source_mode,
            "ohlcv": [],
            "ma_windows": [],
            "helpers_ma_windows": [],
            "returns_windows": [],
            "helpers_returns_windows": [],
            "calendar": [],
            "signal_features": {
                "columns": list(self.signal_feature_names),
                "prediction_dir": self.signal_prediction_dir,
            },
            "portfolio_features": {
                "mode": True,
                "universe_size": int(self.portfolio_universe_size),
                "top_k": int(self.portfolio_top_k),
                "universe_tickers": list(self.universe_tickers),
            },
            "sample_start_date": (
                self.sample_start_date.strftime("%Y-%m-%d")
                if self.sample_start_date is not None
                else None
            ),
            "sample_end_date": (
                self.sample_end_date.strftime("%Y-%m-%d")
                if self.sample_end_date is not None
                else None
            ),
        }

        self._rng = np.random.default_rng()
        self.reset()

    @staticmethod
    def _normalize_date_bound(value: Optional[str]) -> Optional[pd.Timestamp]:
        if value is None:
            return None
        timestamp = pd.Timestamp(value)
        if timestamp.tzinfo is not None:
            timestamp = timestamp.tz_localize(None)
        return timestamp.normalize()

    @staticmethod
    def _infer_ticker(file_path: str) -> str:
        base_name = os.path.basename(file_path).replace(".parquet", "")
        if "gia_lich_su_" in base_name and "_1D" in base_name:
            return base_name.replace("gia_lich_su_", "").replace("_1D", "")
        return base_name

    def _load_price_frame(self, ticker: str) -> pd.DataFrame:
        path = os.path.join(self.data_dir, f"gia_lich_su_{ticker}_1D.parquet")
        if not os.path.exists(path):
            raise FileNotFoundError(f"Missing price parquet for ticker {ticker}: {path}")
        frame = pd.read_parquet(path).sort_values("time").reset_index(drop=True)
        frame["time"] = pd.to_datetime(frame["time"], errors="coerce")
        if frame["time"].isna().any():
            raise ValueError(f"Non-datetime time values found in price parquet for {ticker}")
        if self.sample_start_date is not None:
            frame = frame.loc[frame["time"] >= self.sample_start_date].copy()
        if self.sample_end_date is not None:
            frame = frame.loc[frame["time"] <= self.sample_end_date].copy()
        if frame.empty:
            raise ValueError(f"No price rows remain for {ticker} after date filtering")
        return frame[["time", "open", "close", "volume"]].copy()

    def _load_signal_frame(self, ticker: str) -> pd.DataFrame:
        path = Path(self.signal_prediction_dir) / f"{ticker}_signal_predictions.parquet"
        if not path.exists():
            raise FileNotFoundError(f"Missing signal parquet for ticker {ticker}: {path}")
        frame = pd.read_parquet(path)
        if "date" not in frame.columns:
            raise ValueError(f"Signal parquet for {ticker} is missing required 'date' column")
        frame["time"] = pd.to_datetime(frame["date"], errors="coerce")
        if frame["time"].isna().any():
            raise ValueError(f"Signal parquet for {ticker} contains non-datetime dates")
        if self.sample_start_date is not None:
            frame = frame.loc[frame["time"] >= self.sample_start_date].copy()
        if self.sample_end_date is not None:
            frame = frame.loc[frame["time"] <= self.sample_end_date].copy()
        if frame.empty:
            raise ValueError(f"No signal rows remain for {ticker} after date filtering")
        for column in self.signal_feature_names:
            fill_value = signal_fill_value_for_column(column)
            if column not in frame.columns:
                frame[column] = fill_value
            frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(fill_value)
        return frame[["time", *self.signal_feature_names]].copy()

    def _compute_splits(self, total_len: int) -> dict[str, int]:
        if total_len < 10:
            raise ValueError(f"Panel is too short for portfolio mode: total_len={total_len}")
        train_end_idx = int(total_len * self.train_split) - 1
        val_start_idx = train_end_idx + 2
        val_end_idx = int(total_len * (self.train_split + self.val_split)) - 1
        test_start_idx = val_end_idx + 2
        test_end_idx = total_len - 1
        splits = {
            "train_start_idx": 0,
            "train_end_idx": train_end_idx,
            "val_start_idx": val_start_idx,
            "val_end_idx": val_end_idx,
            "test_start_idx": test_start_idx,
            "test_end_idx": test_end_idx,
        }
        for split_name in ("train", "val", "test"):
            rows = splits[f"{split_name}_end_idx"] - splits[f"{split_name}_start_idx"] + 1
            if rows < 2:
                raise ValueError(
                    f"Split configuration yields non-tradable portfolio {split_name} range: rows={rows}"
                )
        return splits

    def _sample_train_episode_bounds(self) -> tuple[int, int]:
        train_start_idx = int(self.train_start_idx)
        train_end_idx = int(self.train_end_idx - 1)
        if not self.train_episode_sampling_enabled:
            return train_start_idx, train_end_idx

        train_rows = int(train_end_idx - train_start_idx + 1)
        min_rows = max(int(np.floor(train_rows * self.train_episode_min_fraction)), 2)
        max_rows = max(int(np.floor(train_rows * self.train_episode_max_fraction)), min_rows)
        max_rows = min(max_rows, train_rows)
        if max_rows <= min_rows:
            episode_rows = min_rows
        else:
            episode_rows = int(self._rng.integers(min_rows, max_rows + 1))
        latest_start = int(train_end_idx - episode_rows + 1)
        if latest_start <= train_start_idx:
            episode_start_idx = train_start_idx
        else:
            episode_start_idx = int(self._rng.integers(train_start_idx, latest_start + 1))
        episode_end_idx = int(episode_start_idx + episode_rows - 1)
        return episode_start_idx, episode_end_idx

    def _setup_panel(self) -> None:
        parquet_files = sorted(glob.glob(os.path.join(self.data_dir, "gia_lich_su_*_1D.parquet")))
        if not parquet_files:
            raise ValueError(f"No stock parquet files found in {self.data_dir}")

        candidate_rows: list[dict[str, float | str]] = []
        explicit_tickers = set(self.portfolio_universe_tickers or [])
        for file_path in parquet_files:
            ticker = self._infer_ticker(file_path).upper()
            if explicit_tickers and ticker not in explicit_tickers:
                continue
            signal_path = Path(self.signal_prediction_dir) / f"{ticker}_signal_predictions.parquet"
            if not signal_path.exists():
                continue
            frame = self._load_price_frame(ticker)
            splits = self._compute_splits(len(frame))
            train_rows = splits["train_end_idx"] - splits["train_start_idx"] + 1
            if train_rows < 252:
                continue
            train_slice = frame.iloc[splits["train_start_idx"] : splits["train_end_idx"] + 1]
            median_dtv = float(np.nanmedian(train_slice["close"] * train_slice["volume"]))
            if not np.isfinite(median_dtv) or median_dtv <= 0.0:
                continue
            candidate_rows.append({"ticker": ticker, "median_dtv": median_dtv})

        if not candidate_rows:
            raise ValueError("No eligible tickers found for portfolio universe selection")

        candidates = pd.DataFrame(candidate_rows).sort_values(
            ["median_dtv", "ticker"],
            ascending=[False, True],
        )
        if explicit_tickers:
            universe = [ticker for ticker in self.portfolio_universe_tickers if ticker in set(candidates["ticker"])]
        else:
            universe = candidates["ticker"].head(self.portfolio_universe_size).tolist()
        if not universe:
            raise ValueError("Universe selection produced no usable tickers")

        merged_frames: dict[str, pd.DataFrame] = {}
        common_dates: Optional[set[pd.Timestamp]] = None
        for ticker in universe:
            price_frame = self._load_price_frame(ticker)
            signal_frame = self._load_signal_frame(ticker)
            merged = price_frame.merge(signal_frame, on="time", how="inner", validate="one_to_one")
            if merged.empty:
                raise ValueError(f"No overlapping price/signal rows for {ticker}")
            merged = merged.sort_values("time").reset_index(drop=True)
            merged_frames[ticker] = merged
            ticker_dates = set(pd.to_datetime(merged["time"]).tolist())
            common_dates = ticker_dates if common_dates is None else common_dates & ticker_dates

        common_dates_list = sorted(common_dates or [])
        if len(common_dates_list) < 10:
            raise ValueError("Common portfolio panel is too short after date intersection")

        self.universe_tickers = list(universe)
        self.portfolio_universe_size = len(self.universe_tickers)
        self.stock_names = list(self.universe_tickers)
        self.ticker_to_index = {
            ticker: idx for idx, ticker in enumerate(self.universe_tickers)
        }

        aligned_frames: list[pd.DataFrame] = []
        aligned_tradability: list[dict[str, np.ndarray]] = []
        for ticker in self.universe_tickers:
            aligned = (
                merged_frames[ticker]
                .set_index("time")
                .loc[common_dates_list]
                .reset_index()
            )
            if aligned[["open", "close"]].isna().any().any():
                raise ValueError(f"NaN open/close values remain after panel alignment for {ticker}")
            aligned_frames.append(aligned)
            aligned_tradability.append(build_tradability_cache(aligned))

        self.dates = np.asarray(common_dates_list, dtype="datetime64[ns]")
        self.open_matrix = np.stack(
            [frame["open"].to_numpy(dtype=np.float64) for frame in aligned_frames],
            axis=1,
        )
        self.close_matrix = np.stack(
            [frame["close"].to_numpy(dtype=np.float64) for frame in aligned_frames],
            axis=1,
        )
        self.volume_matrix = np.stack(
            [frame["volume"].to_numpy(dtype=np.float64) for frame in aligned_frames],
            axis=1,
        )
        self.signal_tensor = np.stack(
            [
                frame[self.signal_feature_names].to_numpy(dtype=np.float64)
                for frame in aligned_frames
            ],
            axis=1,
        )
        self.can_buy_matrix = np.stack(
            [cache["can_buy_next_open"] for cache in aligned_tradability],
            axis=1,
        )
        self.can_sell_matrix = np.stack(
            [cache["can_sell_next_open"] for cache in aligned_tradability],
            axis=1,
        )
        self.has_volume_matrix = np.stack(
            [cache["has_volume"] for cache in aligned_tradability],
            axis=1,
        )
        self.is_ceiling_matrix = np.stack(
            [cache["is_ceiling"] for cache in aligned_tradability],
            axis=1,
        )
        self.is_floor_matrix = np.stack(
            [cache["is_floor"] for cache in aligned_tradability],
            axis=1,
        )
        self.df = pd.DataFrame(
            {
                "time": pd.to_datetime(self.dates),
                "open": self.open_matrix.mean(axis=1),
                "close": self.close_matrix.mean(axis=1),
            }
        )

        splits = self._compute_splits(len(self.dates))
        self.train_start_idx = splits["train_start_idx"]
        self.train_end_idx = splits["train_end_idx"]
        self.val_start_idx = splits["val_start_idx"]
        self.val_end_idx = splits["val_end_idx"]
        self.test_start_idx = splits["test_start_idx"]
        self.test_end_idx = splits["test_end_idx"]
        self.train_start_date = self.df.iloc[self.train_start_idx]["time"]
        self.train_end_date = self.df.iloc[self.train_end_idx]["time"]
        self.val_start_date = self.df.iloc[self.val_start_idx]["time"]
        self.val_end_date = self.df.iloc[self.val_end_idx]["time"]
        self.test_start_date = self.df.iloc[self.test_start_idx]["time"]
        self.test_end_date = self.df.iloc[self.test_end_idx]["time"]

    def _decode_action(self, action) -> tuple[np.ndarray, list[int], list[str]]:
        raw = np.asarray(action, dtype=np.int64).reshape(-1)
        if raw.size == 1 and self.portfolio_top_k > 1:
            if int(raw[0]) == 0:
                raw = np.full(self.portfolio_top_k, self.portfolio_universe_size, dtype=np.int64)
            else:
                raise ValueError("Portfolio mode expects MultiDiscrete action with top_k slots")
        if raw.size != self.portfolio_top_k:
            raise ValueError(
                f"Portfolio action must have {self.portfolio_top_k} slots, got {raw.size}"
            )
        unique_indices: list[int] = []
        for index in raw.tolist():
            index = int(index)
            if index == self.portfolio_universe_size:
                continue
            if 0 <= index < self.portfolio_universe_size and index not in unique_indices:
                unique_indices.append(index)
        target_weights = np.zeros(self.portfolio_universe_size, dtype=np.float64)
        if unique_indices:
            target_weights[unique_indices] = 1.0 / float(len(unique_indices))
        selected_tickers = [self.universe_tickers[idx] for idx in unique_indices]
        return target_weights, unique_indices, selected_tickers

    def _benchmark_step_return(self, step_idx_t: int, step_idx_t1: int) -> float:
        open_t = np.clip(self.open_matrix[step_idx_t], 1e-12, None)
        open_t1 = self.open_matrix[step_idx_t1]
        returns = (open_t1 / open_t) - 1.0
        return float(np.mean(returns))

    def _get_observation(self) -> np.ndarray:
        signal_slice = self.signal_tensor[self.current_step]
        weight_column = self.current_weights.reshape(-1, 1)
        panel = np.concatenate([signal_slice, weight_column], axis=1)
        obs = np.concatenate(
            [panel.reshape(-1), np.array([self.cash_weight], dtype=np.float64)],
            axis=0,
        )
        return obs.astype(np.float32, copy=False)

    def _set_position_state(self) -> None:
        active_mask = self.current_weights > 1e-12
        self.position = int(np.any(active_mask))
        self.num_holdings = int(np.count_nonzero(active_mask))
        self.avg_holding_age = (
            float(np.mean(self.holding_ages[active_mask]))
            if self.num_holdings > 0
            else 0.0
        )
        self.hold_count = 0

    def reset(self, *, seed: Optional[int] = None, options: Optional[dict] = None):
        super().reset(seed=seed)
        if seed is not None:
            self._rng = np.random.default_rng(seed)

        if self.mode == "train":
            self.episode_start_idx, self.episode_end_idx = self._sample_train_episode_bounds()
        elif self.mode == "val":
            self.episode_start_idx = int(self.val_start_idx)
            self.episode_end_idx = int(self.val_end_idx - 1)
        else:
            self.episode_start_idx = int(self.test_start_idx)
            self.episode_end_idx = int(self.test_end_idx - 1)

        self.current_step = int(self.episode_start_idx)
        self.current_weights = np.zeros(self.portfolio_universe_size, dtype=np.float64)
        self.holding_ages = np.zeros(self.portfolio_universe_size, dtype=np.int64)
        self.cash_weight = 1.0
        self.portfolio_value = 1.0
        self.benchmark_portfolio_value = 1.0
        self.peak_equity = 1.0
        self.last_raw_return = 0.0
        self.last_benchmark_return = 0.0
        self.last_excess_return = 0.0
        self.last_drawdown = 0.0
        self.last_drawdown_penalty = 0.0
        self.last_turnover = 0.0
        self.last_selected_indices: list[int] = []
        self.last_selected_tickers: list[str] = []
        self.last_blocked_buy_indices: tuple[int, ...] = tuple()
        self.last_blocked_sell_indices: tuple[int, ...] = tuple()
        self.cumulative_return = 0.0
        self.episode_rewards: list[float] = []
        self.episode_trades: list[dict] = []
        self._set_position_state()
        return self._get_observation(), self._get_reset_info()

    def _get_reset_info(self) -> dict:
        return {
            "mode": self.mode,
            "episode_start": int(self.episode_start_idx),
            "episode_end": int(self.episode_end_idx),
            "universe_tickers": list(self.universe_tickers),
        }

    def step(self, action):
        if self.current_step >= self.episode_end_idx:
            observation = self._get_observation()
            info = self._get_step_info(0.0)
            return observation, 0.0, True, False, info

        value_t = float(self.portfolio_value)
        open_t = np.clip(self.open_matrix[self.current_step], 1e-12, None)
        next_step = int(self.current_step + 1)
        open_t1 = self.open_matrix[next_step]
        open_returns = (open_t1 / open_t) - 1.0
        gross_multiplier = 1.0 + float(np.dot(self.current_weights, open_returns))
        value_before_rebalance = value_t * gross_multiplier

        previous_weights = self.current_weights.copy()
        previous_holding_ages = self.holding_ages.copy()
        desired_weights, next_indices, next_tickers = self._decode_action(action)
        self.last_selected_indices = next_indices
        self.last_selected_tickers = next_tickers
        execution_result = apply_portfolio_execution_constraints(
            current_weights=previous_weights,
            desired_weights=desired_weights,
            holding_ages=previous_holding_ages,
            can_buy_next_open=self.can_buy_matrix[next_step],
            can_sell_next_open=self.can_sell_matrix[next_step],
            min_hold_days=self.min_hold_days,
        )
        executed_weights = execution_result.executed_weights
        buy_turnover = execution_result.buy_turnover
        sell_turnover = execution_result.sell_turnover
        total_turnover = execution_result.total_turnover
        transaction_cost = (
            buy_turnover * self.buy_fee_rate
            + sell_turnover * (self.sell_fee_rate + self.capital_gains_tax_rate)
        )
        value_after_rebalance = value_before_rebalance * max(1.0 - transaction_cost, 0.0)

        benchmark_return = self._benchmark_step_return(self.current_step, next_step)
        self.benchmark_portfolio_value *= (1.0 + benchmark_return)

        self.current_step = next_step
        self.current_weights = executed_weights
        self.holding_ages = update_holding_ages(
            previous_weights=previous_weights,
            executed_weights=executed_weights,
            previous_holding_ages=previous_holding_ages,
        )
        self.cash_weight = float(max(1.0 - float(self.current_weights.sum()), 0.0))
        self.portfolio_value = float(value_after_rebalance)
        raw_return = (self.portfolio_value / value_t) - 1.0
        excess_return = raw_return - benchmark_return
        relative_reward_signal = raw_return - (self.benchmark_weight * benchmark_return)
        peak_equity = max(float(self.peak_equity), float(self.portfolio_value), 1e-12)
        drawdown = max(0.0, (peak_equity - float(self.portfolio_value)) / peak_equity)
        apply_drawdown_penalty = self.drawdown_penalty_enabled and (
            (not self.drawdown_penalty_train_only) or (self.mode == "train")
        )
        drawdown_penalty = (
            self.drawdown_penalty_lambda * drawdown if apply_drawdown_penalty else 0.0
        )
        reward_signal = (
            relative_reward_signal
            if self.benchmark_relative_reward_enabled
            else raw_return
        )
        reward = reward_signal - drawdown_penalty

        self.peak_equity = float(peak_equity)
        self.last_raw_return = float(raw_return)
        self.last_benchmark_return = float(benchmark_return)
        self.last_excess_return = float(excess_return)
        self.last_drawdown = float(drawdown)
        self.last_drawdown_penalty = float(drawdown_penalty)
        self.last_turnover = float(total_turnover)
        self.last_blocked_buy_indices = execution_result.blocked_buy_indices
        self.last_blocked_sell_indices = execution_result.blocked_sell_indices
        self.cumulative_return += float(reward)
        self.episode_rewards.append(float(reward))
        self._set_position_state()

        if total_turnover > 0.0:
            self.episode_trades.append(
                {
                    "step": int(self.current_step),
                    "date": pd.Timestamp(self.dates[self.current_step]).isoformat(),
                    "turnover": float(total_turnover),
                    "raw_return": float(raw_return),
                    "num_holdings": int(self.num_holdings),
                    "avg_holding_age": float(self.avg_holding_age),
                    "tickers": list(self.last_selected_tickers),
                }
            )

        terminated = bool(self.current_step >= self.episode_end_idx)
        observation = self._get_observation()
        info = self._get_step_info(float(reward))
        return observation, float(reward), terminated, False, info

    def _get_step_info(self, reward: float) -> dict:
        return {
            "step": int(self.current_step),
            "position": int(self.position),
            "reward": float(reward),
            "reward_shaped": float(reward),
            "raw_return": float(self.last_raw_return),
            "benchmark_return": float(self.last_benchmark_return),
            "excess_return": float(self.last_excess_return),
            "drawdown": float(self.last_drawdown),
            "drawdown_penalty": float(self.last_drawdown_penalty),
            "peak_equity": float(self.peak_equity),
            "cumulative_return": float(self.cumulative_return),
            "equity": float(self.portfolio_value),
            "portfolio_value": float(self.portfolio_value),
            "benchmark_portfolio_value": float(self.benchmark_portfolio_value),
            "cash_weight": float(self.cash_weight),
            "turnover": float(self.last_turnover),
            "num_holdings": int(self.num_holdings),
            "avg_holding_age": float(self.avg_holding_age),
            "selected_tickers": list(self.last_selected_tickers),
            "blocked_buy_tickers": [self.universe_tickers[idx] for idx in self.last_blocked_buy_indices],
            "blocked_sell_tickers": [self.universe_tickers[idx] for idx in self.last_blocked_sell_indices],
        }

    def get_episode_stats(self):
        trade_returns = np.asarray(
            [trade["raw_return"] for trade in self.episode_trades],
            dtype=np.float64,
        )
        if trade_returns.size:
            winning_mask = trade_returns > 0.0
            win_rate = float(np.mean(winning_mask))
            num_winning = int(np.count_nonzero(winning_mask))
            avg_trade_return = float(np.mean(trade_returns))
        else:
            win_rate = 0.0
            num_winning = 0
            avg_trade_return = 0.0

        return {
            "portfolio_mode": True,
            "total_return": float(self.cumulative_return),
            "num_trades": int(len(self.episode_trades)),
            "num_winning_trades": int(num_winning),
            "win_rate": float(win_rate),
            "avg_trade_return": float(avg_trade_return),
            "total_steps": int(self.current_step - self.episode_start_idx),
            "reward_mode": (
                "benchmark_relative"
                if self.benchmark_relative_reward_enabled
                else ("drawdown_shaped" if self.drawdown_penalty_enabled else "raw_return")
            ),
            "reward_benchmark": self.reward_benchmark,
            "benchmark_weight": float(self.benchmark_weight),
            "universe_tickers": list(self.universe_tickers),
            "portfolio_universe_size": int(self.portfolio_universe_size),
            "portfolio_top_k": int(self.portfolio_top_k),
            "benchmark_final_return": float(self.benchmark_portfolio_value - 1.0),
            "final_portfolio_value": float(self.portfolio_value),
            "avg_holding_age": float(self.avg_holding_age),
        }

    def render(self):
        current_date = pd.Timestamp(self.dates[self.current_step]).strftime("%Y-%m-%d")
        print(
            f"[PORTFOLIO] step={self.current_step} date={current_date} "
            f"value={self.portfolio_value:.4f} holdings={self.num_holdings} "
            f"cash_weight={self.cash_weight:.2%}"
        )

    def close(self):
        return None
