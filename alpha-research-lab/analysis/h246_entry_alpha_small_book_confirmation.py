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
from src.entry_alpha_research import (
    ENTRY_ALPHA_OUT_DIR,
    add_baseline_deltas,
    backtest_row_from_result,
    build_entry_allowed_matrix_from_mask,
    build_entry_row_mask,
    build_single_family_screen_frame,
    build_small_book_confirmation_overlay_frame,
    build_small_book_threshold_series,
    load_or_build_entry_artifacts,
    prepare_entry_research_panel,
    run_entry_backtest,
)
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


def _coerce_numeric_columns(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    work = frame.copy()
    for column in columns:
        if column in work.columns:
            work[column] = pd.to_numeric(work[column], errors="coerce")
    return work


def _single_flag_threshold_series(
    panel: pd.DataFrame,
    *,
    flag_column: str,
    base_threshold: float,
    bonus: float,
    penalty: float,
) -> pd.Series:
    flag = panel[flag_column].fillna(False).astype(bool)
    threshold = np.where(
        flag.to_numpy(dtype=bool),
        float(base_threshold) - float(bonus),
        float(base_threshold) + float(penalty),
    )
    return pd.Series(np.asarray(threshold, dtype=float), index=panel.index).clip(lower=0.0)


def _print_table(contract_winners: pd.DataFrame) -> None:
    print("\n" + "=" * 220)
    print("H246: ENTRY ALPHA SMALL-BOOK CONFIRMATION OVERLAYS")
    print("=" * 220)
    print(
        f"{'rank':<5} {'top_k':<6} {'variant':<42} {'val_rel':>10} {'2025_rel':>10} {'2026+_rel':>10} "
        f"{'val_d':>9} {'2025_d':>9} {'2026+_d':>9} {'honest':>8}"
    )
    print("-" * 220)
    for idx, row in enumerate(contract_winners.itertuples(index=False), start=1):
        print(
            f"{idx:<5} {int(row.top_k):<6} {str(row.variant):<42} "
            f"{(row.validation_relative_total_return or 0.0)*100:>+9.2f}% "
            f"{(row.confirmation_relative_total_return or 0.0)*100:>+9.2f}% "
            f"{(row.forward_relative_total_return or 0.0)*100:>+9.2f}% "
            f"{(row.validation_relative_delta or 0.0)*100:>+8.2f}% "
            f"{(row.confirmation_relative_delta or 0.0)*100:>+8.2f}% "
            f"{(row.forward_relative_delta or 0.0)*100:>+8.2f}% "
            f"{str(bool(row.honest_promoted)):>8}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H246: small-book confirmation/calibration overlays for entry alpha")
    parser.add_argument("--matrix", type=str, default=str(RL_MATRIX_PATH))
    parser.add_argument("--tradability", type=str, default=str(TRADABILITY_PATH))
    parser.add_argument("--stock-dir", type=str, default=str(STOCK_DIR))
    parser.add_argument("--benchmark", type=str, default=str(BENCHMARK_PATH))
    parser.add_argument("--candidate-panel", type=str, default=str(data_path("features/entry_alpha/candidate_panel_daily.parquet")))
    parser.add_argument("--labels", type=str, default=str(data_path("features/entry_alpha/entry_labels_cycle5.parquet")))
    parser.add_argument("--start-year", type=int, default=2019)
    parser.add_argument("--end-year", type=int, default=2026)
    parser.add_argument("--strategy", type=str, default="full_library")
    parser.add_argument("--top-k-grid", nargs="+", type=int, default=[1, 2])
    parser.add_argument("--rebalance-every", type=int, default=5)
    parser.add_argument("--round-trip-cost", type=float, default=0.003)
    parser.add_argument("--required-holding-age", type=int, default=3)
    parser.add_argument("--initial-notional-vnd", type=float, default=100_000_000.0)
    parser.add_argument("--supportive-bonus", type=float, default=0.02)
    parser.add_argument("--consensus-bonus", type=float, default=0.05)
    parser.add_argument("--no-confirm-penalty", type=float, default=0.03)
    parser.add_argument("--single-flag-bonus", type=float, default=0.04)
    parser.add_argument("--single-flag-penalty", type=float, default=0.02)
    parser.add_argument("--near-cutoff-buffer", type=float, default=0.04)
    parser.add_argument("--forward-rel-delta-floor", type=float, default=-0.05)
    parser.add_argument("--forward-ir-delta-floor", type=float, default=-0.05)
    parser.add_argument("--top-results", type=int, default=8)
    return parser.parse_args()


def _evaluate_contract(
    *,
    inputs,
    panel: pd.DataFrame,
    top_k: int,
    top_m: int,
    min_selection_score: float,
    min_score_gap: float | None,
    market_dates: pd.DatetimeIndex,
    market_tickers: list[str],
    round_trip_cost: float,
    required_holding_age: int,
    initial_notional_vnd: float,
    rebalance_every: int,
    supportive_bonus: float,
    consensus_bonus: float,
    no_confirm_penalty: float,
    single_flag_bonus: float,
    single_flag_penalty: float,
    near_cutoff_buffer: float,
    forward_rel_delta_floor: float,
    forward_ir_delta_floor: float,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame], dict[str, object]]:
    score_values = pd.to_numeric(panel["selection_score"], errors="coerce")
    base_mask = build_entry_row_mask(
        panel,
        top_m=int(top_m),
        min_selection_score=float(min_selection_score),
        min_score_gap=None if min_score_gap is None else float(min_score_gap),
        require_buyable=True,
    )
    rank_gap_mask = build_entry_row_mask(
        panel,
        top_m=int(top_m),
        min_selection_score=None,
        min_score_gap=None if min_score_gap is None else float(min_score_gap),
        require_buyable=True,
    )

    overlay_masks: dict[str, pd.Series] = {
        "base_sparse_contract": base_mask,
        "soft_consensus_threshold": rank_gap_mask
        & (score_values >= build_small_book_threshold_series(
            panel,
            base_threshold=float(min_selection_score),
            confirm_count_column="confirm_count",
            supportive_bonus=float(supportive_bonus),
            consensus_bonus=float(consensus_bonus),
            no_confirm_penalty=float(no_confirm_penalty),
        )),
        "soft_reversal_threshold": rank_gap_mask
        & (score_values >= _single_flag_threshold_series(
            panel,
            flag_column="confirm_reversal",
            base_threshold=float(min_selection_score),
            bonus=float(single_flag_bonus),
            penalty=float(single_flag_penalty),
        )),
        "soft_gap_absorb_threshold": rank_gap_mask
        & (score_values >= _single_flag_threshold_series(
            panel,
            flag_column="confirm_gap_absorb",
            base_threshold=float(min_selection_score),
            bonus=float(single_flag_bonus),
            penalty=float(single_flag_penalty),
        )),
        "soft_uncrowded_threshold": rank_gap_mask
        & (score_values >= _single_flag_threshold_series(
            panel,
            flag_column="confirm_uncrowded",
            base_threshold=float(min_selection_score),
            bonus=float(single_flag_bonus),
            penalty=float(single_flag_penalty),
        )),
        "near_cutoff_no_confirm_veto": base_mask
        & ~(
            (score_values < float(min_selection_score) + float(near_cutoff_buffer))
            & (pd.to_numeric(panel["confirm_count"], errors="coerce").fillna(0.0) <= 0.0)
        ),
        "soft_consensus_plus_veto": rank_gap_mask
        & (score_values >= build_small_book_threshold_series(
            panel,
            base_threshold=float(min_selection_score),
            confirm_count_column="confirm_count",
            supportive_bonus=float(supportive_bonus),
            consensus_bonus=float(consensus_bonus),
            no_confirm_penalty=float(no_confirm_penalty),
        ))
        & ~(
            (score_values < float(min_selection_score) + float(near_cutoff_buffer))
            & (pd.to_numeric(panel["confirm_count"], errors="coerce").fillna(0.0) <= 0.0)
        ),
    }

    rows: list[dict[str, object]] = []
    daily_outputs: dict[str, pd.DataFrame] = {}
    baseline_variant = f"topk{int(top_k)}__base_sparse_contract"
    for short_name, mask in overlay_masks.items():
        variant = f"topk{int(top_k)}__{short_name}"
        entry_allowed_matrix = build_entry_allowed_matrix_from_mask(
            panel,
            dates=market_dates,
            tickers=market_tickers,
            mask=mask,
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
                family="small_book_overlay",
                result=result,
                extra={
                    "top_k": int(top_k),
                    "top_m": int(top_m),
                    "min_selection_score": float(min_selection_score),
                    "min_score_gap": None if min_score_gap is None else float(min_score_gap),
                    "overlay_name": short_name,
                    "allowed_rows": int(pd.Series(mask, index=panel.index).fillna(False).sum()),
                },
            )
        )
        daily_outputs[variant] = result.daily.copy()

    results = add_baseline_deltas(pd.DataFrame(rows), baseline_variant=baseline_variant)
    baseline_row = results.loc[results["variant"] == baseline_variant].iloc[0].to_dict()
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
    contract_results = _coerce_numeric_columns(
        results.loc[results["variant"] != baseline_variant].copy(),
        columns=[
            "validation_relative_total_return",
            "validation_information_ratio_annualized",
            "confirmation_relative_total_return",
            "forward_relative_total_return",
            "validation_relative_delta",
            "confirmation_relative_delta",
            "forward_relative_delta",
        ],
    ).sort_values(
        by=[
            "validation_relative_total_return",
            "validation_information_ratio_annualized",
            "confirmation_relative_total_return",
            "forward_relative_total_return",
            "variant",
        ],
        ascending=[False, False, False, False, True],
        ignore_index=True,
    )
    selected_row = contract_results.iloc[0].to_dict()
    selected_row["baseline_variant"] = baseline_variant
    return results, daily_outputs, selected_row


def main() -> None:
    args = parse_args()
    top_k_grid = sorted(set(int(value) for value in args.top_k_grid))
    unsupported = [value for value in top_k_grid if value not in DEFAULT_SMALL_BOOK_CONTRACTS]
    if unsupported:
        raise ValueError(f"H246 only has calibrated defaults for top_k in {sorted(DEFAULT_SMALL_BOOK_CONTRACTS)}; got {unsupported}")

    inputs, candidate_panel, labels = load_or_build_entry_artifacts(
        candidate_panel_path=Path(args.candidate_panel),
        labels_path=Path(args.labels),
        matrix_path=Path(args.matrix),
        tradability_path=Path(args.tradability),
        stock_dir=Path(args.stock_dir),
        benchmark_path=Path(args.benchmark),
        start_year=int(args.start_year),
        end_year=int(args.end_year),
        strategy_name=str(args.strategy),
        top_m_max=max(int(DEFAULT_SMALL_BOOK_CONTRACTS[value]["top_m"]) for value in top_k_grid),
        top_k=max(top_k_grid),
        rebalance_every=int(args.rebalance_every),
        round_trip_cost=float(args.round_trip_cost),
        required_holding_age=int(args.required_holding_age),
        initial_notional_vnd=float(args.initial_notional_vnd),
    )
    panel = prepare_entry_research_panel(candidate_panel, labels)
    panel, _ = build_single_family_screen_frame(panel)
    panel = build_small_book_confirmation_overlay_frame(panel)

    market_dates = pd.DatetimeIndex(pd.to_datetime(inputs.market_inputs.dates))
    market_tickers = list(inputs.market_inputs.tickers)
    all_results: list[pd.DataFrame] = []
    winner_rows: list[dict[str, object]] = []
    winner_daily_outputs: dict[int, pd.DataFrame] = {}

    for top_k in top_k_grid:
        contract = DEFAULT_SMALL_BOOK_CONTRACTS[int(top_k)]
        results, daily_outputs, winner_row = _evaluate_contract(
            inputs=inputs,
            panel=panel,
            top_k=int(top_k),
            top_m=int(contract["top_m"]),
            min_selection_score=float(contract["min_selection_score"]),
            min_score_gap=None if contract["min_score_gap"] is None else float(contract["min_score_gap"]),
            market_dates=market_dates,
            market_tickers=market_tickers,
            round_trip_cost=float(args.round_trip_cost),
            required_holding_age=int(args.required_holding_age),
            initial_notional_vnd=float(args.initial_notional_vnd),
            rebalance_every=int(args.rebalance_every),
            supportive_bonus=float(args.supportive_bonus),
            consensus_bonus=float(args.consensus_bonus),
            no_confirm_penalty=float(args.no_confirm_penalty),
            single_flag_bonus=float(args.single_flag_bonus),
            single_flag_penalty=float(args.single_flag_penalty),
            near_cutoff_buffer=float(args.near_cutoff_buffer),
            forward_rel_delta_floor=float(args.forward_rel_delta_floor),
            forward_ir_delta_floor=float(args.forward_ir_delta_floor),
        )
        all_results.append(results)
        winner_rows.append(winner_row)
        winner_daily_outputs[int(top_k)] = daily_outputs[str(winner_row["variant"])].copy()

    results = pd.concat(all_results, ignore_index=True)
    contract_winners = _coerce_numeric_columns(
        pd.DataFrame(winner_rows),
        columns=[
            "top_k",
            "validation_relative_total_return",
            "validation_information_ratio_annualized",
            "confirmation_relative_total_return",
            "forward_relative_total_return",
            "validation_relative_delta",
            "confirmation_relative_delta",
            "forward_relative_delta",
        ],
    ).sort_values(
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
    _print_table(contract_winners.head(max(int(args.top_results), 1)))

    selected_contract = contract_winners.iloc[0].to_dict()
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    ENTRY_ALPHA_OUT_DIR.mkdir(parents=True, exist_ok=True)
    results_path = ENTRY_ALPHA_OUT_DIR / f"{ts}_h246_entry_alpha_small_book_confirmation_results.parquet"
    winners_path = ENTRY_ALPHA_OUT_DIR / f"{ts}_h246_entry_alpha_small_book_confirmation_contract_winners.parquet"
    selected_daily_path = ENTRY_ALPHA_OUT_DIR / f"{ts}_h246_entry_alpha_small_book_confirmation_selected_daily.parquet"
    panel_path = ENTRY_ALPHA_OUT_DIR / f"{ts}_h246_entry_alpha_small_book_confirmation_panel.parquet"
    results.to_parquet(results_path, index=False)
    contract_winners.to_parquet(winners_path, index=False)
    winner_daily_outputs[int(selected_contract["top_k"])].to_parquet(selected_daily_path, index=False)
    panel.to_parquet(panel_path, index=False)

    summary = {
        "contract_winners": contract_winners.to_dict("records"),
        "validation_selected_overlay": selected_contract,
        "contracts": {
            int(key): value for key, value in DEFAULT_SMALL_BOOK_CONTRACTS.items() if int(key) in top_k_grid
        },
    }
    write_run_summary(
        ts=ts,
        mode="entry_alpha_small_book_confirmation",
        name="h246_entry_alpha_small_book_confirmation",
        summary=summary,
        artifacts={
            "results": str(results_path),
            "contract_winners": str(winners_path),
            "selected_daily": str(selected_daily_path),
            "panel": str(panel_path),
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
            "round_trip_cost": float(args.round_trip_cost),
            "required_holding_age": int(args.required_holding_age),
            "initial_notional_vnd": float(args.initial_notional_vnd),
            "supportive_bonus": float(args.supportive_bonus),
            "consensus_bonus": float(args.consensus_bonus),
            "no_confirm_penalty": float(args.no_confirm_penalty),
            "single_flag_bonus": float(args.single_flag_bonus),
            "single_flag_penalty": float(args.single_flag_penalty),
            "near_cutoff_buffer": float(args.near_cutoff_buffer),
            "forward_rel_delta_floor": float(args.forward_rel_delta_floor),
            "forward_ir_delta_floor": float(args.forward_ir_delta_floor),
        },
    )


if __name__ == "__main__":
    main()
