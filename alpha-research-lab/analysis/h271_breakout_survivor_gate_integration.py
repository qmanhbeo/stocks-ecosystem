"""
H271: deterministic breakout-survivor gate integration.
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
BASELINE_VARIANT = "observed_breakout_survivor_always_on"
GATE_QUANTILES: tuple[tuple[str, float], ...] = (
    ("dev_q50", 0.50),
    ("dev_q80", 0.80),
    ("dev_q90", 0.90),
)
MIN_CONFIRMATION_ALLOWED_ROWS = 120


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H271: deterministic breakout-survivor gate integration")
    parser.add_argument("--matrix", type=str, default=str(RL_MATRIX_PATH))
    parser.add_argument("--tradability", type=str, default=str(TRADABILITY_PATH))
    parser.add_argument("--stock-dir", type=str, default=str(STOCK_DIR))
    parser.add_argument("--benchmark", type=str, default=str(BENCHMARK_PATH))
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


def _sort_gate_results(results: pd.DataFrame) -> pd.DataFrame:
    if results.empty:
        return results.copy()
    work = results.copy()
    for column in [
        "validation_relative_delta",
        "validation_ir_delta",
        "confirmation_relative_delta",
        "confirmation_ir_delta",
        "confirmation_allowed_rows",
        "allowed_rows",
    ]:
        if column in work.columns:
            work[column] = pd.to_numeric(work[column], errors="coerce")
    return work.sort_values(
        by=[
            "validation_relative_delta",
            "confirmation_relative_delta",
            "validation_ir_delta",
            "confirmation_ir_delta",
            "confirmation_allowed_rows",
            "allowed_rows",
            "variant",
        ],
        ascending=[False, False, False, False, False, False, True],
        ignore_index=True,
    )


def _phase_mask_summary(mask: pd.Series, base_mask: pd.Series, panel: pd.DataFrame) -> dict[str, object]:
    summary: dict[str, object] = {
        "allowed_rows": int(mask.sum()),
        "base_allowed_rows": int(base_mask.sum()),
        "allowed_share": float(mask.mean()) if len(mask) else 0.0,
    }
    for phase in ("dev", "validation", "confirmation"):
        phase_mask = panel["research_phase"].astype(str).eq(phase)
        phase_base = base_mask & phase_mask
        phase_allowed = mask & phase_mask
        base_count = int(phase_base.sum())
        allowed_count = int(phase_allowed.sum())
        summary[f"{phase}_allowed_rows"] = allowed_count
        summary[f"{phase}_base_rows"] = base_count
        summary[f"{phase}_allowed_share"] = float(allowed_count / base_count) if base_count > 0 else None
    return summary


def _threshold_specs(scored_subset: pd.DataFrame, *, score_column: str) -> list[dict[str, object]]:
    dev = scored_subset.loc[scored_subset["research_phase"].astype(str) == "dev", score_column]
    dev = pd.to_numeric(dev, errors="coerce").dropna()
    if dev.empty:
        raise ValueError("H271 requires dev-phase scores for threshold calibration")
    specs: list[dict[str, object]] = []
    for gate_name, quantile in GATE_QUANTILES:
        specs.append(
            {
                "gate_name": gate_name,
                "quantile": float(quantile),
                "threshold": float(dev.quantile(float(quantile))),
            }
        )
    return specs


def _coerce_float(row: pd.Series | dict[str, object], column: str) -> float | None:
    value = pd.to_numeric(row.get(column), errors="coerce")
    return None if pd.isna(value) else float(value)


def _print_table(results: pd.DataFrame) -> None:
    print("\n" + "=" * 205)
    print("H271: BREAKOUT SURVIVOR GATE INTEGRATION")
    print("=" * 205)
    print(
        f"{'rank':<5} {'variant':<24} {'thr':>8} {'allowed':>8} {'2024_rel_d':>11} "
        f"{'2025_rel_d':>11} {'2024_ir_d':>10} {'2025_ir_d':>10} {'2025_rows':>10}"
    )
    print("-" * 205)
    for idx, row in enumerate(results.itertuples(index=False), start=1):
        print(
            f"{idx:<5} {str(row.variant):<24} "
            f"{row.threshold if row.threshold is not None else float('nan'):>8.4f} "
            f"{int(row.allowed_rows):>8d} "
            f"{(row.validation_relative_delta or 0.0) * 100:>+10.2f}% "
            f"{(row.confirmation_relative_delta or 0.0) * 100:>+10.2f}% "
            f"{row.validation_ir_delta if row.validation_ir_delta is not None else float('nan'):>+9.2f} "
            f"{row.confirmation_ir_delta if row.confirmation_ir_delta is not None else float('nan'):>+9.2f} "
            f"{int(row.confirmation_allowed_rows):>10d}"
        )


def main() -> None:
    args = parse_args()
    h270_summary_path = Path(args.h270_summary)
    h270_payload = load_summary_payload(h270_summary_path)
    if not bool(h270_payload.get("summary", {}).get("advance_to_h271", False)):
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        write_run_summary(
            ts=ts,
            mode="entry_alpha_breakout_survivor_gate_integration",
            name="h271_breakout_survivor_gate_integration",
            summary={
                "protocol": INTRADAY_RESTART_PROTOCOL.describe(),
                "skipped": True,
                "reason": "H270 did not clear the breakout-survivor predictive gate",
            },
            artifacts={},
            metadata={"protocol": INTRADAY_RESTART_PROTOCOL.describe()},
        )
        return

    winning_contract = dict(h270_payload.get("summary", {}).get("winning_contract", {}) or {})
    best_intraday_model = dict(h270_payload.get("summary", {}).get("best_intraday_model", {}) or {})
    score_column = f"entry_prob__{str(best_intraday_model.get('model_name', '')).strip()}"
    if score_column == "entry_prob__" or not score_column:
        raise ValueError("H271 requires the H270 winner intraday model")

    score_panel = pd.read_parquet(resolve_summary_artifact(h270_summary_path, "scored_panel"))
    subset_panel = pd.read_parquet(resolve_summary_artifact(h270_summary_path, "subset_panel"))
    if score_column not in score_panel.columns:
        raise ValueError(f"H271 score column missing from H270 scored panel: {score_column}")

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

    observed_breakout_mask = (
        panel["entry_thesis_family"].astype(str).eq(BREAKOUT_FAMILY)
        & panel["can_buy_next_open"].fillna(False).astype(bool)
        & panel[score_column].notna()
    )
    observed_breakout = panel.loc[observed_breakout_mask].copy()
    if observed_breakout.empty:
        raise ValueError("No observed breakout-survivor rows available for H271")

    threshold_specs = _threshold_specs(observed_breakout, score_column=score_column)
    market_dates = pd.DatetimeIndex(pd.to_datetime(inputs.market_inputs.dates))
    market_tickers = list(inputs.market_inputs.tickers)

    rows: list[dict[str, object]] = []
    daily_outputs: dict[str, pd.DataFrame] = {}
    gate_panel = subset_panel.merge(
        score_panel[["time", "ticker", score_column]].copy(),
        on=["time", "ticker"],
        how="left",
        validate="one_to_one",
    ).copy()

    baseline_result = run_entry_backtest(
        inputs,
        entry_allowed_matrix=build_entry_allowed_matrix_from_mask(
            panel,
            dates=market_dates,
            tickers=market_tickers,
            mask=observed_breakout_mask,
        ),
        round_trip_cost=float(args.round_trip_cost),
        required_holding_age=int(args.required_holding_age),
        initial_notional_vnd=float(args.initial_notional_vnd),
        top_k=int(args.top_k),
        rebalance_every=int(args.rebalance_every),
    )
    baseline_summary = _phase_mask_summary(observed_breakout_mask, observed_breakout_mask, panel)
    rows.append(
        backtest_row_from_result(
            variant=BASELINE_VARIANT,
            family="breakout_survivor_gate",
            result=baseline_result,
            protocol=INTRADAY_RESTART_PROTOCOL,
            extra={
                "gate_name": "always_on",
                "threshold": None,
                "quantile": None,
                "score_column": score_column,
                **baseline_summary,
            },
        )
    )
    daily_outputs[BASELINE_VARIANT] = baseline_result.daily.copy()
    gate_panel["gate__always_on"] = True

    for spec in threshold_specs:
        gate_name = str(spec["gate_name"])
        threshold = float(spec["threshold"])
        mask = observed_breakout_mask & (pd.to_numeric(panel[score_column], errors="coerce") >= threshold)
        gate_panel[f"gate__{gate_name}"] = pd.to_numeric(gate_panel[score_column], errors="coerce") >= threshold
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
                variant=gate_name,
                family="breakout_survivor_gate",
                result=result,
                protocol=INTRADAY_RESTART_PROTOCOL,
                extra={
                    "gate_name": gate_name,
                    "threshold": threshold,
                    "quantile": float(spec["quantile"]),
                    "score_column": score_column,
                    **_phase_mask_summary(mask, observed_breakout_mask, panel),
                },
            )
        )
        daily_outputs[gate_name] = result.daily.copy()

    results = add_baseline_deltas(pd.DataFrame(rows), baseline_variant=BASELINE_VARIANT)
    gate_results = _sort_gate_results(results.loc[results["variant"] != BASELINE_VARIANT].copy())
    if gate_results.empty:
        raise ValueError("H271 requires at least one gate candidate")
    _print_table(gate_results)

    best_gate = gate_results.iloc[0]
    baseline_row = results.loc[results["variant"] == BASELINE_VARIANT].iloc[0]
    coverage_ok = bool(
        int(pd.to_numeric(best_gate.get("confirmation_allowed_rows"), errors="coerce")) >= int(MIN_CONFIRMATION_ALLOWED_ROWS)
    )
    passed = bool(
        coverage_ok
        and (_coerce_float(best_gate, "validation_relative_delta") or float("-inf")) > 0.0
        and (_coerce_float(best_gate, "confirmation_relative_delta") or float("-inf")) > 0.0
        and (
            (_coerce_float(best_gate, "validation_ir_delta") or float("-inf")) > 0.0
            or (_coerce_float(best_gate, "confirmation_ir_delta") or float("-inf")) > 0.0
        )
    )
    mixed = bool(
        not passed
        and coverage_ok
        and (_coerce_float(best_gate, "validation_relative_delta") or float("-inf")) > 0.0
        and (_coerce_float(best_gate, "confirmation_relative_delta") or float("-inf")) >= -0.02
    )
    decision = "PASSED" if passed else ("MIXED" if mixed else "FAILED")

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    ENTRY_ALPHA_OUT_DIR.mkdir(parents=True, exist_ok=True)
    results_path = ENTRY_ALPHA_OUT_DIR / f"{ts}_h271_breakout_survivor_gate_integration_results.parquet"
    best_daily_path = ENTRY_ALPHA_OUT_DIR / f"{ts}_h271_breakout_survivor_gate_integration_best_daily.parquet"
    baseline_daily_path = ENTRY_ALPHA_OUT_DIR / f"{ts}_h271_breakout_survivor_gate_integration_baseline_daily.parquet"
    gate_panel_path = ENTRY_ALPHA_OUT_DIR / f"{ts}_h271_breakout_survivor_gate_integration_gate_panel.parquet"
    results.to_parquet(results_path, index=False)
    daily_outputs[str(best_gate["variant"])].to_parquet(best_daily_path, index=False)
    daily_outputs[BASELINE_VARIANT].to_parquet(baseline_daily_path, index=False)
    gate_panel.to_parquet(gate_panel_path, index=False)

    summary = {
        "protocol": INTRADAY_RESTART_PROTOCOL.describe(),
        "decision": decision,
        "advance_to_h272": bool(passed),
        "winning_contract": winning_contract,
        "baseline_variant": baseline_row.to_dict(),
        "best_gate_variant": best_gate.to_dict(),
        "threshold_grid": threshold_specs,
        "score_column": score_column,
        "breakout_family": BREAKOUT_FAMILY,
        "observed_breakout_row_count": int(observed_breakout_mask.sum()),
        "observed_breakout_share": float(
            pd.to_numeric(h270_payload.get("summary", {}).get("observed_breakout_share"), errors="coerce")
        ),
        "coverage_guard": {
            "min_confirmation_allowed_rows": int(MIN_CONFIRMATION_ALLOWED_ROWS),
        },
        "top_gate_candidates": gate_results.head(3).to_dict("records"),
    }
    write_run_summary(
        ts=ts,
        mode="entry_alpha_breakout_survivor_gate_integration",
        name="h271_breakout_survivor_gate_integration",
        summary=summary,
        artifacts={
            "results": str(results_path),
            "best_daily": str(best_daily_path),
            "baseline_daily": str(baseline_daily_path),
            "gate_panel": str(gate_panel_path),
        },
        metadata={
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
