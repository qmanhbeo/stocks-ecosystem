"""
H143: Liquidity-aware scoring for long-only friction extraction.

Purpose:
- test whether soft tradability-aware score variants outperform naive hard clipping
- shift selection toward names that can actually absorb capital instead of selecting
  impossible winners and leaving the portfolio in cash
- identify whether score engineering alone creates a retail-viable long-only region

Usage:
    conda run -n stocks python analysis/h143_liquidity_aware_scoring.py
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
    build_market_inputs,
    compute_strategy_scores,
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
from src.portfolio_friction_features import (
    add_liquidity_aware_score_variants,
    best_variant_rows,
    build_friction_feature_frame,
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
        default=[20_000_000.0, 50_000_000.0, 100_000_000.0],
    )
    parser.add_argument(
        "--max-adv-grid",
        nargs="+",
        type=float,
        default=[0.02, 0.05, 0.10],
    )
    parser.add_argument(
        "--min-adv20-grid",
        nargs="+",
        type=float,
        default=[250_000_000.0, 500_000_000.0, 1_000_000_000.0],
    )
    parser.add_argument(
        "--round-trip-cost-grid",
        nargs="+",
        type=float,
        default=[0.003],
    )
    parser.add_argument("--capital-gains-tax-rate", type=float, default=0.0)
    parser.add_argument("--required-holding-age", type=int, default=3)
    parser.add_argument("--viable-max-cash-weight", type=float, default=0.40)
    parser.add_argument("--viable-min-positive-years", type=int, default=5)
    parser.add_argument("--top-results", type=int, default=20)
    return parser.parse_args()


def _print_top(results: pd.DataFrame, *, title: str, top_n: int) -> None:
    top = results.head(top_n)
    print("\n" + "=" * 214)
    print(title)
    print("=" * 214)
    print(
        f"{'rank':<5} {'variant':<24} {'cand':<12} {'notional':>11} {'adv_cap':>8} {'adv_floor':>10} "
        f"{'tot_ret':>10} {'rel_ret':>10} {'ann_ret':>10} {'IR':>8} {'cash':>8} "
        f"{'turn/day':>10} {'max_dd':>9} {'yrs+':>7}"
    )
    print("-" * 214)
    for i, row in enumerate(top.itertuples(index=False), start=1):
        print(
            f"{i:<5} {row.score_variant:<24} {row.candidate_name:<12} {row.portfolio_notional_vnd/1e6:>10.0f}m "
            f"{row.max_adv_participation*100:>7.2f}% {row.min_adv20_value_vnd/1e9:>9.2f}B "
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

    signal_columns = resolve_strategy_columns(matrix.columns.tolist(), "full_library")
    base_scored = compute_strategy_scores(matrix, {"full_library": signal_columns})
    candidates = parse_fixed_menu_candidates(args.candidate)

    print("Loading prices and ADV20...")
    price_panel = load_price_panel(base_scored["ticker"].unique().tolist(), stock_dir)
    if price_panel.empty:
        raise ValueError(f"No price rows found under {stock_dir}")
    print(f"  price rows={len(price_panel):,}")

    print(f"Loading tradability flags: {tradability_path}")
    tradability, tradability_source = load_or_build_tradability_panel(price_panel, tradability_path)
    print(f"  source={tradability_source} | rows={len(tradability):,}")

    feature_frame = build_friction_feature_frame(base_scored, price_panel, tradability)
    feature_frame, score_variants = add_liquidity_aware_score_variants(
        feature_frame,
        base_score_column="score__full_library",
    )
    scored = feature_frame[["time", "ticker", "actual"] + [f"score__{name}" for name in score_variants]].copy()

    benchmark_open = load_benchmark_open(benchmark_path)
    market_inputs = build_market_inputs(
        scored,
        price_panel,
        tradability,
        benchmark_open,
        tradability_source=tradability_source,
        strategy_names=score_variants,
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
    print(
        f"Variants={len(score_variants)} | candidates={len(candidates)} | "
        f"scenarios={len(score_variants) * len(candidates) * len(notionals) * len(adv_caps) * len(adv_floors) * len(round_trip_costs)} | "
        f"required_holding_age={required_holding_age}"
    )

    rows: list[dict[str, object]] = []
    best_daily: pd.DataFrame | None = None
    best_key: tuple[float, float, float, float, float] | None = None
    for variant in score_variants:
        for candidate in candidates:
            for notional in notionals:
                for adv_cap in adv_caps:
                    for adv_floor in adv_floors:
                        for round_trip_cost in round_trip_costs:
                            fee_leg = round_trip_cost / 2.0
                            result = simulate_strategy(
                                strategy_name=variant,
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
                            )
                            row = {
                                "score_variant": variant,
                                "candidate_name": str(candidate["name"]),
                                "top_k": int(candidate["top_k"]),
                                "rebalance_every": int(candidate["rebalance_every"]),
                                "weighting": str(candidate["weighting"]),
                                "min_score": None if candidate["min_score"] is None else float(candidate["min_score"]),
                                "portfolio_notional_vnd": float(notional),
                                "max_adv_participation": float(adv_cap),
                                "min_adv20_value_vnd": float(adv_floor),
                                "round_trip_cost": float(round_trip_cost),
                            }
                            row.update(result.summary)
                            rows.append(row)

                            sort_key = (
                                float(row["relative_total_return"]),
                                float(row["portfolio_total_return"]),
                                float(row["information_ratio_annualized"] or -999.0),
                                -float(row["avg_cash_weight"]),
                                -float(row["avg_daily_turnover"]),
                            )
                            if best_key is None or sort_key > best_key:
                                best_key = sort_key
                                best_daily = result.daily.assign(
                                    score_variant=variant,
                                    candidate_name=str(candidate["name"]),
                                    portfolio_notional_vnd=float(notional),
                                    max_adv_participation=float(adv_cap),
                                    min_adv20_value_vnd=float(adv_floor),
                                    round_trip_cost=float(round_trip_cost),
                                )

    results = sort_retail_results(pd.DataFrame(rows))
    viable = results.loc[
        retail_viable_mask(
            results,
            max_avg_cash_weight=float(args.viable_max_cash_weight),
            min_positive_years=int(args.viable_min_positive_years),
        )
    ].reset_index(drop=True)
    best_by_variant = best_variant_rows(results)

    _print_top(results, title="H143: LIQUIDITY-AWARE SCORING", top_n=int(args.top_results))
    if not viable.empty:
        _print_top(
            viable,
            title="H143: RETAIL-VIABLE LIQUIDITY-AWARE SCENARIOS",
            top_n=min(int(args.top_results), len(viable)),
        )
    else:
        print("\nNo H143 scenario cleared the retail-viable gate.")

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results_path = OUT_DIR / f"{ts}_h143_liquidity_aware_scoring_results.parquet"
    viable_path = OUT_DIR / f"{ts}_h143_liquidity_aware_scoring_viable.parquet"
    best_variant_path = OUT_DIR / f"{ts}_h143_liquidity_aware_scoring_best_by_variant.parquet"
    best_daily_path = OUT_DIR / f"{ts}_h143_liquidity_aware_scoring_best_daily.parquet"
    results.to_parquet(results_path, index=False)
    viable.to_parquet(viable_path, index=False)
    best_by_variant.to_parquet(best_variant_path, index=False)
    if best_daily is not None:
        best_daily.to_parquet(best_daily_path, index=False)

    summary = {
        "year_range": [int(args.start_year), int(args.end_year)],
        "score_variants": list(score_variants),
        "candidate_count": int(len(candidates)),
        "scenario_count": int(len(results)),
        "required_holding_age": int(required_holding_age),
        "retail_viability_rule": {
            "relative_total_return_gt": 0.0,
            "avg_cash_weight_lt": float(args.viable_max_cash_weight),
            "positive_years_gte": int(args.viable_min_positive_years),
        },
        "viable_scenario_count": int(len(viable)),
        "best_overall": json.loads(results.head(1).to_json(orient="records"))[0] if not results.empty else {},
        "best_viable": json.loads(viable.head(1).to_json(orient="records"))[0] if not viable.empty else {},
        "best_by_variant": json.loads(best_by_variant.to_json(orient="records")),
    }
    summary_path = write_run_summary(
        ts=ts,
        mode="portfolio_liquidity_aware_scoring",
        name="h143_liquidity_aware_scoring",
        summary=summary,
        artifacts={
            "results": str(results_path),
            "viable_results": str(viable_path),
            "best_by_variant": str(best_variant_path),
            "best_daily": str(best_daily_path) if best_daily is not None else None,
        },
        metadata={
            "matrix": str(matrix_path),
            "tradability": str(tradability_path),
            "stock_dir": str(stock_dir),
            "benchmark": str(benchmark_path),
            "tradability_source": tradability_source,
        },
    )
    print(f"\nSaved H143 summary to {summary_path}")


if __name__ == "__main__":
    main()
