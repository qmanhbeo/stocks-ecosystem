"""
H144: Entry slicing simulation for long-only friction extraction.

Purpose:
- test whether multi-day accumulation can convert clipped next-open entries into
  more realistic fills without destroying the economics
- keep exits unchanged while allowing buys to continue over a short pending horizon
- compare sliced entry plans against the unsliced baseline under retail constraints

Usage:
    conda run -n stocks python analysis/h144_entry_slicing_simulation.py
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
    load_benchmark_open,
    load_or_build_tradability_panel,
    load_price_panel,
    resolve_strategy_columns,
    simulate_strategy,
)
from src.portfolio_construction_search import sort_retail_results
from src.portfolio_friction_features import (
    add_liquidity_aware_score_variants,
    build_friction_feature_frame,
)
from src.run_summary import write_run_summary

RL_MATRIX_PATH = Path("data/features/xs_rl_signal_matrix.parquet")
TRADABILITY_PATH = Path("data/features/execution/tradability_daily.parquet")
STOCK_DIR = Path("data/stock")
BENCHMARK_PATH = STOCK_DIR / "gia_lich_su_VNINDEX_1D.parquet"
LATEST_H143_SUMMARY = ROOT / "artifacts/run_summaries/latest_portfolio_liquidity_aware_scoring.json"
OUT_DIR = ROOT / "artifacts/portfolio_baselines"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", type=str, default=str(RL_MATRIX_PATH))
    parser.add_argument("--tradability", type=str, default=str(TRADABILITY_PATH))
    parser.add_argument("--stock-dir", type=str, default=str(STOCK_DIR))
    parser.add_argument("--benchmark", type=str, default=str(BENCHMARK_PATH))
    parser.add_argument("--start-year", type=int, default=2019)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--rebalance-every", type=int, default=5)
    parser.add_argument("--weighting", type=str, default="equal")
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
        default=[0.02, 0.05],
    )
    parser.add_argument(
        "--min-adv20-grid",
        nargs="+",
        type=float,
        default=[250_000_000.0, 500_000_000.0, 1_000_000_000.0],
    )
    parser.add_argument(
        "--entry-slice-grid",
        nargs="+",
        type=int,
        default=[1, 2, 3, 5],
        help="1 = unsliced baseline",
    )
    parser.add_argument("--round-trip-cost", type=float, default=0.003)
    parser.add_argument("--capital-gains-tax-rate", type=float, default=0.0)
    parser.add_argument("--required-holding-age", type=int, default=3)
    parser.add_argument("--top-h143-variants", type=int, default=2)
    parser.add_argument(
        "--score-variant",
        action="append",
        default=[],
        help="Explicit score variant(s) to test; defaults to liq_base plus the best H143 non-base variants",
    )
    parser.add_argument("--top-results", type=int, default=20)
    return parser.parse_args()


def _load_score_variants(args: argparse.Namespace) -> list[str]:
    explicit = [str(v).strip() for v in args.score_variant if str(v).strip()]
    if explicit:
        return list(dict.fromkeys(explicit))

    if not LATEST_H143_SUMMARY.exists():
        return ["liq_base"]

    payload = json.loads(LATEST_H143_SUMMARY.read_text(encoding="utf-8"))
    summary = payload.get("summary", {})
    variant_rows = summary.get("best_by_variant", [])
    ordered = sorted(
        variant_rows,
        key=lambda row: (
            float(row.get("relative_total_return", -999.0)),
            float(row.get("portfolio_total_return", -999.0)),
        ),
        reverse=True,
    )
    selected = ["liq_base"]
    for row in ordered:
        variant = str(row.get("score_variant", "")).strip()
        if not variant or variant == "liq_base":
            continue
        selected.append(variant)
        if len(selected) >= 1 + int(args.top_h143_variants):
            break
    return list(dict.fromkeys(selected))


def _print_top(results: pd.DataFrame, *, title: str, top_n: int) -> None:
    top = results.head(top_n)
    print("\n" + "=" * 220)
    print(title)
    print("=" * 220)
    print(
        f"{'rank':<5} {'variant':<24} {'slice':>5} {'notional':>11} {'adv_cap':>8} {'adv_floor':>10} "
        f"{'tot_ret':>10} {'rel_ret':>10} {'ann_ret':>10} {'IR':>8} {'cash':>8} "
        f"{'pend_d':>8} {'partial':>8} {'expired':>8} {'yrs+':>7}"
    )
    print("-" * 220)
    for i, row in enumerate(top.itertuples(index=False), start=1):
        print(
            f"{i:<5} {row.score_variant:<24} {row.entry_slice_days:>5} {row.portfolio_notional_vnd/1e6:>10.0f}m "
            f"{row.max_adv_participation*100:>7.2f}% {row.min_adv20_value_vnd/1e9:>9.2f}B "
            f"{row.portfolio_total_return*100:>+9.2f}% {row.relative_total_return*100:>+9.2f}% "
            f"{row.portfolio_annualized_return*100 if row.portfolio_annualized_return is not None else float('nan'):>+9.2f}% "
            f"{row.information_ratio_annualized if row.information_ratio_annualized is not None else float('nan'):>8.2f} "
            f"{row.avg_cash_weight*100:>7.2f}% {row.avg_pending_entry_days:>8.2f} "
            f"{row.partial_fill_count:>8} {row.expired_entry_plan_count:>8} {row.positive_years:>3}/{row.total_years:<3}"
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

    print("Loading prices and ADV20...")
    price_panel = load_price_panel(base_scored["ticker"].unique().tolist(), stock_dir)
    if price_panel.empty:
        raise ValueError(f"No price rows found under {stock_dir}")
    print(f"  price rows={len(price_panel):,}")

    print(f"Loading tradability flags: {tradability_path}")
    tradability, tradability_source = load_or_build_tradability_panel(price_panel, tradability_path)
    print(f"  source={tradability_source} | rows={len(tradability):,}")

    feature_frame = build_friction_feature_frame(base_scored, price_panel, tradability)
    feature_frame, all_variants = add_liquidity_aware_score_variants(
        feature_frame,
        base_score_column="score__full_library",
    )
    selected_variants = _load_score_variants(args)
    missing = sorted(set(selected_variants) - set(all_variants))
    if missing:
        raise ValueError(f"Unknown score variants requested: {missing}; available={all_variants}")
    scored = feature_frame[["time", "ticker", "actual"] + [f"score__{name}" for name in selected_variants]].copy()

    benchmark_open = load_benchmark_open(benchmark_path)
    market_inputs = build_market_inputs(
        scored,
        price_panel,
        tradability,
        benchmark_open,
        tradability_source=tradability_source,
        strategy_names=selected_variants,
        start_year=int(args.start_year),
        end_year=int(args.end_year),
    )
    required_holding_age = required_holding_age_for_sell(
        min_hold_days_override=int(args.required_holding_age)
    )

    notionals = sorted(set(float(v) for v in args.portfolio_notional_grid))
    adv_caps = sorted(set(float(v) for v in args.max_adv_grid))
    adv_floors = sorted(set(float(v) for v in args.min_adv20_grid))
    slice_grid = sorted(set(int(v) for v in args.entry_slice_grid))
    print(
        f"Variants={selected_variants} | scenarios={len(selected_variants) * len(slice_grid) * len(notionals) * len(adv_caps) * len(adv_floors)} | "
        f"required_holding_age={required_holding_age}"
    )

    rows: list[dict[str, object]] = []
    best_daily: pd.DataFrame | None = None
    best_key: tuple[float, float, float, float, float] | None = None
    fee_leg = float(args.round_trip_cost) / 2.0
    for variant in selected_variants:
        for entry_slice_days in slice_grid:
            for notional in notionals:
                for adv_cap in adv_caps:
                    for adv_floor in adv_floors:
                        result = simulate_strategy(
                            strategy_name=variant,
                            signal_columns=signal_columns,
                            market_inputs=market_inputs,
                            top_k=int(args.top_k),
                            rebalance_every=int(args.rebalance_every),
                            weighting=str(args.weighting),
                            initial_notional_vnd=float(notional),
                            max_adv_participation=0.0 if int(entry_slice_days) > 1 else float(adv_cap),
                            required_holding_age=int(required_holding_age),
                            buy_fee_rate=float(fee_leg),
                            sell_fee_rate=float(fee_leg),
                            capital_gains_tax_rate=float(args.capital_gains_tax_rate),
                            min_adv20_value_vnd=float(adv_floor),
                            entry_slice_days=int(entry_slice_days),
                            daily_buy_adv_participation=float(adv_cap) if int(entry_slice_days) > 1 else 0.0,
                        )
                        row = {
                            "score_variant": variant,
                            "top_k": int(args.top_k),
                            "rebalance_every": int(args.rebalance_every),
                            "weighting": str(args.weighting),
                            "portfolio_notional_vnd": float(notional),
                            "max_adv_participation": float(adv_cap),
                            "min_adv20_value_vnd": float(adv_floor),
                            "round_trip_cost": float(args.round_trip_cost),
                        }
                        row.update(result.summary)
                        if "entry_slice_days" not in row:
                            row["entry_slice_days"] = int(entry_slice_days)
                            row["avg_pending_entry_days"] = 0.0
                            row["expired_entry_plan_count"] = 0
                            row["partial_fill_count"] = 0
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
                                entry_slice_days=int(entry_slice_days),
                                portfolio_notional_vnd=float(notional),
                                max_adv_participation=float(adv_cap),
                                min_adv20_value_vnd=float(adv_floor),
                            )

    results = sort_retail_results(pd.DataFrame(rows))
    unsliced = results.loc[results["entry_slice_days"] == 1].reset_index(drop=True)
    sliced = results.loc[results["entry_slice_days"] > 1].reset_index(drop=True)

    _print_top(results, title="H144: ENTRY SLICING SIMULATION", top_n=int(args.top_results))

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results_path = OUT_DIR / f"{ts}_h144_entry_slicing_simulation_results.parquet"
    unsliced_path = OUT_DIR / f"{ts}_h144_entry_slicing_simulation_unsliced.parquet"
    sliced_path = OUT_DIR / f"{ts}_h144_entry_slicing_simulation_sliced.parquet"
    best_daily_path = OUT_DIR / f"{ts}_h144_entry_slicing_simulation_best_daily.parquet"
    results.to_parquet(results_path, index=False)
    unsliced.to_parquet(unsliced_path, index=False)
    sliced.to_parquet(sliced_path, index=False)
    if best_daily is not None:
        best_daily.to_parquet(best_daily_path, index=False)

    summary = {
        "year_range": [int(args.start_year), int(args.end_year)],
        "score_variants": selected_variants,
        "construction": {
            "top_k": int(args.top_k),
            "rebalance_every": int(args.rebalance_every),
            "weighting": str(args.weighting),
        },
        "scenario_count": int(len(results)),
        "required_holding_age": int(required_holding_age),
        "best_overall": json.loads(results.head(1).to_json(orient="records"))[0] if not results.empty else {},
        "best_unsliced": json.loads(unsliced.head(1).to_json(orient="records"))[0] if not unsliced.empty else {},
        "best_sliced": json.loads(sliced.head(1).to_json(orient="records"))[0] if not sliced.empty else {},
    }
    summary_path = write_run_summary(
        ts=ts,
        mode="portfolio_entry_slicing_simulation",
        name="h144_entry_slicing_simulation",
        summary=summary,
        artifacts={
            "results": str(results_path),
            "unsliced_results": str(unsliced_path),
            "sliced_results": str(sliced_path),
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
    print(f"\nSaved H144 summary to {summary_path}")


if __name__ == "__main__":
    main()
