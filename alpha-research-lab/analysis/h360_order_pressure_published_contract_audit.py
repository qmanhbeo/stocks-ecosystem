"""
H360 - Order-Pressure Published Contract Audit.

Question:
- Does the published C16 artifact reproduce the H359 winning portfolio result
  when consumed through its documented blend contract?

Design:
- Exclude 2026 entirely.
- Test exactly one fixed consumer formula:
  blended_score = (1 - w) * full_library_score + w * order_volume_ratio_rank
- Use `w = order_pressure_h359_blend_weight` from
  data/features/xs_order_pressure_daily.parquet.
- Compare the resulting executable portfolio to the saved H359 winner.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import sys
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

from src.additive_selector_research import additive_candidate_deltas, additive_candidate_passes
from src.deterministic_portfolio import compute_strategy_scores, resolve_strategy_columns
from src.repo_paths import artifact_path, data_path
from src.research_protocol import DEFAULT_PROTOCOL
from src.run_summary import write_run_summary
from src.tradability_conditioned_research import load_research_bundle, run_selector_candidate

from h358_order_pressure_portfolio_tradability_audit import (
    _execution_health_flags,
    _flatten_phase_rows,
    _phase_execution_summary,
)


MATRIX_PATH = data_path("features/xs_rl_signal_matrix.parquet")
ORDER_PRESSURE_PATH = data_path("features/xs_order_pressure_daily.parquet")
TRADABILITY_PATH = data_path("features/execution/tradability_daily.parquet")
STOCK_DIR = data_path("stock")
BENCHMARK_PATH = STOCK_DIR / "gia_lich_su_VNINDEX_1D.parquet"
H359_SUMMARY_PATH = (
    ROOT
    / "artifacts"
    / "run_summaries"
    / "latest_research_branch_order_pressure_sizing_scope_audit.json"
)
OUT_DIR = artifact_path("portfolio_baselines")

ORDER_FEATURE = "order_volume_ratio_rank"
WEIGHT_FEATURE = "order_pressure_h359_blend_weight"
STRATEGY_NAME = "order_pressure_published_h359_contract"
START_YEAR = 2015
END_YEAR = 2025
PARITY_TOLERANCE = 1e-9
PARITY_KEYS = (
    "validation_relative_total_return",
    "validation_information_ratio_annualized",
    "validation_relative_delta",
    "validation_ir_delta",
    "validation_cash_delta",
    "confirmation_relative_total_return",
    "confirmation_information_ratio_annualized",
    "confirmation_relative_delta",
    "confirmation_ir_delta",
    "confirmation_cash_delta",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", type=str, default=str(MATRIX_PATH))
    parser.add_argument("--order-pressure", type=str, default=str(ORDER_PRESSURE_PATH))
    parser.add_argument("--tradability", type=str, default=str(TRADABILITY_PATH))
    parser.add_argument("--stock-dir", type=str, default=str(STOCK_DIR))
    parser.add_argument("--benchmark", type=str, default=str(BENCHMARK_PATH))
    parser.add_argument("--h359-summary", type=str, default=str(H359_SUMMARY_PATH))
    parser.add_argument("--start-year", type=int, default=START_YEAR)
    parser.add_argument("--end-year", type=int, default=END_YEAR)
    parser.add_argument("--portfolio-notional-vnd", type=float, default=100_000_000.0)
    parser.add_argument("--round-trip-cost", type=float, default=0.003)
    parser.add_argument("--required-holding-age", type=int, default=3)
    return parser.parse_args()


def _safe_float(value: object) -> float | None:
    numeric = pd.to_numeric(value, errors="coerce")
    return None if pd.isna(numeric) else float(numeric)


def _load_order_pressure_artifact(path: Path, *, start_year: int, end_year: int) -> pd.DataFrame:
    frame = pd.read_parquet(path, columns=["time", "ticker", ORDER_FEATURE, WEIGHT_FEATURE]).copy()
    frame["time"] = pd.to_datetime(frame["time"], errors="coerce").dt.normalize()
    frame["ticker"] = frame["ticker"].astype(str).str.upper()
    frame = frame.loc[frame["time"].dt.year.between(int(start_year), int(end_year))].dropna(
        subset=["time", "ticker"]
    )
    duplicate_rows = int(frame.duplicated(["time", "ticker"]).sum())
    if duplicate_rows:
        raise ValueError(f"Published order-pressure artifact has {duplicate_rows:,} duplicate ticker-days")
    frame[ORDER_FEATURE] = pd.to_numeric(frame[ORDER_FEATURE], errors="coerce")
    frame[WEIGHT_FEATURE] = pd.to_numeric(frame[WEIGHT_FEATURE], errors="coerce").fillna(0.0)
    return frame[["time", "ticker", ORDER_FEATURE, WEIGHT_FEATURE]].sort_values(["time", "ticker"])


def _load_h359_winner(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    winner = payload.get("summary", {}).get("winner")
    if not isinstance(winner, dict):
        raise ValueError(f"H359 summary is missing summary.winner: {path}")
    return winner


def _parity_metrics(candidate: pd.Series, reference: dict[str, object]) -> tuple[dict[str, float | None], float]:
    deltas: dict[str, float | None] = {}
    max_abs_delta = 0.0
    for key in PARITY_KEYS:
        left = _safe_float(candidate.get(key))
        right = _safe_float(reference.get(key))
        if left is None or right is None:
            deltas[key] = None
            continue
        delta = float(left - right)
        deltas[key] = delta
        max_abs_delta = max(max_abs_delta, abs(delta))
    return deltas, max_abs_delta


def main() -> None:
    args = parse_args()
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    fee_leg = float(args.round_trip_cost) / 2.0
    required_holding_age = required_holding_age_for_sell(min_hold_days_override=int(args.required_holding_age))

    bundle = load_research_bundle(
        matrix_path=Path(args.matrix),
        tradability_path=Path(args.tradability),
        stock_dir=Path(args.stock_dir),
        benchmark_path=Path(args.benchmark),
        start_year=int(args.start_year),
        end_year=int(args.end_year),
    )
    matrix = bundle.matrix.copy()
    matrix["time"] = pd.to_datetime(matrix["time"], errors="coerce").dt.normalize()
    matrix["ticker"] = matrix["ticker"].astype(str).str.upper()
    order = _load_order_pressure_artifact(
        Path(args.order_pressure),
        start_year=int(args.start_year),
        end_year=int(args.end_year),
    )
    merged = matrix.merge(order, on=["time", "ticker"], how="left", validate="one_to_one")
    merged[WEIGHT_FEATURE] = pd.to_numeric(merged[WEIGHT_FEATURE], errors="coerce").fillna(0.0).clip(0.0, 1.0)
    full_library_columns = resolve_strategy_columns(matrix.columns.tolist(), "full_library")

    base_scored = compute_strategy_scores(
        merged,
        {
            "full_library_baseline": list(full_library_columns),
            "order_pressure_contract_rank": [ORDER_FEATURE],
        },
    )
    weights = merged[WEIGHT_FEATURE].astype(float)
    base = base_scored["score__full_library_baseline"].astype(float)
    order_score = base_scored["score__order_pressure_contract_rank"].astype(float)

    scored = base_scored[["time", "ticker", "actual"]].copy()
    scored["score__full_library_baseline"] = base
    scored[f"score__{STRATEGY_NAME}"] = ((1.0 - weights) * base + weights * order_score).clip(0.0, 1.0)

    rows: list[dict[str, object]] = []
    daily_outputs: dict[str, pd.DataFrame] = {}
    for strategy_name, signal_columns in {
        "full_library_baseline": list(full_library_columns),
        STRATEGY_NAME: ["published_contract::order_pressure_h359"],
    }.items():
        result = run_selector_candidate(
            scored_frame=scored,
            bundle=bundle,
            strategy_name=strategy_name,
            signal_columns=signal_columns,
            start_year=int(args.start_year),
            end_year=int(args.end_year),
            initial_notional_vnd=float(args.portfolio_notional_vnd),
            buy_fee_rate=float(fee_leg),
            sell_fee_rate=float(fee_leg),
            required_holding_age=int(required_holding_age),
        )
        phase_summary = _phase_execution_summary(result.daily)
        row = _flatten_phase_rows(strategy_name, signal_columns, phase_summary, result.summary)
        rows.append(row)
        daily_outputs[strategy_name] = result.daily.copy()

    results = pd.DataFrame(rows)
    baseline = results.loc[results["strategy_name"] == "full_library_baseline"].iloc[0]
    candidate_idx = results.index[results["strategy_name"] == STRATEGY_NAME][0]
    candidate = results.loc[candidate_idx].copy()
    deltas = additive_candidate_deltas(candidate, baseline)
    health = _execution_health_flags(candidate, baseline)
    for key, value in {**deltas, **health}.items():
        results.loc[candidate_idx, key] = value
        candidate[key] = value
    results.loc[candidate_idx, "portfolio_gate_pass"] = bool(additive_candidate_passes(candidate, baseline))
    results.loc[candidate_idx, "verdict"] = "PASSED" if bool(
        results.loc[candidate_idx, "portfolio_gate_pass"] and health["passes_execution_health"]
    ) else "FAILED"
    for key in (
        "validation_relative_delta",
        "validation_ir_delta",
        "confirmation_relative_delta",
        "confirmation_ir_delta",
        "validation_cash_delta",
        "confirmation_cash_delta",
    ):
        results.loc[results["strategy_name"] == "full_library_baseline", key] = 0.0
    results.loc[results["strategy_name"] == "full_library_baseline", "passes_execution_health"] = True
    results.loc[results["strategy_name"] == "full_library_baseline", "portfolio_gate_pass"] = False
    results.loc[results["strategy_name"] == "full_library_baseline", "verdict"] = "BASELINE"

    reference = _load_h359_winner(Path(args.h359_summary))
    candidate_row = results.loc[results["strategy_name"] == STRATEGY_NAME].iloc[0]
    parity_deltas, max_abs_delta = _parity_metrics(candidate_row, reference)
    parity_pass = bool(max_abs_delta <= PARITY_TOLERANCE)
    contract_pass = bool(candidate_row["verdict"] == "PASSED" and parity_pass)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results_path = OUT_DIR / f"{ts}_h360_order_pressure_published_contract_results.parquet"
    daily_path = OUT_DIR / f"{ts}_h360_order_pressure_published_contract_daily.parquet"
    details_path = ROOT / "artifacts" / "run_summaries" / f"{ts}_h360_order_pressure_published_contract_details.json"
    results.to_parquet(results_path, index=False)
    daily_outputs[STRATEGY_NAME].to_parquet(daily_path, index=False)
    details_path.write_text(
        json.dumps(
            {
                "parity_deltas": parity_deltas,
                "max_abs_parity_delta": max_abs_delta,
                "candidate": candidate_row.to_dict(),
                "reference_winner": reference,
            },
            indent=2,
            sort_keys=True,
            default=str,
        )
        + "\n",
        encoding="utf-8",
    )

    summary_path = write_run_summary(
        ts=ts,
        mode="research_branch_order_pressure_published_contract_audit",
        name="h360_order_pressure_published_contract_audit",
        summary={
            "verdict": "PASSED" if contract_pass else "FAILED",
            "branch_decision": (
                "The published C16 artifact reproduces the H359 winner exactly enough for the "
                "documented downstream opt-in contract."
                if contract_pass
                else "The published C16 artifact does not reproduce the saved H359 winner; hold downstream use."
            ),
            "strategy_name": STRATEGY_NAME,
            "portfolio_gate_pass": bool(candidate_row.get("portfolio_gate_pass")),
            "passes_execution_health": bool(candidate_row.get("passes_execution_health")),
            "parity_pass": parity_pass,
            "max_abs_parity_delta": max_abs_delta,
            "validation_relative_delta": _safe_float(candidate_row.get("validation_relative_delta")),
            "confirmation_relative_delta": _safe_float(candidate_row.get("confirmation_relative_delta")),
            "validation_cash_delta": _safe_float(candidate_row.get("validation_cash_delta")),
            "confirmation_cash_delta": _safe_float(candidate_row.get("confirmation_cash_delta")),
        },
        artifacts={
            "order_pressure": str(Path(args.order_pressure)),
            "h359_summary": str(Path(args.h359_summary)),
            "results": str(results_path),
            "daily": str(daily_path),
            "details": str(details_path),
        },
        metadata={
            "start_year": int(args.start_year),
            "end_year": int(args.end_year),
            "protocol": DEFAULT_PROTOCOL.describe(),
            "formula": "(1 - w) * full_library_score + w * order_volume_ratio_rank",
            "weight_column": WEIGHT_FEATURE,
            "parity_tolerance": PARITY_TOLERANCE,
        },
    )

    print("\nH360: ORDER-PRESSURE PUBLISHED CONTRACT AUDIT")
    print(f"  verdict: {'PASSED' if contract_pass else 'FAILED'}")
    print(f"  portfolio gate: {bool(candidate_row.get('portfolio_gate_pass'))}")
    print(f"  execution health: {bool(candidate_row.get('passes_execution_health'))}")
    print(f"  parity max abs delta: {max_abs_delta:.12g}")
    print(f"  validation rel delta: {(_safe_float(candidate_row.get('validation_relative_delta')) or 0.0) * 100:+.2f}%")
    print(f"  confirmation rel delta: {(_safe_float(candidate_row.get('confirmation_relative_delta')) or 0.0) * 100:+.2f}%")
    print(f"  summary: {summary_path}")


if __name__ == "__main__":
    main()
