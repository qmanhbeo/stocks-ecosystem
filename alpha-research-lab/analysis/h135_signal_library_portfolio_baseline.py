"""
H135: Realistic deterministic portfolio baseline for the promoted signal library.

Purpose:
- test whether the current cross-sectional signal set monetizes in a realistic long-only portfolio
- compare simple deterministic blends before spending more effort on portfolio RL
- enforce the workspace execution contract: next-open execution, T+2.5 sellability,
  zero-volume blocks, ceiling/floor blocks, fees, and a simple ADV participation cap

Default strategies:
- s1_only: primary cross-sectional signal only
- recent_core: S1 + C10-C14
- full_library: all promoted columns in xs_rl_signal_matrix.parquet

Default realism settings:
- rebalance every 3 signal days to align with the T+2.5 sellability floor
- capacity cap disabled by default; enable explicitly with --max-adv-participation for stress testing

Usage:
    conda run -n stocks python analysis/h135_signal_library_portfolio_baseline.py
    conda run -n stocks python analysis/h135_signal_library_portfolio_baseline.py \
        --strategies recent_core full_library --top-k 5 --portfolio-notional-vnd 1000000000
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = ROOT.parent
SHARED_MARKET_RULES_ROOT = WORKSPACE_ROOT / "shared-market-rules"
if str(SHARED_MARKET_RULES_ROOT) not in sys.path:
    sys.path.insert(0, str(SHARED_MARKET_RULES_ROOT))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared_market_rules import required_holding_age_for_sell

from src.deterministic_portfolio import (
    WEIGHTING_RULES,
    build_market_inputs,
    compute_strategy_scores,
    default_strategy_names,
    load_benchmark_open,
    load_or_build_tradability_panel,
    load_price_panel,
    resolve_strategy_columns,
    simulate_strategy,
)
from src.run_summary import write_run_summary

RL_MATRIX_PATH = Path("data/features/xs_rl_signal_matrix.parquet")
TRADABILITY_PATH = Path("data/features/execution/tradability_daily.parquet")
STOCK_DIR = Path("data/stock")
BENCHMARK_PATH = STOCK_DIR / "gia_lich_su_VNINDEX_1D.parquet"
OUT_DIR = Path("artifacts/portfolio_baselines")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", type=str, default=str(RL_MATRIX_PATH))
    parser.add_argument("--tradability", type=str, default=str(TRADABILITY_PATH))
    parser.add_argument("--stock-dir", type=str, default=str(STOCK_DIR))
    parser.add_argument("--benchmark", type=str, default=str(BENCHMARK_PATH))
    parser.add_argument(
        "--strategies",
        nargs="+",
        default=list(default_strategy_names()),
        help="Built-in blends to evaluate",
    )
    parser.add_argument(
        "--signal-columns",
        nargs="+",
        default=None,
        help="Optional custom signal column list to evaluate as one extra strategy",
    )
    parser.add_argument("--custom-name", type=str, default="custom_blend")
    parser.add_argument("--start-year", type=int, default=2015)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--rebalance-days", type=int, default=3)
    parser.add_argument(
        "--weighting",
        type=str,
        default="equal",
        choices=list(WEIGHTING_RULES),
        help="Weighting across the selected names; linear/square are relative to the selected score spread",
    )
    parser.add_argument("--min-score", type=float, default=None)
    parser.add_argument("--portfolio-notional-vnd", type=float, default=1_000_000_000.0)
    parser.add_argument(
        "--max-adv-participation",
        type=float,
        default=0.0,
        help="ADV20 participation cap; set to 0 to disable capacity clipping",
    )
    parser.add_argument("--buy-fee-rate", type=float, default=0.0015)
    parser.add_argument("--sell-fee-rate", type=float, default=0.0015)
    parser.add_argument("--capital-gains-tax-rate", type=float, default=0.0)
    parser.add_argument(
        "--required-holding-age",
        type=int,
        default=3,
        help="Sellability floor in execution steps; values below market floor are clamped up",
    )
    return parser.parse_args()


def _resolve_strategy_map(args: argparse.Namespace, matrix_columns: list[str]) -> dict[str, list[str]]:
    strategy_map: dict[str, list[str]] = {}
    for name in args.strategies:
        strategy_map[str(name)] = resolve_strategy_columns(matrix_columns, str(name))

    if args.signal_columns:
        custom_name = str(args.custom_name).strip()
        if not custom_name:
            raise ValueError("custom_name must be non-empty when signal-columns is provided")
        if custom_name in strategy_map:
            raise ValueError(f"custom_name {custom_name!r} collides with a built-in strategy")
        custom_columns = [str(col).strip() for col in args.signal_columns if str(col).strip()]
        missing = [col for col in custom_columns if col not in matrix_columns]
        if missing:
            raise ValueError(f"Custom signal columns missing from matrix: {missing}")
        strategy_map[custom_name] = custom_columns

    return strategy_map


def _print_summary(results: list[dict[str, object]]) -> None:
    print("\n" + "=" * 110)
    print("H135: SIGNAL LIBRARY PORTFOLIO BASELINE")
    print("=" * 110)
    print(
        f"{'strategy':<18} {'tot_ret':>10} {'rel_ret':>10} {'ann_ret':>10} {'IR':>8} "
        f"{'max_dd':>9} {'turn/day':>10} {'cash':>8} {'holds':>8} {'yrs+':>7}"
    )
    print("-" * 110)
    for row in results:
        print(
            f"{row['strategy']:<18} "
            f"{row['portfolio_total_return']*100:>+9.2f}% "
            f"{row['relative_total_return']*100:>+9.2f}% "
            f"{row['portfolio_annualized_return']*100 if row['portfolio_annualized_return'] is not None else float('nan'):>+9.2f}% "
            f"{row['information_ratio_annualized'] if row['information_ratio_annualized'] is not None else float('nan'):>8.2f} "
            f"{row['max_drawdown']*100:>8.2f}% "
            f"{row['avg_daily_turnover']*100:>9.2f}% "
            f"{row['avg_cash_weight']*100:>7.2f}% "
            f"{row['avg_num_holdings']:>8.2f} "
            f"{row['positive_years']:>3}/{row['total_years']:<3}"
        )


def main() -> None:
    args = parse_args()
    matrix_path = Path(args.matrix)
    tradability_path = Path(args.tradability)
    stock_dir = Path(args.stock_dir)
    benchmark_path = Path(args.benchmark)

    print(f"Loading signal matrix: {matrix_path}")
    matrix = pd.read_parquet(matrix_path)
    matrix["time"] = pd.to_datetime(matrix["time"])
    matrix = matrix[(matrix["time"].dt.year >= args.start_year) & (matrix["time"].dt.year <= args.end_year)].copy()
    if matrix.empty:
        raise ValueError(f"No matrix rows in year range {args.start_year}-{args.end_year}")
    print(f"  rows={len(matrix):,} | tickers={matrix['ticker'].nunique()} | dates={matrix['time'].nunique()}")

    strategy_map = _resolve_strategy_map(args, matrix.columns.tolist())
    print(f"Strategies: {', '.join(strategy_map)}")

    scored = compute_strategy_scores(matrix, strategy_map)

    print("Loading prices and ADV20...")
    price_panel = load_price_panel(scored["ticker"].unique().tolist(), stock_dir)
    if price_panel.empty:
        raise ValueError(f"No price rows found under {stock_dir}")
    print(f"  price rows={len(price_panel):,}")

    print(f"Loading tradability flags: {tradability_path}")
    tradability, tradability_source = load_or_build_tradability_panel(price_panel, tradability_path)
    print(f"  source={tradability_source} | rows={len(tradability):,}")

    benchmark_open = load_benchmark_open(benchmark_path)
    market_inputs = build_market_inputs(
        scored,
        price_panel,
        tradability,
        benchmark_open,
        tradability_source=tradability_source,
        strategy_names=list(strategy_map),
        start_year=args.start_year,
        end_year=args.end_year,
    )

    required_holding_age = required_holding_age_for_sell(
        min_hold_days_override=int(args.required_holding_age)
    )
    print(
        f"Execution realism: rebalance_every={args.rebalance_days} | top_k={args.top_k} | "
        f"weighting={args.weighting} | required_holding_age={required_holding_age} | "
        f"max_adv_participation={args.max_adv_participation:.2%}"
    )

    run_results = []
    stacked_daily = []
    for strategy_name, signal_columns in strategy_map.items():
        print(f"\nRunning strategy: {strategy_name} ({len(signal_columns)} signals)")
        result = simulate_strategy(
            strategy_name=strategy_name,
            signal_columns=signal_columns,
            market_inputs=market_inputs,
            top_k=int(args.top_k),
            rebalance_every=int(args.rebalance_days),
            weighting=str(args.weighting),
            initial_notional_vnd=float(args.portfolio_notional_vnd),
            max_adv_participation=float(args.max_adv_participation),
            required_holding_age=int(required_holding_age),
            buy_fee_rate=float(args.buy_fee_rate),
            sell_fee_rate=float(args.sell_fee_rate),
            capital_gains_tax_rate=float(args.capital_gains_tax_rate),
            min_score=float(args.min_score) if args.min_score is not None else None,
        )
        strategy_summary = {
            "strategy": strategy_name,
            "signal_columns": list(result.signal_columns),
            **result.summary,
        }
        run_results.append(strategy_summary)
        stacked_daily.append(result.daily)

    _print_summary(run_results)

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    daily_path = OUT_DIR / f"{ts}_h135_signal_library_portfolio_baseline_daily.parquet"
    pd.concat(stacked_daily, ignore_index=True).to_parquet(daily_path, index=False)

    summary = {
        "year_range": [int(args.start_year), int(args.end_year)],
        "tradability_source": tradability_source,
        "top_k": int(args.top_k),
        "rebalance_days": int(args.rebalance_days),
        "weighting": str(args.weighting),
        "min_score": float(args.min_score) if args.min_score is not None else None,
        "portfolio_notional_vnd": float(args.portfolio_notional_vnd),
        "max_adv_participation": float(args.max_adv_participation),
        "buy_fee_rate": float(args.buy_fee_rate),
        "sell_fee_rate": float(args.sell_fee_rate),
        "capital_gains_tax_rate": float(args.capital_gains_tax_rate),
        "required_holding_age": int(required_holding_age),
        "strategies": {row["strategy"]: row for row in run_results},
    }
    summary_path = write_run_summary(
        ts=ts,
        mode="portfolio_baseline",
        name="h135_signal_library_portfolio_baseline",
        summary=summary,
        artifacts={"daily_results": str(daily_path)},
        metadata={
            "matrix": str(matrix_path),
            "tradability": str(tradability_path),
            "stock_dir": str(stock_dir),
            "benchmark": str(benchmark_path),
        },
    )

    print(f"\nSaved daily results -> {daily_path}")
    print(f"Saved run summary  -> {summary_path}")


if __name__ == "__main__":
    main()
