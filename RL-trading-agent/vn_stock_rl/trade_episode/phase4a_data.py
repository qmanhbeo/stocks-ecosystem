"""Read-only multi-stock Phase 4A data preparation and environment builders."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from vn_stock_rl.trade_episode.causal_features import (
    CAUSAL_MARKET_FEATURE_NAMES,
    TRAILING_VOLATILITY_WINDOW,
    build_causal_normalized_market_features,
    causal_feature_warmup_mask,
)
from vn_stock_rl.trade_episode.data import load_daily_stock_bars, load_daily_tradability_flags
from vn_stock_rl.trade_episode.environment import TradeEpisodeEnv
from vn_stock_rl.trade_episode.multi_stock_environment import MultiStockEpisodeEnv
from vn_stock_rl.trade_episode.signals import ALPHA_FEATURE_NAMES, load_alpha_signals

DATA_CUTOFF = pd.Timestamp("2025-12-31")
FEATURE_START = pd.Timestamp("2015-01-01")
HISTORICAL_LOOKBACK_START = pd.Timestamp("2014-09-01")
SPLIT_BOUNDS = {
    "train": (pd.Timestamp("2015-01-01"), pd.Timestamp("2019-12-31")),
    "validation": (pd.Timestamp("2020-01-01"), pd.Timestamp("2022-12-31")),
    "test": (pd.Timestamp("2023-01-01"), DATA_CUTOFF),
}

# BCG's ended/suspended history is retained to reduce current-survivor-only
# bias. MBB, DGC, and VHC never enter training.
TRAIN_TICKERS = (
    "ACB",
    "BCG",
    "FPT",
    "GAS",
    "HPG",
    "MWG",
    "PVD",
    "REE",
    "SSI",
    "VCB",
    "VIC",
    "VNM",
)
UNSEEN_TICKERS = ("DGC", "MBB", "VHC")
PHASE4A_TICKERS = (*TRAIN_TICKERS, *UNSEEN_TICKERS)


@dataclass(frozen=True)
class PreparedStock:
    ticker: str
    dates: pd.DatetimeIndex
    opens: np.ndarray
    closes: np.ndarray
    market_features: np.ndarray
    alpha_features: np.ndarray
    daily_volatility_scale: np.ndarray
    can_buy: np.ndarray
    can_sell: np.ndarray
    split_masks: dict[str, np.ndarray]
    metadata: dict[str, Any]

    @property
    def market_feature_names(self) -> list[str]:
        return list(CAUSAL_MARKET_FEATURE_NAMES)

    @property
    def alpha_feature_names(self) -> list[str]:
        return list(ALPHA_FEATURE_NAMES)

    def feature_matrix(self, include_alpha: bool) -> tuple[np.ndarray, list[str]]:
        if not include_alpha:
            return self.market_features, self.market_feature_names
        matrix = np.column_stack((self.market_features, self.alpha_features)).astype(np.float32)
        return matrix, self.market_feature_names + self.alpha_feature_names


def _split_mask(dates: pd.DatetimeIndex, split: str) -> np.ndarray:
    start, end = SPLIT_BOUNDS[split]
    return np.asarray((dates >= start) & (dates <= end), dtype=bool)


def alpha_observation_matrix(alpha_frame: pd.DataFrame) -> np.ndarray:
    """Return bounded alpha inputs with explicit missingness indicators."""

    result = alpha_frame.loc[:, ALPHA_FEATURE_NAMES].copy()
    for signal_name in ("alpha_s1_xs_proba", "alpha_c16_order_volume_ratio_rank"):
        result[signal_name] = result[signal_name].fillna(0.5)
        values = result[signal_name].to_numpy(dtype=np.float64)
        if not np.isfinite(values).all() or ((values < 0) | (values > 1)).any():
            raise ValueError(f"{signal_name} must be finite and bounded")
    for availability_name in ("alpha_s1_available", "alpha_c16_available"):
        values = result[availability_name].to_numpy(dtype=np.float64)
        if not np.isfinite(values).all() or not np.isin(values, (0.0, 1.0)).all():
            raise ValueError(f"{availability_name} must be a finite binary indicator")
    return result.to_numpy(dtype=np.float32)


def prepare_stock(ticker: str, *, data_root: str | Path) -> PreparedStock:
    """Filter to the allowed cutoff before building any derived feature."""

    symbol = str(ticker).strip().upper()
    bars = load_daily_stock_bars(
        symbol,
        data_root=data_root,
        start_date=HISTORICAL_LOOKBACK_START,
        end_date=DATA_CUTOFF,
    )
    source_dates = pd.DatetimeIndex(bars["time"].dt.normalize())
    if source_dates.max() > DATA_CUTOFF:
        raise RuntimeError(f"{symbol}: post-cutoff OHLCV reached feature construction")
    if source_dates.has_duplicates or not source_dates.is_monotonic_increasing:
        raise ValueError(f"{symbol}: OHLCV dates must be unique and chronological")

    market_frame, volatility_scale = build_causal_normalized_market_features(bars)
    warm = causal_feature_warmup_mask(market_frame, volatility_scale)
    keep = warm & np.asarray(source_dates >= FEATURE_START, dtype=bool)
    if not keep.any():
        raise ValueError(f"{symbol}: no feature rows remain after causal warm-up")

    alpha_frame = load_alpha_signals(symbol, source_dates, data_root=data_root)
    if alpha_frame.index.has_duplicates:
        raise ValueError(f"{symbol}: alpha dates must be unique")
    # The 0.5 value is a sentinel only; availability bits remain authoritative.
    alpha_values = alpha_observation_matrix(alpha_frame)

    selected_bars = bars.loc[keep].reset_index(drop=True)
    dates = pd.DatetimeIndex(selected_bars["time"].dt.normalize())
    market_selected = market_frame.loc[keep].to_numpy(dtype=np.float32)
    alpha_selected = alpha_values[keep]
    volatility_selected = volatility_scale.to_numpy(dtype=np.float64)[keep]
    if dates.max() > DATA_CUTOFF:
        raise RuntimeError(f"{symbol}: prepared data exceeds 2025-12-31")
    if not np.isfinite(market_selected).all() or not np.isfinite(alpha_selected).all():
        raise ValueError(f"{symbol}: prepared observations contain non-finite features")

    can_buy, can_sell = load_daily_tradability_flags(
        symbol, selected_bars["time"], data_root=data_root
    )
    split_masks = {name: _split_mask(dates, name) for name in SPLIT_BOUNDS}
    for name, mask in split_masks.items():
        if not mask.any():
            raise ValueError(f"{symbol}: {name} split has no rows")
        if not can_buy.to_numpy()[mask].any() or not can_sell.to_numpy()[mask].any():
            raise ValueError(f"{symbol}: {name} split has no legal buy or sell opportunity")

    metadata: dict[str, Any] = {
        "ticker": symbol,
        "date_start": str(dates.min().date()),
        "date_end": str(dates.max().date()),
        "rows": int(len(dates)),
        "future_rows_after_cutoff_used": False,
        "causal_volatility_window": TRAILING_VOLATILITY_WINDOW,
        "training_mean_std_fit": False,
        "split_dates": {},
        "alpha_coverage_pct": {},
        "tradable_buy_days": {},
        "tradable_sell_days": {},
        "sentinel_policy": "missing bounded S1/C16 values become 0.5 with availability=0",
    }
    for name, mask in split_masks.items():
        metadata["split_dates"][name] = {
            "start": str(dates[mask].min().date()),
            "end": str(dates[mask].max().date()),
            "rows": int(mask.sum()),
        }
        metadata["alpha_coverage_pct"][name] = {
            "s1": float(alpha_selected[mask, 1].mean() * 100.0),
            "c16": float(alpha_selected[mask, 3].mean() * 100.0),
        }
        metadata["tradable_buy_days"][name] = int(can_buy.to_numpy()[mask].sum())
        metadata["tradable_sell_days"][name] = int(can_sell.to_numpy()[mask].sum())

    return PreparedStock(
        ticker=symbol,
        dates=dates,
        opens=selected_bars["open"].to_numpy(dtype=np.float64),
        closes=selected_bars["close"].to_numpy(dtype=np.float64),
        market_features=market_selected,
        alpha_features=alpha_selected,
        daily_volatility_scale=volatility_selected,
        can_buy=can_buy.to_numpy(dtype=bool),
        can_sell=can_sell.to_numpy(dtype=bool),
        split_masks=split_masks,
        metadata=metadata,
    )


def make_stock_env(
    stock: PreparedStock,
    split_mask: np.ndarray,
    *,
    env_cfg: dict[str, Any],
    include_alpha: bool,
) -> TradeEpisodeEnv:
    selected = np.flatnonzero(np.asarray(split_mask, dtype=bool))
    if selected.size < 2 or selected[-1] - selected[0] + 1 != selected.size:
        raise ValueError(f"{stock.ticker}: environment slice must be contiguous and have 2+ rows")
    first, last = int(selected[0]), int(selected[-1]) + 1
    features, names = stock.feature_matrix(include_alpha)
    return TradeEpisodeEnv(
        stock.opens[first:last],
        stock.closes[first:last],
        price_basis="user_assumed_dividend_adjusted",
        market_features=features[first:last],
        feature_names=names,
        dates=stock.dates[first:last],
        can_buy_next_open=stock.can_buy[first:last],
        can_sell_next_open=stock.can_sell[first:last],
        daily_volatility_scale=stock.daily_volatility_scale[first:last],
        min_holding_intervals=int(env_cfg.get("min_holding_intervals", 3)),
        max_episode_steps=int(env_cfg["max_episode_steps"]),
        max_wait_steps=int(env_cfg["max_wait_steps"]),
        max_holding_intervals=int(env_cfg["max_holding_intervals"]),
        annualization_intervals=int(env_cfg.get("annualization_intervals", 252)),
        annual_benchmark=float(env_cfg.get("annual_benchmark", 0.07)),
        ticker=stock.ticker,
        random_start=False,
    )


def make_multi_stock_train_env(
    stocks: dict[str, PreparedStock],
    *,
    tickers: tuple[str, ...],
    env_cfg: dict[str, Any],
    include_alpha: bool,
) -> MultiStockEpisodeEnv:
    environments: dict[str, TradeEpisodeEnv] = {}
    eligible_starts: dict[str, np.ndarray] = {}
    max_episode_steps = int(env_cfg["max_episode_steps"])
    for ticker in tickers:
        stock = stocks[ticker]
        train_mask = stock.split_masks["train"]
        env = make_stock_env(stock, train_mask, env_cfg=env_cfg, include_alpha=include_alpha)
        environments[ticker] = env
        last_full_horizon_start = env.n_rows - 1 - max_episode_steps
        latest = last_full_horizon_start if last_full_horizon_start >= 0 else env.n_rows - 5
        latest = max(0, latest)
        candidates = np.arange(latest + 1, dtype=np.int64)
        legal_trade_window = np.zeros(env.n_rows, dtype=bool)
        if env.n_rows > 4:
            legal_trade_window[: env.n_rows - 3] = env.can_buy_next_open[: env.n_rows - 3]
            legal_trade_window[: env.n_rows - 3] &= env.can_sell_next_open[3:]
        starts = candidates[legal_trade_window[candidates]]
        if starts.size == 0:
            env.close()
            raise ValueError(f"{ticker}: no start can support a legal minimum-duration trade")
        eligible_starts[ticker] = starts
    return MultiStockEpisodeEnv(
        environments,
        eligible_start_indices=eligible_starts,
    )
