"""
H146: Variable-breadth long-only portfolio construction.

Purpose:
- test whether fixed top-k is structurally wrong in an illiquid market
- allow the portfolio to hold fewer names when score and deployability gates justify it
- evaluate variable breadth only after choosing the strongest score/gate combination

Usage:
    conda run -n stocks python analysis/h146_variable_breadth_portfolio.py
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
from src.portfolio_construction_search import retail_viable_mask, sort_retail_results
from src.portfolio_friction_features import (
    add_liquidity_aware_score_variants,
    build_boolean_matrix,
    build_friction_feature_frame,
)
from src.run_summary import write_run_summary

RL_MATRIX_PATH = data_path("features/xs_rl_signal_matrix.parquet")
TRADABILITY_PATH = data_path("features/execution/tradability_daily.parquet")
STOCK_DIR = data_path("stock")
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
    parser.add_argument("--rebalance-every", type=int, default=5)
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
    parser.add_argument("--entry-gate", type=str, default="")
    parser.add_argument("--max-k-grid", nargs="+", type=int, default=[3, 5])
    parser.add_argument("--min-score-grid", nargs="+", default=["none", "0.55", "0.60"])
    parser.add_argument("--min-deployable-weight-grid", nargs="+", type=float, default=[0.10, 0.15, 0.20])
    parser.add_argument("--max-names-if-liquidity-thin-grid", nargs="+", type=int, default=[0, 2])
    parser.add_argument("--viable-max-cash-weight", type=float, default=0.40)
    parser.add_argument("--viable-min-positive-years", type=int, default=5)
    parser.add_argument("--top-results", type=int, default=20)
    return parser.parse_args()


def _resolve_defaults(args: argparse.Namespace) -> tuple[str, str]:
    if args.score_variant.strip() and args.entry_gate.strip():
        return args.score_variant.strip(), args.entry_gate.strip()
    if not LATEST_H145_SUMMARY.exists():
        return "liq_base", "none"
    payload = json.loads(LATEST_H145_SUMMARY.read_text(encoding="utf-8"))
    summary = payload.get("summary", {})
    best = summary.get("best_viable") or summary.get("best_overall") or {}
    score_variant = str(args.score_variant.strip() or best.get("score_variant") or "liq_base")
    entry_gate = str(args.entry_gate.strip() or best.get("entry_gate") or "none")
    return score_variant, entry_gate


def _parse_min_score_grid(raw_values: list[str]) -> list[float | None]:
    parsed: list[float | None] = []
    for value in raw_values:
        text = str(value).strip().lower()
        parsed.append(None if text in {"none", "null", "na"} else float(text))
    return parsed


def _print_top(results: pd.DataFrame, *, title: str, top_n: int) -> None:
    top = results.head(top_n)
    print("\n" + "=" * 232)
    print(title)
    print("=" * 232)
    print(
        f"{'rank':<5} {'max_k':>5} {'gate':>7} {'min_w':>7} {'thin':>6} {'notional':>11} {'adv_cap':>8} {'adv_floor':>10} "
        f"{'tot_ret':>10} {'rel_ret':>10} {'ann_ret':>10} {'IR':>8} {'cash':>8} {'holds':>8} {'yrs+':>7}"
    )
    print("-" * 232)
    for i, row in enumerate(top.itertuples(index=False), start=1):
        gate = "none" if row.min_score is None or pd.isna(row.min_score) else f"{row.min_score:.2f}"
        thin_value = row.max_names_if_liquidity_thin
        thin = "-"
        if thin_value is not None and not pd.isna(thin_value) and int(thin_value) > 0:
            thin = str(int(thin_value))
        print(
            f"{i:<5} {row.top_k:>5} {gate:>7} {row.min_deployable_weight*100:>6.1f}% {thin:>6} "
            f"{row.portfolio_notional_vnd/1e6:>10.0f}m {row.max_adv_participation*100:>7.2f}% {row.min_adv20_value_vnd/1e9:>9.2f}B "
            f"{row.portfolio_total_return*100:>+9.2f}% {row.relative_total_return*100:>+9.2f}% "
            f"{row.portfolio_annualized_return*100 if row.portfolio_annualized_return is not None else float('nan'):>+9.2f}% "
            f"{row.information_ratio_annualized if row.information_ratio_annualized is not None else float('nan'):>8.2f} "
            f"{row.avg_cash_weight*100:>7.2f}% {row.avg_num_holdings:>8.2f} {row.positive_years:>3}/{row.total_years:<3}"
        )


def main() -> None:
    args = parse_args()
    matrix_path = Path(args.matrix)
    tradability_path = Path(args.tradability)
    stock_dir = Path(args.stock_dir)
    benchmark_path = Path(args.benchmark)
    score_variant, entry_gate = _resolve_defaults(args)

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
    gate_column = f"gate__{entry_gate}"
    if gate_column not in feature_frame.columns:
        raise ValueError(f"Unknown entry gate {entry_gate!r}")

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
    entry_allowed_matrix = build_boolean_matrix(
        feature_frame,
        value_column=gate_column,
        dates=pd.to_datetime(market_inputs.dates),
        tickers=market_inputs.tickers,
    )

    notionals = sorted(set(float(v) for v in args.portfolio_notional_grid))
    adv_caps = sorted(set(float(v) for v in args.max_adv_grid))
    adv_floors = sorted(set(float(v) for v in args.min_adv20_grid))
    max_k_grid = sorted(set(int(v) for v in args.max_k_grid))
    min_score_grid = _parse_min_score_grid(args.min_score_grid)
    min_deployable_weight_grid = sorted(set(float(v) for v in args.min_deployable_weight_grid))
    thin_grid = sorted(set(int(v) for v in args.max_names_if_liquidity_thin_grid))
    fee_leg = float(args.round_trip_cost) / 2.0
    print(
        f"Score variant={score_variant} | entry_gate={entry_gate} | "
        f"scenarios={len(max_k_grid) * len(min_score_grid) * len(min_deployable_weight_grid) * len(thin_grid) * len(notionals) * len(adv_caps) * len(adv_floors)} | "
        f"required_holding_age={required_holding_age}"
    )

    rows: list[dict[str, object]] = []
    best_daily: pd.DataFrame | None = None
    best_key: tuple[float, float, float, float, float] | None = None
    for top_k in max_k_grid:
        for min_score in min_score_grid:
            for min_deployable_weight in min_deployable_weight_grid:
                for thin_cap in thin_grid:
                    thin_value = None if int(thin_cap) <= 0 else int(thin_cap)
                    for notional in notionals:
                        for adv_cap in adv_caps:
                            for adv_floor in adv_floors:
                                result = simulate_strategy(
                                    strategy_name=score_variant,
                                    signal_columns=signal_columns,
                                    market_inputs=market_inputs,
                                    top_k=int(top_k),
                                    rebalance_every=int(args.rebalance_every),
                                    weighting="equal",
                                    initial_notional_vnd=float(notional),
                                    max_adv_participation=float(adv_cap),
                                    required_holding_age=int(required_holding_age),
                                    buy_fee_rate=float(fee_leg),
                                    sell_fee_rate=float(fee_leg),
                                    capital_gains_tax_rate=float(args.capital_gains_tax_rate),
                                    min_score=min_score,
                                    min_adv20_value_vnd=float(adv_floor),
                                    max_names_if_liquidity_thin=thin_value,
                                    entry_allowed_matrix=entry_allowed_matrix,
                                    min_deployable_weight=float(min_deployable_weight),
                                )
                                row = {
                                    "score_variant": score_variant,
                                    "entry_gate": entry_gate,
                                    "top_k": int(top_k),
                                    "rebalance_every": int(args.rebalance_every),
                                    "weighting": "equal",
                                    "min_score": min_score,
                                    "min_deployable_weight": float(min_deployable_weight),
                                    "max_names_if_liquidity_thin": thin_value,
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
                                        entry_gate=entry_gate,
                                        top_k=int(top_k),
                                        min_score=min_score,
                                        min_deployable_weight=float(min_deployable_weight),
                                        max_names_if_liquidity_thin=thin_value,
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

    _print_top(results, title="H146: VARIABLE-BREADTH PORTFOLIO", top_n=int(args.top_results))
    if not viable.empty:
        _print_top(
            viable,
            title="H146: RETAIL-VIABLE VARIABLE-BREADTH SCENARIOS",
            top_n=min(int(args.top_results), len(viable)),
        )
    else:
        print("\nNo H146 scenario cleared the retail-viable gate.")

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results_path = OUT_DIR / f"{ts}_h146_variable_breadth_portfolio_results.parquet"
    viable_path = OUT_DIR / f"{ts}_h146_variable_breadth_portfolio_viable.parquet"
    best_daily_path = OUT_DIR / f"{ts}_h146_variable_breadth_portfolio_best_daily.parquet"
    results.to_parquet(results_path, index=False)
    viable.to_parquet(viable_path, index=False)
    if best_daily is not None:
        best_daily.to_parquet(best_daily_path, index=False)

    summary = {
        "year_range": [int(args.start_year), int(args.end_year)],
        "score_variant": score_variant,
        "entry_gate": entry_gate,
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
        mode="portfolio_variable_breadth",
        name="h146_variable_breadth_portfolio",
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
    print(f"\nSaved H146 summary to {summary_path}")


if __name__ == "__main__":
    main()
