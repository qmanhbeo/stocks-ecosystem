"""
H136: Portfolio construction sweep for the realistic deterministic signal-library baseline.

Purpose:
- test whether the promoted signal library monetizes under better construction choices
- keep the same execution reality as H135 while sweeping top-k, rebalance cadence,
  weighting, and score gating
- identify the best realistic long-only deterministic baseline before more RL work

Default scope:
- strategy: `full_library`
- top-k: 3, 5, 8, 10
- rebalance cadence: 3, 5, 10 signal days
- weighting: equal, linear, square
- score gates: calibrated from the empirical score distribution for the chosen strategy

Usage:
    conda run -n stocks python analysis/h136_portfolio_construction_sweep.py
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from path_utils import data_path


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
from src.portfolio_construction_search import (
    candidate_sort_key,
    enumerate_config_grid,
    parse_min_score_grid,
    sort_candidate_results,
)
from src.run_summary import write_run_summary

RL_MATRIX_PATH = data_path("features/xs_rl_signal_matrix.parquet")
TRADABILITY_PATH = data_path("features/execution/tradability_daily.parquet")
STOCK_DIR = data_path("stock")
BENCHMARK_PATH = STOCK_DIR / "gia_lich_su_VNINDEX_1D.parquet"
OUT_DIR = ROOT / "artifacts/portfolio_baselines"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", type=str, default=str(RL_MATRIX_PATH))
    parser.add_argument("--tradability", type=str, default=str(TRADABILITY_PATH))
    parser.add_argument("--stock-dir", type=str, default=str(STOCK_DIR))
    parser.add_argument("--benchmark", type=str, default=str(BENCHMARK_PATH))
    parser.add_argument(
        "--strategy",
        type=str,
        default="full_library",
        choices=list(default_strategy_names()),
        help="Built-in signal blend to sweep",
    )
    parser.add_argument("--start-year", type=int, default=2015)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--top-k-grid", nargs="+", type=int, default=[3, 5, 8, 10])
    parser.add_argument("--rebalance-grid", nargs="+", type=int, default=[3, 5, 10])
    parser.add_argument(
        "--weighting-grid",
        nargs="+",
        default=list(WEIGHTING_RULES),
        choices=list(WEIGHTING_RULES),
    )
    parser.add_argument(
        "--min-score-grid",
        nargs="+",
        default=None,
        help="Optional explicit thresholds; use 'none' to include the ungated baseline",
    )
    parser.add_argument("--portfolio-notional-vnd", type=float, default=1_000_000_000.0)
    parser.add_argument("--max-adv-participation", type=float, default=0.0)
    parser.add_argument("--buy-fee-rate", type=float, default=0.0015)
    parser.add_argument("--sell-fee-rate", type=float, default=0.0015)
    parser.add_argument("--capital-gains-tax-rate", type=float, default=0.0)
    parser.add_argument("--required-holding-age", type=int, default=3)
    parser.add_argument("--top-results", type=int, default=15)
    return parser.parse_args()

def _print_top(results: pd.DataFrame, top_n: int) -> None:
    display = results.head(top_n).copy()
    if display.empty:
        print("No sweep results.")
        return
    print("\n" + "=" * 148)
    print("H136: PORTFOLIO CONSTRUCTION SWEEP")
    print("=" * 148)
    print(
        f"{'rank':<5} {'top_k':>5} {'cad':>5} {'weight':>8} {'gate':>7} "
        f"{'tot_ret':>10} {'ann_ret':>10} {'IR':>8} {'max_dd':>9} "
        f"{'turn/day':>10} {'cash':>8} {'holds':>8} {'yrs+':>7}"
    )
    print("-" * 148)
    for i, row in enumerate(display.itertuples(index=False), start=1):
        gate = "none" if row.min_score is None else f"{row.min_score:.3f}"
        print(
            f"{i:<5} {row.top_k:>5} {row.rebalance_every:>5} {row.weighting:>8} {gate:>7} "
            f"{row.portfolio_total_return*100:>+9.2f}% "
            f"{row.portfolio_annualized_return*100 if row.portfolio_annualized_return is not None else float('nan'):>+9.2f}% "
            f"{row.information_ratio_annualized if row.information_ratio_annualized is not None else float('nan'):>8.2f} "
            f"{row.max_drawdown*100:>8.2f}% "
            f"{row.avg_daily_turnover*100:>9.2f}% "
            f"{row.avg_cash_weight*100:>7.2f}% "
            f"{row.avg_num_holdings:>8.2f} "
            f"{row.positive_years:>3}/{row.total_years:<3}"
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

    signal_columns = resolve_strategy_columns(matrix.columns.tolist(), str(args.strategy))
    scored = compute_strategy_scores(matrix, {str(args.strategy): signal_columns})
    score_col = f"score__{args.strategy}"
    min_score_grid = parse_min_score_grid(args.min_score_grid, scored[score_col])
    print(f"Strategy: {args.strategy} ({len(signal_columns)} signals)")
    print(f"Score gates: {['none' if v is None else round(v, 3) for v in min_score_grid]}")

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
        strategy_names=[str(args.strategy)],
        start_year=args.start_year,
        end_year=args.end_year,
    )

    required_holding_age = required_holding_age_for_sell(
        min_hold_days_override=int(args.required_holding_age)
    )

    rows: list[dict[str, object]] = []
    best_daily: pd.DataFrame | None = None
    best_key: tuple[float, float, float, float] | None = None
    grid = enumerate_config_grid(
        top_k_grid=args.top_k_grid,
        rebalance_grid=args.rebalance_grid,
        weighting_grid=args.weighting_grid,
        min_score_grid=min_score_grid,
    )
    print(f"Running {len(grid)} configurations with required_holding_age={required_holding_age}...")

    for top_k, rebalance_days, weighting, min_score in grid:
        result = simulate_strategy(
            strategy_name=str(args.strategy),
            signal_columns=signal_columns,
            market_inputs=market_inputs,
            top_k=int(top_k),
            rebalance_every=int(rebalance_days),
            weighting=str(weighting),
            initial_notional_vnd=float(args.portfolio_notional_vnd),
            max_adv_participation=float(args.max_adv_participation),
            required_holding_age=int(required_holding_age),
            buy_fee_rate=float(args.buy_fee_rate),
            sell_fee_rate=float(args.sell_fee_rate),
            capital_gains_tax_rate=float(args.capital_gains_tax_rate),
            min_score=float(min_score) if min_score is not None else None,
        )
        row = {
            "strategy": str(args.strategy),
            "top_k": int(top_k),
            "rebalance_every": int(rebalance_days),
            "weighting": str(weighting),
            "min_score": float(min_score) if min_score is not None else None,
            "signal_columns": list(result.signal_columns),
        }
        row.update(result.summary)
        row["rebalance_event_days"] = row.pop("rebalance_days")
        rows.append(row)

        sort_key = candidate_sort_key(row)
        if best_key is None or sort_key > best_key:
            best_key = sort_key
            best_daily = result.daily.assign(
                top_k=int(top_k),
                rebalance_days=int(rebalance_days),
                weighting=str(weighting),
                min_score=float(min_score) if min_score is not None else None,
            )

    results = sort_candidate_results(pd.DataFrame(rows))

    _print_top(results, int(args.top_results))

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    sweep_path = OUT_DIR / f"{ts}_h136_portfolio_construction_sweep.parquet"
    csv_path = OUT_DIR / f"{ts}_h136_portfolio_construction_sweep.csv"
    best_daily_path = OUT_DIR / f"{ts}_h136_portfolio_construction_sweep_best_daily.parquet"
    results.to_parquet(sweep_path, index=False)
    results.to_csv(csv_path, index=False)
    if best_daily is not None:
        best_daily.to_parquet(best_daily_path, index=False)

    top_records = json.loads(results.head(min(int(args.top_results), len(results))).to_json(orient="records"))
    best_row = top_records[0] if top_records else {}
    summary = {
        "strategy": str(args.strategy),
        "year_range": [int(args.start_year), int(args.end_year)],
        "top_k_grid": sorted(set(int(v) for v in args.top_k_grid)),
        "rebalance_grid": sorted(set(int(v) for v in args.rebalance_grid)),
        "weighting_grid": [str(v) for v in args.weighting_grid],
        "min_score_grid": [None if v is None else float(v) for v in min_score_grid],
        "required_holding_age": int(required_holding_age),
        "portfolio_notional_vnd": float(args.portfolio_notional_vnd),
        "max_adv_participation": float(args.max_adv_participation),
        "buy_fee_rate": float(args.buy_fee_rate),
        "sell_fee_rate": float(args.sell_fee_rate),
        "capital_gains_tax_rate": float(args.capital_gains_tax_rate),
        "num_configurations": int(len(results)),
        "best_configuration": best_row,
        "top_results": top_records,
    }
    summary_path = write_run_summary(
        ts=ts,
        mode="portfolio_construction_sweep",
        name="h136_portfolio_construction_sweep",
        summary=summary,
        artifacts={
            "sweep_results": str(sweep_path),
            "sweep_results_csv": str(csv_path),
            "best_daily_results": str(best_daily_path) if best_daily is not None else "",
        },
        metadata={
            "matrix": str(matrix_path),
            "tradability": str(tradability_path),
            "stock_dir": str(stock_dir),
            "benchmark": str(benchmark_path),
        },
    )

    print(f"\nSaved sweep results -> {sweep_path}")
    print(f"Saved csv results   -> {csv_path}")
    if best_daily is not None:
        print(f"Saved best daily    -> {best_daily_path}")
    print(f"Saved run summary   -> {summary_path}")


if __name__ == "__main__":
    main()
