"""
H338: failure audit for H337 replacement-aware step-hazard.

Question:
    Why did H337 stay mixed instead of clearing the smart-exit integration bar?

Design:
    - consume the saved H337 step-row artifact rather than rerunning the branch
    - test four competing failure hypotheses:
      1. the one-step label is itself too myopic relative to the H334 oracle
      2. the fixed 0.50 threshold is the main blocker
      3. the sign label is misaligned with utility magnitude
      4. a simple feature-family omission is the main blocker
    - keep all tuning dev-only
    - do not touch 2026+

This is a diagnostic audit, not a new tradable policy.
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
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_DIR = ROOT / "analysis"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ANALYSIS_DIR) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_DIR))

from h335_exit_mdp_lite_distillation import ACTIVATION_FEATURES, SIGNAL_FEATURES  # noqa: E402
from h337_replacement_aware_step_hazard import EVENT_FEATURES  # noqa: E402
from src.run_summary import write_run_summary  # noqa: E402


DETAILS_DIR = ROOT / "artifacts" / "run_summaries"
OUT_DIR = ROOT / "artifacts" / "portfolio_baselines"
HORIZONS = (3, 5, 10, 15)
THRESHOLD_GRID = (0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--h337-summary",
        type=str,
        default=str(DETAILS_DIR / "latest_research_branch_replacement_aware_step_hazard.json"),
    )
    return parser.parse_args()


def _resolve_h337_artifacts(summary_arg: str) -> dict[str, Path]:
    path = Path(summary_arg)
    if not path.exists():
        raise FileNotFoundError(f"missing H337 summary: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    artifacts = payload.get("artifacts", {})
    required = ["step_rows", "policy_entries", "h211_policy_entries", "phase_results"]
    missing = [key for key in required if key not in artifacts]
    if missing:
        raise ValueError(f"H337 summary missing artifacts: {missing}")
    out = {"summary": path}
    for key in required:
        value = Path(str(artifacts[key]))
        out[key] = value if value.is_absolute() else ROOT / value
    return out


def _safe_spearman(a: pd.Series, b: pd.Series) -> float | None:
    clean = pd.DataFrame({"a": a, "b": b}).replace([np.inf, -np.inf], np.nan).dropna()
    if len(clean) < 20 or clean["a"].nunique() < 2 or clean["b"].nunique() < 2:
        return None
    stat = spearmanr(clean["a"], clean["b"])
    value = float(np.asarray(stat.statistic).flat[0])
    return value if np.isfinite(value) else None


def _auc(frame: pd.DataFrame, prob_col: str) -> float | None:
    clean = frame[["wait_one_more_label", prob_col]].replace([np.inf, -np.inf], np.nan).dropna()
    if clean.empty or clean["wait_one_more_label"].nunique() < 2:
        return None
    return float(roc_auc_score(clean["wait_one_more_label"].astype(int), clean[prob_col].astype(float)))


def _policy_from_probabilities(
    scored: pd.DataFrame,
    *,
    prob_col: str,
    threshold: float,
    horizon_col: str = "chosen_horizon",
    utility_col: str = "policy_utility",
    relative_col: str = "policy_relative_return",
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for entry_id, frame in scored.groupby("entry_id", sort=False):
        frame = frame.sort_values("current_horizon")
        first = frame.iloc[0]
        chosen = int(first["max_available_horizon"])
        last_prob = None
        for row in frame.itertuples(index=False):
            prob = float(getattr(row, prob_col))
            last_prob = prob
            if prob < float(threshold):
                chosen = int(row.current_horizon)
                break
        rows.append(
            {
                "entry_id": int(entry_id),
                "ticker": str(first["ticker"]),
                "entry_signal_date": pd.Timestamp(first["entry_signal_date"]),
                "research_phase": str(first["research_phase"]),
                horizon_col: int(chosen),
                utility_col: float(first[f"h{chosen}_utility"]),
                relative_col: float(first[f"h{chosen}_relative_return"]),
                "oracle_horizon": int(first["oracle_horizon"]),
                "oracle_utility": float(first["oracle_utility"]),
                "h3_utility": float(first["h3_utility"]),
                "h5_utility": float(first["h5_utility"]) if pd.notna(first["h5_utility"]) else np.nan,
                "h10_utility": float(first["h10_utility"]) if pd.notna(first["h10_utility"]) else np.nan,
                "h15_utility": float(first["h15_utility"]) if pd.notna(first["h15_utility"]) else np.nan,
                "last_prob": last_prob,
            }
        )
    return pd.DataFrame(rows)


def _policy_from_true_step_labels(scored: pd.DataFrame) -> pd.DataFrame:
    scored = scored.copy()
    scored["perfect_step_prob"] = scored["wait_one_more_label"].astype(float)
    return _policy_from_probabilities(
        scored,
        prob_col="perfect_step_prob",
        threshold=0.5,
        horizon_col="step_oracle_horizon",
        utility_col="step_oracle_utility",
        relative_col="step_oracle_relative_return",
    )


def _summarize_policy(
    policy: pd.DataFrame,
    *,
    horizon_col: str,
    utility_col: str,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for phase in ("dev", "validation", "confirmation"):
        sub = policy.loc[policy["research_phase"] == phase].copy()
        if sub.empty:
            rows.append({"phase": phase, "entries": 0})
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
        rows.append(
            {
                "phase": phase,
                "entries": int(len(sub)),
                "best_fixed_horizon": int(best_fixed_horizon),
                "best_fixed_utility_mean": best_fixed_utility,
                "policy_utility_mean": model_utility,
                "oracle_utility_mean": oracle_utility,
                "policy_uplift_vs_best_fixed": model_uplift,
                "oracle_uplift_vs_best_fixed": oracle_uplift,
                "oracle_uplift_recovered_share": float(model_uplift / oracle_uplift) if abs(oracle_uplift) > 1e-12 else None,
                "policy_not_best_fixed_rate": float((sub[horizon_col] != int(best_fixed_horizon)).mean()),
                "policy_matches_oracle_rate": float((sub[horizon_col] == sub["oracle_horizon"]).mean()),
            }
        )
    return pd.DataFrame(rows)


def _threshold_sweep(scored: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for threshold in THRESHOLD_GRID:
        policy = _policy_from_probabilities(scored, prob_col="wait_one_more_prob", threshold=float(threshold))
        summary = _summarize_policy(policy, horizon_col="chosen_horizon", utility_col="policy_utility")
        for row in summary.to_dict(orient="records"):
            rows.append({"threshold": float(threshold), **row})
    return pd.DataFrame(rows)


def _feature_sets(frame: pd.DataFrame) -> dict[str, list[str]]:
    core = [
        "current_horizon",
        "horizon_eq_3",
        "horizon_eq_5",
        "horizon_eq_10",
        "current_close_return",
        "path_mae_so_far",
        "path_mfe_so_far",
        "drawdown_from_peak",
        "underwater_days_since_entry",
        "current_score__full_library",
        "current_full_library_rank",
        "current_full_library_rank_pct",
        "entry_score__full_library",
        "entry_full_library_rank",
        "entry_full_library_rank_pct",
        "full_score_drop_since_entry",
        "full_score_change_since_entry",
        "full_rank_change_since_entry",
        "full_rank_pct_change_since_entry",
    ]
    replacement = [
        "current_buyable_best_score",
        "current_buyable_top5_cutoff_score",
        "current_score_gap_to_buyable_best",
        "current_score_gap_to_buyable_top5_cutoff",
    ]
    signal = [f"current_{column}" for column in SIGNAL_FEATURES] + [f"entry_{column}" for column in SIGNAL_FEATURES]
    activation = [f"current_{column}" for column in ACTIVATION_FEATURES]
    event = [f"current_{column}" for column in EVENT_FEATURES]

    sets = {
        "core_only": core,
        "core_plus_replacement": [*core, *replacement],
        "full_no_event": [*core, *replacement, *signal, *activation],
        "full_no_replacement": [*core, *signal, *activation, *event],
        "full": [*core, *replacement, *signal, *activation, *event],
    }
    return {
        name: [column for column in columns if column in frame.columns]
        for name, columns in sets.items()
    }


def _fit_probabilities(frame: pd.DataFrame, feature_columns: list[str], prob_col: str) -> tuple[pd.DataFrame, dict[str, object]]:
    work = frame.copy()
    train = work.loc[work["research_phase"] == "dev"].copy()
    for column in feature_columns:
        work[column] = pd.to_numeric(work[column], errors="coerce")
        train[column] = pd.to_numeric(train[column], errors="coerce")
    pipeline = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            (
                "model",
                LogisticRegression(
                    class_weight="balanced",
                    max_iter=2000,
                    random_state=0,
                ),
            ),
        ]
    )
    pipeline.fit(train[feature_columns].to_numpy(dtype=np.float64), train["wait_one_more_label"].astype(int).to_numpy())
    work[prob_col] = pipeline.predict_proba(work[feature_columns].to_numpy(dtype=np.float64))[:, 1]
    return work, {
        "feature_count": int(len(feature_columns)),
        "dev_rows": int(len(train)),
        "dev_auc": _auc(work.loc[work["research_phase"] == "dev"], prob_col),
        "validation_auc": _auc(work.loc[work["research_phase"] == "validation"], prob_col),
        "confirmation_auc": _auc(work.loc[work["research_phase"] == "confirmation"], prob_col),
    }


def _ablation_audit(step_rows: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for name, columns in _feature_sets(step_rows).items():
        scored, diag = _fit_probabilities(step_rows, columns, prob_col=f"{name}_prob")
        policy = _policy_from_probabilities(scored, prob_col=f"{name}_prob", threshold=0.5)
        summary = _summarize_policy(policy, horizon_col="chosen_horizon", utility_col="policy_utility")
        by_phase = {row["phase"]: row for row in summary.to_dict(orient="records")}
        rows.append(
            {
                "model_name": name,
                "feature_count": int(len(columns)),
                "dev_auc": diag["dev_auc"],
                "validation_auc": diag["validation_auc"],
                "confirmation_auc": diag["confirmation_auc"],
                "validation_uplift_vs_best_fixed": by_phase.get("validation", {}).get("policy_uplift_vs_best_fixed"),
                "confirmation_uplift_vs_best_fixed": by_phase.get("confirmation", {}).get("policy_uplift_vs_best_fixed"),
                "validation_recovered_share": by_phase.get("validation", {}).get("oracle_uplift_recovered_share"),
                "confirmation_recovered_share": by_phase.get("confirmation", {}).get("oracle_uplift_recovered_share"),
            }
        )
    return pd.DataFrame(rows)


def _skip_over_conflicts(step_rows: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, object]] = []
    entry_rows: list[dict[str, object]] = []
    work = step_rows.copy()
    work["skip_over_conflict"] = (work["wait_one_more_label"] == 0) & (work["oracle_horizon"] > work["current_horizon"])
    work["oracle_gain_vs_current"] = work["oracle_utility"] - work["current_utility"]
    for (phase, horizon), sub in work.groupby(["research_phase", "current_horizon"], sort=True):
        rows.append(
            {
                "phase": phase,
                "current_horizon": int(horizon),
                "rows": int(len(sub)),
                "skip_over_rate": float(sub["skip_over_conflict"].mean()),
                "skip_over_gain_mean": float(sub.loc[sub["skip_over_conflict"], "oracle_gain_vs_current"].mean())
                if sub["skip_over_conflict"].any()
                else np.nan,
            }
        )
    per_entry = (
        work.groupby(["research_phase", "entry_id"], sort=False)["skip_over_conflict"]
        .any()
        .rename("entry_has_skip_over_conflict")
        .reset_index()
    )
    for phase, sub in per_entry.groupby("research_phase", sort=True):
        entry_rows.append(
            {
                "phase": phase,
                "entries": int(len(sub)),
                "entry_skip_over_rate": float(sub["entry_has_skip_over_conflict"].mean()),
            }
        )
    return pd.DataFrame(rows), pd.DataFrame(entry_rows)


def _utility_alignment(step_rows: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for phase, sub in step_rows.groupby("research_phase", sort=True):
        rows.append(
            {
                "phase": phase,
                "utility_spearman": _safe_spearman(sub["wait_one_more_prob"], sub["step_delta_utility"]),
                "mean_step_delta_utility": float(sub["step_delta_utility"].mean()),
                "positive_rate": float(sub["wait_one_more_label"].mean()),
            }
        )
        for horizon, hh in sub.groupby("current_horizon", sort=True):
            rows.append(
                {
                    "phase": phase,
                    "current_horizon": int(horizon),
                    "utility_spearman": _safe_spearman(hh["wait_one_more_prob"], hh["step_delta_utility"]),
                    "mean_step_delta_utility": float(hh["step_delta_utility"].mean()),
                    "positive_rate": float(hh["wait_one_more_label"].mean()),
                    "positive_step_delta_mean": float(hh.loc[hh["wait_one_more_label"] == 1, "step_delta_utility"].mean())
                    if (hh["wait_one_more_label"] == 1).any()
                    else np.nan,
                    "negative_step_delta_mean": float(hh.loc[hh["wait_one_more_label"] == 0, "step_delta_utility"].mean())
                    if (hh["wait_one_more_label"] == 0).any()
                    else np.nan,
                }
            )
    return pd.DataFrame(rows)


def _decide_root_cause(
    *,
    step_oracle_summary: pd.DataFrame,
    threshold_sweep: pd.DataFrame,
    ablation: pd.DataFrame,
    skip_rows: pd.DataFrame,
    skip_entries: pd.DataFrame,
    utility_alignment: pd.DataFrame,
) -> dict[str, object]:
    step_by_phase = {row["phase"]: row for row in step_oracle_summary.to_dict(orient="records")}
    val_step_share = float(step_by_phase.get("validation", {}).get("oracle_uplift_recovered_share") or np.nan)
    conf_step_share = float(step_by_phase.get("confirmation", {}).get("oracle_uplift_recovered_share") or np.nan)

    dev_grid = threshold_sweep.loc[threshold_sweep["phase"] == "dev"].copy()
    best_threshold = float(dev_grid.sort_values(["policy_utility_mean", "threshold"], ascending=[False, True]).iloc[0]["threshold"])
    best_dev_rows = threshold_sweep.loc[threshold_sweep["threshold"] == best_threshold].copy()
    best_dev_by_phase = {row["phase"]: row for row in best_dev_rows.to_dict(orient="records")}
    val_best_thresh = float(best_dev_by_phase.get("validation", {}).get("policy_uplift_vs_best_fixed") or np.nan)
    conf_best_thresh = float(best_dev_by_phase.get("confirmation", {}).get("policy_uplift_vs_best_fixed") or np.nan)

    best_ablation = ablation.sort_values(
        ["validation_uplift_vs_best_fixed", "confirmation_uplift_vs_best_fixed"],
        ascending=[False, False],
    ).iloc[0]

    phase_alignment = utility_alignment.loc[utility_alignment["phase"].notna() & utility_alignment["current_horizon"].isna()].copy()
    align_by_phase = {row["phase"]: row for row in phase_alignment.to_dict(orient="records")}
    val_utility_rho = float(align_by_phase.get("validation", {}).get("utility_spearman") or np.nan)
    conf_utility_rho = float(align_by_phase.get("confirmation", {}).get("utility_spearman") or np.nan)

    skip_entry_by_phase = {row["phase"]: row for row in skip_entries.to_dict(orient="records")}
    val_skip_entry = float(skip_entry_by_phase.get("validation", {}).get("entry_skip_over_rate") or np.nan)
    conf_skip_entry = float(skip_entry_by_phase.get("confirmation", {}).get("entry_skip_over_rate") or np.nan)

    label_bottleneck = bool(
        np.isfinite(val_step_share)
        and np.isfinite(conf_step_share)
        and np.isfinite(val_skip_entry)
        and np.isfinite(conf_skip_entry)
        and val_step_share < 0.70
        and conf_step_share < 0.70
        and val_skip_entry >= 0.10
        and conf_skip_entry >= 0.10
    )
    threshold_issue = bool(
        np.isfinite(val_best_thresh)
        and np.isfinite(conf_best_thresh)
        and val_best_thresh >= 0.005
        and conf_best_thresh >= 0.005
    )
    feature_family_issue = bool(
        float(best_ablation["validation_uplift_vs_best_fixed"] or -np.inf) >= 0.005
        and float(best_ablation["confirmation_uplift_vs_best_fixed"] or -np.inf) >= 0.005
    )
    utility_mismatch = bool(
        np.isfinite(val_utility_rho)
        and np.isfinite(conf_utility_rho)
        and val_utility_rho < 0.10
        and conf_utility_rho < 0.10
    )

    if label_bottleneck and not threshold_issue and not feature_family_issue:
        verdict = "PASSED"
        root_cause = "myopic_step_label"
        branch_decision = (
            "The main blocker is the H337 label contract itself: even a perfect one-step classifier cannot fully recover "
            "the H334 oracle because skip-over states require looking beyond the immediate next legal step. Threshold tuning "
            "and simple feature-family swaps do not rescue the branch."
        )
    elif not threshold_issue and not feature_family_issue and utility_mismatch:
        verdict = "PASSED"
        root_cause = "sparse_utility_localization"
        branch_decision = (
            "The main blocker is that the current state only weakly ranks utility magnitude. The branch is not mainly failing "
            "because of threshold choice or a missing simple feature family; it is failing because rare high-value continuation "
            "pockets are not well localized on the current daily stack."
        )
    else:
        verdict = "MIXED"
        root_cause = "partial_identification"
        branch_decision = (
            "The audit narrowed the blockers but did not isolate a single dominant cause cleanly enough. The branch should stay "
            "inside diagnostic narrowing rather than claiming an exact solved reason."
        )

    return {
        "verdict": verdict,
        "root_cause": root_cause,
        "branch_decision": branch_decision,
        "label_bottleneck": label_bottleneck,
        "threshold_issue": threshold_issue,
        "feature_family_issue": feature_family_issue,
        "utility_mismatch": utility_mismatch,
        "dev_selected_threshold": best_threshold,
        "dev_selected_threshold_validation_uplift": val_best_thresh,
        "dev_selected_threshold_confirmation_uplift": conf_best_thresh,
        "best_ablation_model": str(best_ablation["model_name"]),
        "best_ablation_validation_uplift": float(best_ablation["validation_uplift_vs_best_fixed"]),
        "best_ablation_confirmation_uplift": float(best_ablation["confirmation_uplift_vs_best_fixed"]),
        "validation_step_oracle_recovered_share": val_step_share,
        "confirmation_step_oracle_recovered_share": conf_step_share,
        "validation_skip_over_entry_rate": val_skip_entry,
        "confirmation_skip_over_entry_rate": conf_skip_entry,
        "validation_utility_spearman": val_utility_rho,
        "confirmation_utility_spearman": conf_utility_rho,
    }


def main() -> int:
    args = parse_args()
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    DETAILS_DIR.mkdir(parents=True, exist_ok=True)

    h337_artifacts = _resolve_h337_artifacts(args.h337_summary)
    step_rows = pd.read_parquet(h337_artifacts["step_rows"]).copy()
    step_rows["entry_signal_date"] = pd.to_datetime(step_rows["entry_signal_date"], errors="coerce")
    step_rows["decision_date"] = pd.to_datetime(step_rows["decision_date"], errors="coerce")

    step_oracle_policy = _policy_from_true_step_labels(step_rows)
    step_oracle_summary = _summarize_policy(
        step_oracle_policy,
        horizon_col="step_oracle_horizon",
        utility_col="step_oracle_utility",
    )
    threshold_sweep = _threshold_sweep(step_rows)
    ablation = _ablation_audit(step_rows)
    skip_rows, skip_entries = _skip_over_conflicts(step_rows)
    utility_alignment = _utility_alignment(step_rows)
    decision = _decide_root_cause(
        step_oracle_summary=step_oracle_summary,
        threshold_sweep=threshold_sweep,
        ablation=ablation,
        skip_rows=skip_rows,
        skip_entries=skip_entries,
        utility_alignment=utility_alignment,
    )

    step_oracle_path = OUT_DIR / f"{ts}_h338_step_hazard_failure_audit_step_oracle.parquet"
    step_oracle_summary_path = OUT_DIR / f"{ts}_h338_step_hazard_failure_audit_step_oracle_summary.parquet"
    threshold_sweep_path = OUT_DIR / f"{ts}_h338_step_hazard_failure_audit_threshold_sweep.parquet"
    ablation_path = OUT_DIR / f"{ts}_h338_step_hazard_failure_audit_ablation.parquet"
    skip_rows_path = OUT_DIR / f"{ts}_h338_step_hazard_failure_audit_skip_rows.parquet"
    skip_entries_path = OUT_DIR / f"{ts}_h338_step_hazard_failure_audit_skip_entries.parquet"
    utility_alignment_path = OUT_DIR / f"{ts}_h338_step_hazard_failure_audit_utility_alignment.parquet"
    details_path = DETAILS_DIR / f"{ts}_h338_step_hazard_failure_audit_details.json"

    step_oracle_policy.to_parquet(step_oracle_path, index=False)
    step_oracle_summary.to_parquet(step_oracle_summary_path, index=False)
    threshold_sweep.to_parquet(threshold_sweep_path, index=False)
    ablation.to_parquet(ablation_path, index=False)
    skip_rows.to_parquet(skip_rows_path, index=False)
    skip_entries.to_parquet(skip_entries_path, index=False)
    utility_alignment.to_parquet(utility_alignment_path, index=False)

    summary = {
        **decision,
        "mechanics": {
            "h337_summary": str(h337_artifacts["summary"]),
            "step_rows": int(len(step_rows)),
            "entries": int(step_rows["entry_id"].nunique()),
            "threshold_grid": list(THRESHOLD_GRID),
            "ablation_models": ablation["model_name"].tolist(),
        },
        "step_oracle_phase_results": step_oracle_summary.to_dict(orient="records"),
        "threshold_sweep": threshold_sweep.to_dict(orient="records"),
        "ablation": ablation.to_dict(orient="records"),
        "skip_over_rows": skip_rows.to_dict(orient="records"),
        "skip_over_entries": skip_entries.to_dict(orient="records"),
        "utility_alignment": utility_alignment.to_dict(orient="records"),
    }
    details_path.write_text(json.dumps(summary, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")

    summary_path = write_run_summary(
        ts=ts,
        mode="research_branch_step_hazard_failure_audit",
        name="h338_step_hazard_failure_audit",
        summary=summary,
        artifacts={
            "step_oracle": step_oracle_path,
            "step_oracle_summary": step_oracle_summary_path,
            "threshold_sweep": threshold_sweep_path,
            "ablation": ablation_path,
            "skip_over_rows": skip_rows_path,
            "skip_over_entries": skip_entries_path,
            "utility_alignment": utility_alignment_path,
            "details": details_path,
        },
        metadata={
            "hypothesis": "The exact H337 blocker can be identified by separating label-ceiling, threshold, utility-mismatch, and feature-family hypotheses.",
            "no_tuning_window": "2026+",
        },
    )

    print("H338 step-hazard failure audit")
    print("=" * 72)
    print(f"verdict: {decision['verdict']}")
    print(f"root cause: {decision['root_cause']}")
    print(f"branch decision: {decision['branch_decision']}")
    print(step_oracle_summary.to_string(index=False))
    print(ablation.to_string(index=False))
    print(f"summary: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
