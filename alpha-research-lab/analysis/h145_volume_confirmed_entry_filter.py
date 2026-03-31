"""
H145: Volume-confirmed entry filters for long-only friction extraction.

Purpose:
- test whether high-score names should only be entered when liquidity is actively opening
- avoid dead illiquid traps by requiring a minimum signal-date volume state for new buys
- keep the base ranking fixed and treat this as an entry gate rather than a new alpha source

Usage:
    conda run -n stocks python analysis/h145_volume_confirmed_entry_filter.py
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
from src.portfolio_construction_search import (
    parse_fixed_menu_candidates,
    retail_viable_mask,
    sort_retail_results,
)
from src.portfolio_friction_features import (
    add_liquidity_aware_score_variants,
    build_boolean_matrix,
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
    parser.add_argument("--round-trip-cost", type=float, default=0.003)
    parser.add_argument("--capital-gains-tax-rate", type=float, default=0.0)
    parser.add_argument("--required-holding-age", type=int, default=3)
    parser.add_argument("--score-variant", type=str, default="")
    parser.add_argument("--viable-max-cash-weight", type=float, default=0.40)
    parser.add_argument("--viable-min-positive-years", type=int, default=5)
    parser.add_argument("--top-results", type=int, default=20)
    return parser.parse_args()


def _resolve_score_variant(explicit: str) -> str:
    if explicit.strip():
        return explicit.strip()
    if not LATEST_H143_SUMMARY.exists():
        return "liq_base"
    payload = json.loads(LATEST_H143_SUMMARY.read_text(encoding="utf-8"))
    summary = payload.get("summary", {})
    best_viable = summary.get("best_viable") or {}
    best_overall = summary.get("best_overall") or {}
    candidate = str(best_viable.get("score_variant") or best_overall.get("score_variant") or "liq_base").strip()
    return candidate or "liq_base"


def _print_top(results: pd.DataFrame, *, title: str, top_n: int) -> None:
    top = results.head(top_n)
    print("\n" + "=" * 222)
    print(title)
    print("=" * 222)
    print(
        f"{'rank':<5} {'gate':<24} {'cand':<12} {'notional':>11} {'adv_cap':>8} {'adv_floor':>10} "
        f"{'tot_ret':>10} {'rel_ret':>10} {'ann_ret':>10} {'IR':>8} {'cash':>8} "
        f"{'blocked':>8} {'max_dd':>9} {'yrs+':>7}"
    )
    print("-" * 222)
    for i, row in enumerate(top.itertuples(index=False), start=1):
        print(
            f"{i:<5} {row.entry_gate:<24} {row.candidate_name:<12} {row.portfolio_notional_vnd/1e6:>10.0f}m "
            f"{row.max_adv_participation*100:>7.2f}% {row.min_adv20_value_vnd/1e9:>9.2f}B "
            f"{row.portfolio_total_return*100:>+9.2f}% {row.relative_total_return*100:>+9.2f}% "
            f"{row.portfolio_annualized_return*100 if row.portfolio_annualized_return is not None else float('nan'):>+9.2f}% "
            f"{row.information_ratio_annualized if row.information_ratio_annualized is not None else float('nan'):>8.2f} "
            f"{row.avg_cash_weight*100:>7.2f}% {row.blocked_buy_events:>8} "
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
    feature_frame, all_variants = add_liquidity_aware_score_variants(
        feature_frame,
        base_score_column="score__full_library",
    )
    score_variant = _resolve_score_variant(args.score_variant)
    if score_variant not in all_variants:
        raise ValueError(f"Unknown score variant {score_variant!r}; available={all_variants}")
    scored = feature_frame[["time", "ticker", "actual", f"score__{score_variant}"]].copy()

    feature_frame["gate__none"] = True
    feature_frame["gate__adv20_125"] = feature_frame["tv_to_adv20"] >= 1.25
    feature_frame["gate__adv20_150"] = feature_frame["tv_to_adv20"] >= 1.50
    feature_frame["gate__adv5_150"] = feature_frame["tv_to_adv5"] >= 1.50
    feature_frame["gate__adv20_125_clv50"] = (
        (feature_frame["tv_to_adv20"] >= 1.25) & (feature_frame["clv"] >= 0.50)
    )
    gate_names = [
        "gate__none",
        "gate__adv20_125",
        "gate__adv20_150",
        "gate__adv5_150",
        "gate__adv20_125_clv50",
    ]

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

    gate_matrices = {
        gate_name.replace("gate__", ""): build_boolean_matrix(
            feature_frame,
            value_column=gate_name,
            dates=pd.to_datetime(market_inputs.dates),
            tickers=market_inputs.tickers,
        )
        for gate_name in gate_names
    }

    notionals = sorted(set(float(v) for v in args.portfolio_notional_grid))
    adv_caps = sorted(set(float(v) for v in args.max_adv_grid))
    adv_floors = sorted(set(float(v) for v in args.min_adv20_grid))
    fee_leg = float(args.round_trip_cost) / 2.0
    print(
        f"Score variant={score_variant} | gates={list(gate_matrices)} | candidates={len(candidates)} | "
        f"scenarios={len(gate_matrices) * len(candidates) * len(notionals) * len(adv_caps) * len(adv_floors)} | "
        f"required_holding_age={required_holding_age}"
    )

    rows: list[dict[str, object]] = []
    best_daily: pd.DataFrame | None = None
    best_key: tuple[float, float, float, float, float] | None = None
    for gate_name, gate_matrix in gate_matrices.items():
        for candidate in candidates:
            for notional in notionals:
                for adv_cap in adv_caps:
                    for adv_floor in adv_floors:
                        result = simulate_strategy(
                            strategy_name=score_variant,
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
                            entry_allowed_matrix=gate_matrix,
                        )
                        row = {
                            "score_variant": score_variant,
                            "entry_gate": gate_name,
                            "candidate_name": str(candidate["name"]),
                            "top_k": int(candidate["top_k"]),
                            "rebalance_every": int(candidate["rebalance_every"]),
                            "weighting": str(candidate["weighting"]),
                            "min_score": None if candidate["min_score"] is None else float(candidate["min_score"]),
                            "portfolio_notional_vnd": float(notional),
                            "max_adv_participation": float(adv_cap),
                            "min_adv20_value_vnd": float(adv_floor),
                            "round_trip_cost": float(args.round_trip_cost),
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
                                score_variant=score_variant,
                                entry_gate=gate_name,
                                candidate_name=str(candidate["name"]),
                                portfolio_notional_vnd=float(notional),
                                max_adv_participation=float(adv_cap),
                                min_adv20_value_vnd=float(adv_floor),
                            )

    results = sort_retail_results(pd.DataFrame(rows))
    viable = results.loc[
        retail_viable_mask(
            results,
            max_avg_cash_weight=float(args.viable_max_cash_weight),
            min_positive_years=int(args.viable_min_positive_years),
        )
    ].reset_index(drop=True)

    _print_top(results, title="H145: VOLUME-CONFIRMED ENTRY FILTER", top_n=int(args.top_results))
    if not viable.empty:
        _print_top(
            viable,
            title="H145: RETAIL-VIABLE ENTRY GATES",
            top_n=min(int(args.top_results), len(viable)),
        )
    else:
        print("\nNo H145 scenario cleared the retail-viable gate.")

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results_path = OUT_DIR / f"{ts}_h145_volume_confirmed_entry_filter_results.parquet"
    viable_path = OUT_DIR / f"{ts}_h145_volume_confirmed_entry_filter_viable.parquet"
    best_daily_path = OUT_DIR / f"{ts}_h145_volume_confirmed_entry_filter_best_daily.parquet"
    results.to_parquet(results_path, index=False)
    viable.to_parquet(viable_path, index=False)
    if best_daily is not None:
        best_daily.to_parquet(best_daily_path, index=False)

    summary = {
        "year_range": [int(args.start_year), int(args.end_year)],
        "score_variant": score_variant,
        "entry_gates": list(gate_matrices),
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
    }
    summary_path = write_run_summary(
        ts=ts,
        mode="portfolio_volume_confirmed_entry_filter",
        name="h145_volume_confirmed_entry_filter",
        summary=summary,
        artifacts={
            "results": str(results_path),
            "viable_results": str(viable_path),
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
    print(f"\nSaved H145 summary to {summary_path}")


if __name__ == "__main__":
    main()
