"""
H355: order-pressure step-hazard continuation.

Question:
    H339 parked smart-exit learning until richer post-entry state/data exists.
    Does the later-validated CafeF order-pressure surface improve the H337
    one-step legal-exit hazard when added to the saved H337 decision rows?

Design:
    - consume saved H337 step rows instead of rebuilding the oracle universe
    - keep the H337 wait-one-more label and fixed 0.50 policy threshold
    - add only current/entry order-pressure fields available at the decision date
    - compare fixed feature sets against an H337 refit baseline
    - evaluate dev / validation / confirmation exactly like H337
    - exclude 2026 entirely via the saved H337 rows
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from path_utils import data_path

ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_DIR = ROOT / "analysis"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ANALYSIS_DIR) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_DIR))

from h337_replacement_aware_step_hazard import (  # noqa: E402
    HOLD_THRESHOLD,
    _feature_columns,
    _h211_policy_for_entries,
    _policy_for_entries,
    _resolve_h211_params,
    fit_model,
    summarize_policies,
)
from src.additive_selector_research import load_summary_payload, resolve_summary_artifact  # noqa: E402
from src.research_protocol import DEFAULT_PROTOCOL  # noqa: E402
from src.run_summary import write_run_summary  # noqa: E402


H337_SUMMARY_PATH = ROOT / "artifacts" / "run_summaries" / "latest_research_branch_replacement_aware_step_hazard.json"
H211_SUMMARY_PATH = ROOT / "artifacts" / "run_summaries" / "latest_portfolio_exit_strength_exhaustion.json"
ORDER_STATS_PATH = data_path("order_stats/cafef/order_stats_daily.parquet")
OUT_DIR = ROOT / "artifacts" / "portfolio_baselines"
DETAILS_DIR = ROOT / "artifacts" / "run_summaries"

ORDER_CURRENT_FEATURES = [
    "current_order_volume_ratio",
    "current_order_count_ratio",
    "current_avg_order_size_ratio",
    "current_order_volume_ratio_rank",
    "current_order_count_ratio_rank",
]
ORDER_ENTRY_FEATURES = [
    "entry_order_volume_ratio",
    "entry_order_count_ratio",
    "entry_avg_order_size_ratio",
    "entry_order_volume_ratio_rank",
    "entry_order_count_ratio_rank",
]
ORDER_DELTA_FEATURES = [
    "order_volume_ratio_change_since_entry",
    "order_count_ratio_change_since_entry",
    "avg_order_size_ratio_change_since_entry",
]
FEATURE_SET_SPECS = (
    ("h337_refit", "Saved H337 feature family refit on unchanged step rows.", []),
    (
        "current_order_pressure",
        "H337 features plus current decision-date order-pressure fields.",
        ORDER_CURRENT_FEATURES,
    ),
    (
        "minimal_order_delta",
        "H337 features plus current volume pressure and change from entry.",
        ["current_order_volume_ratio", "order_volume_ratio_change_since_entry"],
    ),
    (
        "entry_current_order_delta",
        "H337 features plus current, entry, and delta order-pressure fields.",
        [*ORDER_CURRENT_FEATURES, *ORDER_ENTRY_FEATURES, *ORDER_DELTA_FEATURES],
    ),
)

MIN_VALIDATION_IMPROVEMENT = 0.0020
MIN_CONFIRMATION_IMPROVEMENT = 0.0020
MIN_AUC = 0.50


def _safe_float(value: object) -> float | None:
    numeric = pd.to_numeric(value, errors="coerce")
    return None if pd.isna(numeric) else float(numeric)


def _json_safe(value: object):
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, np.ndarray):
        return [_json_safe(item) for item in value.tolist()]
    if isinstance(value, np.generic):
        if pd.isna(value):
            return None
        return value.item()
    if isinstance(value, float) and pd.isna(value):
        return None
    return value


def _daily_rank(series: pd.Series, time_index: pd.Series, *, ascending: bool = True) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").groupby(time_index, sort=False).rank(
        method="average",
        pct=True,
        ascending=ascending,
    )


def _load_h337_step_rows() -> tuple[pd.DataFrame, dict[str, object]]:
    payload = load_summary_payload(H337_SUMMARY_PATH)
    step_path = resolve_summary_artifact(H337_SUMMARY_PATH, "step_rows")
    steps = pd.read_parquet(step_path).copy()
    for column in ("entry_signal_date", "entry_execution_date", "decision_date", "scheduled_exit_date"):
        if column in steps.columns:
            steps[column] = pd.to_datetime(steps[column], errors="coerce").dt.normalize()
    steps["ticker"] = steps["ticker"].astype(str).str.upper()
    steps = steps.loc[steps["decision_date"].dt.year <= 2025].copy()
    if steps.empty:
        raise ValueError("H355 refuses to train/evaluate on empty or 2026-only H337 step rows")
    return steps, payload


def _load_order_features() -> pd.DataFrame:
    order = pd.read_parquet(
        ORDER_STATS_PATH,
        columns=[
            "ticker",
            "date",
            "buy_order_count",
            "buy_order_volume",
            "avg_buy_order_volume",
            "sell_order_count",
            "sell_order_volume",
            "avg_sell_order_volume",
        ],
    ).rename(columns={"date": "time"})
    order["time"] = pd.to_datetime(order["time"], errors="coerce").dt.normalize()
    order["ticker"] = order["ticker"].astype(str).str.upper()
    order = order.loc[order["time"].dt.year.between(2015, 2025)].copy()

    buy_vol = pd.to_numeric(order["buy_order_volume"], errors="coerce").fillna(0.0)
    sell_vol = pd.to_numeric(order["sell_order_volume"], errors="coerce").fillna(0.0)
    buy_count = pd.to_numeric(order["buy_order_count"], errors="coerce").fillna(0.0)
    sell_count = pd.to_numeric(order["sell_order_count"], errors="coerce").fillna(0.0)
    avg_buy = pd.to_numeric(order["avg_buy_order_volume"], errors="coerce").fillna(0.0)
    avg_sell = pd.to_numeric(order["avg_sell_order_volume"], errors="coerce").fillna(0.0)

    order["order_volume_ratio"] = np.where((buy_vol + sell_vol) > 0.0, (buy_vol - sell_vol) / (buy_vol + sell_vol), np.nan)
    order["order_count_ratio"] = np.where((buy_count + sell_count) > 0.0, (buy_count - sell_count) / (buy_count + sell_count), np.nan)
    order["avg_order_size_ratio"] = np.where((avg_buy + avg_sell) > 0.0, (avg_buy - avg_sell) / (avg_buy + avg_sell), np.nan)
    order["order_volume_ratio_rank"] = _daily_rank(order["order_volume_ratio"], order["time"], ascending=True)
    order["order_count_ratio_rank"] = _daily_rank(order["order_count_ratio"], order["time"], ascending=True)
    return order[
        [
            "time",
            "ticker",
            "order_volume_ratio",
            "order_count_ratio",
            "avg_order_size_ratio",
            "order_volume_ratio_rank",
            "order_count_ratio_rank",
        ]
    ].drop_duplicates(["time", "ticker"])


def _prefix_order(frame: pd.DataFrame, prefix: str, date_col: str) -> pd.DataFrame:
    renamed = frame.rename(columns={"time": date_col}).copy()
    return renamed.rename(
        columns={
            column: f"{prefix}_{column}"
            for column in renamed.columns
            if column not in {date_col, "ticker"}
        }
    )


def _augment_with_order(steps: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, object]]:
    order = _load_order_features()
    current = _prefix_order(order, "current", "decision_date")
    entry = _prefix_order(order, "entry", "entry_signal_date")
    out = steps.merge(current, on=["decision_date", "ticker"], how="left", validate="many_to_one")
    out = out.merge(entry, on=["entry_signal_date", "ticker"], how="left", validate="many_to_one")
    out["order_volume_ratio_change_since_entry"] = (
        pd.to_numeric(out["current_order_volume_ratio"], errors="coerce")
        - pd.to_numeric(out["entry_order_volume_ratio"], errors="coerce")
    )
    out["order_count_ratio_change_since_entry"] = (
        pd.to_numeric(out["current_order_count_ratio"], errors="coerce")
        - pd.to_numeric(out["entry_order_count_ratio"], errors="coerce")
    )
    out["avg_order_size_ratio_change_since_entry"] = (
        pd.to_numeric(out["current_avg_order_size_ratio"], errors="coerce")
        - pd.to_numeric(out["entry_avg_order_size_ratio"], errors="coerce")
    )
    coverage = {
        "current_order_coverage_pct": float(100.0 * out["current_order_volume_ratio"].notna().mean()),
        "entry_order_coverage_pct": float(100.0 * out["entry_order_volume_ratio"].notna().mean()),
        "current_order_tickers": int(out.loc[out["current_order_volume_ratio"].notna(), "ticker"].nunique()),
        "entry_order_tickers": int(out.loc[out["entry_order_volume_ratio"].notna(), "ticker"].nunique()),
    }
    return out, coverage


def _phase_value(phase_results: pd.DataFrame, phase: str, column: str) -> float | None:
    rows = phase_results.loc[phase_results["phase"] == phase]
    if rows.empty:
        return None
    return _safe_float(rows.iloc[0].get(column))


def _evaluate_feature_set(
    frame: pd.DataFrame,
    *,
    name: str,
    note: str,
    base_features: list[str],
    add_features: list[str],
    h211_params: dict[str, float],
) -> tuple[dict[str, object], pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    available_add = [column for column in add_features if column in frame.columns]
    feature_columns = [*base_features, *available_add]
    _, scored, model_summary = fit_model(frame.copy(), feature_columns)
    policy = _policy_for_entries(scored, float(HOLD_THRESHOLD))
    h211_policy = _h211_policy_for_entries(scored, h211_params)
    phase_results, decision = summarize_policies(scored, policy, h211_policy)
    result = {
        "feature_set": name,
        "note": note,
        "add_feature_count": int(len(available_add)),
        "feature_count": int(len(feature_columns)),
        "verdict_under_h337_gate": decision["verdict"],
        "validation_model_uplift_vs_best_fixed": decision["validation_model_uplift_vs_best_fixed"],
        "confirmation_model_uplift_vs_best_fixed": decision["confirmation_model_uplift_vs_best_fixed"],
        "validation_oracle_uplift_recovered_share": decision["validation_oracle_uplift_recovered_share"],
        "confirmation_oracle_uplift_recovered_share": decision["confirmation_oracle_uplift_recovered_share"],
        "validation_decision_auc": decision["validation_decision_auc"],
        "confirmation_decision_auc": decision["confirmation_decision_auc"],
        "validation_model_delta_vs_h211": decision["validation_model_delta_vs_h211"],
        "confirmation_model_delta_vs_h211": decision["confirmation_model_delta_vs_h211"],
        "model_summary": model_summary,
        "phase_results": phase_results.to_dict(orient="records"),
    }
    policy = policy.copy()
    policy["feature_set"] = name
    scored = scored.copy()
    scored["feature_set"] = name
    phase_results = phase_results.copy()
    phase_results["feature_set"] = name
    return result, phase_results, policy, scored


def _decide(results: pd.DataFrame) -> dict[str, object]:
    baseline = results.loc[results["feature_set"] == "h337_refit"].iloc[0]
    candidates = results.loc[results["feature_set"] != "h337_refit"].copy()
    for col in [
        "validation_model_uplift_vs_best_fixed",
        "confirmation_model_uplift_vs_best_fixed",
        "validation_decision_auc",
        "confirmation_decision_auc",
    ]:
        candidates[col] = pd.to_numeric(candidates[col], errors="coerce")
    candidates["validation_uplift_delta_vs_h337_refit"] = (
        candidates["validation_model_uplift_vs_best_fixed"]
        - float(baseline["validation_model_uplift_vs_best_fixed"])
    )
    candidates["confirmation_uplift_delta_vs_h337_refit"] = (
        candidates["confirmation_model_uplift_vs_best_fixed"]
        - float(baseline["confirmation_model_uplift_vs_best_fixed"])
    )
    candidates["score"] = (
        candidates["validation_uplift_delta_vs_h337_refit"].fillna(-9.0)
        + candidates["confirmation_uplift_delta_vs_h337_refit"].fillna(-9.0)
        + 0.25 * candidates["validation_decision_auc"].fillna(0.0)
        + 0.25 * candidates["confirmation_decision_auc"].fillna(0.0)
    )
    best = candidates.sort_values("score", ascending=False).iloc[0]

    pass_condition = bool(
        best["validation_uplift_delta_vs_h337_refit"] >= MIN_VALIDATION_IMPROVEMENT
        and best["confirmation_uplift_delta_vs_h337_refit"] >= MIN_CONFIRMATION_IMPROVEMENT
        and best["validation_model_uplift_vs_best_fixed"] > 0.0
        and best["confirmation_model_uplift_vs_best_fixed"] > 0.0
        and (pd.isna(best["validation_decision_auc"]) or best["validation_decision_auc"] >= MIN_AUC)
        and (pd.isna(best["confirmation_decision_auc"]) or best["confirmation_decision_auc"] >= MIN_AUC)
    )
    mixed_condition = bool(
        not pass_condition
        and (
            best["validation_uplift_delta_vs_h337_refit"] > 0.0
            or best["confirmation_uplift_delta_vs_h337_refit"] > 0.0
        )
    )
    if pass_condition:
        verdict = "PASSED"
        branch_decision = (
            "Order-pressure state materially improves H337 in both validation and confirmation. "
            "Advance only to a stricter smart-exit integration audit, not live promotion."
        )
    elif mixed_condition:
        verdict = "MIXED"
        branch_decision = (
            "Order-pressure state improves at least one held-out phase but does not solve the H337/H339 smart-exit blocker. "
            "Keep as offline post-entry-state evidence only."
        )
    else:
        verdict = "FAILED"
        branch_decision = (
            "CafeF order-pressure state does not improve the H337 one-step hazard out of sample. "
            "Keep smart-exit ML parked until genuinely richer post-entry state/data exists."
        )
    return {
        "decision": verdict,
        "branch_decision": branch_decision,
        "best_order_feature_set": _json_safe(best.to_dict()),
        "h337_refit": _json_safe(baseline.to_dict()),
        "pass_condition": pass_condition,
        "mixed_condition": mixed_condition,
        "candidate_deltas": _json_safe(
            candidates[
                [
                    "feature_set",
                    "validation_uplift_delta_vs_h337_refit",
                    "confirmation_uplift_delta_vs_h337_refit",
                    "validation_model_uplift_vs_best_fixed",
                    "confirmation_model_uplift_vs_best_fixed",
                    "validation_decision_auc",
                    "confirmation_decision_auc",
                    "score",
                ]
            ].to_dict(orient="records")
        ),
    }


def main() -> None:
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    DETAILS_DIR.mkdir(parents=True, exist_ok=True)

    steps, h337_payload = _load_h337_step_rows()
    frame, coverage = _augment_with_order(steps)
    base_features = _feature_columns(frame)
    h211_params = _resolve_h211_params(str(H211_SUMMARY_PATH))

    result_rows: list[dict[str, object]] = []
    phase_frames: list[pd.DataFrame] = []
    policy_frames: list[pd.DataFrame] = []
    scored_frames: list[pd.DataFrame] = []
    for name, note, add_features in FEATURE_SET_SPECS:
        result, phase_results, policy, scored = _evaluate_feature_set(
            frame,
            name=name,
            note=note,
            base_features=base_features,
            add_features=list(add_features),
            h211_params=h211_params,
        )
        result_rows.append(result)
        phase_frames.append(phase_results)
        policy_frames.append(policy)
        scored_frames.append(
            scored[
                [
                    "feature_set",
                    "entry_id",
                    "ticker",
                    "decision_date",
                    "current_horizon",
                    "research_phase",
                    "wait_one_more_label",
                    "wait_one_more_prob",
                    "step_delta_utility",
                    "current_order_volume_ratio",
                    "entry_order_volume_ratio",
                    "order_volume_ratio_change_since_entry",
                ]
            ]
        )

    results = pd.DataFrame(result_rows)
    decision = _decide(results)
    phase_results_all = pd.concat(phase_frames, ignore_index=True)
    policies = pd.concat(policy_frames, ignore_index=True)
    scored_diagnostics = pd.concat(scored_frames, ignore_index=True)

    artifact_stem = f"{ts}_h355_order_pressure_step_hazard"
    results_path = OUT_DIR / f"{artifact_stem}_results.parquet"
    phase_results_path = OUT_DIR / f"{artifact_stem}_phase_results.parquet"
    policy_path = OUT_DIR / f"{artifact_stem}_policy_entries.parquet"
    scored_path = OUT_DIR / f"{artifact_stem}_scored_diagnostics.parquet"
    details_path = DETAILS_DIR / f"{artifact_stem}_details.json"

    details_records = results.copy()
    details_records["model_summary"] = details_records["model_summary"].map(_json_safe)
    details_records["phase_results"] = details_records["phase_results"].map(_json_safe)
    compact_results = results.drop(columns=["model_summary", "phase_results"])
    compact_results.to_parquet(results_path, index=False)
    phase_results_all.to_parquet(phase_results_path, index=False)
    policies.to_parquet(policy_path, index=False)
    scored_diagnostics.to_parquet(scored_path, index=False)

    summary = {
        **decision,
        "protocol": DEFAULT_PROTOCOL.describe(),
        "mechanics": {
            "source_h337_summary": str(H337_SUMMARY_PATH),
            "source_h337_ts": h337_payload.get("ts"),
            "step_rows": int(len(frame)),
            "entries": int(frame["entry_id"].nunique()),
            "base_feature_count": int(len(base_features)),
            "hold_threshold": float(HOLD_THRESHOLD),
            "order_coverage": coverage,
            "feature_sets": [
                {"name": name, "note": note, "added_features": list(add_features)}
                for name, note, add_features in FEATURE_SET_SPECS
            ],
        },
    }
    details = {
        "summary": _json_safe(summary),
        "results": _json_safe(details_records.to_dict(orient="records")),
        "phase_results": _json_safe(phase_results_all.to_dict(orient="records")),
    }
    details_path.write_text(json.dumps(details, indent=2, sort_keys=True), encoding="utf-8")

    summary_path = write_run_summary(
        ts=ts,
        mode="research_branch_order_pressure_step_hazard",
        name="h355_order_pressure_step_hazard",
        summary=summary,
        artifacts={
            "results": results_path,
            "phase_results": phase_results_path,
            "policy_entries": policy_path,
            "scored_diagnostics": scored_path,
            "details": details_path,
        },
        metadata={
            "hypothesis": (
                "Adding CafeF order-pressure post-entry state to the H337 decision rows can improve the "
                "one-step legal-exit hazard after H339 identified missing post-entry state as the blocker."
            ),
            "inputs": {
                "h337_summary": H337_SUMMARY_PATH,
                "order_stats": ORDER_STATS_PATH,
                "h211_summary": H211_SUMMARY_PATH,
            },
            "no_tuning_window": "2026+",
        },
    )
    print(summary_path)
    print(compact_results.to_string(index=False))


if __name__ == "__main__":
    main()
