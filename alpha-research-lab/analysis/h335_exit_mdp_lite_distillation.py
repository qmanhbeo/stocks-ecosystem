"""
H335: exit-MDP-lite distillation from the H334 constrained oracle.

Question:
    Can a simple ex-ante hold-vs-sell model recover a material share of the
    H334 legal-exit oracle uplift, without using future path outcomes at
    inference?

Design:
    - consume the latest H334 legal horizon outcomes
    - create decision rows at legal scheduled exits: 3d, 5d, and 10d
    - label a decision as "hold" when a later legal horizon has higher H334
      utility than selling at the current scheduled horizon
    - train a regularized logistic model on dev only
    - run a sequential policy: at 3d / 5d / 10d, sell if hold_prob < 0.5;
      otherwise continue, defaulting to 15d
    - compare utility against the best fixed horizon and the H334 oracle
    - keep 2026+ out of the predictive decision

This is still offline research. A pass unlocks stricter portfolio integration;
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
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from path_utils import data_path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.deterministic_portfolio import compute_strategy_scores  # noqa: E402
from src.research_protocol import DEFAULT_PROTOCOL, assign_research_phase  # noqa: E402
from src.run_summary import write_run_summary  # noqa: E402


RL_MATRIX_PATH = data_path("features/xs_rl_signal_matrix.parquet")
TRADABILITY_PATH = data_path("features/execution/tradability_daily.parquet")
ACTIVATION_PATH = data_path("features/activation_state_daily.parquet")
STOCK_DIR = data_path("stock")
OUT_DIR = ROOT / "artifacts" / "portfolio_baselines"
DETAILS_DIR = ROOT / "artifacts" / "run_summaries"

HORIZONS = (3, 5, 10, 15)
DECISION_HORIZONS = (3, 5, 10)
HOLD_THRESHOLD = 0.5

SIGNAL_FEATURES = [
    "s1_proba",
    "c4_oc_asym_5d",
    "c5_ins_relative_size_5d",
    "c5_signal_present",
    "c6_contrarian_intra_5d",
    "c7_ceiling_count_5d",
    "c8_vol_zscore_5d",
    "c9_reversal_1d",
    "c10_illiq_level_rank",
    "c11_ret_60d_lag_rank",
    "c12_gap_absorb_3",
    "c13_compress_blowoff_2",
    "c14_clv_volconf_resid_rank",
]

ACTIVATION_FEATURES = [
    "full_top1_score",
    "full_top5_mean_score",
    "full_top1_minus_top5_spread",
    "full_top5_score_std",
    "selector_top5_jaccard",
    "buyable_breadth_all",
    "liq_open_breadth_all",
    "xs_ret_std_5d",
    "vni_ret_5d",
    "vni_drawdown_60d",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", type=str, default=str(RL_MATRIX_PATH))
    parser.add_argument("--tradability", type=str, default=str(TRADABILITY_PATH))
    parser.add_argument("--activation", type=str, default=str(ACTIVATION_PATH))
    parser.add_argument("--stock-dir", type=str, default=str(STOCK_DIR))
    parser.add_argument("--h334-summary", type=str, default="")
    parser.add_argument("--hold-threshold", type=float, default=HOLD_THRESHOLD)
    return parser.parse_args()


def _resolve_h334_artifacts(summary_arg: str) -> dict[str, Path]:
    if summary_arg:
        summary_path = Path(summary_arg)
    else:
        summary_path = DETAILS_DIR / "latest_research_branch_exit_oracle_upper_bound.json"
    if not summary_path.exists():
        raise FileNotFoundError(f"missing H334 summary: {summary_path}")
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    artifacts = payload.get("artifacts", {})
    required = ["entry_outcomes", "horizon_outcomes", "phase_results"]
    missing = [key for key in required if key not in artifacts]
    if missing:
        raise ValueError(f"H334 summary missing artifacts: {missing}")

    out: dict[str, Path] = {"summary": summary_path}
    for key in required:
        value = Path(str(artifacts[key]))
        out[key] = value if value.is_absolute() else ROOT / value
    return out


def _load_feature_surface(matrix_path: Path, activation_path: Path, tradability_path: Path) -> pd.DataFrame:
    matrix = pd.read_parquet(matrix_path).copy()
    matrix["time"] = pd.to_datetime(matrix["time"], errors="coerce")
    matrix["ticker"] = matrix["ticker"].astype(str).str.upper()
    signal_cols = [column for column in SIGNAL_FEATURES if column in matrix.columns]
    score_cols = [column for column in matrix.columns if column not in {"time", "ticker", "actual"}]
    scores = compute_strategy_scores(matrix[["time", "ticker", "actual", *score_cols]].copy(), {"full_library": score_cols})
    scores["full_library_rank"] = scores.groupby("time")["score__full_library"].rank(
        method="average",
        ascending=False,
    )
    scores["full_library_rank_pct"] = scores.groupby("time")["score__full_library"].rank(
        method="average",
        pct=True,
        ascending=True,
    )
    features = scores[["time", "ticker", "score__full_library", "full_library_rank", "full_library_rank_pct"]].merge(
        matrix[["time", "ticker", *signal_cols]],
        on=["time", "ticker"],
        how="left",
        validate="one_to_one",
    )

    if activation_path.exists():
        activation = pd.read_parquet(activation_path).copy()
        activation["time"] = pd.to_datetime(activation["time"], errors="coerce")
        activation_cols = [column for column in ACTIVATION_FEATURES if column in activation.columns]
        features = features.merge(activation[["time", *activation_cols]], on="time", how="left")

    if tradability_path.exists():
        tradability = pd.read_parquet(tradability_path).copy()
        tradability["time"] = pd.to_datetime(tradability["time"], errors="coerce")
        tradability["ticker"] = tradability["ticker"].astype(str).str.upper()
        trad_cols = [c for c in ["can_sell_next_open", "can_buy_next_open", "has_volume", "is_floor", "is_ceiling"] if c in tradability.columns]
        features = features.merge(tradability[["time", "ticker", *trad_cols]], on=["time", "ticker"], how="left")

    return features


def _prefix(frame: pd.DataFrame, prefix: str) -> pd.DataFrame:
    renamed = {
        column: f"{prefix}{column}"
        for column in frame.columns
        if column not in {"time", "ticker"}
    }
    return frame.rename(columns=renamed)


def _load_open_wide(tickers: pd.Series, stock_dir: Path, calendar: pd.DatetimeIndex) -> pd.DataFrame:
    parts: list[pd.DataFrame] = []
    for ticker in sorted(set(tickers.astype(str).str.upper())):
        path = stock_dir / f"gia_lich_su_{ticker}_1D.parquet"
        if not path.exists():
            continue
        part = pd.read_parquet(path, columns=["time", "open"]).copy()
        part["time"] = pd.to_datetime(part["time"], errors="coerce")
        part["ticker"] = ticker
        parts.append(part)
    if not parts:
        raise ValueError("No stock open-price files available for H335")
    panel = pd.concat(parts, ignore_index=True)
    wide = panel.pivot(index="time", columns="ticker", values="open").reindex(index=calendar)
    return wide.sort_index()


def _path_state(
    *,
    entry_execution_date: pd.Timestamp,
    decision_date: pd.Timestamp,
    ticker: str,
    entry_open: float,
    open_wide: pd.DataFrame,
) -> dict[str, float | None]:
    if ticker not in open_wide.columns or pd.isna(entry_execution_date) or pd.isna(decision_date):
        return {
            "return_since_entry": None,
            "path_mae_so_far": None,
            "path_mfe_so_far": None,
            "decision_open": None,
        }
    path = open_wide.loc[
        (open_wide.index >= pd.Timestamp(entry_execution_date)) & (open_wide.index <= pd.Timestamp(decision_date)),
        ticker,
    ]
    path = pd.to_numeric(path, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    path = path.loc[path > 0.0]
    if path.empty or not (np.isfinite(entry_open) and entry_open > 0.0):
        return {
            "return_since_entry": None,
            "path_mae_so_far": None,
            "path_mfe_so_far": None,
            "decision_open": None,
        }
    returns = path.astype(float) / float(entry_open) - 1.0
    return {
        "return_since_entry": float(returns.iloc[-1]),
        "path_mae_so_far": float(max(0.0, -float(returns.min()))),
        "path_mfe_so_far": float(max(0.0, float(returns.max()))),
        "decision_open": float(path.iloc[-1]),
    }


def build_decision_rows(
    *,
    entry_outcomes: pd.DataFrame,
    horizon_outcomes: pd.DataFrame,
    features: pd.DataFrame,
    stock_dir: Path,
) -> pd.DataFrame:
    entries = entry_outcomes.copy()
    horizons = horizon_outcomes.copy()
    for column in ["time", "entry_signal_date", "entry_execution_date"]:
        if column in entries.columns:
            entries[column] = pd.to_datetime(entries[column], errors="coerce")
    for column in ["entry_signal_date", "entry_execution_date", "scheduled_exit_date", "legal_exit_date"]:
        if column in horizons.columns:
            horizons[column] = pd.to_datetime(horizons[column], errors="coerce")
    entries["ticker"] = entries["ticker"].astype(str).str.upper()
    horizons["ticker"] = horizons["ticker"].astype(str).str.upper()

    feature_dates = pd.DatetimeIndex(sorted(pd.to_datetime(features["time"].dropna().unique())))
    previous_date = {pd.Timestamp(feature_dates[idx]): pd.Timestamp(feature_dates[idx - 1]) for idx in range(1, len(feature_dates))}
    open_wide = _load_open_wide(entries["ticker"], stock_dir, feature_dates)

    by_entry = {int(entry_id): frame.sort_values("horizon") for entry_id, frame in horizons.groupby("entry_id")}
    rows: list[dict[str, object]] = []
    for entry in entries.itertuples(index=False):
        entry_id = int(entry.entry_id)
        frame = by_entry.get(entry_id)
        if frame is None or frame.empty:
            continue
        utilities = {int(row.horizon): float(row.utility) for row in frame.itertuples(index=False) if pd.notna(row.utility)}
        for horizon in DECISION_HORIZONS:
            if horizon not in utilities:
                continue
            later = {h: u for h, u in utilities.items() if h > int(horizon)}
            if not later:
                continue
            scheduled_exit_date = pd.Timestamp(
                frame.loc[frame["horizon"] == int(horizon), "scheduled_exit_date"].iloc[0]
            )
            decision_date = previous_date.get(scheduled_exit_date)
            if decision_date is None:
                continue
            current_utility = float(utilities[int(horizon)])
            best_later_horizon = max(later, key=lambda h: later[h])
            best_later_utility = float(later[int(best_later_horizon)])
            path = _path_state(
                entry_execution_date=pd.Timestamp(entry.entry_execution_date),
                decision_date=decision_date,
                ticker=str(entry.ticker),
                entry_open=float(entry.entry_open),
                open_wide=open_wide,
            )
            row = {
                "entry_id": entry_id,
                "ticker": str(entry.ticker),
                "entry_signal_date": pd.Timestamp(entry.entry_signal_date),
                "entry_execution_date": pd.Timestamp(entry.entry_execution_date),
                "decision_date": pd.Timestamp(decision_date),
                "scheduled_exit_date": scheduled_exit_date,
                "horizon": int(horizon),
                "current_utility": current_utility,
                "best_later_horizon": int(best_later_horizon),
                "best_later_utility": best_later_utility,
                "hold_label": int(best_later_utility > current_utility + 1e-12),
                "oracle_horizon": int(entry.oracle_horizon),
                "oracle_utility": float(entry.oracle_utility),
                "h3_utility": float(entry.h3_utility) if pd.notna(entry.h3_utility) else np.nan,
                "h5_utility": float(entry.h5_utility) if pd.notna(entry.h5_utility) else np.nan,
                "h10_utility": float(entry.h10_utility) if pd.notna(entry.h10_utility) else np.nan,
                "h15_utility": float(entry.h15_utility) if pd.notna(entry.h15_utility) else np.nan,
                "h3_relative_return": float(entry.h3_relative_return) if pd.notna(entry.h3_relative_return) else np.nan,
                "h5_relative_return": float(entry.h5_relative_return) if pd.notna(entry.h5_relative_return) else np.nan,
                "h10_relative_return": float(entry.h10_relative_return) if pd.notna(entry.h10_relative_return) else np.nan,
                "h15_relative_return": float(entry.h15_relative_return) if pd.notna(entry.h15_relative_return) else np.nan,
                "research_phase": entry.research_phase,
                **path,
            }
            outcome = frame.loc[frame["horizon"] == int(horizon)].iloc[0]
            row["scheduled_blocked_extra_days"] = int(outcome["blocked_extra_days"])
            rows.append(row)

    decisions = pd.DataFrame(rows)
    if decisions.empty:
        return decisions

    current_features = _prefix(features, "current_")
    current_features = current_features.rename(columns={"time": "decision_date"})
    entry_features = _prefix(features, "entry_")
    entry_features = entry_features.rename(columns={"time": "entry_signal_date"})
    decisions = decisions.merge(
        current_features,
        left_on=["decision_date", "ticker"],
        right_on=["decision_date", "ticker"],
        how="left",
    )
    decisions = decisions.merge(
        entry_features,
        left_on=["entry_signal_date", "ticker"],
        right_on=["entry_signal_date", "ticker"],
        how="left",
        suffixes=("", "_entrydup"),
    )
    if "current_score__full_library" in decisions.columns and "entry_score__full_library" in decisions.columns:
        decisions["full_score_change_since_entry"] = (
            pd.to_numeric(decisions["current_score__full_library"], errors="coerce")
            - pd.to_numeric(decisions["entry_score__full_library"], errors="coerce")
        )
    if "current_full_library_rank_pct" in decisions.columns and "entry_full_library_rank_pct" in decisions.columns:
        decisions["full_rank_pct_change_since_entry"] = (
            pd.to_numeric(decisions["current_full_library_rank_pct"], errors="coerce")
            - pd.to_numeric(decisions["entry_full_library_rank_pct"], errors="coerce")
        )
    for horizon in DECISION_HORIZONS:
        decisions[f"horizon_eq_{horizon}"] = (decisions["horizon"] == int(horizon)).astype(float)
    return decisions


def _feature_columns(frame: pd.DataFrame) -> list[str]:
    base = [
        "horizon",
        "horizon_eq_3",
        "horizon_eq_5",
        "horizon_eq_10",
        "return_since_entry",
        "path_mae_so_far",
        "path_mfe_so_far",
        "scheduled_blocked_extra_days",
        "current_score__full_library",
        "current_full_library_rank",
        "current_full_library_rank_pct",
        "entry_score__full_library",
        "entry_full_library_rank",
        "entry_full_library_rank_pct",
        "full_score_change_since_entry",
        "full_rank_pct_change_since_entry",
    ]
    current_signal = [f"current_{column}" for column in SIGNAL_FEATURES]
    entry_signal = [f"entry_{column}" for column in SIGNAL_FEATURES]
    activation = [f"current_{column}" for column in ACTIVATION_FEATURES]
    tradability = [
        "current_can_sell_next_open",
        "current_can_buy_next_open",
        "current_has_volume",
        "current_is_floor",
        "current_is_ceiling",
    ]
    return [column for column in [*base, *current_signal, *entry_signal, *activation, *tradability] if column in frame.columns]


def fit_model(decisions: pd.DataFrame, feature_columns: list[str]) -> tuple[Pipeline, pd.DataFrame, dict[str, object]]:
    train = decisions.loc[decisions["research_phase"] == "dev"].copy()
    if train.empty:
        raise ValueError("No dev rows available for H335")
    if train["hold_label"].nunique() < 2:
        raise ValueError("Dev hold labels have only one class")

    for column in feature_columns:
        decisions[column] = pd.to_numeric(decisions[column], errors="coerce")
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
    pipeline.fit(train[feature_columns].to_numpy(dtype=np.float64), train["hold_label"].astype(int).to_numpy())
    scored = decisions.copy()
    scored["hold_prob"] = pipeline.predict_proba(scored[feature_columns].to_numpy(dtype=np.float64))[:, 1]

    model = pipeline.named_steps["model"]
    coef = dict(zip(feature_columns, [float(x) for x in model.coef_[0]]))
    strongest = sorted(coef.items(), key=lambda item: abs(item[1]), reverse=True)[:15]
    model_summary = {
        "feature_count": int(len(feature_columns)),
        "dev_rows": int(len(train)),
        "dev_positive_rate": float(train["hold_label"].mean()),
        "strongest_standardized_coefficients": strongest,
    }
    return pipeline, scored, model_summary


def _auc(frame: pd.DataFrame) -> float | None:
    clean = frame[["hold_label", "hold_prob"]].replace([np.inf, -np.inf], np.nan).dropna()
    if clean.empty or clean["hold_label"].nunique() < 2:
        return None
    return float(roc_auc_score(clean["hold_label"].astype(int), clean["hold_prob"].astype(float)))


def _policy_for_entries(scored: pd.DataFrame, threshold: float) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    decision_by_entry = {int(entry_id): frame.sort_values("horizon") for entry_id, frame in scored.groupby("entry_id")}
    for entry_id, frame in decision_by_entry.items():
        first = frame.iloc[0]
        chosen = 15
        sell_prob = None
        for horizon in DECISION_HORIZONS:
            subset = frame.loc[frame["horizon"] == int(horizon)]
            if subset.empty:
                continue
            prob = float(subset["hold_prob"].iloc[0])
            if prob < float(threshold):
                chosen = int(horizon)
                sell_prob = prob
                break
        if sell_prob is None and not frame.empty:
            sell_prob = float(frame.sort_values("horizon")["hold_prob"].iloc[-1])
        utility_col = f"h{chosen}_utility"
        if utility_col not in first.index or pd.isna(first[utility_col]):
            available = [h for h in HORIZONS if f"h{h}_utility" in first.index and pd.notna(first[f"h{h}_utility"])]
            if not available:
                continue
            chosen = max(available)
            utility_col = f"h{chosen}_utility"
        rows.append(
            {
                "entry_id": int(entry_id),
                "ticker": str(first["ticker"]),
                "entry_signal_date": pd.Timestamp(first["entry_signal_date"]),
                "research_phase": str(first["research_phase"]),
                "model_horizon": int(chosen),
                "model_utility": float(first[utility_col]),
                "model_relative_return": float(first[f"h{chosen}_relative_return"]) if f"h{chosen}_relative_return" in first.index and pd.notna(first[f"h{chosen}_relative_return"]) else np.nan,
                "oracle_horizon": int(first["oracle_horizon"]),
                "oracle_utility": float(first["oracle_utility"]),
                "h3_utility": float(first["h3_utility"]),
                "h5_utility": float(first["h5_utility"]) if pd.notna(first["h5_utility"]) else np.nan,
                "h10_utility": float(first["h10_utility"]) if pd.notna(first["h10_utility"]) else np.nan,
                "h15_utility": float(first["h15_utility"]) if pd.notna(first["h15_utility"]) else np.nan,
                "last_hold_prob": sell_prob,
            }
        )
    return pd.DataFrame(rows)


def summarize_policy(scored: pd.DataFrame, policy: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, object]]:
    rows: list[dict[str, object]] = []
    for phase in ("dev", "validation", "confirmation"):
        dec = scored.loc[scored["research_phase"] == phase].copy()
        pol = policy.loc[policy["research_phase"] == phase].copy()
        if pol.empty:
            rows.append({"phase": phase, "entries": 0})
            continue
        fixed_means = {h: float(pol[f"h{h}_utility"].mean()) for h in HORIZONS if f"h{h}_utility" in pol.columns and pol[f"h{h}_utility"].notna().any()}
        best_fixed_horizon = max(fixed_means, key=lambda h: fixed_means[h])
        oracle_uplift = float(pol["oracle_utility"].mean() - fixed_means[best_fixed_horizon])
        model_uplift = float(pol["model_utility"].mean() - fixed_means[best_fixed_horizon])
        recovered_share = float(model_uplift / oracle_uplift) if abs(oracle_uplift) > 1e-12 else None
        row: dict[str, object] = {
            "phase": phase,
            "decision_rows": int(len(dec)),
            "entries": int(len(pol)),
            "hold_label_rate": float(dec["hold_label"].mean()) if not dec.empty else None,
            "hold_prob_mean": float(dec["hold_prob"].mean()) if not dec.empty else None,
            "decision_auc": _auc(dec),
            "best_fixed_horizon": int(best_fixed_horizon),
            "best_fixed_utility_mean": float(fixed_means[best_fixed_horizon]),
            "model_utility_mean": float(pol["model_utility"].mean()),
            "oracle_utility_mean": float(pol["oracle_utility"].mean()),
            "model_uplift_vs_best_fixed": model_uplift,
            "oracle_uplift_vs_best_fixed": oracle_uplift,
            "oracle_uplift_recovered_share": recovered_share,
            "model_not_best_fixed_rate": float((pol["model_horizon"] != int(best_fixed_horizon)).mean()),
            "model_matches_oracle_rate": float((pol["model_horizon"] == pol["oracle_horizon"]).mean()),
        }
        for horizon in HORIZONS:
            row[f"model_h{horizon}_choice_rate"] = float((pol["model_horizon"] == int(horizon)).mean())
            if f"h{horizon}_utility" in pol.columns:
                row[f"h{horizon}_utility_mean"] = float(pol[f"h{horizon}_utility"].mean())
        rows.append(row)

    phase_results = pd.DataFrame(rows)
    by_phase = {row["phase"]: row for row in phase_results.to_dict(orient="records")}
    validation = by_phase.get("validation", {})
    confirmation = by_phase.get("confirmation", {})
    validation_uplift = validation.get("model_uplift_vs_best_fixed")
    confirmation_uplift = confirmation.get("model_uplift_vs_best_fixed")
    validation_recovery = validation.get("oracle_uplift_recovered_share")
    confirmation_recovery = confirmation.get("oracle_uplift_recovered_share")
    validation_auc = validation.get("decision_auc")
    confirmation_auc = confirmation.get("decision_auc")
    pass_condition = bool(
        validation_uplift is not None
        and confirmation_uplift is not None
        and validation_recovery is not None
        and confirmation_recovery is not None
        and float(validation_uplift) >= 0.005
        and float(confirmation_uplift) > 0.0
        and float(validation_recovery) >= 0.10
        and float(confirmation_recovery) >= 0.05
        and (validation_auc is None or float(validation_auc) >= 0.52)
        and (confirmation_auc is None or float(confirmation_auc) >= 0.50)
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
            "The simple exit-MDP-lite policy recovered positive validation and confirmation oracle uplift. "
            "Next: integrate the learned rule into the portfolio simulator under a frozen threshold / feature set."
        )
    elif mixed_condition:
        verdict = "MIXED"
        branch_decision = (
            "The exit-MDP-lite policy shows some validation value but not enough confirmation recovery. "
            "Narrow to hazard labels or a more constrained state family before integration."
        )
    else:
        verdict = "FAILED"
        branch_decision = (
            "The exit-MDP-lite classifier did not recover enough H334 oracle uplift out of sample. "
            "Do not integrate this policy; try discrete-exit-hazard only if continuing the branch."
        )
    decision = {
        "verdict": verdict,
        "branch_decision": branch_decision,
        "pass_condition": pass_condition,
        "mixed_condition": mixed_condition,
        "validation_model_uplift_vs_best_fixed": validation_uplift,
        "confirmation_model_uplift_vs_best_fixed": confirmation_uplift,
        "validation_oracle_uplift_recovered_share": validation_recovery,
        "confirmation_oracle_uplift_recovered_share": confirmation_recovery,
        "validation_decision_auc": validation_auc,
        "confirmation_decision_auc": confirmation_auc,
    }
    return phase_results, decision


def main() -> int:
    args = parse_args()
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    DETAILS_DIR.mkdir(parents=True, exist_ok=True)

    h334_artifacts = _resolve_h334_artifacts(args.h334_summary)
    entry_outcomes = pd.read_parquet(h334_artifacts["entry_outcomes"])
    horizon_outcomes = pd.read_parquet(h334_artifacts["horizon_outcomes"])
    features = _load_feature_surface(Path(args.matrix), Path(args.activation), Path(args.tradability))
    decisions = build_decision_rows(
        entry_outcomes=entry_outcomes,
        horizon_outcomes=horizon_outcomes,
        features=features,
        stock_dir=Path(args.stock_dir),
    )
    if decisions.empty:
        raise ValueError("No H335 decision rows built")

    feature_columns = _feature_columns(decisions)
    _, scored, model_summary = fit_model(decisions, feature_columns)
    policy = _policy_for_entries(scored, float(args.hold_threshold))
    phase_results, decision = summarize_policy(scored, policy)

    decision_rows_path = OUT_DIR / f"{ts}_h335_exit_mdp_lite_decision_rows.parquet"
    policy_path = OUT_DIR / f"{ts}_h335_exit_mdp_lite_policy_entries.parquet"
    phase_results_path = OUT_DIR / f"{ts}_h335_exit_mdp_lite_phase_results.parquet"
    details_path = DETAILS_DIR / f"{ts}_h335_exit_mdp_lite_distillation_details.json"

    scored.to_parquet(decision_rows_path, index=False)
    policy.to_parquet(policy_path, index=False)
    phase_results.to_parquet(phase_results_path, index=False)

    summary = {
        **decision,
        "mechanics": {
            "h334_summary": str(h334_artifacts["summary"]),
            "entry_outcomes": str(h334_artifacts["entry_outcomes"]),
            "horizon_outcomes": str(h334_artifacts["horizon_outcomes"]),
            "decision_rows": int(len(scored)),
            "policy_entries": int(len(policy)),
            "feature_count": int(len(feature_columns)),
            "hold_threshold": float(args.hold_threshold),
            "decision_horizons": list(DECISION_HORIZONS),
            "max_horizon": int(max(HORIZONS)),
        },
        "model": model_summary,
        "phase_results": phase_results.to_dict(orient="records"),
    }
    details_path.write_text(json.dumps(summary, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")

    summary_path = write_run_summary(
        ts=ts,
        mode="research_branch_exit_mdp_lite_distillation",
        name="h335_exit_mdp_lite_distillation",
        summary=summary,
        artifacts={
            "decision_rows": decision_rows_path,
            "policy_entries": policy_path,
            "phase_results": phase_results_path,
            "details": details_path,
        },
        metadata={
            "hypothesis": "A simple ex-ante hold-vs-sell classifier can recover useful H334 oracle uplift at legal exit decision horizons.",
            "protocol": DEFAULT_PROTOCOL.describe(),
            "no_tuning_window": "2026+",
        },
    )

    display_cols = [
        "phase",
        "entries",
        "decision_auc",
        "best_fixed_horizon",
        "model_utility_mean",
        "best_fixed_utility_mean",
        "model_uplift_vs_best_fixed",
        "oracle_uplift_recovered_share",
        "model_matches_oracle_rate",
    ]
    print("H335 exit-MDP-lite distillation")
    print("=" * 72)
    print(f"verdict: {decision['verdict']}")
    print(f"branch decision: {decision['branch_decision']}")
    print(phase_results[display_cols].to_string(index=False))
    print(f"summary: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
