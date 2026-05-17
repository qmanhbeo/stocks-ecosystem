#!/usr/bin/env python3
"""
Walk-forward validation harness for heuristic-trader strategies.

This is a VALIDATION pass, NOT a tuning pass:
- No parameter optimization
- No changing top_k/rebalance/blend choices based on results
- Focus is on robustness testing across time periods

Default folds (2015-2025, 11 folds):
  2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025

Usage:
    python walk_forward_validate.py
    python walk_forward_validate.py --strategy s1_top5_rebal10
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import numpy as np

import backtest as bt
import signals as s
from strategies import loader as strategy_loader


ARTIFACT_DIR = Path(__file__).parent / "artifacts"
CACHE_DIR = Path(__file__).parent / "cache"

bt.CACHE_DIR = CACHE_DIR
bt.PRICE_CACHE_FILE = CACHE_DIR / "price_cache.parquet"
bt.LIQUID_CACHE_FILE = CACHE_DIR / "liquid_lookup.joblib"
bt.TRAD_CACHE_FILE = CACHE_DIR / "trad_lookup.joblib"


FOLDS = [
    {"name": "fold_2015", "train_start": "2015-01-01", "train_end": "2014-12-31", "test_start": "2015-01-01", "test_end": "2015-12-31"},
    {"name": "fold_2016", "train_start": "2015-01-01", "train_end": "2015-12-31", "test_start": "2016-01-01", "test_end": "2016-12-31"},
    {"name": "fold_2017", "train_start": "2015-01-01", "train_end": "2016-12-31", "test_start": "2017-01-01", "test_end": "2017-12-31"},
    {"name": "fold_2018", "train_start": "2015-01-01", "train_end": "2017-12-31", "test_start": "2018-01-01", "test_end": "2018-12-31"},
    {"name": "fold_2019", "train_start": "2015-01-01", "train_end": "2018-12-31", "test_start": "2019-01-01", "test_end": "2019-12-31"},
    {"name": "fold_2020", "train_start": "2015-01-01", "train_end": "2019-12-31", "test_start": "2020-01-01", "test_end": "2020-12-31"},
    {"name": "fold_2021", "train_start": "2015-01-01", "train_end": "2020-12-31", "test_start": "2021-01-01", "test_end": "2021-12-31"},
    {"name": "fold_2022", "train_start": "2015-01-01", "train_end": "2021-12-31", "test_start": "2022-01-01", "test_end": "2022-12-31"},
    {"name": "fold_2023", "train_start": "2015-01-01", "train_end": "2022-12-31", "test_start": "2023-01-01", "test_end": "2023-12-31"},
    {"name": "fold_2024", "train_start": "2015-01-01", "train_end": "2023-12-31", "test_start": "2024-01-01", "test_end": "2024-12-31"},
    {"name": "fold_2025", "train_start": "2015-01-01", "train_end": "2024-12-31", "test_start": "2025-01-01", "test_end": "2025-12-31"},
]

CANONICAL_SCHEMA_VERSION = 1
LOCKBOX_MAX_DATE = "2025-12-31"
CANONICAL_LEADERBOARD_COLUMNS = [
    "strategy_name",
    "n_folds",
    "mean_annualized_return",
    "mean_excess_return",
    "positive_folds",
    "beating_benchmark_folds",
    "mean_max_drawdown",
    "total_trades",
    "robustness_notes",
]
CANONICAL_USED_CONFIG_KEYS = [
    "name",
    "signal_type",
    "signal_col",
    "top_k",
    "rebalance_days",
    "min_hold_days",
    "candidate_scan_multiplier",
    "sizing_mode",
    "fallback_mode",
    "active_rank_threshold",
    "low_breadth_percentile",
    "c17_boost_strength",
    "c17_delta_weight",
]


def _canonical_fold_list(active_folds: list[dict]) -> list[dict]:
    """Canonical fold payload (stable subset only)."""
    return [
        {
            "name": fold["name"],
            "test_start": fold["test_start"],
            "test_end": fold["test_end"],
        }
        for fold in active_folds
    ]


def _write_canonical_strategy_outputs(
    canonical_root: Path,
    strategy_name: str,
    config: dict,
    strategy_metrics: list[dict],
    summary_row: dict | None,
    active_folds: list[dict],
):
    """Write deterministic per-strategy canonical artifacts."""
    strategy_dir = canonical_root / "strategies" / strategy_name
    strategy_dir.mkdir(parents=True, exist_ok=True)

    # Exact effective config used (stable key ordering, no runtime fields).
    with open(strategy_dir / "config_effective.json", "w") as f:
        json.dump(config, f, indent=2, sort_keys=True)

    fold_df = pd.DataFrame(strategy_metrics)
    if not fold_df.empty:
        if "elapsed_seconds" in fold_df.columns:
            fold_df = fold_df.drop(columns=["elapsed_seconds"])
        sort_cols = [c for c in ["test_start", "fold_name"] if c in fold_df.columns]
        if sort_cols:
            fold_df = fold_df.sort_values(sort_cols).reset_index(drop=True)
        fold_df.to_csv(strategy_dir / "fold_metrics.csv", index=False, float_format="%.6f")
    else:
        pd.DataFrame().to_csv(strategy_dir / "fold_metrics.csv", index=False)

    if summary_row:
        summary_df = pd.DataFrame([summary_row])
    else:
        summary_df = pd.DataFrame([{"strategy_name": strategy_name, "n_folds": 0}])
    summary_df = summary_df.sort_values(["strategy_name"]).reset_index(drop=True)
    summary_df.to_csv(strategy_dir / "strategy_summary.csv", index=False, float_format="%.6f")

    used_keys = [k for k in CANONICAL_USED_CONFIG_KEYS if k in config]
    metadata = {
        "canonical_schema_version": CANONICAL_SCHEMA_VERSION,
        "strategy_name": strategy_name,
        "validation_type": "walk_forward",
        "lockbox_max_date": LOCKBOX_MAX_DATE,
        "fold_count": len(active_folds),
        "folds": _canonical_fold_list(active_folds),
        "source_config_keys": used_keys,
    }
    with open(strategy_dir / "metadata.json", "w") as f:
        json.dump(metadata, f, indent=2, sort_keys=True)


def _rebuild_canonical_leaderboard(canonical_root: Path) -> pd.DataFrame:
    """Rebuild canonical leaderboard from canonical per-strategy summaries."""
    strategies_dir = canonical_root / "strategies"
    rows = []
    if strategies_dir.exists():
        for strategy_dir in sorted([p for p in strategies_dir.iterdir() if p.is_dir()], key=lambda p: p.name):
            summary_path = strategy_dir / "strategy_summary.csv"
            if not summary_path.exists():
                continue
            summary_df = pd.read_csv(summary_path)
            if summary_df.empty:
                continue
            row = summary_df.iloc[0].to_dict()
            rows.append({col: row.get(col, None) for col in CANONICAL_LEADERBOARD_COLUMNS})

    leaderboard_df = pd.DataFrame(rows, columns=CANONICAL_LEADERBOARD_COLUMNS)
    if not leaderboard_df.empty:
        leaderboard_df = leaderboard_df.sort_values(["strategy_name"]).reset_index(drop=True)
    leaderboard_df.to_csv(
        canonical_root / "leaderboard.csv",
        index=False,
        float_format="%.6f",
    )
    return leaderboard_df


def _write_canonical_manifest(canonical_root: Path, active_folds: list[dict], strategy_count: int):
    """Write deterministic canonical manifest."""
    manifest = {
        "canonical_schema_version": CANONICAL_SCHEMA_VERSION,
        "validation_type": "walk_forward",
        "lockbox_max_date": LOCKBOX_MAX_DATE,
        "fold_count": len(active_folds),
        "folds": _canonical_fold_list(active_folds),
        "strategy_count": int(strategy_count),
        "notes": "Old timestamped artifacts are historical clues; canonical outputs are decision-grade.",
    }
    with open(canonical_root / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)


def load_caches():
    """Load pre-computed caches."""
    liquid_lookup = bt.load_liquid_lookup()
    trad_lookup = bt.load_trad_lookup()
    price_cache = bt.load_price_cache()
    return liquid_lookup, trad_lookup, price_cache


def get_benchmark(start_date: str, end_date: str) -> dict | None:
    """Get VNINDEX benchmark for the date range."""
    import constraints as cn
    try:
        vn = cn.load_vnindex(start=start_date, end=end_date)
        if len(vn) == 0:
            return None

        start_price = vn["open"].iloc[0]
        end_price = vn["open"].iloc[-1]
        shares = int(100_000_000 / start_price)
        cost = shares * start_price * 1.001
        initial_cash = 100_000_000 - cost
        proceeds = shares * end_price * 0.9984
        final_value = initial_cash + proceeds
        total_return = (final_value / 100_000_000) - 1.0

        return {
            "total_return": total_return,
            "name": "VNINDEX",
        }
    except Exception:
        return None


def prepare_signal_df_from_config(
    config: dict,
    start_date: str,
    end_date: str,
    allow_2026: bool = False,
) -> pd.DataFrame:
    """Prepare signal DataFrame from strategy config."""
    signal_type = config["signal_type"]
    s1 = s.load_rl_signal_matrix(start=start_date, end=end_date, allow_2026=allow_2026)
    active_rank_threshold = float(config.get("active_rank_threshold", 0.2))
    low_breadth_percentile = float(config.get("low_breadth_percentile", 0.25))

    if signal_type == "s1_only":
        return s1[['time', 'ticker', 's1_proba']].copy()
    elif signal_type == "c16_only":
        c16 = s.load_order_pressure(start=start_date, end=end_date, allow_2026=allow_2026)
        return c16[['time', 'ticker', 'order_volume_ratio_rank']].copy()
    elif signal_type == "c17_only":
        c17 = s.load_order_pressure_raw(start=start_date, end=end_date, allow_2026=allow_2026)
        return c17[['time', 'ticker', 'order_volume_ratio']].copy()
    elif signal_type == "c17_active_boost":
        c17 = s.load_order_pressure_c17_active_boost(
            start=start_date,
            end=end_date,
            allow_2026=allow_2026,
            active_rank_threshold=active_rank_threshold,
            boost_strength=float(config.get("c17_boost_strength", 0.35)),
            delta_weight=float(config.get("c17_delta_weight", 0.20)),
        )
        return c17[['time', 'ticker', 'c17_active_boost']].copy()
    elif signal_type == "c18_only":
        c18 = s.load_order_pressure_delta(start=start_date, end=end_date, allow_2026=allow_2026)
        return c18[['time', 'ticker', 'order_volume_ratio_rank_delta']].copy()
    elif signal_type == "s1_low_breadth":
        breadth = s.load_low_breadth_regime(
            start=start_date,
            end=end_date,
            allow_2026=allow_2026,
            active_rank_threshold=active_rank_threshold,
            low_breadth_percentile=low_breadth_percentile,
        )
        df = s1[['time', 'ticker', 's1_proba']].merge(
            breadth[['time', 'is_low_breadth']],
            on='time',
            how='inner',
        )
        return df[df['is_low_breadth'] == 1][['time', 'ticker', 's1_proba']].copy()
    elif signal_type == "s1_active_low_breadth":
        c16 = s.load_order_pressure(start=start_date, end=end_date, allow_2026=allow_2026)
        breadth = s.load_low_breadth_regime(
            start=start_date,
            end=end_date,
            allow_2026=allow_2026,
            active_rank_threshold=active_rank_threshold,
            low_breadth_percentile=low_breadth_percentile,
        )
        df = s1[['time', 'ticker', 's1_proba']].merge(
            c16[['time', 'ticker', 'order_volume_ratio_rank']],
            on=['time', 'ticker'],
            how='inner',
        ).merge(
            breadth[['time', 'is_low_breadth']],
            on='time',
            how='inner',
        )
        mask = (df['order_volume_ratio_rank'] < active_rank_threshold) & (df['is_low_breadth'] == 1)
        return df[mask][['time', 'ticker', 's1_proba']].copy()
    elif signal_type in ("blend_70_30", "blend_50_50"):
        c16 = s.load_order_pressure(start=start_date, end=end_date, allow_2026=allow_2026)
        df = s1[['time', 'ticker', 's1_proba']].merge(
            c16[['time', 'ticker', 'order_volume_ratio_rank']],
            on=['time', 'ticker']
        )
        if signal_type == "blend_70_30":
            df['blend'] = df['s1_proba'] * 0.7 + df['order_volume_ratio_rank'] * 0.3
        else:
            df['blend'] = df['s1_proba'] * 0.5 + df['order_volume_ratio_rank'] * 0.5
        return df[['time', 'ticker', 'blend']]
    elif signal_type == "blend_70_30_low_breadth":
        c16 = s.load_order_pressure(start=start_date, end=end_date, allow_2026=allow_2026)
        breadth = s.load_low_breadth_regime(
            start=start_date,
            end=end_date,
            allow_2026=allow_2026,
            active_rank_threshold=active_rank_threshold,
            low_breadth_percentile=low_breadth_percentile,
        )
        df = s1[['time', 'ticker', 's1_proba']].merge(
            c16[['time', 'ticker', 'order_volume_ratio_rank']],
            on=['time', 'ticker'],
            how='inner',
        )
        df['blend'] = df['s1_proba'] * 0.7 + df['order_volume_ratio_rank'] * 0.3
        df = df.merge(breadth[['time', 'is_low_breadth']], on='time', how='inner')
        return df[df['is_low_breadth'] == 1][['time', 'ticker', 'blend']].copy()
    else:
        raise ValueError(f"Unknown signal_type: {signal_type}")


def run_strategy_on_fold(
    config: dict,
    fold: dict,
    liquid_lookup: dict,
    trad_lookup: dict,
    price_cache: dict,
    collect_diagnostics: bool = False,
    diagnostics_output_dir: Path | None = None,
) -> dict:
    """Run a single strategy on a single fold."""
    strategy_name = config["name"]
    test_start = fold["test_start"]
    test_end = fold["test_end"]

    print(f"\n  Running {strategy_name} on {fold['name']} ({test_start} to {test_end})")

    signal_df = prepare_signal_df_from_config(config, test_start, test_end, allow_2026=False)

    if len(signal_df) == 0:
        return {
            "strategy_name": strategy_name,
            "fold_name": fold["name"],
            "test_start": test_start,
            "test_end": test_end,
            "error": "No signal data",
        }

    start_time = time.time()
    result = bt.simulate_topk_constraint_compliant(
        signal_df,
        price_cache,
        signal_col=config["signal_col"],
        top_k=config["top_k"],
        rebalance_days=config["rebalance_days"],
        min_hold_days=config["min_hold_days"],
        use_filters=True,
        liquid_lookup=liquid_lookup,
        trad_lookup=trad_lookup,
        collect_diagnostics=collect_diagnostics,
        candidate_scan_multiplier=config.get("candidate_scan_multiplier", 3),
        sizing_mode=config.get("sizing_mode", "fixed_initial"),
        fallback_mode=config.get("fallback_mode", "none"),
    )
    elapsed = time.time() - start_time

    if collect_diagnostics and diagnostics_output_dir is not None and result.diagnostics:
        diagnostics_output_dir.mkdir(parents=True, exist_ok=True)
        diagnostics_file_map = {
            "trade_log": "trade_log.csv",
            "selection_log": "selection_log.csv",
            "filtered_breakdown": "filtered_breakdown.csv",
            "fallback_log": "fallback_log.csv",
        }
        for key, filename in diagnostics_file_map.items():
            df = result.diagnostics.get(key)
            if isinstance(df, pd.DataFrame) and len(df) > 0:
                df.to_csv(diagnostics_output_dir / filename, index=False)

        metadata = {
            "strategy_name": strategy_name,
            "fold_name": fold["name"],
            "test_start": test_start,
            "test_end": test_end,
            "candidate_scan_multiplier": config.get("candidate_scan_multiplier", 3),
            "sizing_mode": config.get("sizing_mode", "fixed_initial"),
            "fallback_mode": config.get("fallback_mode", "none"),
        }
        with open(diagnostics_output_dir / "metadata.json", "w") as f:
            json.dump(metadata, f, indent=2)

    benchmark = get_benchmark(test_start, test_end)
    benchmark_return = benchmark["total_return"] if benchmark else None
    excess_return = (result.total_return - benchmark_return) if benchmark_return is not None else None

    curve = result.curve
    final_value = curve["portfolio_value"].iloc[-1] if curve is not None and len(curve) > 0 else None

    metrics = {
        "strategy_name": strategy_name,
        "fold_name": fold["name"],
        "train_start": fold["train_start"],
        "train_end": fold["train_end"],
        "test_start": test_start,
        "test_end": test_end,
        "total_return": round(result.total_return, 6) if result.total_return else None,
        "annualized_return": round(result.annualized_return, 6) if result.annualized_return else None,
        "sharpe": round(result.sharpe, 6) if result.sharpe else None,
        "max_drawdown": round(result.max_drawdown, 6) if result.max_drawdown else None,
        "n_trades": result.n_trades,
        "n_filtered": result.n_filtered if hasattr(result, 'n_filtered') else 0,
        "final_value": round(final_value, 2) if final_value else None,
        "benchmark_return": round(benchmark_return, 6) if benchmark_return is not None else None,
        "excess_return_vs_benchmark": round(excess_return, 6) if excess_return is not None else None,
        "elapsed_seconds": round(elapsed, 2),
    }

    print(f"    Result: {result.total_return:.2%} return, {result.n_trades} trades, {elapsed:.1f}s")
    if benchmark_return:
        print(f"    Benchmark: {benchmark_return:.2%}, Excess: {excess_return:+.2%}")

    return metrics


def compute_strategy_summary(strategy_metrics: list[dict]) -> dict:
    """Compute aggregate summary for a single strategy across all folds."""
    if not strategy_metrics:
        return {}

    valid_metrics = [m for m in strategy_metrics if m.get("total_return") is not None]
    if not valid_metrics:
        return {"error": "No valid metrics"}

    returns = [m["total_return"] for m in valid_metrics]
    ann_returns = [m["annualized_return"] for m in valid_metrics if m.get("annualized_return") is not None]
    drawdowns = [abs(m["max_drawdown"]) for m in valid_metrics if m.get("max_drawdown") is not None]
    trades = sum(m["n_trades"] for m in valid_metrics)
    benchmark_returns = [m["benchmark_return"] for m in valid_metrics if m.get("benchmark_return") is not None]
    excess_returns = [m["excess_return_vs_benchmark"] for m in valid_metrics if m.get("excess_return_vs_benchmark") is not None]

    positive_folds = sum(1 for r in returns if r > 0)
    beating_benchmark = sum(1 for e in excess_returns if e > 0) if excess_returns else 0

    summary = {
        "strategy_name": valid_metrics[0]["strategy_name"],
        "n_folds": len(valid_metrics),
        "mean_total_return": round(np.mean(returns), 6),
        "median_total_return": round(np.median(returns), 6),
        "mean_annualized_return": round(np.mean(ann_returns), 6) if ann_returns else None,
        "median_annualized_return": round(np.median(ann_returns), 6) if ann_returns else None,
        "mean_max_drawdown": round(np.mean(drawdowns), 6) if drawdowns else None,
        "positive_folds": positive_folds,
        "beating_benchmark_folds": beating_benchmark,
        "total_trades": trades,
        "mean_benchmark_return": round(np.mean(benchmark_returns), 6) if benchmark_returns else None,
        "mean_excess_return": round(np.mean(excess_returns), 6) if excess_returns else None,
    }

    robustness_score = positive_folds / len(valid_metrics) if valid_metrics else 0
    benchmark_beat_rate = beating_benchmark / len([e for e in excess_returns if e is not None]) if excess_returns else 0

    if robustness_score == 1.0 and benchmark_beat_rate >= 0.67:
        fragility_note = "ROBUST: Positive in all folds, beats benchmark in majority"
    elif robustness_score >= 0.67:
        fragility_note = "MODERATE: Positive in most folds"
    elif robustness_score >= 0.33:
        fragility_note = "FRAGILE: Inconsistent performance across folds"
    else:
        fragility_note = "WEAK: Negative in most or all folds"

    if benchmark_beat_rate == 0 and any(e < 0 for e in excess_returns if e is not None):
        fragility_note += "; underperforms benchmark consistently"

    summary["robustness_notes"] = fragility_note

    return summary


def create_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Walk-forward validation for heuristic-trader strategies",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--strategy",
        type=str,
        default=None,
        help="Specific strategy to validate (default: all strategies)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Custom output directory (default: artifacts/walk_forward/<timestamp>)",
    )
    parser.add_argument(
        "--collect-diagnostics",
        action="store_true",
        help="Persist fold-level diagnostics (trade/selection/filter CSVs)",
    )
    parser.add_argument(
        "--canonical-output",
        type=str,
        default=None,
        help="Deterministic canonical output root (e.g., artifacts/canonical_wfv)",
    )
    return parser


def main():
    parser = create_argument_parser()
    args = parser.parse_args()

    if args.strategy:
        strategy_names = [args.strategy]
    else:
        strategy_names = strategy_loader.list_strategies()

    active_folds = FOLDS

    print("=" * 80)
    print("WALK-FORWARD VALIDATION")
    print("=" * 80)
    print(f"Folds: {len(active_folds)}")
    for fold in active_folds:
        print(f"  {fold['name']}: {fold['test_start']} to {fold['test_end']}")
    print(f"\nStrategies: {len(strategy_names)}")
    for name in strategy_names:
        print(f"  - {name}")

    print("\nLoading caches...")
    liquid_lookup, trad_lookup, price_cache = load_caches()
    print(f"  Liquid: {len(liquid_lookup)} dates, Trad: {len(trad_lookup)} entries, Price: {len(price_cache)} tickers")

    canonical_output_root = Path(args.canonical_output) if args.canonical_output else None
    if canonical_output_root is not None:
        canonical_output_root.mkdir(parents=True, exist_ok=True)
        print(f"\nCanonical output root: {canonical_output_root}")

    # Scratch output policy:
    # - Default behavior: timestamped scratch folder.
    # - Canonical-only mode: skip timestamped scratch unless explicitly requested
    #   (or required for diagnostics capture).
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    output_dir = None
    if args.output_dir:
        output_dir = Path(args.output_dir)
    elif canonical_output_root is None:
        output_dir = ARTIFACT_DIR / "walk_forward" / timestamp
    elif args.collect_diagnostics:
        # Diagnostics are scratch-only by policy.
        output_dir = ARTIFACT_DIR / "walk_forward" / timestamp

    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        print(f"Scratch output directory: {output_dir}")
    else:
        print("Scratch output directory: disabled (canonical-only mode)")

    all_metrics = []
    strategy_metrics_map = {name: [] for name in strategy_names}
    strategy_configs = {}
    failed_runs = []

    total_runs = len(strategy_names) * len(active_folds)
    run_idx = 0

    for strategy_name in strategy_names:
        print(f"\n{'='*60}")
        print(f"Strategy: {strategy_name}")
        print("=" * 60)

        config = strategy_loader.load_strategy_config(strategy_name)
        strategy_configs[strategy_name] = config

        for fold in active_folds:
            run_idx += 1
            print(f"\n[{run_idx}/{total_runs}] ", end="")
            try:
                diagnostics_output_dir = None
                if args.collect_diagnostics and output_dir is not None:
                    diagnostics_output_dir = (
                        output_dir / "diagnostics" / strategy_name / fold["name"]
                    )
                metrics = run_strategy_on_fold(
                    config,
                    fold,
                    liquid_lookup,
                    trad_lookup,
                    price_cache,
                    collect_diagnostics=args.collect_diagnostics,
                    diagnostics_output_dir=diagnostics_output_dir,
                )
                all_metrics.append(metrics)
                strategy_metrics_map[strategy_name].append(metrics)
            except Exception as e:
                print(f"FAILED: {fold['name']} - {e}")
                failed_runs.append((strategy_name, fold["name"], str(e)))
                all_metrics.append({
                    "strategy_name": strategy_name,
                    "fold_name": fold["name"],
                    "test_start": fold["test_start"],
                    "test_end": fold["test_end"],
                    "error": str(e),
                })

    fold_metrics_df = pd.DataFrame(all_metrics)

    strategy_summaries = []
    for strategy_name, metrics_list in strategy_metrics_map.items():
        summary = compute_strategy_summary(metrics_list)
        if summary:
            strategy_summaries.append(summary)

    summary_df = pd.DataFrame(strategy_summaries)
    if not summary_df.empty and "mean_annualized_return" in summary_df.columns:
        summary_df = summary_df.sort_values("mean_annualized_return", ascending=False).reset_index(drop=True)

    if output_dir is not None:
        fold_metrics_path = output_dir / "fold_metrics.csv"
        fold_metrics_df.to_csv(fold_metrics_path, index=False)
        print(f"\nSaved fold_metrics.csv: {fold_metrics_path}")

        csv_path = output_dir / "strategy_summary.csv"
        summary_df.to_csv(csv_path, index=False)
        print(f"Saved strategy_summary.csv: {csv_path}")

        summary_path = output_dir / "summary.json"
        with open(summary_path, "w") as f:
            json.dump(strategy_summaries, f, indent=2)
        print(f"Saved summary.json: {summary_path}")

        readme_content = f"""# Walk-Forward Validation Results

**Generated**: {datetime.now().isoformat()}
**Timestamp**: {timestamp}

## Provenance

This walk-forward validation harness adapts patterns from alpha-research-lab principles:

- **Explicit temporal folds**: Train/context periods followed by distinct test windows
- **No 2026 lockbox access**: All test windows end at 2025-12-31
- **No tuning inside validation**: Parameters fixed from strategies.json; this is validation, not optimization
- **Artifact-first reporting**: CSV + JSON + Markdown for reproducibility
- **Robustness judged across folds**: Consistency over single-period headline numbers

**Key distinction**: This is PnL/execution validation, NOT IC (Information Coefficient) research. The goal is to assess whether strategies survive realistic portfolio/execution assumptions, not whether signals have predictive power.

## Folds

| Fold | Train Period | Test Period |
|------|---------------|--------------|
"""

        for fold in active_folds:
            readme_content += f"| {fold['name']} | {fold['train_start']} to {fold['train_end']} | {fold['test_start']} to {fold['test_end']} |\n"

        readme_content += f"""
## Summary

**Total strategies tested**: {len(strategy_names)}
**Total folds run**: {total_runs}
**Failed runs**: {len(failed_runs)}

### Strategy Rankings by Mean Annualized Return

| Rank | Strategy | Mean Ann. Return | Median Ann. Return | Positive Folds | Beats Benchmark | Robustness |
|------|----------|------------------|--------------------|----------------|------------------|------------|
"""

        for i, row in summary_df.iterrows():
            readme_content += f"| {i+1} | {row['strategy_name']} | {row.get('mean_annualized_return', 'N/A'):.2%} | {row.get('median_annualized_return', 'N/A'):.2%} | {row['positive_folds']}/{row['n_folds']} | {row['beating_benchmark_folds']}/{row['n_folds']} | {row.get('robustness_notes', 'N/A')} |\n"

        readme_content += f"""
## Notes

- This is a VALIDATION pass, NOT a tuning pass
- No parameter optimization was performed
- "Train/context" period is mostly metadata; test periods are what matter
- Robustness assessed by consistency across time periods

## Files

- `fold_metrics.csv`: Detailed metrics for each strategy/fold combination
- `strategy_summary.csv`: Aggregate summary per strategy (CSV format)
- `summary.json`: Aggregate summary per strategy (JSON format)
"""

        readme_path = output_dir / "README.md"
        with open(readme_path, "w") as f:
            f.write(readme_content)
        print(f"Saved README.md: {readme_path}")

    if canonical_output_root is not None:
        summary_lookup = {}
        for row in strategy_summaries:
            name = row.get("strategy_name")
            if name:
                summary_lookup[name] = row

        for strategy_name in strategy_names:
            _write_canonical_strategy_outputs(
                canonical_root=canonical_output_root,
                strategy_name=strategy_name,
                config=strategy_configs[strategy_name],
                strategy_metrics=strategy_metrics_map[strategy_name],
                summary_row=summary_lookup.get(strategy_name),
                active_folds=active_folds,
            )

        leaderboard_df = _rebuild_canonical_leaderboard(canonical_output_root)
        _write_canonical_manifest(
            canonical_root=canonical_output_root,
            active_folds=active_folds,
            strategy_count=len(leaderboard_df),
        )
        print(f"\nSaved canonical outputs under: {canonical_output_root}")

    print("\n" + "=" * 80)
    print("WALK-FORWARD VALIDATION COMPLETE")
    print("=" * 80)

    if strategy_summaries:
        top_strategy = summary_df.iloc[0]
        weakest = summary_df.iloc[-1]

        print(f"\nTop strategy by walk-forward robustness:")
        print(f"  {top_strategy['strategy_name']}")
        print(f"    Mean annualized return: {top_strategy.get('mean_annualized_return', 'N/A'):.2%}")
        print(f"    Positive folds: {top_strategy['positive_folds']}/{top_strategy['n_folds']}")
        print(f"    Robustness: {top_strategy.get('robustness_notes', 'N/A')}")

        print(f"\nWeakest/most fragile strategy:")
        print(f"  {weakest['strategy_name']}")
        print(f"    Mean annualized return: {weakest.get('mean_annualized_return', 'N/A'):.2%}")
        print(f"    Positive folds: {weakest['positive_folds']}/{weakest['n_folds']}")
        print(f"    Robustness: {weakest.get('robustness_notes', 'N/A')}")

        s1_strategy = summary_df[summary_df['strategy_name'] == 's1_top5_rebal10']
        if len(s1_strategy) > 0:
            s1 = s1_strategy.iloc[0]
            is_tradable = s1.get('mean_annualized_return', 0) > 0 and s1['positive_folds'] >= 2
            print(f"\nCurrent best strategy (s1_top5_rebal10) tradability:")
            print(f"  Mean annualized return: {s1.get('mean_annualized_return', 'N/A'):.2%}")
            print(f"  Positive folds: {s1['positive_folds']}/{s1['n_folds']}")
            print(f"  Looks tradable: {'YES' if is_tradable else 'NO'}")
        else:
            print("\nNote: s1_top5_rebal10 not found in results")

    if failed_runs:
        print(f"\nFailed runs: {len(failed_runs)}")
        for strat, fold, err in failed_runs:
            print(f"  {strat} / {fold}: {err}")

    if output_dir is not None:
        print(f"\nArtifacts saved to: {output_dir}")
    if canonical_output_root is not None:
        print(f"Canonical artifacts saved to: {canonical_output_root}")


if __name__ == "__main__":
    main()
