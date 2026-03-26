"""Shared environment construction helpers for training-oriented entrypoints."""

from __future__ import annotations

import os
from argparse import Namespace
from typing import Optional

from stable_baselines3.common.monitor import Monitor

from vn_stock_rl.env import MultiStockEnv, TradingEnv


def filter_help_tickers(help_list, primary_stock, primary_stocks, use_all):
    if not help_list:
        return None
    if use_all:
        return [t.upper() for t in help_list]
    base = set()
    if primary_stock:
        base.add(primary_stock.upper())
    if primary_stocks:
        base |= {s.upper() for s in primary_stocks}
    return [t.upper() for t in help_list if t.upper() not in base]


def build_env_from_args(args: Namespace):
    return build_training_env(
        mode="train",
        stock=args.stock,
        stocks=args.stocks,
        all_stocks=args.all_stocks,
        data_dir=args.data_dir,
        drawdown_penalty_enabled=getattr(args, "drawdown_penalty_enabled", None),
        drawdown_penalty_lambda=getattr(args, "drawdown_penalty_lambda", None),
        drawdown_penalty_train_only=(False if getattr(args, "drawdown_penalty_all_modes", False) else None),
        reward_benchmark=getattr(args, "reward_benchmark", None),
        benchmark_weight=getattr(args, "benchmark_weight", None),
        benchmark_relative_reward=getattr(args, "benchmark_relative_reward", None),
        train_episode_sampling_enabled=getattr(args, "train_episode_sampling_enabled", None),
        train_episode_min_fraction=getattr(args, "train_episode_min_fraction", None),
        train_episode_max_fraction=getattr(args, "train_episode_max_fraction", None),
        start_date=getattr(args, "start_date", None),
        end_date=getattr(args, "end_date", None),
        source_mode=getattr(args, "source_mode", None),
        ma_windows=getattr(args, "ma_windows", None),
        helpers_ma_windows=getattr(args, "helpers_ma_windows", None),
        returns_windows=getattr(args, "returns_windows", None),
        helpers_returns_windows=getattr(args, "helpers_returns_windows", None),
        engineered_features=getattr(args, "engineered_features", None),
        window_policy=getattr(args, "window_policy", None),
        feature_windows=getattr(args, "feature_windows", None),
        logspace_min=getattr(args, "logspace_min", None),
        logspace_max=getattr(args, "logspace_max", None),
        logspace_count=getattr(args, "logspace_count", None),
        rs_market_proxies=getattr(args, "rs_market_proxies", None),
        rs_include_long=(False if getattr(args, "rs_no_long", False) else None),
        calendar_features=getattr(args, "calendar_features", None),
        news_feature_columns=getattr(args, "news_feature_columns", None),
        news_prediction_dir=getattr(args, "news_prediction_dir", None),
        signal_feature_columns=getattr(args, "signal_feature_columns", None),
        signal_prediction_dir=getattr(args, "signal_prediction_dir", None),
        help_tickers=filter_help_tickers(args.help_tickers, args.stock, args.stocks, args.all_stocks),
        market_data_dir=args.market_data_dir,
        help_assets=[a.lower() for a in args.help_assets] if args.help_assets else None,
        help_assets_dir=args.help_assets_dir,
    )


def build_training_env(
    *,
    mode: str,
    stock: str,
    stocks: list,
    all_stocks: bool,
    data_dir: str,
    drawdown_penalty_enabled: Optional[bool],
    drawdown_penalty_lambda: Optional[float],
    drawdown_penalty_train_only: Optional[bool],
    reward_benchmark: Optional[str],
    benchmark_weight: Optional[float],
    benchmark_relative_reward: Optional[bool],
    train_episode_sampling_enabled: Optional[bool],
    train_episode_min_fraction: Optional[float],
    train_episode_max_fraction: Optional[float],
    start_date: Optional[str],
    end_date: Optional[str],
    source_mode: Optional[str],
    ma_windows: list,
    helpers_ma_windows: list,
    returns_windows: list,
    helpers_returns_windows: list,
    engineered_features: Optional[list],
    window_policy: Optional[str],
    feature_windows: Optional[list],
    logspace_min: Optional[int],
    logspace_max: Optional[int],
    logspace_count: Optional[int],
    rs_market_proxies: Optional[list],
    rs_include_long: Optional[bool],
    calendar_features: Optional[list],
    news_feature_columns: Optional[list],
    news_prediction_dir: Optional[str],
    signal_feature_columns: Optional[list],
    signal_prediction_dir: Optional[str],
    help_tickers: list,
    market_data_dir: str,
    help_assets: list,
    help_assets_dir: str,
    monitor_path_or_none: Optional[str] = None,
):
    if all_stocks or stocks:
        env = MultiStockEnv(
            data_dir=data_dir,
            mode=mode,
            stocks=stocks,
            drawdown_penalty_enabled=drawdown_penalty_enabled,
            drawdown_penalty_lambda=drawdown_penalty_lambda,
            drawdown_penalty_train_only=drawdown_penalty_train_only,
            reward_benchmark=reward_benchmark,
            benchmark_weight=benchmark_weight,
            benchmark_relative_reward=benchmark_relative_reward,
            train_episode_sampling_enabled=train_episode_sampling_enabled,
            train_episode_min_fraction=train_episode_min_fraction,
            train_episode_max_fraction=train_episode_max_fraction,
            start_date=start_date,
            end_date=end_date,
            source_mode=source_mode,
            ma_windows=ma_windows,
            helpers_ma_windows=helpers_ma_windows,
            returns_windows=returns_windows,
            helpers_returns_windows=helpers_returns_windows,
            engineered_features=engineered_features,
            window_policy=window_policy,
            feature_windows=feature_windows,
            logspace_min=logspace_min,
            logspace_max=logspace_max,
            logspace_count=logspace_count,
            rs_market_proxies=rs_market_proxies,
            rs_include_long=rs_include_long,
            calendar_features=calendar_features,
            news_feature_columns=news_feature_columns,
            news_prediction_dir=news_prediction_dir,
            signal_feature_columns=signal_feature_columns,
            signal_prediction_dir=signal_prediction_dir,
            help_tickers=help_tickers,
            market_data_dir=market_data_dir,
            help_assets=help_assets,
            help_assets_dir=help_assets_dir,
        )
    else:
        data_path = os.path.join(data_dir, f"gia_lich_su_{stock}_1D.parquet")
        env = TradingEnv(
            data_path=data_path,
            mode=mode,
            drawdown_penalty_enabled=drawdown_penalty_enabled,
            drawdown_penalty_lambda=drawdown_penalty_lambda,
            drawdown_penalty_train_only=drawdown_penalty_train_only,
            reward_benchmark=reward_benchmark,
            benchmark_weight=benchmark_weight,
            benchmark_relative_reward=benchmark_relative_reward,
            train_episode_sampling_enabled=train_episode_sampling_enabled,
            train_episode_min_fraction=train_episode_min_fraction,
            train_episode_max_fraction=train_episode_max_fraction,
            start_date=start_date,
            end_date=end_date,
            source_mode=source_mode,
            ma_windows=ma_windows,
            helpers_ma_windows=helpers_ma_windows,
            returns_windows=returns_windows,
            helpers_returns_windows=helpers_returns_windows,
            engineered_features=engineered_features,
            window_policy=window_policy,
            feature_windows=feature_windows,
            logspace_min=logspace_min,
            logspace_max=logspace_max,
            logspace_count=logspace_count,
            rs_market_proxies=rs_market_proxies,
            rs_include_long=rs_include_long,
            calendar_features=calendar_features,
            news_feature_columns=news_feature_columns,
            news_prediction_dir=news_prediction_dir,
            signal_feature_columns=signal_feature_columns,
            signal_prediction_dir=signal_prediction_dir,
            help_tickers=help_tickers,
            market_data_dir=market_data_dir,
            help_assets=help_assets,
            help_assets_dir=help_assets_dir,
        )

    if monitor_path_or_none is None:
        return env
    if monitor_path_or_none == "":
        return Monitor(env)
    return Monitor(env, monitor_path_or_none)
