from __future__ import annotations

from typing import Any

import gymnasium as gym
import numpy as np
from gymnasium import spaces

ANNUALIZATION_INTERVALS = 252
ANNUAL_BENCHMARK = 0.07
UNREALIZED_RETURN_SCALE = 0.10
ACTION_OUT = 0
ACTION_IN = 1


def annualized_log_excess_reward(
    buy_price: float,
    sell_price: float,
    holding_intervals: int,
    *,
    annualization_intervals: int = ANNUALIZATION_INTERVALS,
    annual_benchmark: float = ANNUAL_BENCHMARK,
) -> float:
    """Compute the specified annualized log excess reward for a completed trade."""

    buy_price = float(buy_price)
    sell_price = float(sell_price)
    holding_intervals = int(holding_intervals)
    if not np.isfinite([buy_price, sell_price]).all() or min(buy_price, sell_price) <= 0.0:
        raise ValueError("Trade prices must be finite and positive")
    if holding_intervals < 3:
        raise ValueError("A trade reward requires at least three fill-to-fill intervals")
    if annualization_intervals <= 0 or annual_benchmark <= -1.0:
        raise ValueError("Invalid annualization or benchmark setting")
    return float(
        (annualization_intervals / holding_intervals) * (np.log(sell_price) - np.log(buy_price))
        - np.log1p(annual_benchmark)
    )


class TradeEpisodeEnv(gym.Env):
    """One long-only trade, with close-time decisions and next-open execution.

    Market features are caller-provided and must be causal, finite, and normalized
    using training-slice statistics only. Price basis must be synthetic, verified,
    or explicitly marked as a user-confirmed adjustment assumption.
    """

    metadata: dict[str, list[str]] = {"render_modes": []}

    def __init__(
        self,
        open_prices,
        close_prices,
        *,
        price_basis: str,
        market_features=None,
        feature_names: list[str] | None = None,
        dates=None,
        can_buy_next_open=None,
        can_sell_next_open=None,
        daily_volatility_scale=None,
        min_holding_intervals: int = 3,
        max_episode_steps: int = 252,
        max_wait_steps: int = 252,
        max_holding_intervals: int = 252,
        annualization_intervals: int = ANNUALIZATION_INTERVALS,
        annual_benchmark: float = ANNUAL_BENCHMARK,
        ticker: str = "SYNTHETIC",
        random_start: bool = False,
    ) -> None:
        super().__init__()
        if price_basis not in {
            "synthetic",
            "verified_adjusted",
            "user_assumed_dividend_adjusted",
        }:
            raise ValueError(
                "price_basis must be 'synthetic', 'verified_adjusted', or "
                "'user_assumed_dividend_adjusted'; raw/unverified prices are rejected"
            )
        self.price_basis = price_basis
        self.ticker = str(ticker).strip().upper()
        self.open_prices = self._validated_prices(open_prices, "open_prices")
        self.close_prices = self._validated_prices(close_prices, "close_prices")
        if self.open_prices.shape != self.close_prices.shape:
            raise ValueError("open_prices and close_prices must have the same length")
        self.n_rows = len(self.open_prices)
        if self.n_rows < 2:
            raise ValueError("At least two daily rows are required for next-open execution")
        if min_holding_intervals < 3:
            raise ValueError("min_holding_intervals cannot be below the required three intervals")
        if min(max_episode_steps, max_wait_steps, max_holding_intervals) < 1:
            raise ValueError("Episode, waiting, and holding horizons must be positive")
        if annualization_intervals <= 0 or annual_benchmark <= -1.0:
            raise ValueError("Invalid annualization or annual benchmark")

        self.min_holding_intervals = int(min_holding_intervals)
        self.max_episode_steps = int(max_episode_steps)
        self.max_wait_steps = int(max_wait_steps)
        self.max_holding_intervals = int(max_holding_intervals)
        self.annualization_intervals = int(annualization_intervals)
        self.annual_benchmark = float(annual_benchmark)
        self.random_start = bool(random_start)

        if market_features is None:
            features = np.zeros((self.n_rows, 0), dtype=np.float32)
        else:
            features = np.asarray(market_features, dtype=np.float64)
            if features.ndim != 2 or features.shape[0] != self.n_rows:
                raise ValueError("market_features must be a 2D array with one row per trading date")
            if not np.isfinite(features).all():
                raise ValueError("market_features must contain only finite values")
            features = features.astype(np.float32)
            if not np.isfinite(features).all():
                raise ValueError("market_features exceed finite float32 observation range")
        self.market_features = features
        if feature_names is None:
            self.feature_names = [f"market_feature_{i}" for i in range(features.shape[1])]
        else:
            self.feature_names = [str(name) for name in feature_names]
            if len(self.feature_names) != features.shape[1]:
                raise ValueError("feature_names count must match market_features columns")
        if dates is None:
            self.dates = np.arange(self.n_rows)
        else:
            self.dates = np.asarray(dates)
            if self.dates.ndim != 1 or len(self.dates) != self.n_rows:
                raise ValueError("dates must have one entry per trading row")

        self.can_buy_next_open = self._validated_flags(can_buy_next_open, "can_buy_next_open")
        self.can_sell_next_open = self._validated_flags(can_sell_next_open, "can_sell_next_open")
        if daily_volatility_scale is None:
            volatility_scale = np.full(self.n_rows, UNREALIZED_RETURN_SCALE, dtype=np.float64)
            self._use_entry_volatility_scale = False
        else:
            self._use_entry_volatility_scale = True
            volatility_scale = np.asarray(daily_volatility_scale, dtype=np.float64)
            if (
                volatility_scale.ndim != 1
                or len(volatility_scale) != self.n_rows
                or not np.isfinite(volatility_scale).all()
                or (volatility_scale <= 0).any()
            ):
                raise ValueError(
                    "daily_volatility_scale must contain one finite positive value per row"
                )
        self.daily_volatility_scale = volatility_scale.copy()
        self.action_space = spaces.Discrete(2)
        self.observation_space = spaces.Box(
            low=-np.inf,
            high=np.inf,
            shape=(features.shape[1] + 5,),
            dtype=np.float32,
        )
        self.observation_feature_names = [
            *self.feature_names,
            "position_in",
            "holding_intervals_normalized",
            "entry_relative_unrealized_log_return_scaled",
            "waiting_steps_normalized",
            "episode_steps_normalized",
        ]
        self._episode_start_index = 0
        self._done = False
        self._clear_episode_state()

    @staticmethod
    def _validated_prices(values, name: str) -> np.ndarray:
        result = np.asarray(values, dtype=np.float64)
        if result.ndim != 1 or result.size == 0:
            raise ValueError(f"{name} must be a non-empty 1D array")
        if not np.isfinite(result).all() or (result <= 0.0).any():
            raise ValueError(f"{name} must contain only finite positive prices")
        return result.copy()

    def _validated_flags(self, values, name: str) -> np.ndarray:
        if values is None:
            return np.ones(self.n_rows, dtype=bool)
        result = np.asarray(values, dtype=bool)
        if result.ndim != 1 or len(result) != self.n_rows:
            raise ValueError(f"{name} must have one boolean per decision date")
        return result.copy()

    def _clear_episode_state(self) -> None:
        self._market_index = self._episode_start_index
        self._episode_steps = 0
        self._wait_steps = 0
        self._position_in = False
        self._cash = 1.0
        self._shares = 0.0
        self._entry_index: int | None = None
        self._entry_price: float | None = None
        self._entry_volatility_scale: float | None = None
        self._entry_wait_steps: int | None = None
        self._exit_index: int | None = None
        self._exit_price: float | None = None
        self._last_trade_intervals: int | None = None
        self._raw_trade_return: float | None = None
        self._annualized_log_trade_return: float | None = None
        self._terminal_reward: float | None = None
        self._done = False

    def _date_label(self, index: int) -> str:
        value = self.dates[index]
        if hasattr(value, "strftime"):
            return value.strftime("%Y-%m-%d")
        return str(value)

    def _holding_intervals(self) -> int:
        if self._entry_index is None:
            return 0
        return self._market_index - self._entry_index

    def _observation(self) -> np.ndarray:
        holding = self._holding_intervals()
        unrealized_scaled = 0.0
        if self._position_in and self._entry_price is not None:
            if self._use_entry_volatility_scale:
                entry_scale = self._entry_volatility_scale or UNREALIZED_RETURN_SCALE
                holding_scale = entry_scale * np.sqrt(max(1, holding))
            else:
                holding_scale = UNREALIZED_RETURN_SCALE
            unrealized_scaled = (
                np.log(self.close_prices[self._market_index]) - np.log(self._entry_price)
            ) / holding_scale
        state = np.asarray(
            [
                float(self._position_in),
                holding / self.max_holding_intervals,
                unrealized_scaled,
                self._wait_steps / self.max_wait_steps,
                self._episode_steps / self.max_episode_steps,
            ],
            dtype=np.float64,
        )
        observation = np.concatenate((self.market_features[self._market_index], state)).astype(
            np.float32
        )
        if not np.isfinite(observation).all():
            raise ValueError("Observation contains non-finite values")
        return observation

    def action_masks(self) -> np.ndarray:
        """Mask target OUT/SELL and IN/BUY when the requested next-open fill is illegal."""

        if self._done:
            return np.ones(2, dtype=bool)
        decision_index = self._market_index
        if decision_index >= self.n_rows - 1:
            return np.array([True, False], dtype=bool)
        if not self._position_in:
            return np.array([True, bool(self.can_buy_next_open[decision_index])], dtype=bool)
        next_fill_intervals = decision_index + 1 - int(self._entry_index)
        sell_allowed = next_fill_intervals >= self.min_holding_intervals and bool(
            self.can_sell_next_open[decision_index]
        )
        return np.array([sell_allowed, True], dtype=bool)

    def _info(self, *, action: int | None = None) -> dict[str, Any]:
        index = self._market_index
        position_value = self._shares * self.close_prices[index] if self._position_in else 0.0
        equity = self._cash + position_value
        holding = self._holding_intervals()
        waiting = self._wait_steps if self._entry_wait_steps is None else self._entry_wait_steps
        info: dict[str, Any] = {
            "ticker": self.ticker,
            "price_basis": self.price_basis,
            "date": self._date_label(index),
            "decision_index": index,
            "episode_steps": self._episode_steps,
            "action": action,
            "action_meaning": None if action is None else ("OUT" if action == ACTION_OUT else "IN"),
            "position": int(self._position_in),
            "cash": float(self._cash),
            "position_value": float(position_value),
            "mark_to_market_portfolio_value": float(equity),
            "entry_date": None
            if self._entry_index is None
            else self._date_label(self._entry_index),
            "entry_price": self._entry_price,
            "exit_date": None if self._exit_index is None else self._date_label(self._exit_index),
            "exit_price": self._exit_price,
            "waiting_duration": int(waiting),
            "holding_duration": int(
                holding if self._last_trade_intervals is None else self._last_trade_intervals
            ),
            "raw_trade_return": self._raw_trade_return,
            "annualized_log_trade_return": self._annualized_log_trade_return,
            "terminal_rl_reward": self._terminal_reward,
            "termination_reason": "sell" if self._exit_index is not None else None,
            "truncation_reason": None,
            "truncated_open_position_value": None,
            "action_mask": self.action_masks().tolist(),
        }
        return info

    def reset(self, *, seed: int | None = None, options: dict | None = None):
        super().reset(seed=seed)
        options = options or {}
        unknown = set(options) - {"start_index"}
        if unknown:
            raise ValueError(f"Unsupported reset options: {sorted(unknown)}")
        if "start_index" in options:
            start_index = int(options["start_index"])
        elif self.random_start:
            latest_full_horizon_start = max(0, self.n_rows - 1 - self.max_episode_steps)
            start_index = int(self.np_random.integers(0, latest_full_horizon_start + 1))
        else:
            start_index = 0
        if not (0 <= start_index < self.n_rows - 1):
            raise ValueError("start_index must leave at least one next-open execution row")
        self._episode_start_index = start_index
        self._clear_episode_state()
        info = self._info()
        info["episode_start_date"] = self._date_label(start_index)
        info["episode_start_index"] = start_index
        info["initial_capital"] = 1.0
        return self._observation(), info

    def step(self, action):
        if self._done:
            raise RuntimeError("step() called after episode completion; call reset()")
        array = np.asarray(action)
        if array.size != 1:
            raise ValueError("action must be one scalar target position")
        try:
            numeric_action = float(array.reshape(-1)[0])
        except (TypeError, ValueError) as exc:
            raise ValueError("action must be an integer target position") from exc
        if not np.isfinite(numeric_action) or not numeric_action.is_integer():
            raise ValueError("action must be an integer target position")
        action = int(numeric_action)
        if action not in (ACTION_OUT, ACTION_IN):
            raise ValueError("action must be 0 (OUT) or 1 (IN)")
        masks = self.action_masks()
        if not masks[action]:
            raise ValueError(
                f"Action {action} is invalid in state position={int(self._position_in)}, "
                f"holding_intervals={self._holding_intervals()}"
            )

        decision_index = self._market_index
        execution_index = decision_index + 1
        self._episode_steps += 1
        reward = 0.0
        terminated = False
        truncated = False

        if not self._position_in and action == ACTION_IN:
            self._entry_index = execution_index
            self._entry_price = float(self.open_prices[execution_index])
            # The decision-time estimate at t is known when the next-open entry
            # is submitted; do not use volatility first observed on entry day.
            self._entry_volatility_scale = float(self.daily_volatility_scale[decision_index])
            self._entry_wait_steps = self._wait_steps
            self._shares = 1.0 / self._entry_price
            self._cash = 0.0
            self._position_in = True
        elif not self._position_in and action == ACTION_OUT:
            self._wait_steps += 1
        elif self._position_in and action == ACTION_OUT:
            self._exit_index = execution_index
            self._exit_price = float(self.open_prices[execution_index])
            self._last_trade_intervals = execution_index - int(self._entry_index)
            reward = annualized_log_excess_reward(
                float(self._entry_price),
                self._exit_price,
                self._last_trade_intervals,
                annualization_intervals=self.annualization_intervals,
                annual_benchmark=self.annual_benchmark,
            )
            self._raw_trade_return = self._exit_price / float(self._entry_price) - 1.0
            self._annualized_log_trade_return = (
                self.annualization_intervals
                / self._last_trade_intervals
                * (np.log(self._exit_price) - np.log(float(self._entry_price)))
            )
            self._terminal_reward = reward
            self._cash = self._shares * self._exit_price
            self._shares = 0.0
            self._position_in = False
            terminated = True
            self._done = True
        # IN while already invested means HOLD; all non-SELL transitions reward zero.

        self._market_index = execution_index
        if not terminated:
            reason = self._truncation_reason()
            if reason is not None:
                truncated = True
                self._done = True
        observation = self._observation()
        info = self._info(action=action)
        if truncated:
            reason = self._truncation_reason()
            info["truncation_reason"] = reason
            if self._position_in:
                info["truncated_open_position_value"] = info["mark_to_market_portfolio_value"]
        if terminated:
            info["terminal_rl_reward"] = float(reward)
        return observation, float(reward), terminated, truncated, info

    def _truncation_reason(self) -> str | None:
        if self._market_index >= self.n_rows - 1:
            return "data_end"
        if self._episode_steps >= self.max_episode_steps:
            return "max_episode_steps"
        if not self._position_in and self._wait_steps >= self.max_wait_steps:
            return "max_wait_steps"
        if self._position_in and self._holding_intervals() >= self.max_holding_intervals:
            return "max_holding_intervals"
        return None
