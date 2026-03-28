from __future__ import annotations

import argparse
from typing import Optional

from vn_stock_rl.config.cli_shared import (
    parse_engineered_feature_families,
    parse_helper_window_list,
    parse_news_feature_columns,
    parse_reward_benchmark,
    parse_rs_market_proxies,
    parse_signal_feature_columns,
    parse_window_list,
)
from vn_stock_rl.external_features import default_help_assets_dir, default_market_data_dir, default_stock_data_dir

_parse_window_list = parse_window_list
_parse_helper_window_list = parse_helper_window_list
_parse_engineered_feature_families = parse_engineered_feature_families
_parse_rs_market_proxies = parse_rs_market_proxies
_parse_news_feature_columns = parse_news_feature_columns
_parse_signal_feature_columns = parse_signal_feature_columns
_parse_reward_benchmark = parse_reward_benchmark


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Train RL trading agent")
    parser.add_argument("--stock", type=str, default=None,
                        help="Stock ticker (e.g., ACB) for single-stock training")
    parser.add_argument("--stocks", type=str, nargs='+', default=None,
                        help="List of stock tickers (e.g., ACB VNM HPG) for multi-stock training")
    parser.add_argument("--all-stocks", action="store_true",
                        help="Train on all stocks in data directory")
    parser.add_argument(
        "--portfolio-choice",
        action="store_true",
        help="Train a portfolio-choice agent over a fixed cross-sectional universe",
    )
    parser.add_argument(
        "--portfolio-universe-size",
        type=int,
        default=20,
        help="Number of liquid stocks in the fixed portfolio universe (default: 20)",
    )
    parser.add_argument(
        "--portfolio-top-k",
        type=int,
        default=3,
        help="Number of stock slots the policy can select each rebalance (default: 3)",
    )
    parser.add_argument("--data-dir", type=str, default=str(default_stock_data_dir()),
                        help="Directory containing parquet files")
    drawdown_group = parser.add_mutually_exclusive_group()
    drawdown_group.add_argument(
        "--drawdown-penalty",
        dest="drawdown_penalty_enabled",
        action="store_true",
        help="Enable drawdown penalty reward shaping",
    )
    drawdown_group.add_argument(
        "--no-drawdown-penalty",
        dest="drawdown_penalty_enabled",
        action="store_false",
        help="Disable drawdown penalty reward shaping",
    )
    parser.set_defaults(drawdown_penalty_enabled=None)
    parser.add_argument(
        "--drawdown-penalty-lambda",
        type=float,
        default=None,
        help="Drawdown penalty strength (>=0)",
    )
    parser.add_argument(
        "--drawdown-penalty-all-modes",
        action="store_true",
        help="Apply drawdown penalty in all modes (default is train-only)",
    )
    benchmark_reward_group = parser.add_mutually_exclusive_group()
    benchmark_reward_group.add_argument(
        "--benchmark-relative-reward",
        dest="benchmark_relative_reward",
        action="store_true",
        help="Optimize benchmark-relative reward (agent return minus weighted benchmark return)",
    )
    benchmark_reward_group.add_argument(
        "--no-benchmark-relative-reward",
        dest="benchmark_relative_reward",
        action="store_false",
        help="Disable benchmark-relative reward shaping",
    )
    parser.set_defaults(benchmark_relative_reward=None)
    parser.add_argument(
        "--reward-benchmark",
        type=str,
        default=None,
        help="Benchmark for relative reward shaping (currently: self_buy_hold)",
    )
    parser.add_argument(
        "--benchmark-weight",
        type=float,
        default=None,
        help="Weight applied to benchmark return when benchmark-relative reward is enabled",
    )
    train_sampling_group = parser.add_mutually_exclusive_group()
    train_sampling_group.add_argument(
        "--train-episode-sampling",
        dest="train_episode_sampling_enabled",
        action="store_true",
        help="Enable randomized train sub-episode windows",
    )
    train_sampling_group.add_argument(
        "--no-train-episode-sampling",
        dest="train_episode_sampling_enabled",
        action="store_false",
        help="Disable randomized train sub-episode windows",
    )
    parser.set_defaults(train_episode_sampling_enabled=None)
    parser.add_argument(
        "--train-episode-min-fraction",
        type=float,
        default=None,
        help="Minimum train sub-episode length as fraction of train split (0,1]",
    )
    parser.add_argument(
        "--train-episode-max-fraction",
        type=float,
        default=None,
        help="Maximum train sub-episode length as fraction of train split (0,1]",
    )
    parser.add_argument("--start-date", type=str, default=None,
                        help="Inclusive sample start date before train/val/test split (YYYY-MM-DD)")
    parser.add_argument("--end-date", type=str, default=None,
                        help="Inclusive sample end date before train/val/test split (YYYY-MM-DD)")
    parser.add_argument("--source-mode", type=str, choices=["raw", "return"], default=None,
                        help="Override feature source mode: raw levels or return features")
    parser.add_argument("--ma-windows", type=int, nargs='+', default=None,
                        help="Moving-average windows as extra features (e.g., 5 10 20)")
    parser.add_argument("--helpers-ma-windows", type=str, nargs='+', default=None,
                        help="Helper MA windows (e.g., 5 10) or 'same' to match target ma_windows")
    parser.add_argument("--returns-windows", type=int, nargs='+', default=None,
                        help="Close-based return windows as extra features (e.g., 5 10 20)")
    parser.add_argument("--helpers-returns-windows", type=str, nargs='+', default=None,
                        help="Helper return windows (e.g., 5 10) or 'same' to match target returns_windows")
    parser.add_argument(
        "--engineered-features",
        type=str,
        nargs='+',
        choices=["volatility", "trend", "momentum", "volume_context", "drawdown", "relative_strength"],
        default=None,
        help="Engineered feature families to enable",
    )
    parser.add_argument("--window-policy", type=str, choices=["explicit", "logspace"], default=None,
                        help="Engineered feature window policy override")
    parser.add_argument("--feature-windows", type=int, nargs='+', default=None,
                        help="Explicit engineered feature windows (used when window-policy=explicit)")
    parser.add_argument("--logspace-min", type=int, default=None,
                        help="Engineered logspace minimum window")
    parser.add_argument("--logspace-max", type=int, default=None,
                        help="Engineered logspace maximum window")
    parser.add_argument("--logspace-count", type=int, default=None,
                        help="Engineered logspace number of windows")
    parser.add_argument("--rs-market-proxies", type=str, nargs='+', default=None,
                        help="Relative-strength market proxy preference (e.g., VNINDEX VN30)")
    parser.add_argument("--rs-no-long", action="store_true",
                        help="Disable long-horizon relative strength feature")
    parser.add_argument("--calendar-features", type=str, nargs='+', choices=["dow", "month", "dom"], default=None,
                        help="Calendar features to append (any of: dow month dom)")
    parser.add_argument(
        "--news-columns",
        type=str,
        nargs='+',
        default=None,
        help=(
            "Daily news feature columns to merge by date. Use 'tabular' for the exported "
            "tabular news set, 'all' to include embeddings too, or list explicit column names."
        ),
    )
    parser.add_argument(
        "--news-prediction-dir",
        type=str,
        default=None,
        help="Directory containing per-ticker news feature exports (defaults to data/features/news/predictions)",
    )
    parser.add_argument(
        "--signal-columns",
        type=str,
        nargs='+',
        default=None,
        help=(
            "Signal feature columns to merge by date. Use 'default' for the standard "
            "probability columns, 'all' for every exported signal column, or list explicit names."
        ),
    )
    parser.add_argument(
        "--signal-prediction-dir",
        type=str,
        default=None,
        help="Directory containing per-ticker signal exports (defaults to data/features/signals/predictions/auto)",
    )
    parser.add_argument("--help-tickers", type=str, nargs='+', default=None,
                        help="Helper tickers to append as features (e.g., VNINDEX VN30)")
    parser.add_argument("--market-data-dir", type=str, default=str(default_market_data_dir()),
                        help="Directory containing market parquet files")
    parser.add_argument("--help-assets", type=str, nargs='+', default=None,
                        help="Helper assets to append as features (e.g., fx_vnd_usd gold oil)")
    parser.add_argument("--help-assets-dir", type=str, default=str(default_help_assets_dir()),
                        help="Directory containing helper asset parquet files")
    parser.add_argument("--timesteps", type=int, default=500_000,
                        help="Total training timesteps")
    parser.add_argument("--name", type=str, default=None,
                        help="Model name (optional). If omitted, auto-generates {policy}_{stock}_{timesteps}_{timestamp}")
    parser.add_argument("--save-dir", type=str, default="artifacts/trained_models",
                        help="Root directory for per-run model artifacts")
    parser.add_argument("--log-dir", type=str, default="artifacts/trained_models",
                        help="Root directory for per-run logs")
    parser.add_argument("--n-envs", type=int, default=4,
                        help="Number of parallel environments (default: 4, use 1 to disable)")
    parser.add_argument(
        "--policy",
        type=str,
        default="mlp",
        choices=[
            'mlp',
            'lstm',
            'cnn',
            'cnn-lstm',
            'cnn_lstm',
            'cnn-attention',
            'cnn-attention-lstm',
            'cnn-window-attention',
            'cnn-window-attention-lstm',
            'multi-cnn',
            'multi-cnn-lstm',
            'transformer',
            'transformer-lstm',
        ],
        help=(
            "Policy architecture: 'mlp' (default), 'lstm', 'cnn', 'cnn-lstm' "
            "(legacy alias: 'cnn_lstm'), 'cnn-attention', 'cnn-attention-lstm', "
            "'cnn-window-attention', 'cnn-window-attention-lstm', "
            "'multi-cnn', 'multi-cnn-lstm', 'transformer', or 'transformer-lstm'."
        )
    )
    parser.add_argument("--ent-coef-start", type=float, default=0.01,
                        help="Starting entropy coefficient (default: 0.01)")
    parser.add_argument("--ent-coef-end", type=float, default=0.0,
                        help="Final entropy coefficient for scheduled decay (default: 0.0)")
    parser.add_argument("--ent-coef-schedule", type=str, default="constant",
                        choices=["constant", "linear", "cosine"],
                        help="Entropy schedule: constant, linear, or cosine")
    parser.add_argument("--eval-freq", type=int, default=50_000,
                        help="Evaluate on validation set every N global timesteps (default: 50000)")
    parser.add_argument("--n-eval-episodes", type=int, default=5,
                        help="Number of validation episodes per evaluation (default: 5)")
    parser.add_argument("--seed", type=int, default=None,
                        help="Random seed for reproducibility (default: None)")

    return parser


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    return build_parser().parse_args(argv)


def namespace_to_train_kwargs(args: argparse.Namespace) -> dict:
    # Handle comma-separated stocks (e.g., "HPG,ACB" becomes ["HPG", "ACB"])
    stocks_list = args.stocks
    if stocks_list and len(stocks_list) == 1 and ',' in stocks_list[0]:
        stocks_list = stocks_list[0].split(',')

    return {
        "stock": args.stock,
        "stocks": stocks_list,
        "all_stocks": args.all_stocks,
        "portfolio_choice": args.portfolio_choice,
        "portfolio_universe_size": args.portfolio_universe_size,
        "portfolio_top_k": args.portfolio_top_k,
        "data_dir": args.data_dir,
        "drawdown_penalty_enabled": args.drawdown_penalty_enabled,
        "drawdown_penalty_lambda": args.drawdown_penalty_lambda,
        "drawdown_penalty_train_only": (False if args.drawdown_penalty_all_modes else None),
        "reward_benchmark": _parse_reward_benchmark(args.reward_benchmark),
        "benchmark_weight": args.benchmark_weight,
        "benchmark_relative_reward": args.benchmark_relative_reward,
        "train_episode_sampling_enabled": args.train_episode_sampling_enabled,
        "train_episode_min_fraction": args.train_episode_min_fraction,
        "train_episode_max_fraction": args.train_episode_max_fraction,
        "start_date": args.start_date,
        "end_date": args.end_date,
        "source_mode": args.source_mode,
        "ma_windows": _parse_window_list(args.ma_windows, "--ma-windows"),
        "helpers_ma_windows": _parse_helper_window_list(args.helpers_ma_windows, "--helpers-ma-windows"),
        "returns_windows": _parse_window_list(args.returns_windows, "--returns-windows"),
        "helpers_returns_windows": _parse_helper_window_list(args.helpers_returns_windows, "--helpers-returns-windows"),
        "engineered_features": _parse_engineered_feature_families(args.engineered_features),
        "window_policy": args.window_policy,
        "feature_windows": _parse_window_list(args.feature_windows, "--feature-windows"),
        "logspace_min": args.logspace_min,
        "logspace_max": args.logspace_max,
        "logspace_count": args.logspace_count,
        "rs_market_proxies": _parse_rs_market_proxies(args.rs_market_proxies),
        "rs_include_long": (False if args.rs_no_long else None),
        "calendar_features": args.calendar_features,
        "news_feature_columns": _parse_news_feature_columns(args.news_columns),
        "news_prediction_dir": args.news_prediction_dir,
        "signal_feature_columns": _parse_signal_feature_columns(args.signal_columns),
        "signal_prediction_dir": args.signal_prediction_dir,
        "help_tickers": args.help_tickers,
        "market_data_dir": args.market_data_dir,
        "help_assets": args.help_assets,
        "help_assets_dir": args.help_assets_dir,
        "total_timesteps": args.timesteps,
        "model_name": args.name,
        "save_dir": args.save_dir,
        "log_dir": args.log_dir,
        "n_envs": args.n_envs,
        "policy": args.policy,
        "ent_coef_start": args.ent_coef_start,
        "ent_coef_end": args.ent_coef_end,
        "ent_coef_schedule": args.ent_coef_schedule,
        "eval_freq": args.eval_freq,
        "n_eval_episodes": args.n_eval_episodes,
        "seed": args.seed,
    }
