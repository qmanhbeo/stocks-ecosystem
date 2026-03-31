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
from src.entry_alpha import build_entry_allowed_matrix, build_entry_labels
from src.entry_alpha_research import (
    ENTRY_ALPHA_OUT_DIR,
    add_baseline_deltas,
    backtest_row_from_result,
    build_entry_allowed_matrix_from_score,
    default_entry_model_specs,
    fit_entry_model,
    load_or_build_entry_artifacts,
    prepare_entry_research_panel,
    run_entry_backtest,
)
from src.research_protocol import DEFAULT_PROTOCOL, PHASE_ORDER, assign_research_phase
from src.run_summary import write_run_summary


DEFAULT_SMALL_BOOK_CONTRACTS: dict[int, dict[str, float | int | None]] = {
    1: {
        "top_m": 5,
        "min_selection_score": 0.60,
        "min_score_gap": None,
    },
    2: {
        "top_m": 5,
        "min_selection_score": 0.65,
        "min_score_gap": 0.03,
    },
}


def _parse_float_grid(values: list[str]) -> list[float]:
    return [float(value) for value in values]


def _tokenize_float(value: float) -> str:
    text = f"{float(value):.3f}".rstrip("0").rstrip(".")
    return text.replace(".", "p")


def _coerce_numeric_columns(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    work = frame.copy()
    for column in columns:
        if column in work.columns:
            work[column] = pd.to_numeric(work[column], errors="coerce")
    return work


def _sort_results(results: pd.DataFrame) -> pd.DataFrame:
    if results.empty:
        return results.copy()
    ordered = _coerce_numeric_columns(
        results,
        columns=[
            "top_k",
            "label_edge_buffer",
            "threshold",
            "validation_auc",
            "confirmation_auc",
            "validation_relative_delta",
            "validation_ir_delta",
            "confirmation_relative_delta",
            "confirmation_ir_delta",
            "validation_relative_total_return",
            "confirmation_relative_total_return",
            "overall_relative_total_return",
        ],
    )
    return ordered.sort_values(
        by=[
            "promoted",
            "validation_relative_delta",
            "validation_auc",
            "validation_ir_delta",
            "confirmation_relative_delta",
            "confirmation_auc",
            "variant",
        ],
        ascending=[False, False, False, False, False, False, True],
        ignore_index=True,
    )


def _label_stats(labels: pd.DataFrame) -> dict[str, object]:
    phased = assign_research_phase(labels, date_column="time", protocol=DEFAULT_PROTOCOL)
    phased["buy_now_label"] = pd.to_numeric(phased["buy_now_label"], errors="coerce")
    stats: dict[str, object] = {
        "overall_rows": int(len(phased)),
        "overall_labeled_rows": int(phased["buy_now_label"].notna().sum()),
        "overall_positive_rate": float(phased["buy_now_label"].dropna().mean()),
    }
    for phase in PHASE_ORDER:
        phase_frame = phased.loc[phased["research_phase"] == phase].copy()
        labeled = phase_frame["buy_now_label"].dropna()
        stats[f"{phase}_rows"] = int(len(phase_frame))
        stats[f"{phase}_labeled_rows"] = int(labeled.shape[0])
        stats[f"{phase}_positive_rate"] = float(labeled.mean()) if not labeled.empty else None
        stats[f"{phase}_years_present"] = sorted(pd.to_datetime(phase_frame["time"]).dt.year.dropna().unique().tolist())
    return stats


def _print_table(contract_winners: pd.DataFrame) -> None:
    print("\n" + "=" * 228)
    print("H247: ENTRY ALPHA LABEL-SHARPEN AUDIT")
    print("=" * 228)
    print(
        f"{'rank':<5} {'top_k':<6} {'variant':<56} {'buf':>6} {'thr':>6} {'val_auc':>8} "
        f"{'2025_auc':>8} {'val_d':>9} {'2025_d':>9} {'promote':>8}"
    )
    print("-" * 228)
    for idx, row in enumerate(contract_winners.itertuples(index=False), start=1):
        print(
            f"{idx:<5} {int(row.top_k):<6} {str(row.variant):<56} "
            f"{(row.label_edge_buffer if row.label_edge_buffer is not None else float('nan')):>6.3f} "
            f"{(row.threshold if row.threshold is not None else float('nan')):>6.2f} "
            f"{(row.validation_auc if row.validation_auc is not None else float('nan')):>8.3f} "
            f"{(row.confirmation_auc if row.confirmation_auc is not None else float('nan')):>8.3f} "
            f"{(row.validation_relative_delta or 0.0)*100:>+8.2f}% "
            f"{(row.confirmation_relative_delta or 0.0)*100:>+8.2f}% "
            f"{str(bool(row.promoted)):>8}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H247: sharpen the small-book entry-alpha label contract")
    parser.add_argument("--matrix", type=str, default=str(RL_MATRIX_PATH))
    parser.add_argument("--tradability", type=str, default=str(TRADABILITY_PATH))
    parser.add_argument("--stock-dir", type=str, default=str(STOCK_DIR))
    parser.add_argument("--benchmark", type=str, default=str(BENCHMARK_PATH))
    parser.add_argument("--start-year", type=int, default=2019)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--strategy", type=str, default="full_library")
    parser.add_argument("--top-k-grid", nargs="+", type=int, default=[1, 2])
    parser.add_argument("--rebalance-every", type=int, default=5)
    parser.add_argument("--model-top-m", type=int, default=5)
    parser.add_argument("--top-m-max", type=int, default=10)
    parser.add_argument("--threshold-grid", nargs="+", default=["0.55", "0.60", "0.65", "0.70"])
    parser.add_argument("--label-edge-buffer-grid", nargs="+", default=["0.00", "0.01", "0.02", "0.03"])
    parser.add_argument("--round-trip-cost", type=float, default=0.003)
    parser.add_argument("--required-holding-age", type=int, default=3)
    parser.add_argument("--initial-notional-vnd", type=float, default=100_000_000.0)
    parser.add_argument("--candidate-panel-cache", type=str, default="")
    parser.add_argument("--base-labels-cache", type=str, default="")
    parser.add_argument("--top-results", type=int, default=8)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    top_k_grid = sorted(set(int(value) for value in args.top_k_grid))
    unsupported = [value for value in top_k_grid if value not in DEFAULT_SMALL_BOOK_CONTRACTS]
    if unsupported:
        raise ValueError(
            f"H247 only carries forward top_k anchors in {sorted(DEFAULT_SMALL_BOOK_CONTRACTS)}; got {unsupported}"
        )

    thresholds = _parse_float_grid(list(args.threshold_grid))
    label_edge_buffers = _parse_float_grid(list(args.label_edge_buffer_grid))

    candidate_panel_cache = (
        Path(args.candidate_panel_cache)
        if str(args.candidate_panel_cache).strip()
        else ENTRY_ALPHA_OUT_DIR / f"h247_candidate_panel_{int(args.start_year)}_{int(args.end_year)}.parquet"
    )
    base_labels_cache = (
        Path(args.base_labels_cache)
        if str(args.base_labels_cache).strip()
        else ENTRY_ALPHA_OUT_DIR / f"h247_base_labels_{int(args.start_year)}_{int(args.end_year)}.parquet"
    )

    inputs, candidate_panel, base_labels = load_or_build_entry_artifacts(
        candidate_panel_path=candidate_panel_cache,
        labels_path=base_labels_cache,
        matrix_path=Path(args.matrix),
        tradability_path=Path(args.tradability),
        stock_dir=Path(args.stock_dir),
        benchmark_path=Path(args.benchmark),
        start_year=int(args.start_year),
        end_year=int(args.end_year),
        strategy_name=str(args.strategy),
        top_m_max=int(args.top_m_max),
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

    signal_dates = sorted(pd.to_datetime(inputs.matrix["time"]).drop_duplicates())
    scenario_panels: dict[float, pd.DataFrame] = {}
    scenario_stats: list[dict[str, object]] = []
    for label_edge_buffer in label_edge_buffers:
        labels = (
            base_labels.copy()
            if float(label_edge_buffer) == 0.0
            else build_entry_labels(
                candidate_panel,
                price_panel=inputs.price_panel,
                benchmark_open=inputs.benchmark_open,
                horizon_signal_steps=int(args.rebalance_every),
                signal_dates=signal_dates,
                round_trip_cost=float(args.round_trip_cost),
                label_edge_buffer=float(label_edge_buffer),
            )
        )
        labels["time"] = pd.to_datetime(labels["time"])
        panel = prepare_entry_research_panel(candidate_panel, labels)
        scenario_panels[float(label_edge_buffer)] = panel
        scenario_stats.append(
            {
                "label_edge_buffer": float(label_edge_buffer),
                **_label_stats(labels),
            }
        )

    market_dates = pd.DatetimeIndex(pd.to_datetime(inputs.market_inputs.dates))
    market_tickers = list(inputs.market_inputs.tickers)

    all_results: list[pd.DataFrame] = []
    winner_rows: list[dict[str, object]] = []
    winner_daily_outputs: list[pd.DataFrame] = []
    best_non_baseline_by_top_k: dict[int, dict[str, object]] = {}

    for top_k in top_k_grid:
        contract = DEFAULT_SMALL_BOOK_CONTRACTS[int(top_k)]
        baseline_variant = f"topk{int(top_k)}__h245_anchor"
        baseline_matrix = build_entry_allowed_matrix(
            candidate_panel,
            dates=market_dates,
            tickers=market_tickers,
            top_m=int(contract["top_m"]),
            min_selection_score=float(contract["min_selection_score"]),
            min_score_gap=None if contract["min_score_gap"] is None else float(contract["min_score_gap"]),
            require_buyable=True,
        )
        baseline_result = run_entry_backtest(
            inputs,
            entry_allowed_matrix=baseline_matrix,
            round_trip_cost=float(args.round_trip_cost),
            required_holding_age=int(args.required_holding_age),
            initial_notional_vnd=float(args.initial_notional_vnd),
            top_k=int(top_k),
            rebalance_every=int(args.rebalance_every),
        )
        rows = [
            backtest_row_from_result(
                variant=baseline_variant,
                family="baseline",
                result=baseline_result,
                extra={
                    "top_k": int(top_k),
                    "top_m": int(contract["top_m"]),
                    "anchor_min_selection_score": float(contract["min_selection_score"]),
                    "anchor_min_score_gap": None
                    if contract["min_score_gap"] is None
                    else float(contract["min_score_gap"]),
                    "label_edge_buffer": None,
                    "model_name": None,
                    "score_column": None,
                    "threshold": None,
                    "validation_auc": None,
                    "confirmation_auc": None,
                    "promoted_label_only": False,
                },
            )
        ]
        daily_outputs: dict[str, pd.DataFrame] = {
            baseline_variant: baseline_result.daily.copy(),
        }

        for label_edge_buffer in label_edge_buffers:
            panel = scenario_panels[float(label_edge_buffer)]
            buffer_stats = next(
                item for item in scenario_stats if float(item["label_edge_buffer"]) == float(label_edge_buffer)
            )
            model_fits = [fit_entry_model(panel, spec=spec) for spec in default_entry_model_specs(panel)]
            for fit in model_fits:
                score_column = f"entry_prob__{fit.spec.name}"
                for threshold in thresholds:
                    variant = (
                        f"topk{int(top_k)}__{fit.spec.name}"
                        f"__label_{_tokenize_float(float(label_edge_buffer))}"
                        f"__threshold_{_tokenize_float(float(threshold))}"
                    )
                    entry_allowed_matrix = build_entry_allowed_matrix_from_score(
                        fit.scored_dataset,
                        dates=market_dates,
                        tickers=market_tickers,
                        score_column=score_column,
                        top_m=int(args.model_top_m),
                        min_score=float(threshold),
                        require_buyable=True,
                    )
                    result = run_entry_backtest(
                        inputs,
                        entry_allowed_matrix=entry_allowed_matrix,
                        round_trip_cost=float(args.round_trip_cost),
                        required_holding_age=int(args.required_holding_age),
                        initial_notional_vnd=float(args.initial_notional_vnd),
                        top_k=int(top_k),
                        rebalance_every=int(args.rebalance_every),
                    )
                    rows.append(
                        backtest_row_from_result(
                            variant=variant,
                            family="label_sharpen_model",
                            result=result,
                            extra={
                                **fit.summary_row,
                                "top_k": int(top_k),
                                "top_m": int(args.model_top_m),
                                "anchor_min_selection_score": float(contract["min_selection_score"]),
                                "anchor_min_score_gap": None
                                if contract["min_score_gap"] is None
                                else float(contract["min_score_gap"]),
                                "label_edge_buffer": float(label_edge_buffer),
                                "model_name": fit.spec.name,
                                "score_column": score_column,
                                "threshold": float(threshold),
                                "overall_positive_rate": buffer_stats["overall_positive_rate"],
                                "dev_positive_rate": buffer_stats["dev_positive_rate"],
                                "validation_positive_rate": buffer_stats["validation_positive_rate"],
                                "confirmation_positive_rate": buffer_stats["confirmation_positive_rate"],
                            },
                        )
                    )
                    daily_outputs[variant] = result.daily.copy()

        results = _sort_results(add_baseline_deltas(pd.DataFrame(rows), baseline_variant=baseline_variant))
        contract_rows = results.loc[results["variant"] != baseline_variant].copy().reset_index(drop=True)
        winner_row = contract_rows.iloc[0].to_dict()
        winner_row["baseline_variant"] = baseline_variant
        winner_row["baseline_validation_relative_total_return"] = results.loc[
            results["variant"] == baseline_variant, "validation_relative_total_return"
        ].iloc[0]
        winner_row["baseline_confirmation_relative_total_return"] = results.loc[
            results["variant"] == baseline_variant, "confirmation_relative_total_return"
        ].iloc[0]

        all_results.append(results)
        winner_rows.append(winner_row)
        best_non_baseline_by_top_k[int(top_k)] = winner_row
        winner_daily_outputs.append(
            daily_outputs[str(winner_row["variant"])].copy().assign(
                top_k=int(top_k),
                variant=str(winner_row["variant"]),
            )
        )

    results = pd.concat([frame for frame in all_results if not frame.empty], ignore_index=True)
    contract_winners = _sort_results(pd.DataFrame(winner_rows))
    _print_table(contract_winners.head(max(int(args.top_results), 1)))

    sharpened_results = results.loc[pd.to_numeric(results["label_edge_buffer"], errors="coerce") > 0.0].copy()
    promoted_mask = pd.Series(sharpened_results["promoted"], dtype="boolean").fillna(False).to_numpy(dtype=bool)
    promoted_sharpened = sharpened_results.loc[promoted_mask].copy()
    best_sharpened = _sort_results(sharpened_results).iloc[0].to_dict() if not sharpened_results.empty else None

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    ENTRY_ALPHA_OUT_DIR.mkdir(parents=True, exist_ok=True)
    results_path = ENTRY_ALPHA_OUT_DIR / f"{ts}_h247_entry_alpha_label_sharpen_audit_results.parquet"
    winners_path = ENTRY_ALPHA_OUT_DIR / f"{ts}_h247_entry_alpha_label_sharpen_audit_contract_winners.parquet"
    best_daily_path = ENTRY_ALPHA_OUT_DIR / f"{ts}_h247_entry_alpha_label_sharpen_audit_selected_daily.parquet"
    label_stats_path = ENTRY_ALPHA_OUT_DIR / f"{ts}_h247_entry_alpha_label_sharpen_audit_label_stats.parquet"
    results.to_parquet(results_path, index=False)
    contract_winners.to_parquet(winners_path, index=False)
    pd.concat(winner_daily_outputs, ignore_index=True).to_parquet(best_daily_path, index=False)
    pd.DataFrame(scenario_stats).to_parquet(label_stats_path, index=False)

    summary = {
        "protocol": DEFAULT_PROTOCOL.describe(),
        "effective_date_range": {
            "start_year": int(args.start_year),
            "end_year": int(args.end_year),
            "dev_years_present": sorted(
                candidate_panel.loc[candidate_panel["time"].dt.year <= DEFAULT_PROTOCOL.dev_end_year, "time"]
                .dt.year.dropna()
                .unique()
                .tolist()
            ),
            "validation_years_present": sorted(
                candidate_panel.loc[
                    candidate_panel["time"].dt.year.between(
                        DEFAULT_PROTOCOL.validation_start_year,
                        DEFAULT_PROTOCOL.validation_end_year,
                    ),
                    "time",
                ]
                .dt.year.dropna()
                .unique()
                .tolist()
            ),
            "confirmation_years_present": sorted(
                candidate_panel.loc[candidate_panel["time"].dt.year == DEFAULT_PROTOCOL.confirmation_year, "time"]
                .dt.year.dropna()
                .unique()
                .tolist()
            ),
        },
        "contracts": {
            int(key): value for key, value in DEFAULT_SMALL_BOOK_CONTRACTS.items() if int(key) in top_k_grid
        },
        "label_stats": scenario_stats,
        "contract_winners": contract_winners.to_dict("records"),
        "best_sharpened_candidate": best_sharpened,
        "promoted_sharpened_candidates": promoted_sharpened[
            [
                "variant",
                "top_k",
                "label_edge_buffer",
                "model_name",
                "threshold",
                "validation_auc",
                "confirmation_auc",
                "validation_relative_delta",
                "confirmation_relative_delta",
            ]
        ].to_dict("records"),
        "verdict_hint": {
            "sharpened_pass_count": int(len(promoted_sharpened)),
            "any_sharpened_promoted": bool(not promoted_sharpened.empty),
        },
    }
    write_run_summary(
        ts=ts,
        mode="entry_alpha_label_sharpen_audit",
        name="h247_entry_alpha_label_sharpen_audit",
        summary=summary,
        artifacts={
            "results": str(results_path),
            "contract_winners": str(winners_path),
            "selected_daily": str(best_daily_path),
            "label_stats": str(label_stats_path),
            "candidate_panel_cache": str(candidate_panel_cache),
            "base_labels_cache": str(base_labels_cache),
        },
        metadata={
            "matrix": str(args.matrix),
            "tradability": str(args.tradability),
            "stock_dir": str(args.stock_dir),
            "benchmark": str(args.benchmark),
            "start_year": int(args.start_year),
            "end_year": int(args.end_year),
            "strategy": str(args.strategy),
            "top_k_grid": top_k_grid,
            "rebalance_every": int(args.rebalance_every),
            "model_top_m": int(args.model_top_m),
            "top_m_max": int(args.top_m_max),
            "threshold_grid": thresholds,
            "label_edge_buffer_grid": label_edge_buffers,
            "round_trip_cost": float(args.round_trip_cost),
            "required_holding_age": int(args.required_holding_age),
            "initial_notional_vnd": float(args.initial_notional_vnd),
        },
    )


if __name__ == "__main__":
    main()
