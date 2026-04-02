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
from src.entry_alpha import build_entry_allowed_matrix
from src.entry_alpha_research import (
    ENTRY_ALPHA_OUT_DIR,
    add_baseline_deltas,
    backtest_row_from_result,
    load_or_build_entry_artifacts,
    run_entry_backtest,
)
from src.research_protocol import DEFAULT_PROTOCOL
from src.run_summary import write_run_summary


def _parse_optional_float_grid(values: list[str]) -> list[float | None]:
    parsed: list[float | None] = []
    for value in values:
        text = str(value).strip().lower()
        parsed.append(None if text in {"none", "null", "na"} else float(text))
    return parsed


def _sort_dev_results(results: pd.DataFrame) -> pd.DataFrame:
    if results.empty:
        return results.copy()
    ordered = results.copy()
    for column in [
        "dev_relative_total_return",
        "dev_information_ratio_annualized",
        "validation_relative_total_return",
        "validation_information_ratio_annualized",
        "confirmation_relative_total_return",
        "forward_relative_total_return",
        "overall_relative_total_return",
        "overall_information_ratio_annualized",
        "dev_avg_cash_weight",
        "dev_avg_daily_turnover",
    ]:
        if column in ordered.columns:
            ordered[column] = pd.to_numeric(ordered[column], errors="coerce")
    return ordered.sort_values(
        by=[
            "dev_relative_total_return",
            "dev_information_ratio_annualized",
            "validation_relative_total_return",
            "validation_information_ratio_annualized",
            "dev_avg_cash_weight",
            "dev_avg_daily_turnover",
            "top_m",
            "variant",
        ],
        ascending=[False, False, False, False, True, True, True, True],
        ignore_index=True,
    )


def _print_table(results: pd.DataFrame, *, top_n: int) -> None:
    top = results.head(max(int(top_n), 1))
    print("\n" + "=" * 208)
    print("H244: ENTRY ALPHA SPARSE-BREADTH HONEST PROTOCOL")
    print("=" * 208)
    print(
        f"{'rank':<5} {'variant':<32} {'dev_rel':>10} {'val_rel':>10} {'2025_rel':>10} {'2026+_rel':>10} "
        f"{'dev_IR':>8} {'val_IR':>8} {'2025_IR':>8} {'2026+_IR':>8} {'honest':>8}"
    )
    print("-" * 208)
    for idx, row in enumerate(top.itertuples(index=False), start=1):
        print(
            f"{idx:<5} {str(row.variant):<32} "
            f"{(row.dev_relative_total_return or 0.0)*100:>+9.2f}% "
            f"{(row.validation_relative_total_return or 0.0)*100:>+9.2f}% "
            f"{(row.confirmation_relative_total_return or 0.0)*100:>+9.2f}% "
            f"{(row.forward_relative_total_return or 0.0)*100:>+9.2f}% "
            f"{row.dev_information_ratio_annualized if row.dev_information_ratio_annualized is not None else float('nan'):>8.2f} "
            f"{row.validation_information_ratio_annualized if row.validation_information_ratio_annualized is not None else float('nan'):>8.2f} "
            f"{row.confirmation_information_ratio_annualized if row.confirmation_information_ratio_annualized is not None else float('nan'):>8.2f} "
            f"{row.forward_information_ratio_annualized if row.forward_information_ratio_annualized is not None else float('nan'):>8.2f} "
            f"{str(bool(row.honest_promoted)):>8}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H244: honest protocol for the sparse-breadth H239 branch")
    parser.add_argument("--matrix", type=str, default=str(RL_MATRIX_PATH))
    parser.add_argument("--tradability", type=str, default=str(TRADABILITY_PATH))
    parser.add_argument("--stock-dir", type=str, default=str(STOCK_DIR))
    parser.add_argument("--benchmark", type=str, default=str(BENCHMARK_PATH))
    parser.add_argument("--candidate-panel", type=str, default=str(data_path("features/entry_alpha/candidate_panel_daily.parquet")))
    parser.add_argument("--labels", type=str, default=str(data_path("features/entry_alpha/entry_labels_cycle5.parquet")))
    parser.add_argument("--start-year", type=int, default=2019)
    parser.add_argument("--end-year", type=int, default=2026)
    parser.add_argument("--strategy", type=str, default="full_library")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--rebalance-every", type=int, default=5)
    parser.add_argument("--top-m-grid", nargs="+", type=int, default=[5, 10, 20])
    parser.add_argument("--min-selection-score-grid", nargs="+", default=["0.60", "0.65", "0.70", "0.75"])
    parser.add_argument("--min-score-gap-grid", nargs="+", default=["none", "0.01", "0.02", "0.03"])
    parser.add_argument("--round-trip-cost", type=float, default=0.003)
    parser.add_argument("--required-holding-age", type=int, default=3)
    parser.add_argument("--initial-notional-vnd", type=float, default=100_000_000.0)
    parser.add_argument("--top-results", type=int, default=12)
    parser.add_argument("--forward-rel-delta-floor", type=float, default=-0.05)
    parser.add_argument("--forward-ir-delta-floor", type=float, default=-0.05)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    inputs, candidate_panel, _ = load_or_build_entry_artifacts(
        candidate_panel_path=Path(args.candidate_panel),
        labels_path=Path(args.labels),
        matrix_path=Path(args.matrix),
        tradability_path=Path(args.tradability),
        stock_dir=Path(args.stock_dir),
        benchmark_path=Path(args.benchmark),
        start_year=int(args.start_year),
        end_year=int(args.end_year),
        strategy_name=str(args.strategy),
        top_m_max=max(int(value) for value in args.top_m_grid),
        top_k=int(args.top_k),
        rebalance_every=int(args.rebalance_every),
        round_trip_cost=float(args.round_trip_cost),
        required_holding_age=int(args.required_holding_age),
        initial_notional_vnd=float(args.initial_notional_vnd),
    )
    candidate_panel = candidate_panel.copy()
    candidate_panel["time"] = pd.to_datetime(candidate_panel["time"])
    candidate_panel = candidate_panel[
        (candidate_panel["time"].dt.year >= int(args.start_year))
        & (candidate_panel["time"].dt.year <= int(args.end_year))
    ].copy()

    top_m_grid = sorted(set(int(value) for value in args.top_m_grid))
    min_score_grid = _parse_optional_float_grid(list(args.min_selection_score_grid))
    min_gap_grid = _parse_optional_float_grid(list(args.min_score_gap_grid))
    market_dates = pd.to_datetime(inputs.market_inputs.dates)
    market_tickers = inputs.market_inputs.tickers

    baseline_result = run_entry_backtest(
        inputs,
        entry_allowed_matrix=pd.DataFrame(True, index=range(len(market_dates)), columns=range(len(market_tickers))).to_numpy(dtype=bool),
        round_trip_cost=float(args.round_trip_cost),
        required_holding_age=int(args.required_holding_age),
        initial_notional_vnd=float(args.initial_notional_vnd),
        top_k=int(args.top_k),
        rebalance_every=int(args.rebalance_every),
    )

    rows = [
        backtest_row_from_result(
            variant="fixed_top_k_baseline",
            family="baseline",
            result=baseline_result,
            extra={
                "top_m": None,
                "min_selection_score": None,
                "min_score_gap": None,
                "dev_selected": False,
            },
        )
    ]
    daily_outputs: dict[str, pd.DataFrame] = {"fixed_top_k_baseline": baseline_result.daily.copy()}

    for top_m in top_m_grid:
        for min_selection_score in min_score_grid:
            for min_score_gap in min_gap_grid:
                variant = (
                    f"topm{int(top_m)}__score_"
                    f"{'none' if min_selection_score is None else str(min_selection_score).replace('.', 'p')}__gap_"
                    f"{'none' if min_score_gap is None else str(min_score_gap).replace('.', 'p')}"
                )
                entry_allowed_matrix = build_entry_allowed_matrix(
                    candidate_panel,
                    dates=market_dates,
                    tickers=market_tickers,
                    top_m=int(top_m),
                    min_selection_score=min_selection_score,
                    min_score_gap=min_score_gap,
                    require_buyable=True,
                )
                result = run_entry_backtest(
                    inputs,
                    entry_allowed_matrix=entry_allowed_matrix,
                    round_trip_cost=float(args.round_trip_cost),
                    required_holding_age=int(args.required_holding_age),
                    initial_notional_vnd=float(args.initial_notional_vnd),
                    top_k=int(args.top_k),
                    rebalance_every=int(args.rebalance_every),
                )
                rows.append(
                    backtest_row_from_result(
                        variant=variant,
                        family="sparse_breadth",
                        result=result,
                        extra={
                            "top_m": int(top_m),
                            "min_selection_score": min_selection_score,
                            "min_score_gap": min_score_gap,
                            "dev_selected": False,
                        },
                    )
                )
                daily_outputs[variant] = result.daily.copy()

    results = add_baseline_deltas(pd.DataFrame(rows), baseline_variant="fixed_top_k_baseline")
    scenario_results = results.loc[results["variant"] != "fixed_top_k_baseline"].copy()
    dev_ordered = _sort_dev_results(scenario_results)
    selected_variant = str(dev_ordered.iloc[0]["variant"])
    results.loc[results["variant"] == selected_variant, "dev_selected"] = True
    results["forward_relative_delta"] = (
        pd.to_numeric(results["forward_relative_total_return"], errors="coerce")
        - pd.to_numeric(results.loc[results["variant"] == "fixed_top_k_baseline", "forward_relative_total_return"].iloc[0], errors="coerce")
    )
    results["forward_ir_delta"] = (
        pd.to_numeric(results["forward_information_ratio_annualized"], errors="coerce")
        - pd.to_numeric(results.loc[results["variant"] == "fixed_top_k_baseline", "forward_information_ratio_annualized"].iloc[0], errors="coerce")
    )
    results["forward_survives"] = (
        pd.to_numeric(results["forward_relative_delta"], errors="coerce") >= float(args.forward_rel_delta_floor)
    ) & (
        pd.to_numeric(results["forward_ir_delta"], errors="coerce") >= float(args.forward_ir_delta_floor)
    )
    results["honest_promoted"] = results["promoted"].fillna(False).astype(bool) & results["forward_survives"].fillna(False).astype(bool)
    ordered = results.loc[results["variant"] != "fixed_top_k_baseline"].copy()
    ordered = ordered.merge(
        dev_ordered[["variant"]].reset_index().rename(columns={"index": "dev_rank"}),
        on="variant",
        how="left",
        validate="one_to_one",
    )
    ordered["dev_rank"] = pd.to_numeric(ordered["dev_rank"], errors="coerce") + 1
    ordered = ordered.sort_values(
        by=["dev_rank", "validation_relative_delta", "confirmation_relative_delta", "variant"],
        ascending=[True, False, False, True],
        ignore_index=True,
    )
    _print_table(ordered, top_n=int(args.top_results))

    selected_row = results.loc[results["variant"] == selected_variant].iloc[0].to_dict()
    baseline_row = results.loc[results["variant"] == "fixed_top_k_baseline"].iloc[0].to_dict()

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    ENTRY_ALPHA_OUT_DIR.mkdir(parents=True, exist_ok=True)
    results_path = ENTRY_ALPHA_OUT_DIR / f"{ts}_h244_entry_alpha_sparse_breadth_protocol_results.parquet"
    selected_daily_path = ENTRY_ALPHA_OUT_DIR / f"{ts}_h244_entry_alpha_sparse_breadth_protocol_selected_daily.parquet"
    baseline_daily_path = ENTRY_ALPHA_OUT_DIR / f"{ts}_h244_entry_alpha_sparse_breadth_protocol_baseline_daily.parquet"
    results.to_parquet(results_path, index=False)
    daily_outputs[selected_variant].to_parquet(selected_daily_path, index=False)
    daily_outputs["fixed_top_k_baseline"].to_parquet(baseline_daily_path, index=False)

    summary = {
        "protocol": DEFAULT_PROTOCOL.describe(),
        "baseline_fixed_top_k": baseline_row,
        "dev_selected_winner": selected_row,
        "dev_top_candidates": ordered.head(5).to_dict("records"),
        "honest_promoted": bool(selected_row.get("honest_promoted", False)),
    }
    write_run_summary(
        ts=ts,
        mode="entry_alpha_sparse_breadth_protocol",
        name="h244_entry_alpha_sparse_breadth_protocol",
        summary=summary,
        artifacts={
            "results": str(results_path),
            "selected_daily": str(selected_daily_path),
            "baseline_daily": str(baseline_daily_path),
            "candidate_panel": str(args.candidate_panel),
        },
        metadata={
            "matrix": str(args.matrix),
            "tradability": str(args.tradability),
            "stock_dir": str(args.stock_dir),
            "benchmark": str(args.benchmark),
            "candidate_panel": str(args.candidate_panel),
            "labels": str(args.labels),
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
            "forward_rel_delta_floor": float(args.forward_rel_delta_floor),
            "forward_ir_delta_floor": float(args.forward_ir_delta_floor),
        },
    )


if __name__ == "__main__":
    main()
