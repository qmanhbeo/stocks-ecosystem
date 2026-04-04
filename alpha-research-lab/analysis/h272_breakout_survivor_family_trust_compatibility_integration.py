"""
H272: family-local breakout-survivor trust compatibility integration.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
from path_utils import data_path

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = ROOT.parent
SHARED_MARKET_RULES_ROOT = WORKSPACE_ROOT / "shared-market-rules"
if str(SHARED_MARKET_RULES_ROOT) not in sys.path:
    sys.path.insert(0, str(SHARED_MARKET_RULES_ROOT))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.additive_selector_research import load_summary_payload, resolve_summary_artifact
from src.entry_alpha_research import (
    ENTRY_ALPHA_OUT_DIR,
    add_baseline_deltas,
    assign_entry_thesis_family,
    backtest_row_from_result,
    build_entry_allowed_matrix_from_mask,
    build_entry_row_mask,
    load_or_build_entry_artifacts,
    prepare_entry_research_panel,
    run_entry_backtest,
)
from src.research_protocol import ResearchProtocol
from src.run_summary import write_run_summary


RL_MATRIX_PATH = data_path("features/xs_rl_signal_matrix.parquet")
TRADABILITY_PATH = data_path("features/execution/tradability_daily.parquet")
STOCK_DIR = data_path("stock")
BENCHMARK_PATH = STOCK_DIR / "gia_lich_su_VNINDEX_1D.parquet"
H271_SUMMARY_PATH = ROOT / "artifacts/run_summaries/latest_entry_alpha_breakout_survivor_gate_integration.json"
H270_SUMMARY_PATH = ROOT / "artifacts/run_summaries/latest_entry_alpha_breakout_survivor_label_rewrite_audit.json"
BRANCH_CACHE_DIR = ROOT / "artifacts/entry_alpha"
H266_CANDIDATE_CACHE_PATH = BRANCH_CACHE_DIR / "h266_candidate_panel_2023_2025.parquet"
H266_LABEL_CACHE_PATH = BRANCH_CACHE_DIR / "h266_base_labels_2023_2025.parquet"

INTRADAY_RESTART_PROTOCOL = ResearchProtocol(
    dev_start_year=2023,
    dev_end_year=2023,
    validation_start_year=2024,
    validation_end_year=2024,
    confirmation_year=2025,
    forward_start_year=2026,
)
BREAKOUT_FAMILY = "breakout_followthrough"
BASELINE_VARIANT = "carried_sparse_contract"
CARRIED_SPARSE_CONTRACT = {
    "top_m": 5,
    "min_selection_score": 0.65,
    "min_score_gap": 0.03,
}
MIN_TOTAL_ALLOWED_ROWS = 150
MIN_VALIDATION_ALLOWED_ROWS = 75
MIN_CONFIRMATION_ALLOWED_ROWS = 70
MAX_CONFIRMATION_CASH_WEIGHT_INCREASE = 0.15


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H272: family-local breakout-survivor trust compatibility integration")
    parser.add_argument("--matrix", type=str, default=str(RL_MATRIX_PATH))
    parser.add_argument("--tradability", type=str, default=str(TRADABILITY_PATH))
    parser.add_argument("--stock-dir", type=str, default=str(STOCK_DIR))
    parser.add_argument("--benchmark", type=str, default=str(BENCHMARK_PATH))
    parser.add_argument("--h271-summary", type=str, default=str(H271_SUMMARY_PATH))
    parser.add_argument("--h270-summary", type=str, default=str(H270_SUMMARY_PATH))
    parser.add_argument("--start-year", type=int, default=2023)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--strategy", type=str, default="full_library")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--rebalance-every", type=int, default=5)
    parser.add_argument("--top-m-max", type=int, default=20)
    parser.add_argument("--round-trip-cost", type=float, default=0.003)
    parser.add_argument("--required-holding-age", type=int, default=3)
    parser.add_argument("--initial-notional-vnd", type=float, default=100_000_000.0)
    parser.add_argument("--candidate-cache", type=str, default=str(H266_CANDIDATE_CACHE_PATH))
    parser.add_argument("--labels-cache", type=str, default=str(H266_LABEL_CACHE_PATH))
    return parser.parse_args()


def _coerce_float(row: pd.Series | dict[str, object], column: str) -> float | None:
    value = pd.to_numeric(row.get(column), errors="coerce")
    return None if pd.isna(value) else float(value)


def _sort_results(results: pd.DataFrame) -> pd.DataFrame:
    if results.empty:
        return results.copy()
    work = results.copy()
    for column in [
        "validation_relative_delta",
        "validation_ir_delta",
        "confirmation_relative_delta",
        "confirmation_ir_delta",
        "overall_relative_delta",
        "overall_ir_delta",
        "allowed_rows",
        "confirmation_allowed_rows",
        "confirmation_avg_cash_weight",
        "variant",
    ]:
        if column in work.columns and column != "variant":
            work[column] = pd.to_numeric(work[column], errors="coerce")
    return work.sort_values(
        by=[
            "validation_relative_delta",
            "validation_ir_delta",
            "confirmation_relative_delta",
            "confirmation_ir_delta",
            "overall_relative_delta",
            "overall_ir_delta",
            "allowed_rows",
            "confirmation_allowed_rows",
            "confirmation_avg_cash_weight",
            "variant",
        ],
        ascending=[False, False, False, False, False, False, False, False, True, True],
        ignore_index=True,
    )


def _mask_summary(
    mask: pd.Series,
    *,
    baseline_mask: pd.Series,
    breakout_mask: pd.Series,
    observed_breakout_mask: pd.Series,
    panel: pd.DataFrame,
) -> dict[str, object]:
    summary: dict[str, object] = {
        "allowed_rows": int(mask.sum()),
        "allowed_share_vs_baseline": float(mask.sum() / baseline_mask.sum()) if int(baseline_mask.sum()) > 0 else None,
        "breakout_allowed_rows": int((mask & breakout_mask).sum()),
        "breakout_observed_allowed_rows": int((mask & observed_breakout_mask).sum()),
        "breakout_blocked_rows": int((baseline_mask & breakout_mask & ~mask).sum()),
        "breakout_observed_blocked_rows": int((baseline_mask & observed_breakout_mask & ~mask).sum()),
        "breakout_missing_rows_in_baseline": int((baseline_mask & breakout_mask & ~observed_breakout_mask).sum()),
    }
    for phase in ("dev", "validation", "confirmation"):
        phase_mask = panel["research_phase"].astype(str).eq(phase)
        summary[f"{phase}_allowed_rows"] = int((mask & phase_mask).sum())
        summary[f"{phase}_breakout_allowed_rows"] = int((mask & breakout_mask & phase_mask).sum())
        summary[f"{phase}_breakout_observed_allowed_rows"] = int((mask & observed_breakout_mask & phase_mask).sum())
    return summary


def _print_table(results: pd.DataFrame) -> None:
    top = results.head(max(len(results), 1))
    print("\n" + "=" * 224)
    print("H272: BREAKOUT SURVIVOR FAMILY TRUST COMPATIBILITY INTEGRATION")
    print("=" * 224)
    print(
        f"{'rank':<5} {'variant':<44} {'allowed':>8} {'brk_obs':>8} {'val_d':>10} {'2025_d':>10} "
        f"{'overall_d':>10} {'val_ir_d':>9} {'2025_ir_d':>10} {'cash_2025':>10}"
    )
    print("-" * 224)
    for idx, row in enumerate(top.itertuples(index=False), start=1):
        print(
            f"{idx:<5} {str(row.variant):<44} "
            f"{int(row.allowed_rows):>8d} "
            f"{int(row.breakout_observed_allowed_rows):>8d} "
            f"{(row.validation_relative_delta or 0.0)*100:>+9.2f}% "
            f"{(row.confirmation_relative_delta or 0.0)*100:>+9.2f}% "
            f"{(row.overall_relative_delta or 0.0)*100:>+9.2f}% "
            f"{row.validation_ir_delta if row.validation_ir_delta is not None else float('nan'):>+8.2f} "
            f"{row.confirmation_ir_delta if row.confirmation_ir_delta is not None else float('nan'):>+9.2f} "
            f"{(row.confirmation_avg_cash_weight or 0.0):>9.3f}"
        )


def main() -> None:
    args = parse_args()
    h271_summary_path = Path(args.h271_summary)
    h271_payload = load_summary_payload(h271_summary_path)
    if not bool(h271_payload.get("summary", {}).get("advance_to_h272", False)):
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        write_run_summary(
            ts=ts,
            mode="entry_alpha_breakout_survivor_family_trust_compatibility_integration",
            name="h272_breakout_survivor_family_trust_compatibility_integration",
            summary={
                "protocol": INTRADAY_RESTART_PROTOCOL.describe(),
                "skipped": True,
                "reason": "H271 did not clear the breakout-survivor gate integration",
            },
            artifacts={},
            metadata={"protocol": INTRADAY_RESTART_PROTOCOL.describe()},
        )
        return

    best_gate = dict(h271_payload.get("summary", {}).get("best_gate_variant", {}) or {})
    score_column = str(best_gate.get("score_column", "")).strip()
    threshold = _coerce_float(best_gate, "threshold")
    if not score_column or threshold is None:
        raise ValueError("H272 requires the H271 winner score and threshold")

    h270_summary_text = str(h271_payload.get("metadata", {}).get("h270_summary", "")).strip()
    h270_summary_path = Path(h270_summary_text) if h270_summary_text else Path(args.h270_summary)
    h270_payload = load_summary_payload(h270_summary_path)
    score_panel = pd.read_parquet(resolve_summary_artifact(h270_summary_path, "scored_panel"))
    if score_column not in score_panel.columns:
        raise ValueError(f"H272 score column missing from H270 scored panel: {score_column}")

    inputs, candidate_panel, labels = load_or_build_entry_artifacts(
        matrix_path=Path(args.matrix),
        tradability_path=Path(args.tradability),
        stock_dir=Path(args.stock_dir),
        benchmark_path=Path(args.benchmark),
        start_year=int(args.start_year),
        end_year=int(args.end_year),
        strategy_name=str(args.strategy),
        top_m_max=int(args.top_m_max),
        top_k=int(args.top_k),
        rebalance_every=int(args.rebalance_every),
        round_trip_cost=float(args.round_trip_cost),
        required_holding_age=int(args.required_holding_age),
        initial_notional_vnd=float(args.initial_notional_vnd),
        candidate_panel_path=Path(args.candidate_cache),
        labels_path=Path(args.labels_cache),
    )
    panel = prepare_entry_research_panel(candidate_panel, labels, protocol=INTRADAY_RESTART_PROTOCOL)
    panel = assign_entry_thesis_family(panel)
    panel = panel.merge(
        score_panel[["time", "ticker", score_column]].copy(),
        on=["time", "ticker"],
        how="left",
        validate="one_to_one",
    )

    breakout_mask = panel["entry_thesis_family"].astype(str).eq(BREAKOUT_FAMILY)
    observed_breakout_mask = breakout_mask & panel[score_column].notna()
    sparse_baseline_mask = build_entry_row_mask(
        panel,
        top_m=int(CARRIED_SPARSE_CONTRACT["top_m"]),
        min_selection_score=float(CARRIED_SPARSE_CONTRACT["min_selection_score"]),
        min_score_gap=float(CARRIED_SPARSE_CONTRACT["min_score_gap"]),
        require_buyable=True,
    )
    gate_pass_mask = pd.to_numeric(panel[score_column], errors="coerce") >= float(threshold)
    variants = [
        {
            "variant": "survivor_dev_q90_keep_missing",
            "missing_policy": "keep_missing",
            "mask": sparse_baseline_mask & (~breakout_mask | ~observed_breakout_mask | gate_pass_mask),
        },
        {
            "variant": "survivor_dev_q90_block_missing",
            "missing_policy": "block_missing",
            "mask": sparse_baseline_mask & (~breakout_mask | (observed_breakout_mask & gate_pass_mask)),
        },
    ]

    market_dates = pd.DatetimeIndex(pd.to_datetime(inputs.market_inputs.dates))
    market_tickers = list(inputs.market_inputs.tickers)
    rows: list[dict[str, object]] = []
    daily_outputs: dict[str, pd.DataFrame] = {}

    compatibility_panel = panel[
        [
            "time",
            "ticker",
            "research_phase",
            "entry_thesis_family",
            "selection_score",
            "candidate_pool_rank",
            "can_buy_next_open",
            score_column,
        ]
    ].copy()
    compatibility_panel["baseline_sparse_contract"] = sparse_baseline_mask.astype(bool).to_numpy()
    compatibility_panel["breakout_observed"] = observed_breakout_mask.astype(bool).to_numpy()
    compatibility_panel["breakout_survivor_gate_pass"] = gate_pass_mask.fillna(False).astype(bool).to_numpy()

    baseline_result = run_entry_backtest(
        inputs,
        entry_allowed_matrix=build_entry_allowed_matrix_from_mask(
            panel,
            dates=market_dates,
            tickers=market_tickers,
            mask=sparse_baseline_mask,
        ),
        round_trip_cost=float(args.round_trip_cost),
        required_holding_age=int(args.required_holding_age),
        initial_notional_vnd=float(args.initial_notional_vnd),
        top_k=int(args.top_k),
        rebalance_every=int(args.rebalance_every),
    )
    rows.append(
        backtest_row_from_result(
            variant=BASELINE_VARIANT,
            family="breakout_survivor_family_trust_compatibility",
            result=baseline_result,
            protocol=INTRADAY_RESTART_PROTOCOL,
            extra={
                "score_column": score_column,
                "threshold": None,
                "missing_policy": "baseline",
                "carried_top_m": int(CARRIED_SPARSE_CONTRACT["top_m"]),
                "carried_min_selection_score": float(CARRIED_SPARSE_CONTRACT["min_selection_score"]),
                "carried_min_score_gap": float(CARRIED_SPARSE_CONTRACT["min_score_gap"]),
                "winner_survivor_contract": str(
                    h270_payload.get("summary", {}).get("winning_contract", {}).get("contract_name", "unknown")
                ),
                **_mask_summary(
                    sparse_baseline_mask,
                    baseline_mask=sparse_baseline_mask,
                    breakout_mask=breakout_mask,
                    observed_breakout_mask=observed_breakout_mask,
                    panel=panel,
                ),
            },
        )
    )
    daily_outputs[BASELINE_VARIANT] = baseline_result.daily.copy()

    for spec in variants:
        variant_name = str(spec["variant"])
        mask = pd.Series(spec["mask"], index=panel.index).fillna(False).astype(bool)
        compatibility_panel[f"gate__{variant_name}"] = mask.astype(bool).to_numpy()
        result = run_entry_backtest(
            inputs,
            entry_allowed_matrix=build_entry_allowed_matrix_from_mask(
                panel,
                dates=market_dates,
                tickers=market_tickers,
                mask=mask,
            ),
            round_trip_cost=float(args.round_trip_cost),
            required_holding_age=int(args.required_holding_age),
            initial_notional_vnd=float(args.initial_notional_vnd),
            top_k=int(args.top_k),
            rebalance_every=int(args.rebalance_every),
        )
        rows.append(
            backtest_row_from_result(
                variant=variant_name,
                family="breakout_survivor_family_trust_compatibility",
                result=result,
                protocol=INTRADAY_RESTART_PROTOCOL,
                extra={
                    "score_column": score_column,
                    "threshold": float(threshold),
                    "missing_policy": str(spec["missing_policy"]),
                    "carried_top_m": int(CARRIED_SPARSE_CONTRACT["top_m"]),
                    "carried_min_selection_score": float(CARRIED_SPARSE_CONTRACT["min_selection_score"]),
                    "carried_min_score_gap": float(CARRIED_SPARSE_CONTRACT["min_score_gap"]),
                    "winner_survivor_contract": str(
                        h270_payload.get("summary", {}).get("winning_contract", {}).get("contract_name", "unknown")
                    ),
                    **_mask_summary(
                        mask,
                        baseline_mask=sparse_baseline_mask,
                        breakout_mask=breakout_mask,
                        observed_breakout_mask=observed_breakout_mask,
                        panel=panel,
                    ),
                },
            )
        )
        daily_outputs[variant_name] = result.daily.copy()

    results = add_baseline_deltas(pd.DataFrame(rows), baseline_variant=BASELINE_VARIANT)
    baseline_row = results.loc[results["variant"] == BASELINE_VARIANT].iloc[0]
    results["overall_relative_delta"] = pd.to_numeric(results["overall_relative_total_return"], errors="coerce") - float(
        pd.to_numeric(baseline_row.get("overall_relative_total_return"), errors="coerce")
    )
    results["overall_ir_delta"] = pd.to_numeric(results["overall_information_ratio_annualized"], errors="coerce") - float(
        pd.to_numeric(baseline_row.get("overall_information_ratio_annualized"), errors="coerce")
    )
    candidate_results = _sort_results(results.loc[results["variant"] != BASELINE_VARIANT].copy())
    if candidate_results.empty:
        raise ValueError("H272 requires at least one compatibility variant")
    _print_table(candidate_results)

    best_variant = candidate_results.iloc[0]
    baseline_confirmation_cash = _coerce_float(baseline_row, "confirmation_avg_cash_weight")
    best_confirmation_cash = _coerce_float(best_variant, "confirmation_avg_cash_weight")
    coverage_ok = bool(
        int(pd.to_numeric(best_variant.get("allowed_rows"), errors="coerce")) >= int(MIN_TOTAL_ALLOWED_ROWS)
        and int(pd.to_numeric(best_variant.get("validation_allowed_rows"), errors="coerce")) >= int(MIN_VALIDATION_ALLOWED_ROWS)
        and int(pd.to_numeric(best_variant.get("confirmation_allowed_rows"), errors="coerce")) >= int(MIN_CONFIRMATION_ALLOWED_ROWS)
        and baseline_confirmation_cash is not None
        and best_confirmation_cash is not None
        and float(best_confirmation_cash) <= float(baseline_confirmation_cash) + float(MAX_CONFIRMATION_CASH_WEIGHT_INCREASE)
    )
    passed = bool(
        coverage_ok
        and (_coerce_float(best_variant, "validation_relative_delta") or float("-inf")) > 0.0
        and (_coerce_float(best_variant, "confirmation_relative_delta") or float("-inf")) > 0.0
        and (_coerce_float(best_variant, "validation_ir_delta") or float("-inf")) > 0.0
        and (_coerce_float(best_variant, "confirmation_ir_delta") or float("-inf")) > 0.0
        and (_coerce_float(best_variant, "overall_relative_delta") or float("-inf")) > 0.0
        and (_coerce_float(best_variant, "overall_ir_delta") or float("-inf")) > 0.0
    )
    mixed = bool(
        not passed
        and coverage_ok
        and (_coerce_float(best_variant, "overall_relative_delta") or float("-inf")) > 0.0
        and (_coerce_float(best_variant, "overall_ir_delta") or float("-inf")) > 0.0
        and (_coerce_float(best_variant, "validation_relative_delta") or float("-inf")) >= -0.02
        and (_coerce_float(best_variant, "confirmation_relative_delta") or float("-inf")) >= -0.02
    )
    decision = "PASSED" if passed else ("MIXED" if mixed else "FAILED")

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    ENTRY_ALPHA_OUT_DIR.mkdir(parents=True, exist_ok=True)
    results_path = ENTRY_ALPHA_OUT_DIR / f"{ts}_h272_breakout_survivor_family_trust_compatibility_integration_results.parquet"
    best_daily_path = ENTRY_ALPHA_OUT_DIR / f"{ts}_h272_breakout_survivor_family_trust_compatibility_integration_best_daily.parquet"
    baseline_daily_path = ENTRY_ALPHA_OUT_DIR / f"{ts}_h272_breakout_survivor_family_trust_compatibility_integration_baseline_daily.parquet"
    compatibility_panel_path = ENTRY_ALPHA_OUT_DIR / f"{ts}_h272_breakout_survivor_family_trust_compatibility_integration_panel.parquet"
    results.to_parquet(results_path, index=False)
    daily_outputs[str(best_variant["variant"])].to_parquet(best_daily_path, index=False)
    daily_outputs[BASELINE_VARIANT].to_parquet(baseline_daily_path, index=False)
    compatibility_panel.to_parquet(compatibility_panel_path, index=False)

    summary = {
        "protocol": INTRADAY_RESTART_PROTOCOL.describe(),
        "decision": decision,
        "advance_to_h273": bool(passed),
        "baseline_variant": baseline_row.to_dict(),
        "best_variant": best_variant.to_dict(),
        "compatibility_variants": candidate_results.to_dict("records"),
        "score_column": score_column,
        "threshold": float(threshold),
        "breakout_family": BREAKOUT_FAMILY,
        "carried_sparse_contract": dict(CARRIED_SPARSE_CONTRACT),
        "winner_survivor_contract": dict(h270_payload.get("summary", {}).get("winning_contract", {}) or {}),
        "coverage_guard": {
            "min_total_allowed_rows": int(MIN_TOTAL_ALLOWED_ROWS),
            "min_validation_allowed_rows": int(MIN_VALIDATION_ALLOWED_ROWS),
            "min_confirmation_allowed_rows": int(MIN_CONFIRMATION_ALLOWED_ROWS),
            "max_confirmation_cash_weight_increase": float(MAX_CONFIRMATION_CASH_WEIGHT_INCREASE),
        },
        "h270_observed_breakout_share": h270_payload.get("summary", {}).get("observed_breakout_share"),
    }
    write_run_summary(
        ts=ts,
        mode="entry_alpha_breakout_survivor_family_trust_compatibility_integration",
        name="h272_breakout_survivor_family_trust_compatibility_integration",
        summary=summary,
        artifacts={
            "results": str(results_path),
            "best_daily": str(best_daily_path),
            "baseline_daily": str(baseline_daily_path),
            "compatibility_panel": str(compatibility_panel_path),
        },
        metadata={
            "h271_summary": str(h271_summary_path),
            "h270_summary": str(h270_summary_path),
            "candidate_cache": str(args.candidate_cache),
            "labels_cache": str(args.labels_cache),
            "matrix": str(args.matrix),
            "tradability": str(args.tradability),
            "stock_dir": str(args.stock_dir),
            "benchmark": str(args.benchmark),
            "strategy": str(args.strategy),
            "top_k": int(args.top_k),
            "rebalance_every": int(args.rebalance_every),
            "top_m_max": int(args.top_m_max),
            "round_trip_cost": float(args.round_trip_cost),
            "required_holding_age": int(args.required_holding_age),
            "initial_notional_vnd": float(args.initial_notional_vnd),
            "protocol": INTRADAY_RESTART_PROTOCOL.describe(),
        },
    )


if __name__ == "__main__":
    main()
