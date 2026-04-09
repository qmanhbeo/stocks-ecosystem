"""
H295: big-name cohort audit.

Question:
    While waiting for the LLM cache to finish, should the lab reopen
    stock-local work by sweeping the big HOSE names one by one?

Smallest honest test:
    Freeze the canonical S1/H93 probability surface, use a predeclared
    big-name proxy (VN30 constituents), and compare:
      1. internal cross-sectional quality for the big-name cohort
      2. the same metrics for the rest of the universe
      3. stock-level selection-edge stability inside the big-name cohort

Decision rule:
    PASSED:
      - big-name cohort keeps >= 80% of full-universe IC
      - big-name cohort keeps >= 50% of full-universe top-5 edge
      - dev->validation stock-edge rank correlation >= 0.30
    MIXED:
      - big-name cohort stays directionally positive, but fails the pass bar
      - keep only a narrow follow-up (execution/router or recipient audit)
    FAILED:
      - big-name cohort loses most of the signal and shows no stable stock-level
        structure worth continuing
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.run_summary import write_run_summary
from src.standalone_signal_utils import load_s1_frame

TOP_N = 5
START_YEAR = 2015
END_YEAR = 2025
DEV_END_YEAR = 2022
VAL_END_YEAR = 2024
MIN_DEV_DAYS = 20
MIN_VAL_DAYS = 10
PASS_IC_RETENTION = 0.80
PASS_EDGE_RETENTION = 0.50
PASS_RANK_STABILITY = 0.30

# Frozen big-name proxy for HOSE.
VN30_TICKERS = {
    "ACB",
    "BCM",
    "BID",
    "BVH",
    "CTG",
    "FPT",
    "GAS",
    "GVR",
    "HDB",
    "HPG",
    "MBB",
    "MWG",
    "NVL",
    "PDR",
    "PLX",
    "PNJ",
    "POW",
    "SAB",
    "SHB",
    "SSI",
    "STB",
    "TCB",
    "TPB",
    "VCB",
    "VHM",
    "VIB",
    "VIC",
    "VJC",
    "VNM",
    "VPB",
}


def _cohort_daily_metrics(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, float | int | pd.Timestamp]] = []
    for date, day in frame.groupby("time"):
        day = day[["ticker", "xs_proba", "actual"]].replace([np.inf, -np.inf], np.nan).dropna()
        if len(day) < 10:
            continue
        ranks = day["xs_proba"].rank(method="average", pct=True)
        q5 = day.loc[ranks >= 0.8, "actual"].mean()
        q1 = day.loc[ranks <= 0.2, "actual"].mean()
        top = day.nlargest(min(TOP_N, len(day)), "xs_proba")
        rho = spearmanr(day["xs_proba"], day["actual"]).statistic
        rows.append(
            {
                "time": pd.Timestamp(date),
                "year": int(pd.Timestamp(date).year),
                "n_tickers": int(len(day)),
                "ic": float(np.asarray(rho).flat[0]),
                "q5_q1_spread": float(q5 - q1),
                "top5_edge": float(top["actual"].mean() - day["actual"].mean()),
                "baseline_hit_rate": float(day["actual"].mean()),
                "top5_hit_rate": float(top["actual"].mean()),
            }
        )
    return pd.DataFrame(rows)


def _summarize_cohort(label: str, frame: pd.DataFrame) -> tuple[dict[str, object], pd.DataFrame]:
    daily = _cohort_daily_metrics(frame)
    if daily.empty:
        return {
            "cohort": label,
            "days": 0,
            "avg_n_tickers": None,
            "avg_ic": None,
            "avg_q5_q1_spread": None,
            "avg_top5_edge": None,
            "avg_baseline_hit_rate": None,
            "avg_top5_hit_rate": None,
            "positive_ic_years": 0,
            "years": 0,
        }, daily

    yearly = (
        daily.groupby("year")[["ic", "q5_q1_spread", "top5_edge"]]
        .mean()
        .reset_index()
        .sort_values("year")
    )
    return {
        "cohort": label,
        "days": int(len(daily)),
        "avg_n_tickers": float(daily["n_tickers"].mean()),
        "avg_ic": float(daily["ic"].mean()),
        "avg_q5_q1_spread": float(daily["q5_q1_spread"].mean()),
        "avg_top5_edge": float(daily["top5_edge"].mean()),
        "avg_baseline_hit_rate": float(daily["baseline_hit_rate"].mean()),
        "avg_top5_hit_rate": float(daily["top5_hit_rate"].mean()),
        "positive_ic_years": int((yearly["ic"] > 0).sum()),
        "years": int(len(yearly)),
    }, yearly


def _window_label(ts: pd.Timestamp) -> str:
    year = int(ts.year)
    if year <= DEV_END_YEAR:
        return "dev_2015_2022"
    if year <= VAL_END_YEAR:
        return "val_2023_2024"
    return "tail_2025"


def _build_selection_panel(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for date, day in frame.groupby("time"):
        day = day[["time", "ticker", "xs_proba", "actual"]].replace([np.inf, -np.inf], np.nan).dropna()
        if len(day) < TOP_N:
            continue
        top = day.nlargest(TOP_N, "xs_proba").copy()
        base = float(day["actual"].mean())
        top["selection_edge"] = top["actual"] - base
        top["window"] = _window_label(pd.Timestamp(date))
        rows.append(top[["time", "ticker", "window", "selection_edge"]])
    if not rows:
        return pd.DataFrame(columns=["time", "ticker", "window", "selection_edge"])
    return pd.concat(rows, ignore_index=True)


def _stock_edge_table(frame: pd.DataFrame) -> tuple[pd.DataFrame, float | None]:
    selected = _build_selection_panel(frame)
    if selected.empty:
        return pd.DataFrame(), None

    edge_stats = (
        selected.groupby(["ticker", "window"])["selection_edge"]
        .agg(["mean", "count"])
        .reset_index()
        .rename(columns={"mean": "edge", "count": "selected_days"})
    )

    edge_wide = edge_stats.pivot(index="ticker", columns="window", values="edge")
    day_wide = edge_stats.pivot(index="ticker", columns="window", values="selected_days")

    tickers = sorted(selected["ticker"].unique())
    rows: list[dict[str, object]] = []
    for ticker in tickers:
        row = {"ticker": ticker}
        for window in ["dev_2015_2022", "val_2023_2024", "tail_2025"]:
            row[f"{window}_edge"] = float(edge_wide.at[ticker, window]) if window in edge_wide.columns and pd.notna(edge_wide.at[ticker, window]) else None
            row[f"{window}_days"] = int(day_wide.at[ticker, window]) if window in day_wide.columns and pd.notna(day_wide.at[ticker, window]) else 0
        dev_edge = row["dev_2015_2022_edge"]
        val_edge = row["val_2023_2024_edge"]
        dev_days = row["dev_2015_2022_days"]
        val_days = row["val_2023_2024_days"]
        qualified = dev_days >= MIN_DEV_DAYS and val_days >= MIN_VAL_DAYS
        row["qualified_dev_val"] = qualified
        row["stable_positive_dev_val"] = bool(
            qualified and dev_edge is not None and val_edge is not None and dev_edge > 0 and val_edge > 0
        )
        if dev_edge is not None and val_edge is not None:
            row["avg_dev_val_edge"] = float((dev_edge + val_edge) / 2.0)
            row["min_dev_val_edge"] = float(min(dev_edge, val_edge))
        else:
            row["avg_dev_val_edge"] = None
            row["min_dev_val_edge"] = None
        rows.append(row)

    table = pd.DataFrame(rows).sort_values(
        by=["stable_positive_dev_val", "min_dev_val_edge", "avg_dev_val_edge"],
        ascending=[False, False, False],
        ignore_index=True,
    )

    qualified = table[table["qualified_dev_val"]].copy()
    if len(qualified) >= 5:
        stability = spearmanr(
            qualified["dev_2015_2022_edge"],
            qualified["val_2023_2024_edge"],
        ).statistic
        stability = float(np.asarray(stability).flat[0])
    else:
        stability = None
    return table, stability


def _safe_ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return float(numerator / denominator)


def main() -> None:
    s1 = load_s1_frame()[["time", "ticker", "xs_proba", "actual"]]
    s1 = s1.loc[s1["time"].dt.year.between(START_YEAR, END_YEAR)].copy()

    available_big_names = sorted(VN30_TICKERS & set(s1["ticker"].unique()))
    big_frame = s1[s1["ticker"].isin(available_big_names)].copy()
    rest_frame = s1[~s1["ticker"].isin(available_big_names)].copy()

    full_summary, full_yearly = _summarize_cohort("full_universe", s1)
    big_summary, big_yearly = _summarize_cohort("big_name_vn30_proxy", big_frame)
    rest_summary, rest_yearly = _summarize_cohort("rest_of_universe", rest_frame)

    big_summary["ic_retention_vs_full"] = _safe_ratio(big_summary["avg_ic"], full_summary["avg_ic"])
    big_summary["top5_edge_retention_vs_full"] = _safe_ratio(big_summary["avg_top5_edge"], full_summary["avg_top5_edge"])
    big_summary["spread_retention_vs_full"] = _safe_ratio(big_summary["avg_q5_q1_spread"], full_summary["avg_q5_q1_spread"])

    rest_summary["ic_retention_vs_full"] = _safe_ratio(rest_summary["avg_ic"], full_summary["avg_ic"])
    rest_summary["top5_edge_retention_vs_full"] = _safe_ratio(rest_summary["avg_top5_edge"], full_summary["avg_top5_edge"])
    rest_summary["spread_retention_vs_full"] = _safe_ratio(rest_summary["avg_q5_q1_spread"], full_summary["avg_q5_q1_spread"])

    stock_table, dev_val_rank_stability = _stock_edge_table(big_frame)
    qualified = stock_table[stock_table["qualified_dev_val"]].copy()
    stable_positive = stock_table[stock_table["stable_positive_dev_val"]].copy()

    pass_big_name = bool(
        (big_summary["ic_retention_vs_full"] or 0.0) >= PASS_IC_RETENTION
        and (big_summary["top5_edge_retention_vs_full"] or 0.0) >= PASS_EDGE_RETENTION
        and (dev_val_rank_stability or 0.0) >= PASS_RANK_STABILITY
    )
    mixed_big_name = bool(
        (big_summary["avg_ic"] or 0.0) > 0.05
        and (big_summary["top5_edge_retention_vs_full"] or 0.0) > 0.20
        and len(stable_positive) >= 5
    )

    if pass_big_name:
        verdict = "PASSED"
        branch_decision = (
            "The big-name cohort retains enough of the frozen S1 signal to justify a narrow "
            "recipient-first follow-through."
        )
    elif mixed_big_name:
        verdict = "MIXED"
        branch_decision = (
            "Generic big-name cohort revival is not justified. Some stock-local response exists "
            "inside the big-name proxy, but the cohort loses too much signal and the stock ranking "
            "is not stable enough to reopen a broad stock-local branch."
        )
    else:
        verdict = "FAILED"
        branch_decision = (
            "Kill the big-name stock-local branch under the current contract. "
            "Only execution/router work would remain worth testing."
        )

    top_names = stock_table[
        [
            "ticker",
            "dev_2015_2022_edge",
            "dev_2015_2022_days",
            "val_2023_2024_edge",
            "val_2023_2024_days",
            "tail_2025_edge",
            "tail_2025_days",
            "stable_positive_dev_val",
            "min_dev_val_edge",
        ]
    ].head(10)

    cohort_table = pd.DataFrame([full_summary, big_summary, rest_summary])
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    out_dir = REPO_ROOT / "artifacts" / "portfolio_baselines"
    out_dir.mkdir(parents=True, exist_ok=True)
    cohort_path = out_dir / f"{ts}_h295_big_name_cohort_metrics.parquet"
    stock_path = out_dir / f"{ts}_h295_big_name_stock_edges.parquet"
    details_path = REPO_ROOT / "artifacts" / "run_summaries" / f"{ts}_h295_big_name_cohort_audit_details.json"

    cohort_table.to_parquet(cohort_path, index=False)
    stock_table.to_parquet(stock_path, index=False)

    summary_payload = {
        "verdict": verdict,
        "hypothesis": (
            "If stock-local work is still alive anywhere, a frozen big-name HOSE proxy should keep "
            "most of the S1 signal and show stable stock-level response ordering."
        ),
        "decision_rule": {
            "pass_ic_retention_vs_full": PASS_IC_RETENTION,
            "pass_top5_edge_retention_vs_full": PASS_EDGE_RETENTION,
            "pass_dev_val_rank_stability": PASS_RANK_STABILITY,
            "min_dev_days": MIN_DEV_DAYS,
            "min_val_days": MIN_VAL_DAYS,
        },
        "cohorts": cohort_table.to_dict(orient="records"),
        "stock_local_diagnostics": {
            "big_name_proxy_size": len(available_big_names),
            "qualified_names": int(len(qualified)),
            "stable_positive_dev_val_names": int(len(stable_positive)),
            "dev_val_edge_rank_spearman": dev_val_rank_stability,
            "top_names_by_min_dev_val_edge": top_names.to_dict(orient="records"),
        },
        "branch_decision": branch_decision,
    }
    details_path.write_text(json.dumps(summary_payload, indent=2), encoding="utf-8")

    write_run_summary(
        ts=ts,
        mode="research_branch_big_name_cohort_audit",
        name="h295_big_name_cohort_audit",
        summary=summary_payload,
        artifacts={
            "cohort_metrics": str(cohort_path),
            "stock_edges": str(stock_path),
            "details": str(details_path),
        },
        metadata={
            "session": 126,
            "signal_surface": "data/features/xs_barrier_vol_1d_hose_full.parquet",
            "big_name_proxy": sorted(available_big_names),
            "top_n": TOP_N,
            "years": [START_YEAR, END_YEAR],
        },
    )

    print("H295 big-name cohort audit")
    print(cohort_table.to_string(index=False))
    print("\nTop big-name recipients")
    print(top_names.to_string(index=False))
    print(f"\nDev->validation edge rank Spearman: {dev_val_rank_stability}")
    print(f"Verdict: {verdict}")
    print(branch_decision)


if __name__ == "__main__":
    main()
