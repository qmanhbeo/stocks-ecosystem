#!/usr/bin/env python3
"""
CLI entrypoint for heuristic-trader backtests.

Usage:
    python run_backtest.py --strategy s1_top5_rebal10 --start-date 2019-01-01 --end-date 2025-12-31
    python run_backtest.py --all-strategies --start-date 2019-01-01 --end-date 2025-12-31

The lockbox is enforced by default: end dates past 2025-12-31 are forbidden.
Use --allow-lockbox to override (only for testing).
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

import backtest as bt
import signals as s
from strategies import loader as strategy_loader


ARTIFACT_DIR = Path(__file__).parent / "artifacts"
CACHE_DIR = Path(__file__).parent / "cache"

import backtest as bt
bt.CACHE_DIR = CACHE_DIR
bt.PRICE_CACHE_FILE = CACHE_DIR / "price_cache.parquet"
bt.LIQUID_CACHE_FILE = CACHE_DIR / "liquid_lookup.joblib"
bt.TRAD_CACHE_FILE = CACHE_DIR / "trad_lookup.joblib"

BENCHMARK_CACHE = None


def get_benchmark(start_date: str, end_date: str) -> dict | None:
    """Get VNINDEX benchmark for the date range."""
    global BENCHMARK_CACHE
    if BENCHMARK_CACHE is not None:
        return BENCHMARK_CACHE

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

        BENCHMARK_CACHE = {
            "total_return": total_return,
            "name": "VNINDEX",
        }
        return BENCHMARK_CACHE
    except Exception:
        return None


def create_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run heuristic-trader backtest with artifact output",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--strategy",
        type=str,
        default=None,
        help="Strategy name from strategies.json (e.g., s1_top5_rebal10)",
    )
    parser.add_argument(
        "--all-strategies",
        action="store_true",
        help="Run all strategies from strategies.json",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        default="2019-01-01",
        help="Start date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        default="2025-12-31",
        help="End date (YYYY-MM-DD). Lockbox defaults to 2025-12-31 max.",
    )
    parser.add_argument(
        "--allow-lockbox",
        action="store_true",
        help="Allow 2026+ data (for testing only, not for real trading)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Custom output directory (default: artifacts/runs/<timestamp>)",
    )
    parser.add_argument(
        "--collect-diagnostics",
        action="store_true",
        help="Persist backtest diagnostics (trade/selection/filter CSVs)",
    )
    parser.add_argument(
        "--update-latest",
        action="store_true",
        help="Update artifacts/summaries/latest_summary.* (default: disabled)",
    )
    return parser


def load_caches():
    """Load pre-computed caches."""
    liquid_lookup = bt.load_liquid_lookup()
    trad_lookup = bt.load_trad_lookup()
    price_cache = bt.load_price_cache()
    return liquid_lookup, trad_lookup, price_cache


def run_strategy_for_test(
    strategy_name: str,
    start_date: str,
    end_date: str,
    output_dir: Path,
    allow_2026: bool = False,
    collect_diagnostics: bool = False,
) -> dict:
    """Run a single strategy for testing (uses real artifact path).

    This is a thin wrapper around the real artifact-writing path.
    Use this in smoke tests instead of manually writing artifacts.
    """
    config = strategy_loader.load_strategy_config(strategy_name)
    liquid_lookup, trad_lookup, price_cache = load_caches()

    signal_df = prepare_signal_df_from_config(config, start_date, end_date, allow_2026)

    metrics = run_backtest_and_save(
        signal_df,
        price_cache,
        strategy_name=config["name"],
        signal_col=config["signal_col"],
        top_k=config["top_k"],
        rebalance_days=config["rebalance_days"],
        min_hold_days=config["min_hold_days"],
        candidate_scan_multiplier=config.get("candidate_scan_multiplier", 3),
        sizing_mode=config.get("sizing_mode", "fixed_initial"),
        fallback_mode=config.get("fallback_mode", "none"),
        liquid_lookup=liquid_lookup,
        trad_lookup=trad_lookup,
        output_dir=output_dir,
        start_date=start_date,
        end_date=end_date,
        collect_diagnostics=collect_diagnostics,
    )
    return metrics


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


def run_backtest_and_save(
    signal_df: pd.DataFrame,
    price_cache: dict,
    strategy_name: str,
    signal_col: str,
    top_k: int,
    rebalance_days: int,
    min_hold_days: int,
    candidate_scan_multiplier: int,
    sizing_mode: str,
    fallback_mode: str,
    liquid_lookup: dict,
    trad_lookup: dict,
    output_dir: Path,
    start_date: str,
    end_date: str,
    collect_diagnostics: bool = False,
) -> dict:
    """Run backtest and save artifacts."""
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n  Running: {strategy_name}")
    print(
        "    Signal: "
        f"{signal_col}, Top-K: {top_k}, Rebal: {rebalance_days}d, Hold: {min_hold_days}d, "
        f"Scan: {candidate_scan_multiplier}, Sizing: {sizing_mode}, Fallback: {fallback_mode}"
    )

    start_time = time.time()
    result = bt.simulate_topk_constraint_compliant(
        signal_df,
        price_cache,
        signal_col=signal_col,
        top_k=top_k,
        rebalance_days=rebalance_days,
        min_hold_days=min_hold_days,
        use_filters=True,
        liquid_lookup=liquid_lookup,
        trad_lookup=trad_lookup,
        collect_diagnostics=collect_diagnostics,
        candidate_scan_multiplier=candidate_scan_multiplier,
        sizing_mode=sizing_mode,
        fallback_mode=fallback_mode,
    )
    elapsed = time.time() - start_time

    print(f"    Result: {result.total_return:.2%} return, {result.n_trades} trades, {elapsed:.1f}s")

    curve = result.curve
    if curve is not None and len(curve) > 0:
        curve.to_parquet(output_dir / "daily_equity.parquet", index=False)

    config = {
        "strategy": strategy_name,
        "signal_col": signal_col,
        "top_k": top_k,
        "rebalance_days": rebalance_days,
        "min_hold_days": min_hold_days,
        "candidate_scan_multiplier": candidate_scan_multiplier,
        "sizing_mode": sizing_mode,
        "fallback_mode": fallback_mode,
        "collect_diagnostics": collect_diagnostics,
        "start_date": start_date,
        "end_date": end_date,
        "timestamp": datetime.now().isoformat(),
    }
    with open(output_dir / "config.json", "w") as f:
        json.dump(config, f, indent=2)

    per_year = []
    if curve is not None and len(curve) > 0:
        curve_copy = curve.copy()
        curve_copy['year'] = pd.to_datetime(curve_copy['date']).dt.year
        for year, grp in curve_copy.groupby('year'):
            if len(grp) > 1:
                year_ret = (grp['portfolio_value'].iloc[-1] / grp['portfolio_value'].iloc[0]) - 1.0
                per_year.append({
                    "year": int(year),
                    "return": round(year_ret, 6),
                    "days": len(grp),
                })

    benchmark = get_benchmark(start_date, end_date)
    benchmark_return = benchmark["total_return"] if benchmark else None
    excess_return = (result.total_return - benchmark_return) if benchmark_return is not None else None

    metrics = {
        "strategy_name": strategy_name,
        "start_date": start_date,
        "end_date": end_date,
        "total_return": round(result.total_return, 6),
        "annualized_return": round(result.annualized_return, 6) if result.annualized_return else None,
        "sharpe": round(result.sharpe, 6) if result.sharpe else None,
        "max_drawdown": round(result.max_drawdown, 6) if result.max_drawdown else None,
        "total_trades": result.n_trades,
        "n_filtered": result.n_filtered if hasattr(result, 'n_filtered') else 0,
        "per_year": per_year,
        "benchmark_return": round(benchmark_return, 6) if benchmark_return is not None else None,
        "excess_return": round(excess_return, 6) if excess_return is not None else None,
    }
    with open(output_dir / "metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)

    if collect_diagnostics and result.diagnostics:
        diagnostics_file_map = {
            "trade_log": "trade_log.csv",
            "selection_log": "selection_log.csv",
            "filtered_breakdown": "filtered_breakdown.csv",
            "fallback_log": "fallback_log.csv",
        }
        for key, filename in diagnostics_file_map.items():
            df = result.diagnostics.get(key)
            if isinstance(df, pd.DataFrame) and len(df) > 0:
                df.to_csv(output_dir / filename, index=False)

    print(f"    Artifacts: {output_dir.name}")
    return metrics


def run_single_strategy(
    config: dict,
    start_date: str,
    end_date: str,
    allow_2026: bool,
    liquid_lookup: dict,
    trad_lookup: dict,
    price_cache: dict,
    run_id: str,
    output_dir: Path = None,
    collect_diagnostics: bool = False,
) -> dict:
    """Run a single strategy and return metrics."""
    strategy_name = config["name"]
    if output_dir is None:
        output_dir = ARTIFACT_DIR / "runs" / run_id / strategy_name

    signal_df = prepare_signal_df_from_config(config, start_date, end_date, allow_2026)

    return run_backtest_and_save(
        signal_df,
        price_cache,
        strategy_name=strategy_name,
        signal_col=config["signal_col"],
        top_k=config["top_k"],
        rebalance_days=config["rebalance_days"],
        min_hold_days=config["min_hold_days"],
        candidate_scan_multiplier=config.get("candidate_scan_multiplier", 3),
        sizing_mode=config.get("sizing_mode", "fixed_initial"),
        fallback_mode=config.get("fallback_mode", "none"),
        liquid_lookup=liquid_lookup,
        trad_lookup=trad_lookup,
        output_dir=output_dir,
        start_date=start_date,
        end_date=end_date,
        collect_diagnostics=collect_diagnostics,
    )


def save_summary_table(all_metrics: list[dict], run_id: str, update_latest: bool = False):
    """Save comparison summary table."""
    summary_dir = ARTIFACT_DIR / "summaries"
    summary_dir.mkdir(parents=True, exist_ok=True)

    df = pd.DataFrame(all_metrics)
    df = df.sort_values("annualized_return", ascending=False)

    # Save as parquet
    parquet_path = summary_dir / f"{run_id}_summary.parquet"
    df.to_parquet(parquet_path, index=False)

    # Save as CSV
    csv_path = summary_dir / f"{run_id}_summary.csv"
    df.to_csv(csv_path, index=False)

    # Optionally save as "latest" (disabled by default to avoid noisy git diffs)
    if update_latest:
        df.to_parquet(summary_dir / "latest_summary.parquet", index=False)
        df.to_csv(summary_dir / "latest_summary.csv", index=False)

    return df


def print_summary_table(all_metrics: list[dict], failed_strategies: list[tuple] = None):
    """Print a compact summary table to console."""
    if not all_metrics and not failed_strategies:
        return

    print("\n" + "=" * 80)
    print("STRATEGY COMPARISON")
    print("=" * 80)

    has_benchmark = any(m.get('benchmark_return') is not None for m in all_metrics)

    if has_benchmark:
        print(f"{'Strategy':<25} {'Return':>10} {'Benchmark':>10} {'Excess':>10} {'Sharpe':>8} {'Trades':>8}")
        print("-" * 80)
        for m in sorted(all_metrics, key=lambda x: x.get('annualized_return') or 0, reverse=True):
            ret = f"{m.get('total_return', 0):.1%}" if m.get('total_return') else "N/A"
            bench = f"{m.get('benchmark_return', 0):.1%}" if m.get('benchmark_return') is not None else "N/A"
            excess = f"{m.get('excess_return', 0):+.1%}" if m.get('excess_return') is not None else "N/A"
            sharpe = f"{m['sharpe']:.2f}" if m.get('sharpe') else "N/A"
            trades = str(m.get('total_trades', 0))
            print(f"{m['strategy_name']:<25} {ret:>10} {bench:>10} {excess:>10} {sharpe:>8} {trades:>8}")
    else:
        print(f"{'Strategy':<25} {'Return':>10} {'Sharpe':>8} {'MDD':>10} {'Trades':>8}")
        print("-" * 80)
        for m in sorted(all_metrics, key=lambda x: x.get('annualized_return') or 0, reverse=True):
            ret = f"{m.get('total_return', 0):.1%}" if m.get('total_return') else "N/A"
            sharpe = f"{m['sharpe']:.2f}" if m.get('sharpe') else "N/A"
            mdd = f"{m.get('max_drawdown', 0):.1%}" if m.get('max_drawdown') else "N/A"
            trades = str(m.get('total_trades', 0))
            print(f"{m['strategy_name']:<25} {ret:>10} {sharpe:>8} {mdd:>10} {trades:>8}")

    print("=" * 80)


def main():
    parser = create_argument_parser()
    args = parser.parse_args()

    # Validate arguments
    if not args.strategy and not args.all_strategies:
        print("ERROR: Must specify --strategy or --all-strategies")
        print("Available strategies:")
        for name in strategy_loader.list_strategies():
            print(f"  {name}")
        sys.exit(1)

    allow_2026 = args.allow_lockbox
    start_date = args.start_date
    end_date = args.end_date
    custom_output_dir = Path(args.output_dir) if args.output_dir else None

    if not allow_2026 and end_date > "2025-12-31":
        print(f"ERROR: end-date {end_date} is past lockbox date 2025-12-31.")
        print("Use --allow-lockbox to override (only for testing).")
        sys.exit(1)

    # Determine strategies to run
    if args.all_strategies:
        strategy_names = strategy_loader.list_strategies()
    else:
        strategy_names = [args.strategy]

    print("Loading caches...")
    liquid_lookup, trad_lookup, price_cache = load_caches()
    print(f"  Liquid: {len(liquid_lookup)} dates, Trad: {len(trad_lookup)} entries, Price: {len(price_cache)} tickers")

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    all_metrics = []
    failed_strategies = []

    print(f"\nRunning {len(strategy_names)} strategy(ies) from {start_date} to {end_date}...")

    for i, name in enumerate(strategy_names):
        print(f"\n[{i+1}/{len(strategy_names)}] ", end="")
        try:
            config = strategy_loader.load_strategy_config(name)

            if custom_output_dir and not args.all_strategies:
                output_dir = custom_output_dir / name
            else:
                output_dir = ARTIFACT_DIR / "runs" / run_id / name

            metrics = run_single_strategy(
                config, start_date, end_date, allow_2026,
                liquid_lookup, trad_lookup, price_cache, run_id,
                output_dir=output_dir,
                collect_diagnostics=args.collect_diagnostics,
            )
            all_metrics.append(metrics)
        except Exception as e:
            print(f"FAILED: {name} - {e}")
            failed_strategies.append((name, str(e)))
            continue

    # Generate summary
    if all_metrics:
        df = save_summary_table(all_metrics, run_id, update_latest=args.update_latest)
        print_summary_table(all_metrics, failed_strategies)

        summary_dir = ARTIFACT_DIR / "summaries"
        print(f"\nSummary saved to:")
        print(f"  {summary_dir / run_id}_summary.parquet")
        print(f"  {summary_dir / run_id}_summary.csv")
        if args.update_latest:
            print(f"  {summary_dir / 'latest_summary.parquet'}")

        if custom_output_dir and not args.all_strategies:
            print(f"  {custom_output_dir / name}")
    else:
        print("\nNo strategies completed successfully.")

    # Report failed strategies
    if failed_strategies:
        print(f"\n{'='*80}")
        print(f"FAILED STRATEGIES: {len(failed_strategies)}")
        print("=" * 80)
        for name, err in failed_strategies:
            print(f"  {name}: {err}")
        print(f"\nSuccessful: {len(all_metrics)}, Failed: {len(failed_strategies)}")


if __name__ == "__main__":
    main()
