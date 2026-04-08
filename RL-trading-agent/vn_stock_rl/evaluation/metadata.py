from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd

from vn_stock_rl.external_features import default_help_assets_dir, default_market_data_dir, default_stock_data_dir
from vn_stock_rl.policies.registry import read_policy_from_metadata

_read_policy_from_metadata = read_policy_from_metadata
def _to_json_safe(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (np.ndarray,)):
        return value.tolist()
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _to_json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_json_safe(v) for v in value]
    return value

def _load_eval_meta(model_path: str) -> Optional[dict]:
    meta_path = os.path.splitext(model_path)[0] + "_meta.json"
    if not os.path.exists(meta_path):
        return None
    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        return meta if isinstance(meta, dict) else None
    except Exception:
        return None

def _resolve_helper_inputs_from_meta(
    meta: Optional[dict],
    data_dir: str,
    help_tickers: Optional[list],
    market_data_dir: str,
    help_assets: Optional[list],
    help_assets_dir: str,
) -> Tuple[str, Optional[list], str, Optional[list], str]:
    if not isinstance(meta, dict):
        return data_dir, help_tickers, market_data_dir, help_assets, help_assets_dir
    if _is_default_shared_path(data_dir, default_stock_data_dir(), "data/stock/") and meta.get("data_dir"):
        data_dir = meta["data_dir"]
    if help_tickers is None:
        help_tickers = meta.get("help_tickers") or None
    if _is_default_shared_path(market_data_dir, default_market_data_dir(), "data/stock/") and meta.get(
        "market_data_dir"
    ):
        market_data_dir = meta["market_data_dir"]
    if help_assets is None:
        help_assets = meta.get("help_assets") or None
    if _is_default_shared_path(
        help_assets_dir,
        default_help_assets_dir(),
        "data/fx-commodities/",
    ) and meta.get("help_assets_dir"):
        help_assets_dir = meta["help_assets_dir"]
    return data_dir, help_tickers, market_data_dir, help_assets, help_assets_dir


def _is_default_shared_path(value: str, canonical_default: Path, legacy_default: str) -> bool:
    candidate = Path(str(value)).expanduser()
    if str(candidate).rstrip("/\\") == legacy_default.rstrip("/\\"):
        return True
    return candidate == Path(canonical_default).expanduser()

def _merge_env_overrides(
    meta: Optional[dict],
    explicit_env_overrides: Dict[str, Optional[Any]],
    forced_policy: Optional[str],
) -> Dict[str, Any]:
    env_kwargs: Dict[str, Any] = {}
    if isinstance(meta, dict):
        meta_env = meta.get("environment_config")
        if isinstance(meta_env, dict):
            meta_input_features = meta_env.get("input_features")
            if isinstance(meta_input_features, dict):
                input_source_mode = meta_input_features.get("source_mode")
                input_ohlcv = meta_input_features.get("ohlcv")
                input_ma = meta_input_features.get("ma_windows")
                input_helpers_ma = meta_input_features.get("helpers_ma_windows")
                input_returns = meta_input_features.get("returns_windows")
                input_helpers_returns = meta_input_features.get("helpers_returns_windows")
                input_calendar = meta_input_features.get("calendar")
                input_news = meta_input_features.get("news_features")
                input_signal = meta_input_features.get("signal_features")
                input_portfolio = meta_input_features.get("portfolio_features")
                input_sample_start = meta_input_features.get("sample_start_date")
                input_sample_end = meta_input_features.get("sample_end_date")
                input_start_episode_position = meta_input_features.get("start_episode_position")
                input_engineered_block = meta_input_features.get("engineered_features")
                input_train_episode_sampling = meta_input_features.get("train_episode_sampling")
                input_reward_shaping = meta_input_features.get("reward_shaping")
                if input_source_mode is not None:
                    env_kwargs["source_mode"] = input_source_mode
                if input_ohlcv is not None:
                    env_kwargs["ohlcv"] = input_ohlcv
                if input_ma is not None:
                    env_kwargs["ma_windows"] = input_ma
                if input_helpers_ma is not None:
                    env_kwargs["helpers_ma_windows"] = input_helpers_ma
                if input_returns is not None:
                    env_kwargs["returns_windows"] = input_returns
                if input_helpers_returns is not None:
                    env_kwargs["helpers_returns_windows"] = input_helpers_returns
                if input_calendar is not None:
                    env_kwargs["calendar_features"] = input_calendar
                if isinstance(input_news, dict):
                    if input_news.get("columns") is not None:
                        env_kwargs["news_feature_columns"] = input_news.get("columns")
                    if input_news.get("prediction_dir") is not None:
                        env_kwargs["news_prediction_dir"] = input_news.get("prediction_dir")
                if isinstance(input_signal, dict):
                    if input_signal.get("columns") is not None:
                        env_kwargs["signal_feature_columns"] = input_signal.get("columns")
                    if input_signal.get("prediction_dir") is not None:
                        env_kwargs["signal_prediction_dir"] = input_signal.get("prediction_dir")
                if isinstance(input_portfolio, dict):
                    if input_portfolio.get("mode") is not None:
                        env_kwargs["portfolio_choice"] = input_portfolio.get("mode")
                    if input_portfolio.get("universe_size") is not None:
                        env_kwargs["portfolio_universe_size"] = input_portfolio.get("universe_size")
                    if input_portfolio.get("top_k") is not None:
                        env_kwargs["portfolio_top_k"] = input_portfolio.get("top_k")
                    if input_portfolio.get("universe_tickers") is not None:
                        env_kwargs["portfolio_universe_tickers"] = input_portfolio.get("universe_tickers")
                if input_sample_start is not None:
                    env_kwargs["start_date"] = input_sample_start
                if input_sample_end is not None:
                    env_kwargs["end_date"] = input_sample_end
                if input_start_episode_position is not None:
                    env_kwargs["start_episode_position"] = input_start_episode_position
                if isinstance(input_engineered_block, dict):
                    enabled = input_engineered_block.get("enabled")
                    if enabled is not None:
                        env_kwargs["engineered_features"] = enabled
                    wp = input_engineered_block.get("window_policy")
                    if isinstance(wp, dict):
                        if wp.get("mode") is not None:
                            env_kwargs["window_policy"] = wp.get("mode")
                        if wp.get("explicit_windows") is not None:
                            env_kwargs["feature_windows"] = wp.get("explicit_windows")
                        if wp.get("logspace_min") is not None:
                            env_kwargs["logspace_min"] = wp.get("logspace_min")
                        if wp.get("logspace_max") is not None:
                            env_kwargs["logspace_max"] = wp.get("logspace_max")
                        if wp.get("logspace_count") is not None:
                            env_kwargs["logspace_count"] = wp.get("logspace_count")
                    rs_cfg = input_engineered_block.get("relative_strength")
                    if isinstance(rs_cfg, dict):
                        if rs_cfg.get("market_proxy_preference") is not None:
                            env_kwargs["rs_market_proxies"] = rs_cfg.get("market_proxy_preference")
                        if rs_cfg.get("include_long_horizon") is not None:
                            env_kwargs["rs_include_long"] = rs_cfg.get("include_long_horizon")
                if isinstance(input_train_episode_sampling, dict):
                    if input_train_episode_sampling.get("enabled") is not None:
                        env_kwargs["train_episode_sampling_enabled"] = input_train_episode_sampling.get("enabled")
                    if input_train_episode_sampling.get("min_fraction") is not None:
                        env_kwargs["train_episode_min_fraction"] = input_train_episode_sampling.get("min_fraction")
                    if input_train_episode_sampling.get("max_fraction") is not None:
                        env_kwargs["train_episode_max_fraction"] = input_train_episode_sampling.get("max_fraction")
                if isinstance(input_reward_shaping, dict):
                    dd_cfg = input_reward_shaping.get("drawdown_penalty")
                    if isinstance(dd_cfg, dict):
                        if dd_cfg.get("enabled") is not None:
                            env_kwargs["drawdown_penalty_enabled"] = dd_cfg.get("enabled")
                        if dd_cfg.get("lambda") is not None:
                            env_kwargs["drawdown_penalty_lambda"] = dd_cfg.get("lambda")
                        if dd_cfg.get("train_only") is not None:
                            env_kwargs["drawdown_penalty_train_only"] = dd_cfg.get("train_only")
                    br_cfg = input_reward_shaping.get("benchmark_relative")
                    if isinstance(br_cfg, dict):
                        if br_cfg.get("enabled") is not None:
                            env_kwargs["benchmark_relative_reward"] = br_cfg.get("enabled")
                        if br_cfg.get("benchmark") is not None:
                            env_kwargs["reward_benchmark"] = br_cfg.get("benchmark")
                        if br_cfg.get("weight") is not None:
                            env_kwargs["benchmark_weight"] = br_cfg.get("weight")
            meta_reward_shaping = meta_env.get("reward_shaping")
            if isinstance(meta_reward_shaping, dict):
                dd_cfg = meta_reward_shaping.get("drawdown_penalty")
                if isinstance(dd_cfg, dict):
                    if dd_cfg.get("enabled") is not None:
                        env_kwargs["drawdown_penalty_enabled"] = dd_cfg.get("enabled")
                    if dd_cfg.get("lambda") is not None:
                        env_kwargs["drawdown_penalty_lambda"] = dd_cfg.get("lambda")
                    if dd_cfg.get("train_only") is not None:
                        env_kwargs["drawdown_penalty_train_only"] = dd_cfg.get("train_only")
                br_cfg = meta_reward_shaping.get("benchmark_relative")
                if isinstance(br_cfg, dict):
                    if br_cfg.get("enabled") is not None:
                        env_kwargs["benchmark_relative_reward"] = br_cfg.get("enabled")
                    if br_cfg.get("benchmark") is not None:
                        env_kwargs["reward_benchmark"] = br_cfg.get("benchmark")
                    if br_cfg.get("weight") is not None:
                        env_kwargs["benchmark_weight"] = br_cfg.get("weight")

            for key in (
                "lookback_window",
                "source_mode",
                "ohlcv",
                "ma_windows",
                "helpers_ma_windows",
                "returns_windows",
                "helpers_returns_windows",
                "engineered_features",
                "window_policy",
                "feature_windows",
                "logspace_min",
                "logspace_max",
                "logspace_count",
                "rs_market_proxies",
                "rs_include_long",
                "news_feature_columns",
                "news_prediction_dir",
                "signal_feature_columns",
                "signal_prediction_dir",
                "portfolio_choice",
                "portfolio_universe_size",
                "portfolio_top_k",
                "portfolio_universe_tickers",
                "start_date",
                "end_date",
                "train_episode_sampling_enabled",
                "train_episode_min_fraction",
                "train_episode_max_fraction",
                "start_episode_position",
                "drawdown_penalty_enabled",
                "drawdown_penalty_lambda",
                "drawdown_penalty_train_only",
                "benchmark_relative_reward",
                "reward_benchmark",
                "benchmark_weight",
                "reward_shaping",
                "calendar_features",
                "train_split",
                "val_split",
                "min_hold_days",
                "buy_fee_rate",
                "sell_fee_rate",
                "capital_gains_tax_rate",
                "stop_loss",
            ):
                value = meta_env.get(key)
                if value is not None:
                    env_kwargs[key] = value
    for key, value in explicit_env_overrides.items():
        if value is not None:
            env_kwargs[key] = value
    if forced_policy == "buy_hold":
        env_kwargs["stop_loss"] = None
    return env_kwargs
