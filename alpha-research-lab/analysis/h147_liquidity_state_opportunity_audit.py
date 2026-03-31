"""
H147: Opportunity density audit around the H145 near-miss.

Purpose:
- quantify how often the liquidity-opening gate leaves the portfolio with no legal candidates
- separate "good strategy but no opportunities" from "bad strategy despite opportunities"
- audit the H145 near-miss before doing more local threshold tuning

Usage:
    conda run -n stocks python analysis/h147_liquidity_state_opportunity_audit.py
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
    add_liquidity_opening_gate_columns,
    build_boolean_matrix,
    build_friction_feature_frame,
)
from src.run_summary import write_run_summary

RL_MATRIX_PATH = Path("data/features/xs_rl_signal_matrix.parquet")
TRADABILITY_PATH = Path("data/features/execution/tradability_daily.parquet")
STOCK_DIR = Path("data/stock")
BENCHMARK_PATH = STOCK_DIR / "gia_lich_su_VNINDEX_1D.parquet"
LATEST_H145_SUMMARY = ROOT / "artifacts/run_summaries/latest_portfolio_volume_confirmed_entry_filter.json"
OUT_DIR = ROOT / "artifacts/portfolio_baselines"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", type=str, default=str(RL_MATRIX_PATH))
    parser.add_argument("--tradability", type=str, default=str(TRADABILITY_PATH))
    parser.add_argument("--stock-dir", type=str, default=str(STOCK_DIR))
    parser.add_argument("--benchmark", type=str, default=str(BENCHMARK_PATH))
    parser.add_argument("--start-year", type=int, default=2019)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--portfolio-notional-vnd", type=float, default=20_000_000.0)
    parser.add_argument("--max-adv-participation", type=float, default=0.05)
    parser.add_argument("--round-trip-cost", type=float, default=0.003)
    parser.add_argument("--capital-gains-tax-rate", type=float, default=0.0)
    parser.add_argument("--required-holding-age", type=int, default=3)
    parser.add_argument("--adv20-ratio-grid", nargs="+", type=float, default=[1.05, 1.10, 1.15, 1.20, 1.25])
    parser.add_argument("--clv-threshold-grid", nargs="+", default=["none", "0.45", "0.50", "0.55"])
    parser.add_argument("--min-adv20-grid", nargs="+", type=float, default=[500_000_000.0, 750_000_000.0, 1_000_000_000.0, 1_500_000_000.0])
    parser.add_argument("--top-results", type=int, default=20)
    return parser.parse_args()


def _resolve_defaults() -> dict[str, object]:
    if not LATEST_H145_SUMMARY.exists():
        return {
            "score_variant": "liq_blend_50_50",
            "top_k": 3,
            "rebalance_every": 5,
            "weighting": "equal",
        }
    payload = json.loads(LATEST_H145_SUMMARY.read_text(encoding="utf-8"))
    best = payload.get("summary", {}).get("best_overall") or {}
    return {
        "score_variant": str(best.get("score_variant") or "liq_blend_50_50"),
        "top_k": int(best.get("top_k") or 3),
        "rebalance_every": int(best.get("rebalance_every") or 5),
        "weighting": str(best.get("weighting") or "equal"),
    }


def _parse_clv_grid(values: list[str]) -> list[float | None]:
    parsed: list[float | None] = []
    for value in values:
        text = str(value).strip().lower()
        parsed.append(None if text in {"none", "null", "na"} else float(text))
    return parsed


def _print_top(results: pd.DataFrame, *, title: str, top_n: int) -> None:
    top = results.head(top_n)
    print("\n" + "=" * 222)
    print(title)
    print("=" * 222)
    print(
        f"{'rank':<5} {'gate':<20} {'adv_floor':>10} {'rel_ret':>10} {'tot_ret':>10} {'cash':>8} "
        f"{'zero_days':>10} {'avg_elig':>9} {'nz_elig':>9} {'holds':>8} {'yrs+':>7}"
    )
    print("-" * 222)
    for i, row in enumerate(top.itertuples(index=False), start=1):
        print(
            f"{i:<5} {row.entry_gate:<20} {row.min_adv20_value_vnd/1e9:>9.2f}B "
            f"{row.relative_total_return*100:>+9.2f}% {row.portfolio_total_return*100:>+9.2f}% "
            f"{row.avg_cash_weight*100:>7.2f}% {row.zero_candidate_day_pct*100:>9.2f}% "
            f"{row.avg_eligible_count:>8.2f} {row.avg_eligible_count_nonzero:>8.2f} "
            f"{row.avg_num_holdings:>8.2f} {row.positive_years:>3}/{row.total_years:<3}"
        )


def main() -> None:
    args = parse_args()
    defaults = _resolve_defaults()
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

    signal_columns = resolve_strategy_columns(matrix.columns.tolist(), "full_library")
    base_scored = compute_strategy_scores(matrix, {"full_library": signal_columns})

    print("Loading prices and ADV20...")
    price_panel = load_price_panel(base_scored["ticker"].unique().tolist(), stock_dir)
    if price_panel.empty:
        raise ValueError(f"No price rows found under {stock_dir}")

    print(f"Loading tradability flags: {tradability_path}")
    tradability, tradability_source = load_or_build_tradability_panel(price_panel, tradability_path)

    feature_frame = build_friction_feature_frame(base_scored, price_panel, tradability)
    feature_frame, score_variants = add_liquidity_aware_score_variants(
        feature_frame,
        base_score_column="score__full_library",
    )
    score_variant = str(defaults["score_variant"])
    if score_variant not in score_variants:
        raise ValueError(f"Unknown score variant {score_variant!r}; available={score_variants}")

    adv20_ratio_grid = sorted(set(float(v) for v in args.adv20_ratio_grid))
    clv_threshold_grid = _parse_clv_grid(args.clv_threshold_grid)
    min_adv20_grid = sorted(set(float(v) for v in args.min_adv20_grid))
    feature_frame, gate_columns = add_liquidity_opening_gate_columns(
        feature_frame,
        adv20_ratio_thresholds=adv20_ratio_grid,
        clv_thresholds=clv_threshold_grid,
    )

    scored = feature_frame[["time", "ticker", "actual", f"score__{score_variant}"]].copy()
    benchmark_open = load_benchmark_open(benchmark_path)
    market_inputs = build_market_inputs(
        scored,
        price_panel,
        tradability,
        benchmark_open,
        tradability_source=tradability_source,
        strategy_names=[score_variant],
        start_year=int(args.start_year),
        end_year=int(args.end_year),
    )
    required_holding_age = required_holding_age_for_sell(
        min_hold_days_override=int(args.required_holding_age)
    )
    fee_leg = float(args.round_trip_cost) / 2.0

    rows: list[dict[str, object]] = []
    daily_audit_parts: list[pd.DataFrame] = []
    for gate_column in gate_columns:
        gate_name = gate_column.replace("gate__", "")
        gate_matrix = build_boolean_matrix(
            feature_frame,
            value_column=gate_column,
            dates=pd.to_datetime(market_inputs.dates),
            tickers=market_inputs.tickers,
        )
        for adv_floor in min_adv20_grid:
            feature_frame["_legal_candidate"] = (
                feature_frame[gate_column].astype(bool)
                & feature_frame["can_buy_next_open"].astype(bool)
                & (pd.to_numeric(feature_frame["adv20_value"], errors="coerce") >= float(adv_floor))
            )
            counts = (
                feature_frame.groupby("time", sort=True)["_legal_candidate"]
                .sum()
                .rename("legal_candidate_count")
                .reset_index()
            )
            counts["entry_gate"] = gate_name
            counts["min_adv20_value_vnd"] = float(adv_floor)
            counts["year"] = counts["time"].dt.year.astype(int)
            daily_audit_parts.append(counts)

            result = simulate_strategy(
                strategy_name=score_variant,
                signal_columns=signal_columns,
                market_inputs=market_inputs,
                top_k=int(defaults["top_k"]),
                rebalance_every=int(defaults["rebalance_every"]),
                weighting=str(defaults["weighting"]),
                initial_notional_vnd=float(args.portfolio_notional_vnd),
                max_adv_participation=float(args.max_adv_participation),
                required_holding_age=int(required_holding_age),
                buy_fee_rate=float(fee_leg),
                sell_fee_rate=float(fee_leg),
                capital_gains_tax_rate=float(args.capital_gains_tax_rate),
                min_adv20_value_vnd=float(adv_floor),
                entry_allowed_matrix=gate_matrix,
            )
            nonzero_counts = counts.loc[counts["legal_candidate_count"] > 0, "legal_candidate_count"]
            row = {
                "score_variant": score_variant,
                "entry_gate": gate_name,
                "top_k": int(defaults["top_k"]),
                "rebalance_every": int(defaults["rebalance_every"]),
                "weighting": str(defaults["weighting"]),
                "portfolio_notional_vnd": float(args.portfolio_notional_vnd),
                "max_adv_participation": float(args.max_adv_participation),
                "min_adv20_value_vnd": float(adv_floor),
                "zero_candidate_day_pct": float((counts["legal_candidate_count"] == 0).mean()),
                "avg_eligible_count": float(counts["legal_candidate_count"].mean()),
                "avg_eligible_count_nonzero": float(nonzero_counts.mean()) if not nonzero_counts.empty else 0.0,
                "active_year_count": int(counts.groupby("year")["legal_candidate_count"].sum().gt(0).sum()),
            }
            row.update(result.summary)
            rows.append(row)

    results = sort_retail_results(pd.DataFrame(rows))
    daily_audit = pd.concat(daily_audit_parts, ignore_index=True) if daily_audit_parts else pd.DataFrame()

    _print_top(results, title="H147: LIQUIDITY STATE OPPORTUNITY AUDIT", top_n=int(args.top_results))

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results_path = OUT_DIR / f"{ts}_h147_liquidity_state_opportunity_audit_results.parquet"
    daily_audit_path = OUT_DIR / f"{ts}_h147_liquidity_state_opportunity_audit_daily.parquet"
    results.to_parquet(results_path, index=False)
    daily_audit.to_parquet(daily_audit_path, index=False)

    summary = {
        "year_range": [int(args.start_year), int(args.end_year)],
        "score_variant": score_variant,
        "construction": {
            "top_k": int(defaults["top_k"]),
            "rebalance_every": int(defaults["rebalance_every"]),
            "weighting": str(defaults["weighting"]),
        },
        "scenario_count": int(len(results)),
        "required_holding_age": int(required_holding_age),
        "best_overall": json.loads(results.head(1).to_json(orient="records"))[0] if not results.empty else {},
        "top_results": json.loads(results.head(min(int(args.top_results), len(results))).to_json(orient="records")),
    }
    summary_path = write_run_summary(
        ts=ts,
        mode="portfolio_liquidity_state_opportunity_audit",
        name="h147_liquidity_state_opportunity_audit",
        summary=summary,
        artifacts={
            "results": str(results_path),
            "daily_audit": str(daily_audit_path),
        },
        metadata={
            "matrix": str(matrix_path),
            "tradability": str(tradability_path),
            "stock_dir": str(stock_dir),
            "benchmark": str(benchmark_path),
            "tradability_source": tradability_source,
        },
    )
    print(f"\nSaved H147 summary to {summary_path}")


if __name__ == "__main__":
    main()
