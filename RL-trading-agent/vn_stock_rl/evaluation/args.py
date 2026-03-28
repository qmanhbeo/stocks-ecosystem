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
)
from vn_stock_rl.external_features import default_help_assets_dir, default_market_data_dir, default_stock_data_dir

_parse_helper_window_list = parse_helper_window_list
_parse_engineered_feature_families = parse_engineered_feature_families
_parse_rs_market_proxies = parse_rs_market_proxies
_parse_news_feature_columns = parse_news_feature_columns
_parse_signal_feature_columns = parse_signal_feature_columns
_parse_reward_benchmark = parse_reward_benchmark


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate trained RL trading agent")
    parser.add_argument("--model", type=str, default="artifacts/trained_models/ppo_trading/model_final.zip",
                        help="Path to trained model")
    parser.add_argument("--stock", type=str, required=True,
                        help="Stock ticker (e.g., ACB)")
    parser.add_argument("--data-dir", type=str, default=str(default_stock_data_dir()),
                        help="Directory containing parquet files")
    parser.add_argument("--help-tickers", type=str, nargs='+', default=None,
                        help="Helper tickers to append as features (e.g., VNINDEX VN30)")
    parser.add_argument("--market-data-dir", type=str, default=str(default_market_data_dir()),
                        help="Directory containing market parquet files")
    parser.add_argument("--help-assets", type=str, nargs='+', default=None,
                        help="Helper assets to append as features (e.g., fx_vnd_usd gold oil)")
    parser.add_argument("--help-assets-dir", type=str, default=str(default_help_assets_dir()),
                        help="Directory containing helper asset parquet files")
    parser.add_argument("--mode", type=str, default="test", choices=['train', 'val', 'test'],
                        help="Which data split to evaluate on (default: test)")
    parser.add_argument("--output", type=str, default="artifacts/evaluation_results",
                        help="Root directory for evaluation results")
    parser.add_argument("--render", action="store_true",
                        help="Print step-by-step info")
    parser.add_argument("--forced-policy", type=str, choices=["flat", "buy_hold"],
                        help="Force actions without loading a model (flat or buy_hold)")
    parser.add_argument("--metrics-only", action="store_true",
                        help="Write only metrics_summary.json (skip plots/history/trades files)")
    parser.add_argument("--lookback-window", type=int, default=None,
                        help="Override lookback_window (default: use metadata if available)")
    drawdown_group = parser.add_mutually_exclusive_group()
    drawdown_group.add_argument(
        "--drawdown-penalty",
        dest="drawdown_penalty_enabled",
        action="store_true",
        help="Override drawdown penalty to enabled",
    )
    drawdown_group.add_argument(
        "--no-drawdown-penalty",
        dest="drawdown_penalty_enabled",
        action="store_false",
        help="Override drawdown penalty to disabled",
    )
    parser.set_defaults(drawdown_penalty_enabled=None)
    parser.add_argument("--drawdown-penalty-lambda", type=float, default=None,
                        help="Override drawdown penalty strength (>=0)")
    parser.add_argument("--drawdown-penalty-all-modes", action="store_true",
                        help="Override drawdown penalty to apply in all modes")
    benchmark_reward_group = parser.add_mutually_exclusive_group()
    benchmark_reward_group.add_argument(
        "--benchmark-relative-reward",
        dest="benchmark_relative_reward",
        action="store_true",
        help="Override benchmark-relative reward shaping to enabled",
    )
    benchmark_reward_group.add_argument(
        "--no-benchmark-relative-reward",
        dest="benchmark_relative_reward",
        action="store_false",
        help="Override benchmark-relative reward shaping to disabled",
    )
    parser.set_defaults(benchmark_relative_reward=None)
    parser.add_argument(
        "--reward-benchmark",
        type=str,
        default=None,
        help="Override benchmark for relative reward shaping (currently: self_buy_hold)",
    )
    parser.add_argument(
        "--benchmark-weight",
        type=float,
        default=None,
        help="Override benchmark weight for relative reward shaping",
    )
    train_sampling_group = parser.add_mutually_exclusive_group()
    train_sampling_group.add_argument(
        "--train-episode-sampling",
        dest="train_episode_sampling_enabled",
        action="store_true",
        help="Override randomized train sub-episode windows to enabled",
    )
    train_sampling_group.add_argument(
        "--no-train-episode-sampling",
        dest="train_episode_sampling_enabled",
        action="store_false",
        help="Override randomized train sub-episode windows to disabled",
    )
    parser.set_defaults(train_episode_sampling_enabled=None)
    parser.add_argument("--train-episode-min-fraction", type=float, default=None,
                        help="Override train sub-episode min fraction (0,1]")
    parser.add_argument("--train-episode-max-fraction", type=float, default=None,
                        help="Override train sub-episode max fraction (0,1]")
    parser.add_argument("--start-date", type=str, default=None,
                        help="Inclusive sample start date before train/val/test split (YYYY-MM-DD)")
    parser.add_argument("--end-date", type=str, default=None,
                        help="Inclusive sample end date before train/val/test split (YYYY-MM-DD)")
    parser.add_argument("--source-mode", type=str, choices=["raw", "return"], default=None,
                        help="Override feature source mode (default: use metadata if available)")
    parser.add_argument("--ma-windows", type=int, nargs='+', default=None,
                        help="Override MA windows (default: use metadata if available)")
    parser.add_argument("--helpers-ma-windows", type=str, nargs='+', default=None,
                        help="Override helper MA windows (e.g., 5 10) or 'same'")
    parser.add_argument("--returns-windows", type=int, nargs='+', default=None,
                        help="Override close-based return windows (default: use metadata if available)")
    parser.add_argument("--helpers-returns-windows", type=str, nargs='+', default=None,
                        help="Override helper return windows (e.g., 5 10) or 'same'")
    parser.add_argument(
        "--engineered-features",
        type=str,
        nargs='+',
        choices=["volatility", "trend", "momentum", "volume_context", "drawdown", "relative_strength"],
        default=None,
        help="Override engineered feature families",
    )
    parser.add_argument("--window-policy", type=str, choices=["explicit", "logspace"], default=None,
                        help="Override engineered feature window policy")
    parser.add_argument("--feature-windows", type=int, nargs='+', default=None,
                        help="Override explicit engineered windows")
    parser.add_argument("--logspace-min", type=int, default=None,
                        help="Override engineered logspace minimum window")
    parser.add_argument("--logspace-max", type=int, default=None,
                        help="Override engineered logspace maximum window")
    parser.add_argument("--logspace-count", type=int, default=None,
                        help="Override engineered logspace count")
    parser.add_argument("--rs-market-proxies", type=str, nargs='+', default=None,
                        help="Override RS market proxy preference (e.g., VNINDEX VN30)")
    parser.add_argument("--rs-no-long", action="store_true",
                        help="Disable long-horizon relative strength feature")
    parser.add_argument("--calendar-features", type=str, nargs='+', choices=["dow", "month", "dom"], default=None,
                        help="Override calendar features (default: use metadata if available)")
    parser.add_argument(
        "--news-columns",
        type=str,
        nargs='+',
        default=None,
        help=(
            "Override daily news feature columns. Use 'tabular' for the exported tabular "
            "news set, 'all' to include embeddings too, or list explicit column names."
        ),
    )
    parser.add_argument(
        "--news-prediction-dir",
        type=str,
        default=None,
        help="Override directory containing per-ticker news feature exports",
    )
    parser.add_argument(
        "--signal-columns",
        type=str,
        nargs='+',
        default=None,
        help=(
            "Override signal feature columns. Use 'default' for the standard probability "
            "columns, 'all' for every signal column, or list explicit names."
        ),
    )
    parser.add_argument(
        "--signal-prediction-dir",
        type=str,
        default=None,
        help="Override directory containing per-ticker signal exports (default: data/features/signals/predictions/auto)",
    )
    parser.add_argument("--train-split", type=float, default=None,
                        help="Override train split ratio (default: use metadata if available)")
    parser.add_argument("--val-split", type=float, default=None,
                        help="Override validation split ratio (default: use metadata if available)")
    parser.add_argument("--min-hold-days", type=int, default=None,
                        help="Override min hold days (default: use metadata if available)")
    parser.add_argument("--buy-fee-rate", type=float, default=None,
                        help="Override buy fee rate (default: use metadata if available)")
    parser.add_argument("--sell-fee-rate", type=float, default=None,
                        help="Override sell fee rate (default: use metadata if available)")
    parser.add_argument("--capital-gains-tax-rate", type=float, default=None,
                        help="Override capital gains tax rate (default: use metadata if available)")
    parser.add_argument("--stop-loss", type=float, default=None,
                        help="Override stop-loss threshold (default: use metadata if available)")
    return parser


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    return build_parser().parse_args(argv)


def namespace_to_evaluate_kwargs(args: argparse.Namespace) -> dict:
    return {
        "model_path": args.model,
        "stock": args.stock,
        "data_dir": args.data_dir,
        "help_tickers": args.help_tickers,
        "market_data_dir": args.market_data_dir,
        "help_assets": args.help_assets,
        "help_assets_dir": args.help_assets_dir,
        "mode": args.mode,
        "output_dir": args.output,
        "render": args.render,
        "forced_policy": args.forced_policy,
        "metrics_only": args.metrics_only,
        "lookback_window": args.lookback_window,
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
        "ma_windows": args.ma_windows,
        "helpers_ma_windows": _parse_helper_window_list(args.helpers_ma_windows, "--helpers-ma-windows"),
        "returns_windows": args.returns_windows,
        "helpers_returns_windows": _parse_helper_window_list(args.helpers_returns_windows, "--helpers-returns-windows"),
        "engineered_features": _parse_engineered_feature_families(args.engineered_features),
        "window_policy": args.window_policy,
        "feature_windows": args.feature_windows,
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
        "train_split": args.train_split,
        "val_split": args.val_split,
        "min_hold_days": args.min_hold_days,
        "buy_fee_rate": args.buy_fee_rate,
        "sell_fee_rate": args.sell_fee_rate,
        "capital_gains_tax_rate": args.capital_gains_tax_rate,
        "stop_loss": args.stop_loss,
    }
