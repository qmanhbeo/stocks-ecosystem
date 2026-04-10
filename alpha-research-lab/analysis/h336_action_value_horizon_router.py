"""
H336: action-value horizon router.

Question:
    Can a model learn "if the entry scenario looks like this, choose this legal
    exit horizon" as an expected-utility problem rather than a hold-label
    classification problem?

Design:
    - consume the H334 constrained legal-exit outcomes
    - train one dev-only utility regressor per legal horizon: 3d / 5d / 10d / 15d
    - choose the horizon with highest predicted utility only when its predicted
      margin over fixed 3d clears a dev-selected conservative margin
    - otherwise default to fixed 3d
    - evaluate validation and confirmation against fixed 3d and the H334 oracle
    - keep 2026+ out of the predictive decision

This is offline research only. A pass would justify portfolio integration under
frozen model and margin settings; it does not change the live sticky branch.
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
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_squared_error
from sklearn.pipeline import Pipeline

from path_utils import data_path

ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_DIR = ROOT / "analysis"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ANALYSIS_DIR) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_DIR))

from h335_exit_mdp_lite_distillation import (  # noqa: E402
    ACTIVATION_FEATURES,
    SIGNAL_FEATURES,
    _load_feature_surface,
    _resolve_h334_artifacts,
)
from src.research_protocol import DEFAULT_PROTOCOL  # noqa: E402
from src.run_summary import write_run_summary  # noqa: E402


RL_MATRIX_PATH = data_path("features/xs_rl_signal_matrix.parquet")
TRADABILITY_PATH = data_path("features/execution/tradability_daily.parquet")
ACTIVATION_PATH = data_path("features/activation_state_daily.parquet")
OUT_DIR = ROOT / "artifacts" / "portfolio_baselines"
DETAILS_DIR = ROOT / "artifacts" / "run_summaries"

HORIZONS = (3, 5, 10, 15)
MARGIN_GRID = (0.0, 0.0025, 0.005, 0.01, 0.015, 0.02, 0.03)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", type=str, default=str(RL_MATRIX_PATH))
    parser.add_argument("--tradability", type=str, default=str(TRADABILITY_PATH))
    parser.add_argument("--activation", type=str, default=str(ACTIVATION_PATH))
    parser.add_argument("--h334-summary", type=str, default="")
    return parser.parse_args()


def _safe_spearman(a: pd.Series, b: pd.Series) -> float | None:
    clean = pd.DataFrame({"a": a, "b": b}).replace([np.inf, -np.inf], np.nan).dropna()
    if len(clean) < 20 or clean["a"].nunique() < 2 or clean["b"].nunique() < 2:
        return None
    stat = spearmanr(clean["a"], clean["b"])
    value = float(np.asarray(stat.statistic).flat[0])
    return value if np.isfinite(value) else None


def _feature_columns(frame: pd.DataFrame) -> list[str]:
    base = [
        "entry_open",
        "score__full_library",
        "full_library_rank",
        "full_library_rank_pct",
    ]
    signal_cols = [column for column in SIGNAL_FEATURES if column in frame.columns]
    activation_cols = [column for column in ACTIVATION_FEATURES if column in frame.columns]
    tradability_cols = [
        column
        for column in ["can_buy_next_open", "can_sell_next_open", "has_volume", "is_floor", "is_ceiling"]
        if column in frame.columns
    ]
    return [column for column in [*base, *signal_cols, *activation_cols, *tradability_cols] if column in frame.columns]


def build_entry_panel(entry_outcomes: pd.DataFrame, features: pd.DataFrame) -> pd.DataFrame:
    entries = entry_outcomes.copy()
    entries["entry_signal_date"] = pd.to_datetime(entries["entry_signal_date"], errors="coerce")
    entries["ticker"] = entries["ticker"].astype(str).str.upper()
    feature_frame = features.copy()
    feature_frame["time"] = pd.to_datetime(feature_frame["time"], errors="coerce")
    feature_frame["ticker"] = feature_frame["ticker"].astype(str).str.upper()
    merged = entries.merge(
        feature_frame,
        left_on=["entry_signal_date", "ticker"],
        right_on=["time", "ticker"],
        how="left",
        validate="many_to_one",
    )
    return merged.drop(columns=["time_y"], errors="ignore").rename(columns={"time_x": "time"})


def _make_model() -> Pipeline:
    return Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            (
                "model",
                GradientBoostingRegressor(
                    n_estimators=80,
                    learning_rate=0.05,
                    max_depth=2,
                    min_samples_leaf=30,
                    subsample=0.85,
                    random_state=0,
                ),
            ),
        ]
    )


def fit_action_value_models(panel: pd.DataFrame, feature_columns: list[str]) -> tuple[pd.DataFrame, dict[str, object]]:
    scored = panel.copy()
    for column in feature_columns:
        scored[column] = pd.to_numeric(scored[column], errors="coerce")
    train = scored.loc[scored["research_phase"] == "dev"].copy()
    if train.empty:
        raise ValueError("No dev rows available for H336")

    model_summaries: dict[str, object] = {}
    for horizon in HORIZONS:
        target_col = f"h{horizon}_utility"
        pred_col = f"pred_h{horizon}_utility"
        target_train = train.loc[train[target_col].notna()].copy()
        if len(target_train) < 100:
            raise ValueError(f"Insufficient dev rows for horizon {horizon}: {len(target_train)}")
        model = _make_model()
        model.fit(
            target_train[feature_columns].to_numpy(dtype=np.float64),
            pd.to_numeric(target_train[target_col], errors="coerce").to_numpy(dtype=np.float64),
        )
        scored[pred_col] = model.predict(scored[feature_columns].to_numpy(dtype=np.float64))
        unavailable = ~scored.get(f"h{horizon}_available", pd.Series(True, index=scored.index)).fillna(False).astype(bool)
        scored.loc[unavailable, pred_col] = -np.inf

        metrics: dict[str, object] = {
            "dev_train_rows": int(len(target_train)),
        }
        for phase in ("dev", "validation", "confirmation"):
            phase_frame = scored.loc[(scored["research_phase"] == phase) & scored[target_col].notna()].copy()
            if phase_frame.empty:
                metrics[f"{phase}_rmse"] = None
                metrics[f"{phase}_spearman"] = None
                continue
            metrics[f"{phase}_rmse"] = float(np.sqrt(mean_squared_error(phase_frame[target_col], phase_frame[pred_col])))
            metrics[f"{phase}_spearman"] = _safe_spearman(phase_frame[target_col], phase_frame[pred_col])
        model_summaries[f"h{horizon}"] = metrics
    return scored, model_summaries


def _choose_policy(frame: pd.DataFrame, *, margin: float) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for row in frame.itertuples(index=False):
        available_horizons = [
            horizon
            for horizon in HORIZONS
            if getattr(row, f"h{horizon}_available", False)
            and pd.notna(getattr(row, f"h{horizon}_utility", np.nan))
            and np.isfinite(getattr(row, f"pred_h{horizon}_utility", -np.inf))
        ]
        if not available_horizons:
            continue
        pred = {h: float(getattr(row, f"pred_h{h}_utility")) for h in available_horizons}
        best_pred_horizon = max(pred, key=lambda h: pred[h])
        pred_h3 = pred.get(3, -np.inf)
        if best_pred_horizon != 3 and np.isfinite(pred_h3) and pred[best_pred_horizon] - pred_h3 >= float(margin):
            chosen_horizon = int(best_pred_horizon)
        else:
            chosen_horizon = 3 if 3 in available_horizons else min(available_horizons)
        rows.append(
            {
                "entry_id": int(row.entry_id),
                "ticker": str(row.ticker),
                "entry_signal_date": pd.Timestamp(row.entry_signal_date),
                "research_phase": str(row.research_phase),
                "chosen_horizon": int(chosen_horizon),
                "best_pred_horizon": int(best_pred_horizon),
                "pred_margin_vs_h3": float(pred[best_pred_horizon] - pred_h3) if np.isfinite(pred_h3) else None,
                "model_utility": float(getattr(row, f"h{chosen_horizon}_utility")),
                "model_relative_return": float(getattr(row, f"h{chosen_horizon}_relative_return")),
                "h3_utility": float(getattr(row, "h3_utility")),
                "h5_utility": float(getattr(row, "h5_utility")) if pd.notna(getattr(row, "h5_utility")) else np.nan,
                "h10_utility": float(getattr(row, "h10_utility")) if pd.notna(getattr(row, "h10_utility")) else np.nan,
                "h15_utility": float(getattr(row, "h15_utility")) if pd.notna(getattr(row, "h15_utility")) else np.nan,
                "oracle_horizon": int(row.oracle_horizon),
                "oracle_utility": float(row.oracle_utility),
            }
        )
    return pd.DataFrame(rows)


def _summarize_policy(policy: pd.DataFrame, *, margin: float) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for phase in ("dev", "validation", "confirmation"):
        phase_frame = policy.loc[policy["research_phase"] == phase].copy()
        if phase_frame.empty:
            rows.append({"phase": phase, "margin": float(margin), "entries": 0})
            continue
        fixed_means = {
            h: float(phase_frame[f"h{h}_utility"].mean())
            for h in HORIZONS
            if f"h{h}_utility" in phase_frame.columns and phase_frame[f"h{h}_utility"].notna().any()
        }
        best_fixed_horizon = max(fixed_means, key=lambda h: fixed_means[h])
        fixed_utility = float(fixed_means[best_fixed_horizon])
        model_utility = float(phase_frame["model_utility"].mean())
        oracle_utility = float(phase_frame["oracle_utility"].mean())
        oracle_uplift = oracle_utility - fixed_utility
        model_uplift = model_utility - fixed_utility
        rows.append(
            {
                "phase": phase,
                "margin": float(margin),
                "entries": int(len(phase_frame)),
                "best_fixed_horizon": int(best_fixed_horizon),
                "best_fixed_utility_mean": fixed_utility,
                "model_utility_mean": model_utility,
                "oracle_utility_mean": oracle_utility,
                "model_uplift_vs_best_fixed": float(model_uplift),
                "oracle_uplift_vs_best_fixed": float(oracle_uplift),
                "oracle_uplift_recovered_share": float(model_uplift / oracle_uplift)
                if abs(oracle_uplift) > 1e-12
                else None,
                "model_not_best_fixed_rate": float((phase_frame["chosen_horizon"] != int(best_fixed_horizon)).mean()),
                "model_matches_oracle_rate": float((phase_frame["chosen_horizon"] == phase_frame["oracle_horizon"]).mean()),
                **{
                    f"model_h{horizon}_choice_rate": float((phase_frame["chosen_horizon"] == int(horizon)).mean())
                    for horizon in HORIZONS
                },
            }
        )
    return rows


def evaluate_margin_grid(scored: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, float]:
    policies: list[pd.DataFrame] = []
    summaries: list[dict[str, object]] = []
    for margin in MARGIN_GRID:
        policy = _choose_policy(scored, margin=float(margin))
        policy["margin"] = float(margin)
        policies.append(policy)
        summaries.extend(_summarize_policy(policy, margin=float(margin)))
    grid = pd.DataFrame(summaries)
    dev = grid.loc[grid["phase"] == "dev"].copy()
    if dev.empty:
        raise ValueError("No dev grid rows for H336")
    dev = dev.sort_values(
        ["model_utility_mean", "model_not_best_fixed_rate", "margin"],
        ascending=[False, True, True],
        ignore_index=True,
    )
    selected_margin = float(dev.iloc[0]["margin"])
    selected_policy = pd.concat(policies, ignore_index=True)
    selected_policy = selected_policy.loc[selected_policy["margin"] == selected_margin].copy()
    return grid, selected_policy, selected_margin


def decide(phase_results: pd.DataFrame) -> dict[str, object]:
    by_phase = {row["phase"]: row for row in phase_results.to_dict(orient="records")}
    validation = by_phase.get("validation", {})
    confirmation = by_phase.get("confirmation", {})
    validation_uplift = validation.get("model_uplift_vs_best_fixed")
    confirmation_uplift = confirmation.get("model_uplift_vs_best_fixed")
    validation_recovery = validation.get("oracle_uplift_recovered_share")
    confirmation_recovery = confirmation.get("oracle_uplift_recovered_share")
    validation_override = validation.get("model_not_best_fixed_rate")
    confirmation_override = confirmation.get("model_not_best_fixed_rate")
    pass_condition = bool(
        validation_uplift is not None
        and confirmation_uplift is not None
        and validation_recovery is not None
        and confirmation_recovery is not None
        and float(validation_uplift) >= 0.003
        and float(confirmation_uplift) > 0.0
        and float(validation_recovery) >= 0.05
        and float(confirmation_recovery) >= 0.02
        and float(validation_override or 0.0) >= 0.05
        and float(confirmation_override or 0.0) >= 0.05
    )
    mixed_condition = bool(
        validation_uplift is not None
        and confirmation_uplift is not None
        and float(validation_uplift) > 0.0
        and float(confirmation_uplift) > -0.002
    )
    if pass_condition:
        verdict = "PASSED"
        branch_decision = (
            "The action-value horizon router recovered out-of-sample oracle uplift. "
            "Next: freeze the selected margin and integrate the router into the portfolio simulator."
        )
    elif mixed_condition:
        verdict = "MIXED"
        branch_decision = (
            "The action-value router is not a clean promotion but may have a narrow signal. "
            "Do not integrate; inspect whether the edge is limited to a sparse confidence state."
        )
    else:
        verdict = "FAILED"
        branch_decision = (
            "The action-value router did not recover enough oracle uplift out of sample. "
            "Do not continue entry-time horizon routing on the current daily feature state."
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
        "validation_override_rate": validation_override,
        "confirmation_override_rate": confirmation_override,
    }


def main() -> int:
    args = parse_args()
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    DETAILS_DIR.mkdir(parents=True, exist_ok=True)

    h334_artifacts = _resolve_h334_artifacts(args.h334_summary)
    entry_outcomes = pd.read_parquet(h334_artifacts["entry_outcomes"])
    features = _load_feature_surface(Path(args.matrix), Path(args.activation), Path(args.tradability))
    panel = build_entry_panel(entry_outcomes, features)
    feature_columns = _feature_columns(panel)
    if not feature_columns:
        raise ValueError("No feature columns available for H336")

    scored, model_summary = fit_action_value_models(panel, feature_columns)
    margin_grid, policy, selected_margin = evaluate_margin_grid(scored)
    phase_results = pd.DataFrame(_summarize_policy(policy, margin=selected_margin))
    decision = decide(phase_results)

    scored_path = OUT_DIR / f"{ts}_h336_action_value_horizon_router_scored_entries.parquet"
    grid_path = OUT_DIR / f"{ts}_h336_action_value_horizon_router_margin_grid.parquet"
    policy_path = OUT_DIR / f"{ts}_h336_action_value_horizon_router_policy_entries.parquet"
    phase_results_path = OUT_DIR / f"{ts}_h336_action_value_horizon_router_phase_results.parquet"
    details_path = DETAILS_DIR / f"{ts}_h336_action_value_horizon_router_details.json"
    scored.to_parquet(scored_path, index=False)
    margin_grid.to_parquet(grid_path, index=False)
    policy.to_parquet(policy_path, index=False)
    phase_results.to_parquet(phase_results_path, index=False)

    summary = {
        **decision,
        "mechanics": {
            "h334_summary": str(h334_artifacts["summary"]),
            "entry_outcomes": str(h334_artifacts["entry_outcomes"]),
            "rows": int(len(scored)),
            "feature_count": int(len(feature_columns)),
            "horizons": list(HORIZONS),
            "margin_grid": list(MARGIN_GRID),
            "selected_margin_dev_only": float(selected_margin),
            "model_type": "GradientBoostingRegressor(max_depth=2, n_estimators=80, min_samples_leaf=30)",
        },
        "model": model_summary,
        "phase_results": phase_results.to_dict(orient="records"),
    }
    details_path.write_text(json.dumps(summary, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")

    summary_path = write_run_summary(
        ts=ts,
        mode="research_branch_action_value_horizon_router",
        name="h336_action_value_horizon_router",
        summary=summary,
        artifacts={
            "scored_entries": scored_path,
            "margin_grid": grid_path,
            "policy_entries": policy_path,
            "phase_results": phase_results_path,
            "details": details_path,
        },
        metadata={
            "hypothesis": "Predict per-horizon exit utility and override fixed 3d only when the predicted best horizon has a dev-selected utility margin.",
            "protocol": DEFAULT_PROTOCOL.describe(),
            "no_tuning_window": "2026+",
        },
    )

    display_cols = [
        "phase",
        "entries",
        "best_fixed_horizon",
        "model_utility_mean",
        "best_fixed_utility_mean",
        "model_uplift_vs_best_fixed",
        "oracle_uplift_recovered_share",
        "model_not_best_fixed_rate",
        "model_matches_oracle_rate",
    ]
    print("H336 action-value horizon router")
    print("=" * 72)
    print(f"verdict: {decision['verdict']}")
    print(f"selected margin: {selected_margin:+.4f}")
    print(f"branch decision: {decision['branch_decision']}")
    print(phase_results[display_cols].to_string(index=False))
    print(f"summary: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
