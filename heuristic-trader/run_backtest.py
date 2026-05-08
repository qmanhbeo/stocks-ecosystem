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


ARTIFACT_DIR = Path("/home/manh/stocks-ecosystem/heuristic-trader/artifacts")
CACHE_DIR = Path("/home/manh/stocks-ecosystem/heuristic-trader/cache")

import backtest as bt
bt.CACHE_DIR = CACHE_DIR
bt.PRICE_CACHE_FILE = CACHE_DIR / "price_cache.parquet"
bt.LIQUID_CACHE_FILE = CACHE_DIR / "liquid_lookup.joblib"
bt.TRAD_CACHE_FILE = CACHE_DIR / "trad_lookup.joblib"


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
    return parser


def load_caches():
    """Load pre-computed caches."""
    liquid_lookup = bt.load_liquid_lookup()
    trad_lookup = bt.load_trad_lookup()
    price_cache = bt.load_price_cache()
    return liquid_lookup, trad_lookup, price_cache


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
        df = c16[['time', 'ticker', 'order_volume_ratio_rank']].copy()
        df = df.rename(columns={'order_volume_ratio_rank': 's1_proba'})
        return df
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


def run_backtest_and_save(
    signal_df: pd.DataFrame,
    price_cache: dict,
    strategy_name: str,
    signal_col: str,
    top_k: int,
    rebalance_days: int,
    min_hold_days: int,
    liquid_lookup: dict,
    trad_lookup: dict,
    output_dir: Path,
    start_date: str,
    end_date: str,
) -> dict:
    """Run backtest and save artifacts."""
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n  Running: {strategy_name}")
    print(f"    Signal: {signal_col}, Top-K: {top_k}, Rebal: {rebalance_days}d, Hold: {min_hold_days}d")

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
    }
    with open(output_dir / "metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)

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
) -> dict:
    """Run a single strategy and return metrics."""
    strategy_name = config["name"]
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
        liquid_lookup=liquid_lookup,
        trad_lookup=trad_lookup,
        output_dir=output_dir,
        start_date=start_date,
        end_date=end_date,
    )


def save_summary_table(all_metrics: list[dict], run_id: str):
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

    # Also save as "latest"
    df.to_parquet(summary_dir / "latest_summary.parquet", index=False)
    df.to_csv(summary_dir / "latest_summary.csv", index=False)

    return df


def print_summary_table(all_metrics: list[dict]):
    """Print a compact summary table to console."""
    if not all_metrics:
        return

    print("\n" + "=" * 80)
    print("STRATEGY COMPARISON")
    print("=" * 80)
    print(f"{'Strategy':<25} {'Return':>10} {'Sharpe':>8} {'MDD':>10} {'Trades':>8}")
    print("-" * 80)

    for m in sorted(all_metrics, key=lambda x: x.get('annualized_return') or 0, reverse=True):
        ret = f"{m.get('total_return', 0):.1%}" if m.get('total_return') else "N/A"
        sharpe = f"{m['sharpe']:.2f}" if m.get('sharpe') else "N/A"
        mdd = f"{m['max_drawdown']:.1%}" if m.get('max_drawdown') else "N/A"
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

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    all_metrics = []

    print(f"\nRunning {len(strategy_names)} strategy(ies) from {start_date} to {end_date}...")

    for i, name in enumerate(strategy_names):
        print(f"\n[{i+1}/{len(strategy_names)}] ", end="")
        try:
            config = strategy_loader.load_strategy_config(name)
            metrics = run_single_strategy(
                config, start_date, end_date, allow_2026,
                liquid_lookup, trad_lookup, price_cache, run_id
            )
            all_metrics.append(metrics)
        except (KeyError, ValueError) as e:
            print(f"ERROR loading strategy '{name}': {e}")
            continue

    # Generate summary
    if all_metrics:
        df = save_summary_table(all_metrics, run_id)
        print_summary_table(all_metrics)

        summary_dir = ARTIFACT_DIR / "summaries"
        print(f"\nSummary saved to:")
        print(f"  {summary_dir / run_id}_summary.parquet")
        print(f"  {summary_dir / run_id}_summary.csv")
        print(f"  {summary_dir / 'latest_summary.parquet'}")
    else:
        print("\nNo strategies completed successfully.")


if __name__ == "__main__":
    main()