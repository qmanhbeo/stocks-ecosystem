"""
H339: skip-aware step-value hazard for the H334 smart-exit oracle branch.

Question:
    Does the H338-implied fix help: replace the H337 immediate-next-step sign
    label with a skip-aware continuous utility target,
    max(later legal utility) - current utility?

Design:
    - consume the saved H337 step rows so the entry universe and state surface
      are fixed
    - add a skip-aware value target at each current legal decision horizon
    - train a dev-only regularized linear value model on the same H337 features
    - select the hold margin on dev only
    - compare the sequential policy against fixed horizons, H334 oracle, and
      the saved H337 policy on validation / confirmation
    - keep 2026+ out of the predictive decision

This is offline research. A pass would justify a stricter robustness follow-up;
it does not change the live sticky branch.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_DIR = ROOT / "analysis"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ANALYSIS_DIR) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_DIR))

from h337_replacement_aware_step_hazard import _feature_columns  # noqa: E402
from h338_step_hazard_failure_audit import _resolve_h337_artifacts  # noqa: E402
from src.run_summary import write_run_summary  # noqa: E402


DETAILS_DIR = ROOT / "artifacts" / "run_summaries"
OUT_DIR = ROOT / "artifacts" / "portfolio_baselines"
HORIZONS = (3, 5, 10, 15)
MARGIN_GRID = (-0.005, 0.0, 0.0025, 0.005, 0.01, 0.015, 0.02)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--h337-summary",
        type=str,
        default=str(DETAILS_DIR / "latest_research_branch_replacement_aware_step_hazard.json"),
    )
    parser.add_argument("--ridge-alpha", type=float, default=10.0)
    return parser.parse_args()


def _safe_spearman(a: pd.Series, b: pd.Series) -> float | None:
    clean = pd.DataFrame({"a": a, "b": b}).replace([np.inf, -np.inf], np.nan).dropna()
    if len(clean) < 20 or clean["a"].nunique() < 2 or clean["b"].nunique() < 2:
        return None
    stat = spearmanr(clean["a"], clean["b"])
    value = float(np.asarray(stat.statistic).flat[0])
    return value if np.isfinite(value) else None


def _rmse(a: pd.Series, b: pd.Series) -> float | None:
    clean = pd.DataFrame({"a": a, "b": b}).replace([np.inf, -np.inf], np.nan).dropna()
    if clean.empty:
        return None
    return float(np.sqrt(np.mean((clean["a"].to_numpy(dtype=np.float64) - clean["b"].to_numpy(dtype=np.float64)) ** 2)))


def _load_h337_phase_map(summary_path: Path) -> dict[str, dict[str, object]]:
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    rows = payload.get("summary", {}).get("phase_results", [])
    return {str(row["phase"]): row for row in rows if "phase" in row}


def _add_skip_value_targets(step_rows: pd.DataFrame) -> pd.DataFrame:
    rows = step_rows.copy()
    best_later_horizons: list[int | None] = []
    best_later_utilities: list[float] = []
    skip_value_deltas: list[float] = []

    for row in rows.itertuples(index=False):
        current_horizon = int(row.current_horizon)
        candidates: list[tuple[int, float]] = []
        for horizon in HORIZONS:
            if horizon <= current_horizon:
                continue
            available = bool(getattr(row, f"h{horizon}_available", False))
            utility = getattr(row, f"h{horizon}_utility", np.nan)
            if available and pd.notna(utility) and np.isfinite(float(utility)):
                candidates.append((int(horizon), float(utility)))
        if not candidates:
            best_later_horizons.append(None)
            best_later_utilities.append(np.nan)
            skip_value_deltas.append(np.nan)
            continue
        best_horizon, best_utility = max(candidates, key=lambda item: item[1])
        current_utility = float(row.current_utility)
        best_later_horizons.append(int(best_horizon))
        best_later_utilities.append(float(best_utility))
        skip_value_deltas.append(float(best_utility - current_utility))

    rows["best_later_horizon"] = best_later_horizons
    rows["best_later_utility"] = best_later_utilities
    rows["skip_value_delta"] = skip_value_deltas
    rows["skip_value_hold_label"] = (rows["skip_value_delta"] > 1e-12).astype(int)
    rows = rows.loc[rows["skip_value_delta"].notna()].copy()
    rows["best_later_horizon"] = rows["best_later_horizon"].astype(int)
    return rows


def _fit_value_model(
    rows: pd.DataFrame,
    feature_columns: list[str],
    *,
    ridge_alpha: float,
) -> tuple[Pipeline, pd.DataFrame, dict[str, object]]:
    work = rows.copy()
    train = work.loc[work["research_phase"] == "dev"].copy()
    if train.empty:
        raise ValueError("No dev rows available for H339")
    for column in feature_columns:
        work[column] = pd.to_numeric(work[column], errors="coerce")
        train[column] = pd.to_numeric(train[column], errors="coerce")

    pipeline = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            ("model", Ridge(alpha=float(ridge_alpha))),
        ]
    )
    pipeline.fit(train[feature_columns].to_numpy(dtype=np.float64), train["skip_value_delta"].to_numpy(dtype=np.float64))

    scored = work.copy()
    scored["pred_skip_value_delta"] = pipeline.predict(scored[feature_columns].to_numpy(dtype=np.float64))
    model = pipeline.named_steps["model"]
    coef = dict(zip(feature_columns, [float(x) for x in model.coef_]))
    strongest = sorted(coef.items(), key=lambda item: abs(item[1]), reverse=True)[:20]
    summary = {
        "model_type": "Pipeline(SimpleImputer, StandardScaler, Ridge)",
        "ridge_alpha": float(ridge_alpha),
        "feature_count": int(len(feature_columns)),
        "dev_rows": int(len(train)),
        "dev_target_mean": float(train["skip_value_delta"].mean()),
        "dev_positive_rate": float(train["skip_value_hold_label"].mean()),
        "strongest_standardized_coefficients": strongest,
    }
    return pipeline, scored, summary


def _policy_for_entries(
    scored: pd.DataFrame,
    *,
    margin: float,
    pred_col: str,
    horizon_col: str,
    utility_col: str,
    relative_col: str,
    last_pred_col: str,
) -> pd.DataFrame:
    needed_columns = [
        "entry_id",
        "ticker",
        "entry_signal_date",
        "research_phase",
        "current_horizon",
        pred_col,
        "oracle_horizon",
        "oracle_utility",
        "max_available_horizon",
    ]
    for horizon in HORIZONS:
        needed_columns.extend([f"h{horizon}_utility", f"h{horizon}_relative_return"])
    work = scored[needed_columns].sort_values(["entry_id", "current_horizon"], kind="mergesort")

    rows: list[dict[str, object]] = []
    active: dict[str, object] | None = None

    def emit(active_entry: dict[str, object]) -> None:
        first = active_entry["first"]
        chosen = int(active_entry["chosen"])
        relative_value = first.get(f"h{chosen}_relative_return", np.nan)
        rows.append(
            {
                "entry_id": int(active_entry["entry_id"]),
                "ticker": str(first["ticker"]),
                "entry_signal_date": pd.Timestamp(first["entry_signal_date"]),
                "research_phase": str(first["research_phase"]),
                horizon_col: int(chosen),
                utility_col: float(first[f"h{chosen}_utility"]),
                relative_col: float(relative_value) if pd.notna(relative_value) else np.nan,
                "oracle_horizon": int(first["oracle_horizon"]),
                "oracle_utility": float(first["oracle_utility"]),
                "h3_utility": float(first["h3_utility"]) if pd.notna(first["h3_utility"]) else np.nan,
                "h5_utility": float(first["h5_utility"]) if pd.notna(first["h5_utility"]) else np.nan,
                "h10_utility": float(first["h10_utility"]) if pd.notna(first["h10_utility"]) else np.nan,
                "h15_utility": float(first["h15_utility"]) if pd.notna(first["h15_utility"]) else np.nan,
                "max_available_horizon": int(first["max_available_horizon"]),
                last_pred_col: active_entry["last_pred"],
                "stop_horizon": active_entry["stop_horizon"],
            }
        )

    for record in work.to_dict(orient="records"):
        entry_id = int(record["entry_id"])
        if active is None or entry_id != int(active["entry_id"]):
            if active is not None:
                emit(active)
            active = {
                "entry_id": entry_id,
                "first": record,
                "chosen": int(record["max_available_horizon"]),
                "last_pred": np.nan,
                "stop_horizon": None,
                "stopped": False,
            }
        if not bool(active["stopped"]):
            pred_value = float(record[pred_col])
            active["last_pred"] = pred_value
            if pred_value <= float(margin):
                active["chosen"] = int(record["current_horizon"])
                active["stop_horizon"] = int(record["current_horizon"])
                active["stopped"] = True

    if active is not None:
        emit(active)
    return pd.DataFrame(rows)


def _summarize_policy(
    policy: pd.DataFrame,
    *,
    margin: float,
    horizon_col: str,
    utility_col: str,
    h337_phase_map: dict[str, dict[str, object]],
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for phase in ("dev", "validation", "confirmation"):
        sub = policy.loc[policy["research_phase"] == phase].copy()
        if sub.empty:
            rows.append({"phase": phase, "entries": 0, "margin": float(margin)})
            continue
        fixed_means = {
            h: float(sub[f"h{h}_utility"].mean())
            for h in HORIZONS
            if f"h{h}_utility" in sub.columns and sub[f"h{h}_utility"].notna().any()
        }
        best_fixed_horizon = max(fixed_means, key=lambda h: fixed_means[h])
        best_fixed_utility = float(fixed_means[best_fixed_horizon])
        oracle_utility = float(sub["oracle_utility"].mean())
        model_utility = float(sub[utility_col].mean())
        oracle_uplift = float(oracle_utility - best_fixed_utility)
        model_uplift = float(model_utility - best_fixed_utility)
        h337_row = h337_phase_map.get(phase, {})
        h337_uplift = h337_row.get("model_uplift_vs_best_fixed")
        h337_utility = h337_row.get("model_utility_mean")
        h337_recovered = h337_row.get("oracle_uplift_recovered_share")
        rows.append(
            {
                "phase": phase,
                "margin": float(margin),
                "entries": int(len(sub)),
                "best_fixed_horizon": int(best_fixed_horizon),
                "best_fixed_utility_mean": best_fixed_utility,
                "model_utility_mean": model_utility,
                "oracle_utility_mean": oracle_utility,
                "model_uplift_vs_best_fixed": model_uplift,
                "oracle_uplift_vs_best_fixed": oracle_uplift,
                "oracle_uplift_recovered_share": float(model_uplift / oracle_uplift) if abs(oracle_uplift) > 1e-12 else None,
                "h337_model_utility_mean": float(h337_utility) if h337_utility is not None else np.nan,
                "h337_model_uplift_vs_best_fixed": float(h337_uplift) if h337_uplift is not None else np.nan,
                "h337_oracle_uplift_recovered_share": float(h337_recovered) if h337_recovered is not None else np.nan,
                "model_delta_vs_h337": float(model_utility - float(h337_utility)) if h337_utility is not None else np.nan,
                "model_uplift_delta_vs_h337": float(model_uplift - float(h337_uplift)) if h337_uplift is not None else np.nan,
                "recovered_share_delta_vs_h337": (
                    float(model_uplift / oracle_uplift) - float(h337_recovered)
                    if abs(oracle_uplift) > 1e-12 and h337_recovered is not None
                    else np.nan
                ),
                "model_not_best_fixed_rate": float((sub[horizon_col] != int(best_fixed_horizon)).mean()),
                "model_matches_oracle_rate": float((sub[horizon_col] == sub["oracle_horizon"]).mean()),
                "choice_rate_h3": float((sub[horizon_col] == 3).mean()),
                "choice_rate_h5": float((sub[horizon_col] == 5).mean()),
                "choice_rate_h10": float((sub[horizon_col] == 10).mean()),
                "choice_rate_h15": float((sub[horizon_col] == 15).mean()),
            }
        )
    return pd.DataFrame(rows)


def _margin_sweep(scored: pd.DataFrame, h337_phase_map: dict[str, dict[str, object]]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for margin in MARGIN_GRID:
        policy = _policy_for_entries(
            scored,
            margin=float(margin),
            pred_col="pred_skip_value_delta",
            horizon_col="model_horizon",
            utility_col="model_utility",
            relative_col="model_relative_return",
            last_pred_col="last_pred_skip_value_delta",
        )
        summary = _summarize_policy(
            policy,
            margin=float(margin),
            horizon_col="model_horizon",
            utility_col="model_utility",
            h337_phase_map=h337_phase_map,
        )
        rows.extend(summary.to_dict(orient="records"))
    return pd.DataFrame(rows)


def _select_margin(margin_grid: pd.DataFrame) -> float:
    dev = margin_grid.loc[margin_grid["phase"] == "dev"].copy()
    if dev.empty:
        raise ValueError("No dev margin rows available for H339")
    selected = dev.sort_values(["model_utility_mean", "margin"], ascending=[False, False]).iloc[0]
    return float(selected["margin"])


def _prediction_diagnostics(scored: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for phase, sub in scored.groupby("research_phase", sort=True):
        rows.append(
            {
                "phase": phase,
                "current_horizon": None,
                "rows": int(len(sub)),
                "target_mean": float(sub["skip_value_delta"].mean()),
                "target_positive_rate": float(sub["skip_value_hold_label"].mean()),
                "pred_mean": float(sub["pred_skip_value_delta"].mean()),
                "pred_target_spearman": _safe_spearman(sub["pred_skip_value_delta"], sub["skip_value_delta"]),
                "pred_target_rmse": _rmse(sub["pred_skip_value_delta"], sub["skip_value_delta"]),
            }
        )
        for horizon, hh in sub.groupby("current_horizon", sort=True):
            rows.append(
                {
                    "phase": phase,
                    "current_horizon": int(horizon),
                    "rows": int(len(hh)),
                    "target_mean": float(hh["skip_value_delta"].mean()),
                    "target_positive_rate": float(hh["skip_value_hold_label"].mean()),
                    "pred_mean": float(hh["pred_skip_value_delta"].mean()),
                    "pred_target_spearman": _safe_spearman(hh["pred_skip_value_delta"], hh["skip_value_delta"]),
                    "pred_target_rmse": _rmse(hh["pred_skip_value_delta"], hh["skip_value_delta"]),
                }
            )
    return pd.DataFrame(rows)


def _decide(phase_results: pd.DataFrame) -> dict[str, object]:
    by_phase = {row["phase"]: row for row in phase_results.to_dict(orient="records")}
    validation = by_phase.get("validation", {})
    confirmation = by_phase.get("confirmation", {})

    validation_uplift = validation.get("model_uplift_vs_best_fixed")
    confirmation_uplift = confirmation.get("model_uplift_vs_best_fixed")
    validation_recovery = validation.get("oracle_uplift_recovered_share")
    confirmation_recovery = confirmation.get("oracle_uplift_recovered_share")
    validation_delta_h337 = validation.get("model_uplift_delta_vs_h337")
    confirmation_delta_h337 = confirmation.get("model_uplift_delta_vs_h337")
    validation_recovery_delta = validation.get("recovered_share_delta_vs_h337")
    confirmation_recovery_delta = confirmation.get("recovered_share_delta_vs_h337")

    def finite(value: object) -> bool:
        try:
            return np.isfinite(float(value))
        except (TypeError, ValueError):
            return False

    pass_condition = bool(
        finite(validation_uplift)
        and finite(confirmation_uplift)
        and finite(validation_recovery)
        and finite(confirmation_recovery)
        and finite(validation_delta_h337)
        and finite(confirmation_delta_h337)
        and float(validation_uplift) >= 0.005
        and float(confirmation_uplift) >= 0.005
        and float(validation_recovery) >= 0.10
        and float(confirmation_recovery) >= 0.10
        and float(validation_delta_h337) > 0.0
        and float(confirmation_delta_h337) > 0.0
    )
    mixed_condition = bool(
        finite(validation_uplift)
        and finite(confirmation_uplift)
        and float(validation_uplift) > 0.0
        and float(confirmation_uplift) > 0.0
        and (
            (finite(validation_delta_h337) and float(validation_delta_h337) > 0.0)
            or (finite(confirmation_delta_h337) and float(confirmation_delta_h337) > 0.0)
            or (finite(validation_recovery_delta) and float(validation_recovery_delta) > 0.0)
            or (finite(confirmation_recovery_delta) and float(confirmation_recovery_delta) > 0.0)
        )
    )

    if pass_condition:
        verdict = "PASSED"
        branch_decision = (
            "The skip-aware utility target beat fixed 3d and H337 in validation and confirmation with material oracle "
            "recovery. Advance to robustness checks before any integration."
        )
    elif mixed_condition:
        verdict = "MIXED"
        branch_decision = (
            "The skip-aware utility target improved at least one H337 comparison while staying positive out of sample, "
            "but it did not clear the material smart-exit bar. Keep as offline evidence only."
        )
    else:
        verdict = "FAILED"
        branch_decision = (
            "The skip-aware utility target did not rescue the current-state daily smart-exit branch. Do not continue by "
            "retuning margins; the next distinct fix needs better post-entry state/data or a materially different model contract."
        )

    return {
        "verdict": verdict,
        "branch_decision": branch_decision,
        "pass_condition": pass_condition,
        "mixed_condition": mixed_condition,
        "validation_model_uplift_vs_best_fixed": validation_uplift,
        "confirmation_model_uplift_vs_best_fixed": confirmation_uplift,
        "validation_oracle_uplift_recovered_share": validation_recovery,
        "confirmation_oracle_uplift_recovered_share": confirmation_recovery,
        "validation_model_uplift_delta_vs_h337": validation_delta_h337,
        "confirmation_model_uplift_delta_vs_h337": confirmation_delta_h337,
        "validation_recovered_share_delta_vs_h337": validation_recovery_delta,
        "confirmation_recovered_share_delta_vs_h337": confirmation_recovery_delta,
    }


def main() -> int:
    args = parse_args()
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    DETAILS_DIR.mkdir(parents=True, exist_ok=True)

    h337_artifacts = _resolve_h337_artifacts(args.h337_summary)
    h337_phase_map = _load_h337_phase_map(h337_artifacts["summary"])
    base_rows = pd.read_parquet(h337_artifacts["step_rows"]).copy()
    base_rows["entry_signal_date"] = pd.to_datetime(base_rows["entry_signal_date"], errors="coerce")
    base_rows["decision_date"] = pd.to_datetime(base_rows["decision_date"], errors="coerce")
    if (base_rows["entry_signal_date"].dt.year >= 2026).any():
        raise ValueError("H339 refuses to train/evaluate on 2026+ rows")

    target_rows = _add_skip_value_targets(base_rows)
    feature_columns = _feature_columns(target_rows)
    _, scored, model_summary = _fit_value_model(target_rows, feature_columns, ridge_alpha=float(args.ridge_alpha))
    diagnostics = _prediction_diagnostics(scored)

    margin_grid = _margin_sweep(scored, h337_phase_map)
    selected_margin = _select_margin(margin_grid)
    policy = _policy_for_entries(
        scored,
        margin=selected_margin,
        pred_col="pred_skip_value_delta",
        horizon_col="model_horizon",
        utility_col="model_utility",
        relative_col="model_relative_return",
        last_pred_col="last_pred_skip_value_delta",
    )
    phase_results = _summarize_policy(
        policy,
        margin=selected_margin,
        horizon_col="model_horizon",
        utility_col="model_utility",
        h337_phase_map=h337_phase_map,
    )
    decision = _decide(phase_results)

    scored["perfect_skip_delta"] = scored["skip_value_delta"]
    skip_oracle_policy = _policy_for_entries(
        scored,
        margin=0.0,
        pred_col="perfect_skip_delta",
        horizon_col="skip_oracle_horizon",
        utility_col="skip_oracle_utility",
        relative_col="skip_oracle_relative_return",
        last_pred_col="last_true_skip_value_delta",
    )
    skip_oracle_summary = _summarize_policy(
        skip_oracle_policy,
        margin=0.0,
        horizon_col="skip_oracle_horizon",
        utility_col="skip_oracle_utility",
        h337_phase_map=h337_phase_map,
    )

    step_rows_path = OUT_DIR / f"{ts}_h339_skip_aware_step_value_hazard_step_rows.parquet"
    policy_path = OUT_DIR / f"{ts}_h339_skip_aware_step_value_hazard_policy_entries.parquet"
    margin_grid_path = OUT_DIR / f"{ts}_h339_skip_aware_step_value_hazard_margin_grid.parquet"
    phase_results_path = OUT_DIR / f"{ts}_h339_skip_aware_step_value_hazard_phase_results.parquet"
    diagnostics_path = OUT_DIR / f"{ts}_h339_skip_aware_step_value_hazard_prediction_diagnostics.parquet"
    skip_oracle_path = OUT_DIR / f"{ts}_h339_skip_aware_step_value_hazard_skip_oracle_entries.parquet"
    skip_oracle_summary_path = OUT_DIR / f"{ts}_h339_skip_aware_step_value_hazard_skip_oracle_summary.parquet"
    details_path = DETAILS_DIR / f"{ts}_h339_skip_aware_step_value_hazard_details.json"

    scored.to_parquet(step_rows_path, index=False)
    policy.to_parquet(policy_path, index=False)
    margin_grid.to_parquet(margin_grid_path, index=False)
    phase_results.to_parquet(phase_results_path, index=False)
    diagnostics.to_parquet(diagnostics_path, index=False)
    skip_oracle_policy.to_parquet(skip_oracle_path, index=False)
    skip_oracle_summary.to_parquet(skip_oracle_summary_path, index=False)

    target_summary = {
        "step_rows": int(len(scored)),
        "policy_entries": int(policy["entry_id"].nunique()),
        "feature_count": int(len(feature_columns)),
        "selected_margin": float(selected_margin),
        "margin_grid": list(MARGIN_GRID),
        "h337_summary": str(h337_artifacts["summary"]),
        "h337_step_rows": str(h337_artifacts["step_rows"]),
        "skip_hold_positive_rate": float(scored["skip_value_hold_label"].mean()),
        "skip_value_delta_mean": float(scored["skip_value_delta"].mean()),
        "perfect_skip_oracle_validation_recovered_share": float(
            skip_oracle_summary.loc[
                skip_oracle_summary["phase"] == "validation",
                "oracle_uplift_recovered_share",
            ].iloc[0]
        ),
        "perfect_skip_oracle_confirmation_recovered_share": float(
            skip_oracle_summary.loc[
                skip_oracle_summary["phase"] == "confirmation",
                "oracle_uplift_recovered_share",
            ].iloc[0]
        ),
    }

    summary = {
        **decision,
        "mechanics": target_summary,
        "model": model_summary,
        "prediction_diagnostics": diagnostics.to_dict(orient="records"),
        "phase_results": phase_results.to_dict(orient="records"),
        "skip_oracle_phase_results": skip_oracle_summary.to_dict(orient="records"),
        "dev_margin_grid": margin_grid.loc[margin_grid["phase"] == "dev"].to_dict(orient="records"),
    }
    details_path.write_text(json.dumps(summary, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")

    summary_path = write_run_summary(
        ts=ts,
        mode="research_branch_skip_aware_step_value_hazard",
        name="h339_skip_aware_step_value_hazard",
        summary=summary,
        artifacts={
            "step_rows": step_rows_path,
            "policy_entries": policy_path,
            "margin_grid": margin_grid_path,
            "phase_results": phase_results_path,
            "prediction_diagnostics": diagnostics_path,
            "skip_oracle_entries": skip_oracle_path,
            "skip_oracle_summary": skip_oracle_summary_path,
            "details": details_path,
        },
        metadata={
            "hypothesis": (
                "A skip-aware continuous step-value target can remove the H337 skip-over ceiling and recover more H334 "
                "legal-exit oracle uplift than the H337 immediate-next-step classifier."
            ),
            "no_tuning_window": "2026+",
            "comparison_baseline": "H337 replacement-aware step hazard",
        },
    )

    display_cols = [
        "phase",
        "entries",
        "margin",
        "best_fixed_horizon",
        "model_utility_mean",
        "best_fixed_utility_mean",
        "model_uplift_vs_best_fixed",
        "model_uplift_delta_vs_h337",
        "oracle_uplift_recovered_share",
        "model_not_best_fixed_rate",
    ]
    print("H339 skip-aware step-value hazard")
    print("=" * 72)
    print(f"verdict: {decision['verdict']}")
    print(f"branch decision: {decision['branch_decision']}")
    print(phase_results[display_cols].to_string(index=False))
    print(f"summary: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
