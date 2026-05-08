#!/usr/bin/env python3
"""
CLI entrypoint for heuristic-trader backtests.

Usage:
    python run_backtest.py --strategy s1_only --start-date 2019-01-01 --end-date 2025-12-31 --top-k 5 --rebalance-days 5

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
        default="s1_only",
        choices=["s1_only", "blend_70_30", "blend_50_50", "c16_only"],
        help="Signal strategy to use",
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
        "--top-k",
        type=int,
        default=5,
        help="Number of top stocks to hold",
    )
    parser.add_argument(
        "--rebalance-days",
        type=int,
        default=5,
        help="Rebalance every N days",
    )
    parser.add_argument(
        "--min-hold-days",
        type=int,
        default=3,
        help="Minimum holding days before selling",
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


def prepare_signal_df(
    strategy: str,
    start_date: str,
    end_date: str,
    allow_2026: bool = False,
) -> pd.DataFrame:
    """Prepare signal DataFrame based on strategy."""
    s1 = s.load_rl_signal_matrix(start=start_date, end=end_date, allow_2026=allow_2026)

    if strategy == "s1_only":
        return s1[['time', 'ticker', 's1_proba']].copy()
    elif strategy == "c16_only":
        c16 = s.load_order_pressure(start=start_date, end=end_date, allow_2026=allow_2026)
        df = c16[['time', 'ticker', 'order_volume_ratio_rank']].copy()
        df = df.rename(columns={'order_volume_ratio_rank': 's1_proba'})
        return df
    elif strategy in ("blend_70_30", "blend_50_50"):
        c16 = s.load_order_pressure(start=start_date, end=end_date, allow_2026=allow_2026)
        df = s1[['time', 'ticker', 's1_proba']].merge(
            c16[['time', 'ticker', 'order_volume_ratio_rank']],
            on=['time', 'ticker']
        )
        if strategy == "blend_70_30":
            df['signal'] = df['s1_proba'] * 0.7 + df['order_volume_ratio_rank'] * 0.3
        else:
            df['signal'] = df['s1_proba'] * 0.5 + df['order_volume_ratio_rank'] * 0.5
        return df[['time', 'ticker', 'signal']]
    else:
        raise ValueError(f"Unknown strategy: {strategy}")


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

    print(f"\nRunning backtest: {strategy_name}")
    print(f"  Signal column: {signal_col}")
    print(f"  Top-K: {top_k}, Rebalance: {rebalance_days}d, Min hold: {min_hold_days}d")

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

    print(f"  Result: {result.total_return:.2%} return, {result.n_trades} trades, {elapsed:.1f}s")

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

    years_in_data = pd.to_datetime(curve['date']).dt.year.unique() if curve is not None and len(curve) > 0 else []
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
        "strategy_name": result.name,
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

    print(f"\nArtifacts saved to: {output_dir}")
    print(f"  - config.json")
    print(f"  - metrics.json")
    if curve is not None and len(curve) > 0:
        print(f"  - daily_equity.parquet ({len(curve)} rows)")

    return metrics


def main():
    parser = create_argument_parser()
    args = parser.parse_args()

    allow_2026 = args.allow_lockbox
    start_date = args.start_date
    end_date = args.end_date

    if not allow_2026 and end_date > "2025-12-31":
        print(f"ERROR: end-date {end_date} is past lockbox date 2025-12-31.")
        print("Use --allow-lockbox to override (only for testing).")
        sys.exit(1)

    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = ARTIFACT_DIR / "runs" / run_id

    print("Loading caches...")
    liquid_lookup, trad_lookup, price_cache = load_caches()
    print(f"  Liquid dates: {len(liquid_lookup)}")
    print(f"  Trad entries: {len(trad_lookup)}")
    print(f"  Price tickers: {len(price_cache)}")

    signal_col = "s1_proba" if args.strategy == "s1_only" else "signal"
    signal_df = prepare_signal_df(args.strategy, start_date, end_date, allow_2026)
    print(f"  Signal rows: {len(signal_df)}")

    metrics = run_backtest_and_save(
        signal_df,
        price_cache,
        strategy_name=args.strategy,
        signal_col=signal_col,
        top_k=args.top_k,
        rebalance_days=args.rebalance_days,
        min_hold_days=args.min_hold_days,
        liquid_lookup=liquid_lookup,
        trad_lookup=trad_lookup,
        output_dir=output_dir,
        start_date=start_date,
        end_date=end_date,
    )

    print("\n=== Summary ===")
    print(f"Total Return: {metrics['total_return']:.2%}")
    if metrics['annualized_return'] is not None:
        print(f"Annualized Return: {metrics['annualized_return']:.2%}")
    if metrics['sharpe'] is not None:
        print(f"Sharpe: {metrics['sharpe']:.2f}")
    if metrics['max_drawdown'] is not None:
        print(f"Max Drawdown: {metrics['max_drawdown']:.2%}")
    print(f"Total Trades: {metrics['total_trades']}")


if __name__ == "__main__":
    main()