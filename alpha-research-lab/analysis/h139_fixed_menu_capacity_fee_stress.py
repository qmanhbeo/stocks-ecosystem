"""
H139: Capacity and fee stress for fixed-menu long-only candidates.

Purpose:
- test whether the H138 fixed-rule survivors remain attractive after realistic deployment stress
- vary portfolio notional, ADV participation cap, and round-trip cost on the honest holdout period
- map the deployable region before considering more ML or RL complexity

Default holdout:
- 2019-2025

Default candidate menu:
- same simple rules as H138

Usage:
    conda run -n stocks python analysis/h139_fixed_menu_capacity_fee_stress.py
"""

from __future__ import annotations

import argparse
import json
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
    build_market_inputs,
    compute_strategy_scores,
    default_strategy_names,
    load_benchmark_open,
    load_or_build_tradability_panel,
    load_price_panel,
    resolve_strategy_columns,
    simulate_strategy,
)
from src.portfolio_construction_search import parse_fixed_menu_candidates
from src.run_summary import write_run_summary

RL_MATRIX_PATH = Path("data/features/xs_rl_signal_matrix.parquet")
TRADABILITY_PATH = Path("data/features/execution/tradability_daily.parquet")
STOCK_DIR = Path("data/stock")
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
    )
    parser.add_argument("--start-year", type=int, default=2019)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument(
        "--candidate",
        action="append",
        default=[],
        help="name:top_k:rebalance_every:weighting:min_score ; may be repeated",
    )
    parser.add_argument(
        "--portfolio-notional-grid",
        nargs="+",
        type=float,
        default=[50_000_000.0, 100_000_000.0, 250_000_000.0, 500_000_000.0, 1_000_000_000.0],
    )
    parser.add_argument(
        "--max-adv-grid",
        nargs="+",
        type=float,
        default=[0.0, 0.005, 0.01, 0.02],
    )
    parser.add_argument(
        "--round-trip-cost-grid",
        nargs="+",
        type=float,
        default=[0.003, 0.005],
        help="Round-trip cost assumptions; split evenly between buy and sell fees",
    )
    parser.add_argument("--capital-gains-tax-rate", type=float, default=0.0)
    parser.add_argument("--required-holding-age", type=int, default=3)
    parser.add_argument("--top-results", type=int, default=20)
    return parser.parse_args()


def _sort_results(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.sort_values(
        by=[
            "relative_total_return",
            "portfolio_total_return",
            "information_ratio_annualized",
            "avg_cash_weight",
            "avg_daily_turnover",
            "candidate_name",
            "portfolio_notional_vnd",
            "max_adv_participation",
            "round_trip_cost",
        ],
        ascending=[False, False, False, True, True, True, True, True, True],
        ignore_index=True,
    )


def _print_top(results: pd.DataFrame, top_n: int) -> None:
    top = results.head(top_n)
    print("\n" + "=" * 180)
    print("H139: FIXED-MENU CAPACITY / FEE STRESS")
    print("=" * 180)
    print(
        f"{'rank':<5} {'cand':<12} {'notional':>11} {'adv_cap':>8} {'rt_cost':>8} "
        f"{'tot_ret':>10} {'rel_ret':>10} {'ann_ret':>10} {'IR':>8} "
        f"{'cash':>8} {'turn/day':>10} {'max_dd':>9} {'yrs+':>7}"
    )
    print("-" * 180)
    for i, row in enumerate(top.itertuples(index=False), start=1):
        print(
            f"{i:<5} {row.candidate_name:<12} {row.portfolio_notional_vnd/1e6:>10.0f}m "
            f"{row.max_adv_participation*100:>7.2f}% {row.round_trip_cost*100:>7.2f}% "
            f"{row.portfolio_total_return*100:>+9.2f}% "
            f"{row.relative_total_return*100:>+9.2f}% "
            f"{row.portfolio_annualized_return*100 if row.portfolio_annualized_return is not None else float('nan'):>+9.2f}% "
            f"{row.information_ratio_annualized if row.information_ratio_annualized is not None else float('nan'):>8.2f} "
            f"{row.avg_cash_weight*100:>7.2f}% "
            f"{row.avg_daily_turnover*100:>9.2f}% "
            f"{row.max_drawdown*100:>8.2f}% "
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
    candidates = parse_fixed_menu_candidates(args.candidate)

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
        start_year=int(args.start_year),
        end_year=int(args.end_year),
    )
    required_holding_age = required_holding_age_for_sell(
        min_hold_days_override=int(args.required_holding_age)
    )

    notionals = sorted(set(float(v) for v in args.portfolio_notional_grid))
    adv_caps = sorted(set(float(v) for v in args.max_adv_grid))
    round_trip_costs = sorted(set(float(v) for v in args.round_trip_cost_grid))
    print(
        f"Strategy: {args.strategy} ({len(signal_columns)} signals) | candidates={len(candidates)} | "
        f"scenarios={len(candidates) * len(notionals) * len(adv_caps) * len(round_trip_costs)} | "
        f"required_holding_age={required_holding_age}"
    )

    rows: list[dict[str, object]] = []
    for candidate in candidates:
        for notional in notionals:
            for adv_cap in adv_caps:
                for round_trip_cost in round_trip_costs:
                    fee_leg = round_trip_cost / 2.0
                    result = simulate_strategy(
                        strategy_name=str(args.strategy),
                        signal_columns=signal_columns,
                        market_inputs=market_inputs,
                        top_k=int(candidate["top_k"]),
                        rebalance_every=int(candidate["rebalance_every"]),
                        weighting=str(candidate["weighting"]),
                        initial_notional_vnd=float(notional),
                        max_adv_participation=float(adv_cap),
                        required_holding_age=int(required_holding_age),
                        buy_fee_rate=float(fee_leg),
                        sell_fee_rate=float(fee_leg),
                        capital_gains_tax_rate=float(args.capital_gains_tax_rate),
                        min_score=float(candidate["min_score"]) if candidate["min_score"] is not None else None,
                    )
                    row = {
                        "candidate_name": str(candidate["name"]),
                        "top_k": int(candidate["top_k"]),
                        "rebalance_every": int(candidate["rebalance_every"]),
                        "weighting": str(candidate["weighting"]),
                        "min_score": None if candidate["min_score"] is None else float(candidate["min_score"]),
                        "portfolio_notional_vnd": float(notional),
                        "max_adv_participation": float(adv_cap),
                        "round_trip_cost": float(round_trip_cost),
                        **result.summary,
                    }
                    rows.append(row)

    results = _sort_results(pd.DataFrame(rows))
    _print_top(results, int(args.top_results))

    deployable = results[(results["relative_total_return"] > 0.0) & (results["avg_cash_weight"] < 0.20)].copy()
    by_candidate = (
        results.groupby("candidate_name")[["portfolio_total_return", "relative_total_return"]]
        .max()
        .round(6)
        .reset_index()
    )

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results_path = OUT_DIR / f"{ts}_h139_fixed_menu_capacity_fee_stress_results.parquet"
    results.to_parquet(results_path, index=False)

    summary = {
        "strategy": str(args.strategy),
        "year_range": [int(args.start_year), int(args.end_year)],
        "required_holding_age": int(required_holding_age),
        "portfolio_notional_grid": notionals,
        "max_adv_grid": adv_caps,
        "round_trip_cost_grid": round_trip_costs,
        "capital_gains_tax_rate": float(args.capital_gains_tax_rate),
        "num_scenarios": int(len(results)),
        "best_scenarios": json.loads(results.head(min(int(args.top_results), len(results))).to_json(orient="records")),
        "deployable_positive_count": int(len(deployable)),
        "best_by_candidate": json.loads(by_candidate.to_json(orient="records")),
    }
    summary_path = write_run_summary(
        ts=ts,
        mode="portfolio_capacity_fee_stress",
        name="h139_fixed_menu_capacity_fee_stress",
        summary=summary,
        artifacts={"results": str(results_path)},
        metadata={
            "matrix": str(matrix_path),
            "tradability": str(tradability_path),
            "stock_dir": str(stock_dir),
            "benchmark": str(benchmark_path),
        },
    )

    print(f"\nDeployable positive scenarios (rel_ret > 0 and cash < 20%): {len(deployable)}")
    print(f"Saved results -> {results_path}")
    print(f"Saved run summary -> {summary_path}")


if __name__ == "__main__":
    main()
