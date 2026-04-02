from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import sys

import numpy as np
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


def _coerce_numeric_columns(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    work = frame.copy()
    for column in columns:
        if column in work.columns:
            work[column] = pd.to_numeric(work[column], errors="coerce")
    return work


def _sort_dev_results(results: pd.DataFrame) -> pd.DataFrame:
    if results.empty:
        return results.copy()
    ordered = _coerce_numeric_columns(
        results,
        columns=[
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
            "top_k",
            "top_m",
        ],
    )
    return ordered.sort_values(
        by=[
            "dev_relative_total_return",
            "dev_information_ratio_annualized",
            "validation_relative_total_return",
            "validation_information_ratio_annualized",
            "confirmation_relative_total_return",
            "forward_relative_total_return",
            "dev_avg_cash_weight",
            "dev_avg_daily_turnover",
            "top_m",
            "variant",
        ],
        ascending=[False, False, False, False, False, False, True, True, True, True],
        ignore_index=True,
    )


def _sort_contract_winners(results: pd.DataFrame) -> pd.DataFrame:
    if results.empty:
        return results.copy()
    ordered = _coerce_numeric_columns(
        results,
        columns=[
            "top_k",
            "validation_relative_total_return",
            "validation_information_ratio_annualized",
            "confirmation_relative_total_return",
            "confirmation_information_ratio_annualized",
            "forward_relative_total_return",
            "forward_information_ratio_annualized",
            "overall_relative_total_return",
        ],
    )
    return ordered.sort_values(
        by=[
            "validation_relative_total_return",
            "validation_information_ratio_annualized",
            "confirmation_relative_total_return",
            "forward_relative_total_return",
            "top_k",
        ],
        ascending=[False, False, False, False, True],
        ignore_index=True,
    )


def _print_contract_table(contract_winners: pd.DataFrame) -> None:
    print("\n" + "=" * 216)
    print("H245: ENTRY ALPHA TOP-K CONTRACT AUDIT")
    print("=" * 216)
    print(
        f"{'rank':<5} {'top_k':<6} {'variant':<40} {'val_rel':>10} {'2025_rel':>10} {'2026+_rel':>10} "
        f"{'val_IR':>8} {'2025_IR':>8} {'2026+_IR':>8} {'honest':>8} {'dev_rel':>10}"
    )
    print("-" * 216)
    for idx, row in enumerate(contract_winners.itertuples(index=False), start=1):
        print(
            f"{idx:<5} {int(row.top_k):<6} {str(row.variant):<40} "
            f"{(row.validation_relative_total_return or 0.0)*100:>+9.2f}% "
            f"{(row.confirmation_relative_total_return or 0.0)*100:>+9.2f}% "
            f"{(row.forward_relative_total_return or 0.0)*100:>+9.2f}% "
            f"{row.validation_information_ratio_annualized if row.validation_information_ratio_annualized is not None else float('nan'):>8.2f} "
            f"{row.confirmation_information_ratio_annualized if row.confirmation_information_ratio_annualized is not None else float('nan'):>8.2f} "
            f"{row.forward_information_ratio_annualized if row.forward_information_ratio_annualized is not None else float('nan'):>8.2f} "
            f"{str(bool(row.honest_promoted)):>8} "
            f"{(row.dev_relative_total_return or 0.0)*100:>+9.2f}%"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H245: sparse top-k contract audit for the entry-alpha branch")
    parser.add_argument("--matrix", type=str, default=str(RL_MATRIX_PATH))
    parser.add_argument("--tradability", type=str, default=str(TRADABILITY_PATH))
    parser.add_argument("--stock-dir", type=str, default=str(STOCK_DIR))
    parser.add_argument("--benchmark", type=str, default=str(BENCHMARK_PATH))
    parser.add_argument("--candidate-panel", type=str, default=str(data_path("features/entry_alpha/candidate_panel_daily.parquet")))
    parser.add_argument("--labels", type=str, default=str(data_path("features/entry_alpha/entry_labels_cycle5.parquet")))
    parser.add_argument("--start-year", type=int, default=2019)
    parser.add_argument("--end-year", type=int, default=2026)
    parser.add_argument("--strategy", type=str, default="full_library")
    parser.add_argument("--top-k-grid", nargs="+", type=int, default=[1, 2, 3, 5])
    parser.add_argument("--rebalance-every", type=int, default=5)
    parser.add_argument("--top-m-grid", nargs="+", type=int, default=[5, 10, 20])
    parser.add_argument("--min-selection-score-grid", nargs="+", default=["0.60", "0.65", "0.70", "0.75"])
    parser.add_argument("--min-score-gap-grid", nargs="+", default=["none", "0.01", "0.02", "0.03"])
    parser.add_argument("--round-trip-cost", type=float, default=0.003)
    parser.add_argument("--required-holding-age", type=int, default=3)
    parser.add_argument("--initial-notional-vnd", type=float, default=100_000_000.0)
    parser.add_argument("--top-results", type=int, default=8)
    parser.add_argument("--forward-rel-delta-floor", type=float, default=-0.05)
    parser.add_argument("--forward-ir-delta-floor", type=float, default=-0.05)
    return parser.parse_args()


def _evaluate_top_k_contract(
    *,
    inputs,
    candidate_panel: pd.DataFrame,
    top_k: int,
    top_m_grid: list[int],
    min_score_grid: list[float | None],
    min_gap_grid: list[float | None],
    market_dates: pd.DatetimeIndex,
    market_tickers: list[str],
    round_trip_cost: float,
    required_holding_age: int,
    initial_notional_vnd: float,
    rebalance_every: int,
    forward_rel_delta_floor: float,
    forward_ir_delta_floor: float,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame], dict[str, object], dict[str, object]]:
    baseline_variant = f"topk{int(top_k)}__fixed_baseline"
    baseline_result = run_entry_backtest(
        inputs,
        entry_allowed_matrix=np.ones((len(market_dates), len(market_tickers)), dtype=bool),
        round_trip_cost=float(round_trip_cost),
        required_holding_age=int(required_holding_age),
        initial_notional_vnd=float(initial_notional_vnd),
        top_k=int(top_k),
        rebalance_every=int(rebalance_every),
    )

    rows = [
        backtest_row_from_result(
            variant=baseline_variant,
            family="baseline",
            result=baseline_result,
            extra={
                "top_k": int(top_k),
                "top_m": None,
                "min_selection_score": None,
                "min_score_gap": None,
                "dev_selected": False,
            },
        )
    ]
    daily_outputs: dict[str, pd.DataFrame] = {baseline_variant: baseline_result.daily.copy()}

    for top_m in top_m_grid:
        for min_selection_score in min_score_grid:
            for min_score_gap in min_gap_grid:
                variant = (
                    f"topk{int(top_k)}__topm{int(top_m)}__score_"
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
                    round_trip_cost=float(round_trip_cost),
                    required_holding_age=int(required_holding_age),
                    initial_notional_vnd=float(initial_notional_vnd),
                    top_k=int(top_k),
                    rebalance_every=int(rebalance_every),
                )
                rows.append(
                    backtest_row_from_result(
                        variant=variant,
                        family="sparse_breadth",
                        result=result,
                        extra={
                            "top_k": int(top_k),
                            "top_m": int(top_m),
                            "min_selection_score": min_selection_score,
                            "min_score_gap": min_score_gap,
                            "dev_selected": False,
                        },
                    )
                )
                daily_outputs[variant] = result.daily.copy()

    results = add_baseline_deltas(pd.DataFrame(rows), baseline_variant=baseline_variant)
    baseline_row = results.loc[results["variant"] == baseline_variant].iloc[0].to_dict()
    scenario_results = results.loc[results["variant"] != baseline_variant].copy()
    dev_ordered = _sort_dev_results(scenario_results)
    selected_variant = str(dev_ordered.iloc[0]["variant"])
    results.loc[results["variant"] == selected_variant, "dev_selected"] = True
    results["forward_relative_delta"] = (
        pd.to_numeric(results["forward_relative_total_return"], errors="coerce")
        - pd.to_numeric(baseline_row.get("forward_relative_total_return"), errors="coerce")
    )
    results["forward_ir_delta"] = (
        pd.to_numeric(results["forward_information_ratio_annualized"], errors="coerce")
        - pd.to_numeric(baseline_row.get("forward_information_ratio_annualized"), errors="coerce")
    )
    results["forward_survives"] = (
        pd.to_numeric(results["forward_relative_delta"], errors="coerce") >= float(forward_rel_delta_floor)
    ) & (
        pd.to_numeric(results["forward_ir_delta"], errors="coerce") >= float(forward_ir_delta_floor)
    )
    promoted_mask = pd.Series(results["promoted"], dtype="boolean").fillna(False).astype(bool)
    forward_mask = pd.Series(results["forward_survives"], dtype="boolean").fillna(False).astype(bool)
    results["honest_promoted"] = promoted_mask & forward_mask
    selected_row = results.loc[results["variant"] == selected_variant].iloc[0].to_dict()
    selected_row["baseline_variant"] = baseline_variant
    selected_row["baseline_validation_relative_total_return"] = baseline_row.get("validation_relative_total_return")
    selected_row["baseline_confirmation_relative_total_return"] = baseline_row.get("confirmation_relative_total_return")
    selected_row["baseline_forward_relative_total_return"] = baseline_row.get("forward_relative_total_return")
    selected_row["baseline_validation_information_ratio_annualized"] = baseline_row.get("validation_information_ratio_annualized")
    selected_row["baseline_confirmation_information_ratio_annualized"] = baseline_row.get("confirmation_information_ratio_annualized")
    selected_row["baseline_forward_information_ratio_annualized"] = baseline_row.get("forward_information_ratio_annualized")
    return results, daily_outputs, selected_row, baseline_row


def main() -> None:
    args = parse_args()
    top_k_grid = sorted(set(int(value) for value in args.top_k_grid))
    top_m_grid = sorted(set(int(value) for value in args.top_m_grid))
    min_score_grid = _parse_optional_float_grid(list(args.min_selection_score_grid))
    min_gap_grid = _parse_optional_float_grid(list(args.min_score_gap_grid))

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
        top_m_max=max(int(value) for value in top_m_grid),
        top_k=max(top_k_grid),
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

    market_dates = pd.DatetimeIndex(pd.to_datetime(inputs.market_inputs.dates))
    market_tickers = list(inputs.market_inputs.tickers)

    all_results: list[pd.DataFrame] = []
    all_winner_rows: list[dict[str, object]] = []
    baseline_rows: list[dict[str, object]] = []
    winner_daily_outputs: dict[int, pd.DataFrame] = {}

    for top_k in top_k_grid:
        results, daily_outputs, selected_row, baseline_row = _evaluate_top_k_contract(
            inputs=inputs,
            candidate_panel=candidate_panel,
            top_k=int(top_k),
            top_m_grid=top_m_grid,
            min_score_grid=min_score_grid,
            min_gap_grid=min_gap_grid,
            market_dates=market_dates,
            market_tickers=market_tickers,
            round_trip_cost=float(args.round_trip_cost),
            required_holding_age=int(args.required_holding_age),
            initial_notional_vnd=float(args.initial_notional_vnd),
            rebalance_every=int(args.rebalance_every),
            forward_rel_delta_floor=float(args.forward_rel_delta_floor),
            forward_ir_delta_floor=float(args.forward_ir_delta_floor),
        )
        all_results.append(results)
        all_winner_rows.append(selected_row)
        baseline_rows.append(baseline_row)
        winner_daily_outputs[int(top_k)] = daily_outputs[str(selected_row["variant"])].copy()

    results = pd.concat(all_results, ignore_index=True)
    contract_winners = _sort_contract_winners(pd.DataFrame(all_winner_rows))
    contract_winners["validation_contract_rank"] = np.arange(1, len(contract_winners) + 1, dtype=int)
    validation_selected = contract_winners.iloc[0].to_dict()
    top5_winner = contract_winners.loc[contract_winners["top_k"] == 5].iloc[0].to_dict() if (contract_winners["top_k"] == 5).any() else None
    if top5_winner is not None:
        validation_selected["validation_relative_delta_vs_top5_contract"] = (
            (validation_selected.get("validation_relative_total_return") or 0.0)
            - (top5_winner.get("validation_relative_total_return") or 0.0)
        )
        validation_selected["confirmation_relative_delta_vs_top5_contract"] = (
            (validation_selected.get("confirmation_relative_total_return") or 0.0)
            - (top5_winner.get("confirmation_relative_total_return") or 0.0)
        )
        validation_selected["forward_relative_delta_vs_top5_contract"] = (
            (validation_selected.get("forward_relative_total_return") or 0.0)
            - (top5_winner.get("forward_relative_total_return") or 0.0)
        )

    _print_contract_table(contract_winners.head(max(int(args.top_results), 1)))

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    ENTRY_ALPHA_OUT_DIR.mkdir(parents=True, exist_ok=True)
    results_path = ENTRY_ALPHA_OUT_DIR / f"{ts}_h245_entry_alpha_topk_contract_audit_results.parquet"
    winners_path = ENTRY_ALPHA_OUT_DIR / f"{ts}_h245_entry_alpha_topk_contract_audit_contract_winners.parquet"
    selected_daily_path = ENTRY_ALPHA_OUT_DIR / f"{ts}_h245_entry_alpha_topk_contract_audit_selected_daily.parquet"
    top5_daily_path = ENTRY_ALPHA_OUT_DIR / f"{ts}_h245_entry_alpha_topk_contract_audit_top5_daily.parquet"
    baselines_path = ENTRY_ALPHA_OUT_DIR / f"{ts}_h245_entry_alpha_topk_contract_audit_baselines.parquet"
    results.to_parquet(results_path, index=False)
    contract_winners.to_parquet(winners_path, index=False)
    winner_daily_outputs[int(validation_selected["top_k"])].to_parquet(selected_daily_path, index=False)
    if top5_winner is not None:
        winner_daily_outputs[int(top5_winner["top_k"])].to_parquet(top5_daily_path, index=False)
    pd.DataFrame(baseline_rows).to_parquet(baselines_path, index=False)

    summary = {
        "protocol": DEFAULT_PROTOCOL.describe(),
        "contract_winners": contract_winners.to_dict("records"),
        "validation_selected_contract": validation_selected,
        "top5_contract_winner": top5_winner,
        "top_k_grid": top_k_grid,
        "top_m_grid": top_m_grid,
        "min_selection_score_grid": min_score_grid,
        "min_score_gap_grid": min_gap_grid,
    }
    write_run_summary(
        ts=ts,
        mode="entry_alpha_topk_contract_audit",
        name="h245_entry_alpha_topk_contract_audit",
        summary=summary,
        artifacts={
            "results": str(results_path),
            "contract_winners": str(winners_path),
            "selected_daily": str(selected_daily_path),
            "top5_daily": str(top5_daily_path) if top5_winner is not None else None,
            "baselines": str(baselines_path),
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
            "top_k_grid": top_k_grid,
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
