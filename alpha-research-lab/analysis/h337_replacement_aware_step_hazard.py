"""
H337: replacement-aware step-hazard distillation from the H334 constrained oracle.

Question:
    Can a one-legal-step-ahead hazard model recover useful H334 oracle uplift
    once the target is localized and the state is evaluated at the current
    legal decision date instead of only at entry?

Design:
    - consume the latest H334 legal horizon outcomes
    - create held-position rows at legal decision steps: 3d, 5d, and 10d
    - label each row by whether waiting exactly one more legal step has higher
      utility than exiting now
    - use only current hold-day state available at the decision date:
      path state, score decay, current signal state, activation state,
      tradability, event state, and a 2015-compatible replacement-pressure
      proxy from the full daily score surface
    - train a dev-only logistic hazard model with fixed threshold 0.50
    - compare against fixed horizons, the H334 oracle, and a local H211
      strength-exhaustion policy on the same H334 entry universe
    - keep 2026+ out of the predictive decision

This is still offline research. A pass would justify a narrower hazard follow-up;
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
ANALYSIS_DIR = ROOT / "analysis"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ANALYSIS_DIR) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_DIR))

from h335_exit_mdp_lite_distillation import (  # noqa: E402
    ACTIVATION_FEATURES,
    SIGNAL_FEATURES,
    _load_feature_surface as _load_base_feature_surface,
    _resolve_h334_artifacts,
)
from src.research_protocol import DEFAULT_PROTOCOL  # noqa: E402
from src.run_summary import write_run_summary  # noqa: E402


RL_MATRIX_PATH = data_path("features/xs_rl_signal_matrix.parquet")
TRADABILITY_PATH = data_path("features/execution/tradability_daily.parquet")
ACTIVATION_PATH = data_path("features/activation_state_daily.parquet")
EVENT_PATH = data_path("features/event_surface_daily.parquet")
STOCK_DIR = data_path("stock")
H211_SUMMARY_PATH = ROOT / "artifacts" / "run_summaries" / "latest_portfolio_exit_strength_exhaustion.json"
OUT_DIR = ROOT / "artifacts" / "portfolio_baselines"
DETAILS_DIR = ROOT / "artifacts" / "run_summaries"

HORIZONS = (3, 5, 10, 15)
DECISION_HORIZONS = (3, 5, 10)
NEXT_HORIZON = {3: 5, 5: 10, 10: 15}
HOLD_THRESHOLD = 0.5

EVENT_FEATURES = [
    "recent_insider_filing_5d",
    "recent_insider_filing_20d",
    "recent_major_holder_filing_5d",
    "recent_major_holder_filing_20d",
    "recent_any_filing_5d",
    "recent_any_filing_20d",
    "in_report_w15_45",
    "in_report_w30_60",
    "pre_q_end_10d",
    "post_q_end_10d",
    "dividend_window_pre_20d",
    "dividend_window_post_5d",
    "issuance_window_pre_20d",
    "issuance_window_post_5d",
    "event_density_20d",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", type=str, default=str(RL_MATRIX_PATH))
    parser.add_argument("--tradability", type=str, default=str(TRADABILITY_PATH))
    parser.add_argument("--activation", type=str, default=str(ACTIVATION_PATH))
    parser.add_argument("--event", type=str, default=str(EVENT_PATH))
    parser.add_argument("--stock-dir", type=str, default=str(STOCK_DIR))
    parser.add_argument("--h334-summary", type=str, default="")
    parser.add_argument("--h211-summary", type=str, default=str(H211_SUMMARY_PATH))
    parser.add_argument("--hold-threshold", type=float, default=HOLD_THRESHOLD)
    return parser.parse_args()


def _resolve_h211_params(summary_arg: str) -> dict[str, float]:
    path = Path(summary_arg)
    if not path.exists():
        return {"return_since_entry_threshold": 0.15, "score_drop_threshold": 0.05}
    payload = json.loads(path.read_text(encoding="utf-8"))
    winner = payload.get("summary", {}).get("winner", {})
    params = winner.get("exit_rule_params", {}) if isinstance(winner, dict) else {}
    return {
        "return_since_entry_threshold": float(params.get("return_since_entry_threshold", 0.15)),
        "score_drop_threshold": float(params.get("score_drop_threshold", 0.05)),
    }


def _load_feature_surface(
    matrix_path: Path,
    activation_path: Path,
    tradability_path: Path,
    event_path: Path,
) -> pd.DataFrame:
    features = _load_base_feature_surface(matrix_path, activation_path, tradability_path).copy()

    if event_path.exists():
        event = pd.read_parquet(event_path).copy()
        event["time"] = pd.to_datetime(event["time"], errors="coerce")
        event["ticker"] = event["ticker"].astype(str).str.upper()
        event_cols = [column for column in EVENT_FEATURES if column in event.columns]
        features = features.merge(event[["time", "ticker", *event_cols]], on=["time", "ticker"], how="left")

    eligible = features["can_buy_next_open"].fillna(True).astype(bool) if "can_buy_next_open" in features.columns else pd.Series(True, index=features.index)
    eligible_scores = features.loc[eligible & features["score__full_library"].notna(), ["time", "score__full_library"]].copy()
    best_by_date = eligible_scores.groupby("time")["score__full_library"].max().rename("buyable_best_score")
    cutoff_by_date = (
        eligible_scores.sort_values(["time", "score__full_library"], ascending=[True, False])
        .groupby("time", sort=True)
        .head(5)
        .groupby("time")["score__full_library"]
        .min()
        .rename("buyable_top5_cutoff_score")
    )
    features = features.merge(best_by_date, on="time", how="left")
    features = features.merge(cutoff_by_date, on="time", how="left")
    features["score_gap_to_buyable_best"] = (
        pd.to_numeric(features["buyable_best_score"], errors="coerce")
        - pd.to_numeric(features["score__full_library"], errors="coerce")
    )
    features["score_gap_to_buyable_top5_cutoff"] = (
        pd.to_numeric(features["buyable_top5_cutoff_score"], errors="coerce")
        - pd.to_numeric(features["score__full_library"], errors="coerce")
    )
    return features


def _prefix(frame: pd.DataFrame, prefix: str) -> pd.DataFrame:
    renamed = {column: f"{prefix}{column}" for column in frame.columns if column not in {"time", "ticker"}}
    return frame.rename(columns=renamed)


def _load_price_surfaces(
    tickers: pd.Series,
    stock_dir: Path,
    calendar: pd.DatetimeIndex,
) -> dict[str, pd.DataFrame]:
    parts: list[pd.DataFrame] = []
    for ticker in sorted(set(tickers.astype(str).str.upper())):
        path = stock_dir / f"gia_lich_su_{ticker}_1D.parquet"
        if not path.exists():
            continue
        part = pd.read_parquet(path, columns=["time", "high", "low", "close"]).copy()
        part["time"] = pd.to_datetime(part["time"], errors="coerce")
        part["ticker"] = ticker
        parts.append(part)
    if not parts:
        raise ValueError("No stock daily price files available for H337")
    panel = pd.concat(parts, ignore_index=True)
    out: dict[str, pd.DataFrame] = {}
    for column in ("high", "low", "close"):
        out[column] = panel.pivot(index="time", columns="ticker", values=column).reindex(index=calendar).sort_index()
    return out


def _hold_state(
    *,
    entry_execution_date: pd.Timestamp,
    decision_date: pd.Timestamp,
    ticker: str,
    entry_open: float,
    price_surfaces: dict[str, pd.DataFrame],
) -> dict[str, float | None]:
    close_wide = price_surfaces["close"]
    if ticker not in close_wide.columns or pd.isna(entry_execution_date) or pd.isna(decision_date):
        return {
            "current_close_return": None,
            "path_mae_so_far": None,
            "path_mfe_so_far": None,
            "drawdown_from_peak": None,
            "underwater_days_since_entry": None,
        }
    mask = (close_wide.index >= pd.Timestamp(entry_execution_date)) & (close_wide.index <= pd.Timestamp(decision_date))
    close_path = pd.to_numeric(close_wide.loc[mask, ticker], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    high_path = pd.to_numeric(price_surfaces["high"].loc[mask, ticker], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    low_path = pd.to_numeric(price_surfaces["low"].loc[mask, ticker], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    close_path = close_path.loc[close_path > 0.0]
    high_path = high_path.loc[high_path > 0.0]
    low_path = low_path.loc[low_path > 0.0]
    if close_path.empty or not (np.isfinite(entry_open) and entry_open > 0.0):
        return {
            "current_close_return": None,
            "path_mae_so_far": None,
            "path_mfe_so_far": None,
            "drawdown_from_peak": None,
            "underwater_days_since_entry": None,
        }
    close_returns = close_path.astype(float) / float(entry_open) - 1.0
    current_close_return = float(close_returns.iloc[-1])
    mfe = float(max(0.0, float(high_path.max()) / float(entry_open) - 1.0)) if not high_path.empty else float(max(0.0, close_returns.max()))
    mae = float(max(0.0, 1.0 - float(low_path.min()) / float(entry_open))) if not low_path.empty else float(max(0.0, -close_returns.min()))
    return {
        "current_close_return": current_close_return,
        "path_mae_so_far": mae,
        "path_mfe_so_far": mfe,
        "drawdown_from_peak": float(max(0.0, mfe - current_close_return)),
        "underwater_days_since_entry": int((close_returns < 0.0).sum()),
    }


def build_step_rows(
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
    previous_date = {
        pd.Timestamp(feature_dates[idx]): pd.Timestamp(feature_dates[idx - 1])
        for idx in range(1, len(feature_dates))
    }
    price_surfaces = _load_price_surfaces(entries["ticker"], stock_dir, feature_dates)

    by_entry = {int(entry_id): frame.sort_values("horizon") for entry_id, frame in horizons.groupby("entry_id")}
    rows: list[dict[str, object]] = []
    for entry in entries.itertuples(index=False):
        entry_id = int(entry.entry_id)
        frame = by_entry.get(entry_id)
        if frame is None or frame.empty:
            continue
        available = {
            int(h): bool(getattr(entry, f"h{h}_available", False)) and pd.notna(getattr(entry, f"h{h}_utility", np.nan))
            for h in HORIZONS
        }
        for horizon in DECISION_HORIZONS:
            next_horizon = NEXT_HORIZON[int(horizon)]
            if not available.get(int(horizon), False) or not available.get(int(next_horizon), False):
                continue
            scheduled_exit_series = frame.loc[frame["horizon"] == int(horizon), "scheduled_exit_date"]
            if scheduled_exit_series.empty:
                continue
            scheduled_exit_date = pd.Timestamp(scheduled_exit_series.iloc[0])
            decision_date = previous_date.get(scheduled_exit_date)
            if decision_date is None:
                continue
            hold_state = _hold_state(
                entry_execution_date=pd.Timestamp(entry.entry_execution_date),
                decision_date=decision_date,
                ticker=str(entry.ticker),
                entry_open=float(entry.entry_open),
                price_surfaces=price_surfaces,
            )
            current_utility = float(getattr(entry, f"h{horizon}_utility"))
            next_utility = float(getattr(entry, f"h{next_horizon}_utility"))
            row = {
                "entry_id": entry_id,
                "ticker": str(entry.ticker),
                "entry_signal_date": pd.Timestamp(entry.entry_signal_date),
                "entry_execution_date": pd.Timestamp(entry.entry_execution_date),
                "decision_date": pd.Timestamp(decision_date),
                "scheduled_exit_date": scheduled_exit_date,
                "current_horizon": int(horizon),
                "next_horizon": int(next_horizon),
                "current_utility": current_utility,
                "next_step_utility": next_utility,
                "step_delta_utility": float(next_utility - current_utility),
                "wait_one_more_label": int(next_utility > current_utility + 1e-12),
                "oracle_horizon": int(entry.oracle_horizon),
                "oracle_utility": float(entry.oracle_utility),
                "research_phase": str(entry.research_phase),
                **hold_state,
            }
            for hh in HORIZONS:
                row[f"h{hh}_utility"] = float(getattr(entry, f"h{hh}_utility")) if pd.notna(getattr(entry, f"h{hh}_utility", np.nan)) else np.nan
                row[f"h{hh}_relative_return"] = (
                    float(getattr(entry, f"h{hh}_relative_return"))
                    if pd.notna(getattr(entry, f"h{hh}_relative_return", np.nan))
                    else np.nan
                )
                row[f"h{hh}_available"] = bool(getattr(entry, f"h{hh}_available", False))
            rows.append(row)

    decisions = pd.DataFrame(rows)
    if decisions.empty:
        return decisions

    current_features = _prefix(features, "current_").rename(columns={"time": "decision_date"})
    entry_features = _prefix(features, "entry_").rename(columns={"time": "entry_signal_date"})
    decisions = decisions.merge(
        current_features,
        on=["decision_date", "ticker"],
        how="left",
    )
    decisions = decisions.merge(
        entry_features,
        on=["entry_signal_date", "ticker"],
        how="left",
        suffixes=("", "_entrydup"),
    )
    if "current_score__full_library" in decisions.columns and "entry_score__full_library" in decisions.columns:
        decisions["full_score_drop_since_entry"] = (
            pd.to_numeric(decisions["entry_score__full_library"], errors="coerce")
            - pd.to_numeric(decisions["current_score__full_library"], errors="coerce")
        )
        decisions["full_score_change_since_entry"] = (
            pd.to_numeric(decisions["current_score__full_library"], errors="coerce")
            - pd.to_numeric(decisions["entry_score__full_library"], errors="coerce")
        )
    if "current_full_library_rank" in decisions.columns and "entry_full_library_rank" in decisions.columns:
        decisions["full_rank_change_since_entry"] = (
            pd.to_numeric(decisions["current_full_library_rank"], errors="coerce")
            - pd.to_numeric(decisions["entry_full_library_rank"], errors="coerce")
        )
    if "current_full_library_rank_pct" in decisions.columns and "entry_full_library_rank_pct" in decisions.columns:
        decisions["full_rank_pct_change_since_entry"] = (
            pd.to_numeric(decisions["current_full_library_rank_pct"], errors="coerce")
            - pd.to_numeric(decisions["entry_full_library_rank_pct"], errors="coerce")
        )
    for horizon in DECISION_HORIZONS:
        decisions[f"horizon_eq_{horizon}"] = (decisions["current_horizon"] == int(horizon)).astype(float)
    decisions["max_available_horizon"] = decisions[[f"h{h}_available" for h in HORIZONS]].apply(
        lambda row: max((h for h in HORIZONS if bool(row[f"h{h}_available"])), default=max(HORIZONS)),
        axis=1,
    )
    return decisions


def _feature_columns(frame: pd.DataFrame) -> list[str]:
    base = [
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
        "current_buyable_best_score",
        "current_buyable_top5_cutoff_score",
        "current_score_gap_to_buyable_best",
        "current_score_gap_to_buyable_top5_cutoff",
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
    event = [f"current_{column}" for column in EVENT_FEATURES]
    return [
        column
        for column in [*base, *current_signal, *entry_signal, *activation, *tradability, *event]
        if column in frame.columns
    ]


def fit_model(decisions: pd.DataFrame, feature_columns: list[str]) -> tuple[Pipeline, pd.DataFrame, dict[str, object]]:
    train = decisions.loc[decisions["research_phase"] == "dev"].copy()
    if train.empty:
        raise ValueError("No dev rows available for H337")
    if train["wait_one_more_label"].nunique() < 2:
        raise ValueError("Dev wait-one-more labels have only one class")

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
    pipeline.fit(train[feature_columns].to_numpy(dtype=np.float64), train["wait_one_more_label"].astype(int).to_numpy())
    scored = decisions.copy()
    scored["wait_one_more_prob"] = pipeline.predict_proba(scored[feature_columns].to_numpy(dtype=np.float64))[:, 1]

    model = pipeline.named_steps["model"]
    coef = dict(zip(feature_columns, [float(x) for x in model.coef_[0]]))
    strongest = sorted(coef.items(), key=lambda item: abs(item[1]), reverse=True)[:20]
    model_summary = {
        "feature_count": int(len(feature_columns)),
        "dev_rows": int(len(train)),
        "dev_positive_rate": float(train["wait_one_more_label"].mean()),
        "strongest_standardized_coefficients": strongest,
    }
    return pipeline, scored, model_summary


def _auc(frame: pd.DataFrame) -> float | None:
    clean = frame[["wait_one_more_label", "wait_one_more_prob"]].replace([np.inf, -np.inf], np.nan).dropna()
    if clean.empty or clean["wait_one_more_label"].nunique() < 2:
        return None
    return float(roc_auc_score(clean["wait_one_more_label"].astype(int), clean["wait_one_more_prob"].astype(float)))


def _policy_for_entries(scored: pd.DataFrame, threshold: float) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    decision_by_entry = {int(entry_id): frame.sort_values("current_horizon") for entry_id, frame in scored.groupby("entry_id")}
    for entry_id, frame in decision_by_entry.items():
        first = frame.iloc[0]
        chosen = int(first["max_available_horizon"])
        last_prob = None
        for row in frame.itertuples(index=False):
            prob = float(row.wait_one_more_prob)
            last_prob = prob
            if prob < float(threshold):
                chosen = int(row.current_horizon)
                break
        utility_col = f"h{chosen}_utility"
        relative_col = f"h{chosen}_relative_return"
        rows.append(
            {
                "entry_id": int(entry_id),
                "ticker": str(first["ticker"]),
                "entry_signal_date": pd.Timestamp(first["entry_signal_date"]),
                "research_phase": str(first["research_phase"]),
                "model_horizon": int(chosen),
                "model_utility": float(first[utility_col]),
                "model_relative_return": float(first[relative_col]) if relative_col in first.index and pd.notna(first[relative_col]) else np.nan,
                "oracle_horizon": int(first["oracle_horizon"]),
                "oracle_utility": float(first["oracle_utility"]),
                "h3_utility": float(first["h3_utility"]) if pd.notna(first["h3_utility"]) else np.nan,
                "h5_utility": float(first["h5_utility"]) if pd.notna(first["h5_utility"]) else np.nan,
                "h10_utility": float(first["h10_utility"]) if pd.notna(first["h10_utility"]) else np.nan,
                "h15_utility": float(first["h15_utility"]) if pd.notna(first["h15_utility"]) else np.nan,
                "last_wait_one_more_prob": last_prob,
            }
        )
    return pd.DataFrame(rows)


def _h211_policy_for_entries(scored: pd.DataFrame, h211_params: dict[str, float]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    ret_thr = float(h211_params.get("return_since_entry_threshold", 0.15))
    score_drop_thr = float(h211_params.get("score_drop_threshold", 0.05))
    decision_by_entry = {int(entry_id): frame.sort_values("current_horizon") for entry_id, frame in scored.groupby("entry_id")}
    for entry_id, frame in decision_by_entry.items():
        first = frame.iloc[0]
        chosen = int(first["max_available_horizon"])
        trigger_horizon = None
        for row in frame.itertuples(index=False):
            current_return = float(row.current_close_return) if pd.notna(row.current_close_return) else np.nan
            score_drop = float(row.full_score_drop_since_entry) if pd.notna(row.full_score_drop_since_entry) else np.nan
            if np.isfinite(current_return) and np.isfinite(score_drop) and current_return >= ret_thr and score_drop >= score_drop_thr:
                chosen = int(row.current_horizon)
                trigger_horizon = int(row.current_horizon)
                break
        utility_col = f"h{chosen}_utility"
        rows.append(
            {
                "entry_id": int(entry_id),
                "research_phase": str(first["research_phase"]),
                "h211_horizon": int(chosen),
                "h211_trigger_horizon": trigger_horizon,
                "h211_utility": float(first[utility_col]),
            }
        )
    return pd.DataFrame(rows)


def summarize_policies(
    scored: pd.DataFrame,
    policy: pd.DataFrame,
    h211_policy: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, object]]:
    rows: list[dict[str, object]] = []
    for phase in ("dev", "validation", "confirmation"):
        dec = scored.loc[scored["research_phase"] == phase].copy()
        pol = policy.loc[policy["research_phase"] == phase].copy()
        h211 = h211_policy.loc[h211_policy["research_phase"] == phase].copy()
        if pol.empty:
            rows.append({"phase": phase, "entries": 0})
            continue
        fixed_means = {
            h: float(pol[f"h{h}_utility"].mean())
            for h in HORIZONS
            if f"h{h}_utility" in pol.columns and pol[f"h{h}_utility"].notna().any()
        }
        best_fixed_horizon = max(fixed_means, key=lambda h: fixed_means[h])
        best_fixed_utility = float(fixed_means[best_fixed_horizon])
        oracle_utility = float(pol["oracle_utility"].mean())
        model_utility = float(pol["model_utility"].mean())
        h211_utility = float(h211["h211_utility"].mean()) if not h211.empty else np.nan
        oracle_uplift = float(oracle_utility - best_fixed_utility)
        model_uplift = float(model_utility - best_fixed_utility)
        h211_uplift = float(h211_utility - best_fixed_utility) if np.isfinite(h211_utility) else np.nan
        rows.append(
            {
                "phase": phase,
                "decision_rows": int(len(dec)),
                "entries": int(len(pol)),
                "wait_label_rate": float(dec["wait_one_more_label"].mean()) if not dec.empty else None,
                "wait_prob_mean": float(dec["wait_one_more_prob"].mean()) if not dec.empty else None,
                "decision_auc": _auc(dec),
                "best_fixed_horizon": int(best_fixed_horizon),
                "best_fixed_utility_mean": best_fixed_utility,
                "model_utility_mean": model_utility,
                "h211_utility_mean": h211_utility,
                "oracle_utility_mean": oracle_utility,
                "model_uplift_vs_best_fixed": model_uplift,
                "h211_uplift_vs_best_fixed": h211_uplift,
                "model_delta_vs_h211": float(model_utility - h211_utility) if np.isfinite(h211_utility) else np.nan,
                "oracle_uplift_vs_best_fixed": oracle_uplift,
                "oracle_uplift_recovered_share": float(model_uplift / oracle_uplift) if abs(oracle_uplift) > 1e-12 else None,
                "model_not_best_fixed_rate": float((pol["model_horizon"] != int(best_fixed_horizon)).mean()),
                "model_matches_oracle_rate": float((pol["model_horizon"] == pol["oracle_horizon"]).mean()),
                "h211_not_best_fixed_rate": float((h211["h211_horizon"] != int(best_fixed_horizon)).mean()) if not h211.empty else np.nan,
            }
        )
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
    validation_vs_h211 = validation.get("model_delta_vs_h211")
    confirmation_vs_h211 = confirmation.get("model_delta_vs_h211")

    pass_condition = bool(
        validation_uplift is not None
        and confirmation_uplift is not None
        and validation_recovery is not None
        and confirmation_recovery is not None
        and validation_vs_h211 is not None
        and confirmation_vs_h211 is not None
        and float(validation_uplift) >= 0.005
        and float(confirmation_uplift) > 0.0
        and float(validation_recovery) >= 0.10
        and float(confirmation_recovery) >= 0.05
        and float(validation_vs_h211) > 0.0
        and float(confirmation_vs_h211) >= 0.0
        and (validation_auc is None or float(validation_auc) >= 0.52)
        and (confirmation_auc is None or float(confirmation_auc) >= 0.50)
    )
    mixed_condition = bool(
        validation_uplift is not None
        and confirmation_uplift is not None
        and validation_vs_h211 is not None
        and confirmation_vs_h211 is not None
        and (float(validation_uplift) > 0.0 or float(confirmation_uplift) > 0.0 or float(validation_vs_h211) > 0.0 or float(confirmation_vs_h211) > 0.0)
    )
    if pass_condition:
        verdict = "PASSED"
        branch_decision = (
            "The replacement-aware step-hazard recovered positive validation and confirmation utility over fixed exits "
            "and matched or beat the local H211 strength-exhaustion benchmark. Advance to a stricter hazard follow-up."
        )
    elif mixed_condition:
        verdict = "MIXED"
        branch_decision = (
            "The replacement-aware step-hazard improved one benchmark but did not clear the full confirmation bar. "
            "Narrow to a smaller state family or a stronger replacement-relative label before integration."
        )
    else:
        verdict = "FAILED"
        branch_decision = (
            "The replacement-aware step-hazard did not recover enough H334 oracle uplift out of sample. "
            "Do not continue smart-exit ML on the current daily state without new post-entry data or a materially better label."
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
        "validation_model_delta_vs_h211": validation_vs_h211,
        "confirmation_model_delta_vs_h211": confirmation_vs_h211,
    }
    return phase_results, decision


def main() -> int:
    args = parse_args()
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    DETAILS_DIR.mkdir(parents=True, exist_ok=True)

    h334_artifacts = _resolve_h334_artifacts(args.h334_summary)
    h211_params = _resolve_h211_params(args.h211_summary)
    entry_outcomes = pd.read_parquet(h334_artifacts["entry_outcomes"])
    horizon_outcomes = pd.read_parquet(h334_artifacts["horizon_outcomes"])
    features = _load_feature_surface(
        Path(args.matrix),
        Path(args.activation),
        Path(args.tradability),
        Path(args.event),
    )
    decisions = build_step_rows(
        entry_outcomes=entry_outcomes,
        horizon_outcomes=horizon_outcomes,
        features=features,
        stock_dir=Path(args.stock_dir),
    )
    if decisions.empty:
        raise ValueError("No H337 step rows built")

    feature_columns = _feature_columns(decisions)
    _, scored, model_summary = fit_model(decisions, feature_columns)
    policy = _policy_for_entries(scored, float(args.hold_threshold))
    h211_policy = _h211_policy_for_entries(scored, h211_params)
    phase_results, decision = summarize_policies(scored, policy, h211_policy)

    step_rows_path = OUT_DIR / f"{ts}_h337_replacement_aware_step_hazard_step_rows.parquet"
    policy_path = OUT_DIR / f"{ts}_h337_replacement_aware_step_hazard_policy_entries.parquet"
    h211_policy_path = OUT_DIR / f"{ts}_h337_replacement_aware_step_hazard_h211_policy_entries.parquet"
    phase_results_path = OUT_DIR / f"{ts}_h337_replacement_aware_step_hazard_phase_results.parquet"
    details_path = DETAILS_DIR / f"{ts}_h337_replacement_aware_step_hazard_details.json"

    scored.to_parquet(step_rows_path, index=False)
    policy.to_parquet(policy_path, index=False)
    h211_policy.to_parquet(h211_policy_path, index=False)
    phase_results.to_parquet(phase_results_path, index=False)

    summary = {
        **decision,
        "mechanics": {
            "h334_summary": str(h334_artifacts["summary"]),
            "entry_outcomes": str(h334_artifacts["entry_outcomes"]),
            "horizon_outcomes": str(h334_artifacts["horizon_outcomes"]),
            "step_rows": int(len(scored)),
            "policy_entries": int(len(policy)),
            "feature_count": int(len(feature_columns)),
            "hold_threshold": float(args.hold_threshold),
            "decision_horizons": list(DECISION_HORIZONS),
            "max_horizon": int(max(HORIZONS)),
            "event_feature_count": int(sum(1 for col in EVENT_FEATURES if f"current_{col}" in feature_columns)),
            "h211_local_params": h211_params,
        },
        "model": model_summary,
        "phase_results": phase_results.to_dict(orient="records"),
    }
    details_path.write_text(json.dumps(summary, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")

    summary_path = write_run_summary(
        ts=ts,
        mode="research_branch_replacement_aware_step_hazard",
        name="h337_replacement_aware_step_hazard",
        summary=summary,
        artifacts={
            "step_rows": step_rows_path,
            "policy_entries": policy_path,
            "h211_policy_entries": h211_policy_path,
            "phase_results": phase_results_path,
            "details": details_path,
        },
        metadata={
            "hypothesis": "A one-step, replacement-aware hazard with current hold-day state can recover useful legal-exit oracle uplift better than entry-time routing or unconditional hold labels.",
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
        "h211_utility_mean",
        "best_fixed_utility_mean",
        "model_uplift_vs_best_fixed",
        "model_delta_vs_h211",
        "oracle_uplift_recovered_share",
    ]
    print("H337 replacement-aware step-hazard")
    print("=" * 72)
    print(f"verdict: {decision['verdict']}")
    print(f"branch decision: {decision['branch_decision']}")
    print(phase_results[display_cols].to_string(index=False))
    print(f"summary: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
