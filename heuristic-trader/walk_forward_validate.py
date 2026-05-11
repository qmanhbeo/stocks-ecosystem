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

    if signal_type == "s1_only":
        return s1[['time', 'ticker', 's1_proba']].copy()
    elif signal_type == "c16_only":
        c16 = s.load_order_pressure(start=start_date, end=end_date, allow_2026=allow_2026)
        return c16[['time', 'ticker', 'order_volume_ratio_rank']].copy()
    elif signal_type == "c17_only":
        c17 = s.load_order_pressure_raw(start=start_date, end=end_date, allow_2026=allow_2026)
        return c17[['time', 'ticker', 'order_volume_ratio']].copy()
    elif signal_type == "c18_only":
        c18 = s.load_order_pressure_delta(start=start_date, end=end_date, allow_2026=allow_2026)
        return c18[['time', 'ticker', 'order_volume_ratio_rank_delta']].copy()
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
    else:
        raise ValueError(f"Unknown signal_type: {signal_type}")


def run_strategy_on_fold(
    config: dict,
    fold: dict,
    liquid_lookup: dict,
    trad_lookup: dict,
    price_cache: dict,
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
        candidate_scan_multiplier=config.get("candidate_scan_multiplier", 3),
        sizing_mode=config.get("sizing_mode", "fixed_initial"),
    )
    elapsed = time.time() - start_time

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

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output_dir) if args.output_dir else ARTIFACT_DIR / "walk_forward" / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nOutput directory: {output_dir}")

    all_metrics = []
    strategy_metrics_map = {name: [] for name in strategy_names}
    failed_runs = []

    total_runs = len(strategy_names) * len(active_folds)
    run_idx = 0

    for strategy_name in strategy_names:
        print(f"\n{'='*60}")
        print(f"Strategy: {strategy_name}")
        print("=" * 60)

        config = strategy_loader.load_strategy_config(strategy_name)

        for fold in active_folds:
            run_idx += 1
            print(f"\n[{run_idx}/{total_runs}] ", end="")
            try:
                metrics = run_strategy_on_fold(
                    config, fold, liquid_lookup, trad_lookup, price_cache
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
    fold_metrics_path = output_dir / "fold_metrics.csv"
    fold_metrics_df.to_csv(fold_metrics_path, index=False)
    print(f"\nSaved fold_metrics.csv: {fold_metrics_path}")

    strategy_summaries = []
    for strategy_name, metrics_list in strategy_metrics_map.items():
        summary = compute_strategy_summary(metrics_list)
        if summary:
            strategy_summaries.append(summary)

    summary_df = pd.DataFrame(strategy_summaries)
    summary_df = summary_df.sort_values("mean_annualized_return", ascending=False)

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

    print(f"\nArtifacts saved to: {output_dir}")


if __name__ == "__main__":
    main()