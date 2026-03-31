"""
H140: Retail-scale capacity-aware validation for fixed long-only candidates.

Purpose:
- answer the real deployability question at retail notionals instead of institutional stress sizes
- test whether the H138 fixed-menu candidates remain benchmark-positive once realistic retail
  liquidity floors and percentage-of-ADV limits are imposed
- identify a viable retail liquidity region before doing any more construction tuning

Usage:
    conda run -n stocks python analysis/h140_retail_capacity_aware_validation.py
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
from src.portfolio_construction_search import (
    parse_fixed_menu_candidates,
    retail_viable_mask,
    sort_retail_results,
)
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
        default=[20_000_000.0, 50_000_000.0, 100_000_000.0, 200_000_000.0],
    )
    parser.add_argument(
        "--max-adv-grid",
        nargs="+",
        type=float,
        default=[0.02, 0.05, 0.10],
        help="Maximum allowed target position notional as a fraction of ADV20",
    )
    parser.add_argument(
        "--min-adv20-grid",
        nargs="+",
        type=float,
        default=[250_000_000.0, 500_000_000.0, 1_000_000_000.0, 2_000_000_000.0, 5_000_000_000.0],
        help="Minimum ADV20 value floor for a stock to enter the eligible universe",
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
    parser.add_argument("--max-position-vnd", type=float, default=0.0)
    parser.add_argument("--max-names-if-liquidity-thin", type=int, default=0)
    parser.add_argument("--viable-max-cash-weight", type=float, default=0.25)
    parser.add_argument("--viable-min-positive-years", type=int, default=5)
    parser.add_argument("--top-results", type=int, default=20)
    return parser.parse_args()


def _print_top(results: pd.DataFrame, *, title: str, top_n: int) -> None:
    top = results.head(top_n)
    print("\n" + "=" * 196)
    print(title)
    print("=" * 196)
    print(
        f"{'rank':<5} {'cand':<12} {'notional':>11} {'adv_cap':>8} {'adv_floor':>10} {'rt_cost':>8} "
        f"{'tot_ret':>10} {'rel_ret':>10} {'ann_ret':>10} {'IR':>8} {'cash':>8} "
        f"{'turn/day':>10} {'max_dd':>9} {'yrs+':>7}"
    )
    print("-" * 196)
    for i, row in enumerate(top.itertuples(index=False), start=1):
        print(
            f"{i:<5} {row.candidate_name:<12} {row.portfolio_notional_vnd/1e6:>10.0f}m "
            f"{row.max_adv_participation*100:>7.2f}% {row.min_adv20_value_vnd/1e9:>9.2f}B {row.round_trip_cost*100:>7.2f}% "
            f"{row.portfolio_total_return*100:>+9.2f}% {row.relative_total_return*100:>+9.2f}% "
            f"{row.portfolio_annualized_return*100 if row.portfolio_annualized_return is not None else float('nan'):>+9.2f}% "
            f"{row.information_ratio_annualized if row.information_ratio_annualized is not None else float('nan'):>8.2f} "
            f"{row.avg_cash_weight*100:>7.2f}% {row.avg_daily_turnover*100:>9.2f}% "
            f"{row.max_drawdown*100:>8.2f}% {row.positive_years:>3}/{row.total_years:<3}"
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
    adv_floors = sorted(set(float(v) for v in args.min_adv20_grid))
    round_trip_costs = sorted(set(float(v) for v in args.round_trip_cost_grid))
    max_names_if_liquidity_thin = (
        int(args.max_names_if_liquidity_thin) if int(args.max_names_if_liquidity_thin) > 0 else None
    )
    print(
        f"Strategy: {args.strategy} ({len(signal_columns)} signals) | candidates={len(candidates)} | "
        f"scenarios={len(candidates) * len(notionals) * len(adv_caps) * len(adv_floors) * len(round_trip_costs)} | "
        f"required_holding_age={required_holding_age}"
    )

    rows: list[dict[str, object]] = []
    for candidate in candidates:
        for notional in notionals:
            for adv_cap in adv_caps:
                for adv_floor in adv_floors:
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
                            min_adv20_value_vnd=float(adv_floor),
                            max_position_vnd=float(args.max_position_vnd),
                            max_names_if_liquidity_thin=max_names_if_liquidity_thin,
                        )
                        rows.append(
                            {
                                "candidate_name": str(candidate["name"]),
                                "top_k": int(candidate["top_k"]),
                                "rebalance_every": int(candidate["rebalance_every"]),
                                "weighting": str(candidate["weighting"]),
                                "min_score": None if candidate["min_score"] is None else float(candidate["min_score"]),
                                "portfolio_notional_vnd": float(notional),
                                "max_adv_participation": float(adv_cap),
                                "min_adv20_value_vnd": float(adv_floor),
                                "round_trip_cost": float(round_trip_cost),
                                "max_position_vnd": float(args.max_position_vnd),
                                "max_names_if_liquidity_thin": max_names_if_liquidity_thin,
                                **result.summary,
                            }
                        )

    results = sort_retail_results(pd.DataFrame(rows))
    viable = results.loc[
        retail_viable_mask(
            results,
            max_avg_cash_weight=float(args.viable_max_cash_weight),
            min_positive_years=int(args.viable_min_positive_years),
        )
    ].reset_index(drop=True)

    _print_top(results, title="H140: RETAIL CAPACITY-AWARE VALIDATION", top_n=int(args.top_results))
    if not viable.empty:
        _print_top(viable, title="H140: RETAIL-VIABLE REGION", top_n=min(int(args.top_results), len(viable)))
    else:
        print("\nNo retail-viable scenarios met the relative-return / cash / positive-year gate.")

    viable_regions = (
        viable[
            [
                "portfolio_notional_vnd",
                "max_adv_participation",
                "min_adv20_value_vnd",
                "round_trip_cost",
                "max_position_vnd",
                "max_names_if_liquidity_thin",
            ]
        ]
        .drop_duplicates()
        .sort_values(
            by=["portfolio_notional_vnd", "max_adv_participation", "min_adv20_value_vnd", "round_trip_cost"],
            ignore_index=True,
        )
    )
    viable_by_candidate = (
        viable.groupby("candidate_name")["relative_total_return"]
        .agg([("viable_count", "count"), ("best_relative_total_return", "max")])
        .reset_index()
    ) if not viable.empty else pd.DataFrame(columns=["candidate_name", "viable_count", "best_relative_total_return"])

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results_path = OUT_DIR / f"{ts}_h140_retail_capacity_aware_validation_results.parquet"
    viable_path = OUT_DIR / f"{ts}_h140_retail_capacity_aware_validation_viable.parquet"
    results.to_parquet(results_path, index=False)
    viable.to_parquet(viable_path, index=False)

    summary = {
        "strategy": str(args.strategy),
        "year_range": [int(args.start_year), int(args.end_year)],
        "required_holding_age": int(required_holding_age),
        "portfolio_notional_grid": notionals,
        "max_adv_grid": adv_caps,
        "min_adv20_grid": adv_floors,
        "round_trip_cost_grid": round_trip_costs,
        "max_position_vnd": float(args.max_position_vnd),
        "max_names_if_liquidity_thin": max_names_if_liquidity_thin,
        "retail_viability_rule": {
            "relative_total_return_gt": 0.0,
            "avg_cash_weight_lt": float(args.viable_max_cash_weight),
            "positive_years_gte": int(args.viable_min_positive_years),
        },
        "num_scenarios": int(len(results)),
        "viable_count": int(len(viable)),
        "best_scenarios": json.loads(results.head(min(int(args.top_results), len(results))).to_json(orient="records")),
        "best_viable_scenarios": json.loads(viable.head(min(int(args.top_results), len(viable))).to_json(orient="records")),
        "viable_regions": json.loads(viable_regions.to_json(orient="records")),
        "viable_by_candidate": json.loads(viable_by_candidate.to_json(orient="records")),
    }
    summary_path = write_run_summary(
        ts=ts,
        mode="portfolio_retail_validation",
        name="h140_retail_capacity_aware_validation",
        summary=summary,
        artifacts={
            "results": str(results_path),
            "viable_results": str(viable_path),
        },
        metadata={
            "matrix": str(matrix_path),
            "tradability": str(tradability_path),
            "stock_dir": str(stock_dir),
            "benchmark": str(benchmark_path),
        },
    )

    print(f"\nRetail-viable scenarios: {len(viable)}")
    print(f"Saved results -> {results_path}")
    print(f"Saved viable subset -> {viable_path}")
    print(f"Saved run summary -> {summary_path}")


if __name__ == "__main__":
    main()
