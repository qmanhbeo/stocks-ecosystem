from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.activation_alpha import BENCHMARK_PATH, RL_MATRIX_PATH, STOCK_DIR, TRADABILITY_PATH
from src.entry_alpha import (
    ENTRY_ALPHA_CANDIDATE_PANEL_PATH,
    build_entry_allowed_matrix,
    build_entry_candidate_panel,
    load_entry_alpha_inputs,
)
from src.run_summary import write_run_summary
from src.deterministic_portfolio import simulate_strategy


OUT_DIR = Path("artifacts/entry_alpha")


def _parse_optional_float_grid(values: list[str]) -> list[float | None]:
    parsed: list[float | None] = []
    for value in values:
        text = str(value).strip().lower()
        parsed.append(None if text in {"none", "null", "na"} else float(text))
    return parsed


def _sort_results(results: pd.DataFrame) -> pd.DataFrame:
    if results.empty:
        return results.copy()
    ordered = results.copy()
    for column in [
        "relative_total_return",
        "portfolio_total_return",
        "information_ratio_annualized",
        "avg_cash_weight",
        "avg_num_holdings",
        "positive_years",
    ]:
        ordered[column] = pd.to_numeric(ordered[column], errors="coerce")
    return ordered.sort_values(
        by=[
            "relative_total_return",
            "portfolio_total_return",
            "information_ratio_annualized",
            "avg_cash_weight",
            "avg_num_holdings",
            "positive_years",
        ],
        ascending=[False, False, False, True, False, False],
        ignore_index=True,
    )


def _print_top(results: pd.DataFrame, *, top_n: int) -> None:
    top = results.head(max(int(top_n), 1))
    print("\n" + "=" * 144)
    print("H239 TOP SPARSE-BREADTH SCENARIOS")
    print("=" * 144)
    print(
        f"{'rank':<5} {'top_m':>5} {'min_score':>10} {'min_gap':>8} "
        f"{'rel_ret':>10} {'tot_ret':>10} {'IR':>8} {'cash':>8} {'holds':>8} {'yrs+':>7}"
    )
    print("-" * 144)
    for idx, row in enumerate(top.itertuples(index=False), start=1):
        min_score = "-" if pd.isna(row.min_selection_score) else f"{row.min_selection_score:.2f}"
        min_gap = "-" if pd.isna(row.min_score_gap) else f"{row.min_score_gap:.3f}"
        print(
            f"{idx:<5} {int(row.top_m):>5} {min_score:>10} {min_gap:>8} "
            f"{float(row.relative_total_return) * 100:>+9.2f}% {float(row.portfolio_total_return) * 100:>+9.2f}% "
            f"{float(row.information_ratio_annualized):>8.2f} {float(row.avg_cash_weight) * 100:>7.2f}% "
            f"{float(row.avg_num_holdings):>8.2f} {int(row.positive_years):>3}/{int(row.total_years):<3}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H239: sparse-breadth threshold baseline for entry alpha")
    parser.add_argument("--matrix", type=str, default=str(RL_MATRIX_PATH))
    parser.add_argument("--tradability", type=str, default=str(TRADABILITY_PATH))
    parser.add_argument("--stock-dir", type=str, default=str(STOCK_DIR))
    parser.add_argument("--benchmark", type=str, default=str(BENCHMARK_PATH))
    parser.add_argument("--candidate-panel", type=str, default=str(ENTRY_ALPHA_CANDIDATE_PANEL_PATH))
    parser.add_argument("--start-year", type=int, default=2019)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--strategy", type=str, default="full_library")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--rebalance-every", type=int, default=5)
    parser.add_argument("--top-m-grid", nargs="+", type=int, default=[10, 20])
    parser.add_argument("--min-selection-score-grid", nargs="+", default=["0.60", "0.65", "0.70"])
    parser.add_argument("--min-score-gap-grid", nargs="+", default=["none", "0.01", "0.02"])
    parser.add_argument("--round-trip-cost", type=float, default=0.003)
    parser.add_argument("--required-holding-age", type=int, default=3)
    parser.add_argument("--initial-notional-vnd", type=float, default=100_000_000.0)
    parser.add_argument("--top-results", type=int, default=20)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    inputs = load_entry_alpha_inputs(
        matrix_path=Path(args.matrix),
        tradability_path=Path(args.tradability),
        stock_dir=Path(args.stock_dir),
        benchmark_path=Path(args.benchmark),
        start_year=int(args.start_year),
        end_year=int(args.end_year),
        strategy_name=str(args.strategy),
        round_trip_cost=float(args.round_trip_cost),
        required_holding_age=int(args.required_holding_age),
        initial_notional_vnd=float(args.initial_notional_vnd),
    )
    candidate_panel_path = Path(args.candidate_panel)
    top_m_grid = sorted(set(int(value) for value in args.top_m_grid))
    min_score_grid = _parse_optional_float_grid(list(args.min_selection_score_grid))
    min_gap_grid = _parse_optional_float_grid(list(args.min_score_gap_grid))
    max_top_m = max(top_m_grid)

    if candidate_panel_path.exists():
        candidate_panel = pd.read_parquet(candidate_panel_path)
        candidate_panel["time"] = pd.to_datetime(candidate_panel["time"])
        max_existing_rank = int(pd.to_numeric(candidate_panel["candidate_pool_rank"], errors="coerce").max())
        if max_existing_rank < max_top_m:
            candidate_panel = build_entry_candidate_panel(
                inputs,
                top_m_max=int(max_top_m),
                top_k=int(args.top_k),
                rebalance_every=int(args.rebalance_every),
                round_trip_cost=float(args.round_trip_cost),
                required_holding_age=int(args.required_holding_age),
                initial_notional_vnd=float(args.initial_notional_vnd),
            )
            candidate_panel_path.parent.mkdir(parents=True, exist_ok=True)
            candidate_panel.to_parquet(candidate_panel_path, index=False)
    else:
        candidate_panel = build_entry_candidate_panel(
            inputs,
            top_m_max=int(max_top_m),
            top_k=int(args.top_k),
            rebalance_every=int(args.rebalance_every),
            round_trip_cost=float(args.round_trip_cost),
            required_holding_age=int(args.required_holding_age),
            initial_notional_vnd=float(args.initial_notional_vnd),
        )
        candidate_panel_path.parent.mkdir(parents=True, exist_ok=True)
        candidate_panel.to_parquet(candidate_panel_path, index=False)

    fee_leg = float(args.round_trip_cost) / 2.0
    baseline = simulate_strategy(
        strategy_name=inputs.strategy_name,
        signal_columns=list(inputs.signal_columns),
        market_inputs=inputs.market_inputs,
        top_k=int(args.top_k),
        rebalance_every=int(args.rebalance_every),
        weighting="equal",
        initial_notional_vnd=float(args.initial_notional_vnd),
        max_adv_participation=0.0,
        required_holding_age=int(args.required_holding_age),
        buy_fee_rate=float(fee_leg),
        sell_fee_rate=float(fee_leg),
        capital_gains_tax_rate=0.0,
    )

    rows: list[dict[str, object]] = []
    best_daily: pd.DataFrame | None = None
    best_key: tuple[float, float, float, float, float] | None = None
    for top_m in top_m_grid:
        for min_selection_score in min_score_grid:
            for min_score_gap in min_gap_grid:
                entry_allowed_matrix = build_entry_allowed_matrix(
                    candidate_panel,
                    dates=pd.to_datetime(inputs.market_inputs.dates),
                    tickers=inputs.market_inputs.tickers,
                    top_m=int(top_m),
                    min_selection_score=min_selection_score,
                    min_score_gap=min_score_gap,
                    require_buyable=True,
                )
                result = simulate_strategy(
                    strategy_name=inputs.strategy_name,
                    signal_columns=list(inputs.signal_columns),
                    market_inputs=inputs.market_inputs,
                    top_k=int(args.top_k),
                    rebalance_every=int(args.rebalance_every),
                    weighting="equal",
                    initial_notional_vnd=float(args.initial_notional_vnd),
                    max_adv_participation=0.0,
                    required_holding_age=int(args.required_holding_age),
                    buy_fee_rate=float(fee_leg),
                    sell_fee_rate=float(fee_leg),
                    capital_gains_tax_rate=0.0,
                    entry_allowed_matrix=entry_allowed_matrix,
                )
                row = {
                    "scenario_name": (
                        f"topm{int(top_m)}__score_"
                        f"{'none' if min_selection_score is None else str(min_selection_score).replace('.', 'p')}__gap_"
                        f"{'none' if min_score_gap is None else str(min_score_gap).replace('.', 'p')}"
                    ),
                    "top_m": int(top_m),
                    "min_selection_score": min_selection_score,
                    "min_score_gap": min_score_gap,
                    **result.summary,
                }
                rows.append(row)
                key = (
                    float(row["relative_total_return"]),
                    float(row["portfolio_total_return"]),
                    float(row["information_ratio_annualized"]) if row["information_ratio_annualized"] is not None else float("-inf"),
                    -float(row["avg_cash_weight"]),
                    float(row["avg_num_holdings"]),
                )
                if best_key is None or key > best_key:
                    best_key = key
                    best_daily = result.daily.copy()

    results = _sort_results(pd.DataFrame(rows))
    baseline_row = pd.DataFrame(
        [
            {
                "scenario_name": "fixed_top_k_baseline",
                "top_m": None,
                "min_selection_score": None,
                "min_score_gap": None,
                **baseline.summary,
            }
        ]
    )

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results_path = OUT_DIR / f"{ts}_h239_sparse_breadth_results.parquet"
    best_daily_path = OUT_DIR / f"{ts}_h239_sparse_breadth_best_daily.parquet"
    baseline_daily_path = OUT_DIR / f"{ts}_h239_sparse_breadth_baseline_daily.parquet"
    results.to_parquet(results_path, index=False)
    baseline.daily.to_parquet(baseline_daily_path, index=False)
    if best_daily is None:
        best_daily = baseline.daily.copy()
    best_daily.to_parquet(best_daily_path, index=False)

    best = results.iloc[0].to_dict() if not results.empty else {}
    baseline_summary = baseline_row.iloc[0].to_dict()
    summary = {
        "strategy_name": inputs.strategy_name,
        "selector_name": inputs.selector_name,
        "baseline_fixed_top_k": baseline_summary,
        "best_sparse_breadth": best,
        "candidate_panel_path": str(candidate_panel_path),
        "results_path": str(results_path),
    }
    if best:
        summary["best_vs_baseline_relative_return_delta"] = (
            float(best["relative_total_return"]) - float(baseline_summary["relative_total_return"])
        )
        summary["best_vs_baseline_ir_delta"] = (
            (
                float(best["information_ratio_annualized"])
                if best.get("information_ratio_annualized") is not None
                else float("nan")
            )
            - (
                float(baseline_summary["information_ratio_annualized"])
                if baseline_summary.get("information_ratio_annualized") is not None
                else float("nan")
            )
        )

    write_run_summary(
        ts=ts,
        mode="entry_alpha_sparse_breadth_baseline",
        name="h239_entry_alpha_sparse_breadth_baseline",
        summary=summary,
        artifacts={
            "results": str(results_path),
            "best_daily": str(best_daily_path),
            "baseline_daily": str(baseline_daily_path),
            "candidate_panel": str(candidate_panel_path),
        },
        metadata={
            "matrix": str(args.matrix),
            "tradability": str(args.tradability),
            "stock_dir": str(args.stock_dir),
            "benchmark": str(args.benchmark),
            "start_year": int(args.start_year),
            "end_year": int(args.end_year),
            "strategy": str(args.strategy),
            "top_k": int(args.top_k),
            "rebalance_every": int(args.rebalance_every),
            "top_m_grid": top_m_grid,
            "min_selection_score_grid": min_score_grid,
            "min_score_gap_grid": min_gap_grid,
            "round_trip_cost": float(args.round_trip_cost),
            "required_holding_age": int(args.required_holding_age),
            "initial_notional_vnd": float(args.initial_notional_vnd),
        },
    )

    print("\nH239: ENTRY ALPHA SPARSE-BREADTH BASELINE")
    print(f"candidate_panel={candidate_panel_path}")
    print(
        "baseline rel_ret="
        f"{float(baseline_summary['relative_total_return']) * 100:+.2f}% | "
        f"IR={float(baseline_summary['information_ratio_annualized']) if baseline_summary['information_ratio_annualized'] is not None else float('nan'):.2f}"
    )
    if best:
        print(
            "best sparse rel_ret="
            f"{float(best['relative_total_return']) * 100:+.2f}% | "
            f"IR={float(best['information_ratio_annualized']) if best['information_ratio_annualized'] is not None else float('nan'):.2f}"
        )
    _print_top(results, top_n=int(args.top_results))


if __name__ == "__main__":
    main()
