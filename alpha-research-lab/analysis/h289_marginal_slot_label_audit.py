"""
H289 - Marginal-slot label audit.

Question:
- If we relabel the activated book as candidate return minus the weakest held
  return on the same day, do the existing entry-alpha score-gap features still
  separate the target in a monotone way?

Design:
- join the entry-alpha candidate panel with the cycle-5 labels
- define the marginal label as:
  candidate_cycle_relative_return_vs_vnindex - weakest_held_cycle_relative_return_vs_vnindex
- restrict to 2019-2025
- test a small basket of existing row-level entry-alpha features on the marginal label
- keep only the features that are actually row-varying within a date

Usage:
    conda run -n stocks python analysis/h289_marginal_slot_label_audit.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from path_utils import data_path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.run_summary import write_run_summary

PANEL_PATH = data_path("features/entry_alpha/candidate_panel_daily.parquet")
LABELS_PATH = data_path("features/entry_alpha/entry_labels_cycle5.parquet")

FEATURES = [
    "selection_score",
    "selection_rank",
    "selection_score_gap_to_next_candidate",
    "selection_score_gap_to_top_k_cutoff",
]


def _daily_ic_series(df: pd.DataFrame, feature_col: str, target_col: str) -> pd.DataFrame:
    rows = []
    for time, group in df.groupby("time", sort=True):
        gg = group[[feature_col, target_col]].replace([np.inf, -np.inf], np.nan).dropna()
        if len(gg) < 3:
            continue
        if gg[feature_col].nunique() < 2 or gg[target_col].nunique() < 2:
            continue
        rho, p = spearmanr(gg[feature_col], gg[target_col])
        if np.isfinite(rho):
            rows.append({"time": pd.to_datetime(time), "ic": float(rho), "p_value": float(p), "n": int(len(gg))})
    return pd.DataFrame(rows)


def _quintile_table(frame: pd.DataFrame, feature_col: str, target_col: str) -> pd.DataFrame:
    work = frame[[feature_col, target_col]].replace([np.inf, -np.inf], np.nan).dropna().copy()
    if work.empty or work[feature_col].nunique() < 5:
        return pd.DataFrame()
    work["quintile"] = pd.qcut(work[feature_col].rank(method="first"), 5, labels=False) + 1
    summary = (
        work.groupby("quintile", sort=True)
        .agg(
            n=(target_col, "size"),
            feature_mean=(feature_col, "mean"),
            label_mean=(target_col, "mean"),
        )
        .reset_index()
    )
    summary["winner"] = np.where(summary["label_mean"] > 0.0, "positive", "negative")
    return summary


def main() -> None:
    print("Building marginal-slot label audit panel...")

    panel = pd.read_parquet(PANEL_PATH, columns=["time", "ticker", "is_held_prev_close", *FEATURES]).copy()
    labels = pd.read_parquet(LABELS_PATH, columns=["time", "ticker", "cycle_relative_return_vs_vnindex", "buy_now_label"]).copy()

    panel["time"] = pd.to_datetime(panel["time"], errors="coerce")
    labels["time"] = pd.to_datetime(labels["time"], errors="coerce")
    panel = panel[(panel["time"].dt.year >= 2019) & (panel["time"].dt.year <= 2025)].copy()
    labels = labels[(labels["time"].dt.year >= 2019) & (labels["time"].dt.year <= 2025)].copy()

    work = panel.merge(labels, on=["time", "ticker"], how="inner", validate="one_to_one")
    work["is_held_prev_close"] = work["is_held_prev_close"].fillna(False)

    weakest = (
        work.loc[work["is_held_prev_close"]]
        .groupby("time")["cycle_relative_return_vs_vnindex"]
        .min()
        .rename("weakest_held_cycle_rel")
    )
    work = work.merge(weakest, on="time", how="left")
    work = work.dropna(subset=["weakest_held_cycle_rel", "cycle_relative_return_vs_vnindex"])
    work["marginal_label"] = work["cycle_relative_return_vs_vnindex"] - work["weakest_held_cycle_rel"]

    feature_results: dict[str, dict[str, object]] = {}
    for feat in FEATURES:
        series = _daily_ic_series(work, feat, "marginal_label")
        if series.empty:
            feature_results[feat] = {
                "mean_ic": float("nan"),
                "p_value_mean": float("nan"),
                "positive_years": 0,
                "years_present": 0,
                "daily_rows": 0,
                "quintile_table": [],
            }
            continue
        years = []
        for year, frame in series.assign(year=series["time"].dt.year).groupby("year"):
            if frame["ic"].mean() > 0.0:
                years.append(int(year))
        qtab = _quintile_table(work, feat, "marginal_label")
        feature_results[feat] = {
            "mean_ic": float(series["ic"].mean()),
            "p_value_mean": float(series["p_value"].mean()),
            "positive_years": int(len(years)),
            "years_present": int(series["time"].dt.year.nunique()),
            "daily_rows": int(len(series)),
            "quintile_table": qtab.to_dict("records"),
        }

    best_feat, best_metrics = max(
        feature_results.items(),
        key=lambda item: (abs(item[1]["mean_ic"]), item[1]["positive_years"]),
    )
    best_qtab = pd.DataFrame(best_metrics["quintile_table"])
    if best_qtab.empty:
        q1_mean = q5_mean = float("nan")
        monotone = False
    else:
        q1_mean = float(best_qtab.loc[best_qtab["quintile"] == 1, "label_mean"].iloc[0])
        q5_mean = float(best_qtab.loc[best_qtab["quintile"] == 5, "label_mean"].iloc[0])
        monotone = bool(q1_mean < q5_mean)

    best_abs_ic = abs(float(best_metrics["mean_ic"]))
    pass_condition = bool(best_abs_ic >= 0.02 and best_metrics["positive_years"] >= 5 and monotone)
    mixed_condition = bool(best_abs_ic >= 0.005 or monotone)
    verdict = "PASS" if pass_condition else "MIXED" if mixed_condition else "FAIL"

    print("\nH289 MARGINAL-SLOT LABEL RESULTS")
    print("=" * 132)
    print(f"{'feature':<36} {'mean_ic':>9} {'p_mean':>9} {'pos_years':>10} {'days':>8}")
    print("-" * 132)
    for feat, metrics in feature_results.items():
        print(
            f"{feat:<36} {metrics['mean_ic']:>+9.4f} {metrics['p_value_mean']:>9.4g} "
            f"{metrics['positive_years']:>10d} {metrics['daily_rows']:>8d}"
        )

    if not best_qtab.empty:
        print("\nBest feature quintiles:")
        for row in best_qtab.itertuples(index=False):
            print(
                f"  q{int(row.quintile)}: n={int(row.n):4d} "
                f"feature_mean={float(row.feature_mean):+.4f} label_mean={float(row.label_mean):+.4f}"
            )

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    details_path = REPO_ROOT / "artifacts" / "run_summaries" / f"{ts}_h289_marginal_slot_label_audit_details.json"
    summary = {
        "verdict": verdict,
        "best_feature": best_feat,
        "best_metrics": best_metrics,
        "feature_results": feature_results,
        "panel_rows": int(len(work)),
        "panel_dates": int(work["time"].nunique()),
        "label_mean": float(work["marginal_label"].mean()),
        "label_positive_rate": float((work["marginal_label"] > 0.0).mean()),
        "best_q1_mean": q1_mean,
        "best_q5_mean": q5_mean,
        "monotone": monotone,
        "pass_condition": pass_condition,
        "mixed_condition": mixed_condition,
    }
    details_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    path = write_run_summary(
        ts=ts,
        mode="standalone_signal",
        name="h289_marginal_slot_label_audit",
        summary=summary,
        artifacts={"details_json": str(details_path)},
        metadata={"signal": "H289"},
    )
    print(f"\nsummary: {path}")


if __name__ == "__main__":
    main()
