"""
H302: news-attention disagreement audit.

Question:
    Does LLM novelty become useful only when it is not already crowded by
    repeated article coverage?
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

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.run_summary import write_run_summary


LLM_PATH = data_path("features/xs_llm_news_ticker_day.parquet")
ROLLING_NEWS_PATH = data_path("features/xs_news_sentiment_rolling.parquet")
BARRIER_PATH = data_path("features/xs_barrier_vol_1d_hose_full.parquet")
PANEL_PATH = data_path("features/entry_alpha/candidate_panel_daily.parquet")
LABELS_PATH = data_path("features/entry_alpha/entry_labels_cycle5.parquet")
OUT_DIR = ROOT / "artifacts" / "portfolio_baselines"


def _safe_float(value: object) -> float | None:
    numeric = pd.to_numeric(value, errors="coerce")
    return None if pd.isna(numeric) else float(numeric)


def _daily_ic_series(df: pd.DataFrame, feature_col: str, target_col: str) -> pd.DataFrame:
    rows = []
    for time, group in df.groupby("time", sort=True):
        gg = group[[feature_col, target_col]].replace([np.inf, -np.inf], np.nan).dropna()
        if len(gg) < 6 or gg[feature_col].nunique() < 3 or gg[target_col].nunique() < 2:
            continue
        rho = spearmanr(gg[feature_col], gg[target_col]).statistic
        if np.isfinite(rho):
            rows.append({"time": pd.Timestamp(time), "ic": float(np.asarray(rho).flat[0]), "n": int(len(gg))})
    return pd.DataFrame(rows)


def _summary_from_series(series: pd.DataFrame) -> dict[str, object]:
    if series.empty:
        return {"mean_ic": None, "hit_rate": None, "positive_years": 0, "years_present": 0, "days": 0}
    yearly = series.assign(year=series["time"].dt.year).groupby("year")["ic"].mean()
    return {
        "mean_ic": _safe_float(series["ic"].mean()),
        "hit_rate": _safe_float((series["ic"] > 0.0).mean()),
        "positive_years": int((yearly > 0.0).sum()),
        "years_present": int(len(yearly)),
        "days": int(len(series)),
    }


def _build_marginal_panel() -> pd.DataFrame:
    panel = pd.read_parquet(
        PANEL_PATH,
        columns=["time", "ticker", "is_held_prev_close"],
    ).copy()
    labels = pd.read_parquet(
        LABELS_PATH,
        columns=["time", "ticker", "cycle_relative_return_vs_vnindex"],
    ).copy()
    panel["time"] = pd.to_datetime(panel["time"], errors="coerce").dt.normalize()
    labels["time"] = pd.to_datetime(labels["time"], errors="coerce").dt.normalize()
    panel = panel.loc[panel["time"].dt.year.between(2018, 2025)].copy()
    labels = labels.loc[labels["time"].dt.year.between(2018, 2025)].copy()
    work = panel.merge(labels, on=["time", "ticker"], how="inner", validate="one_to_one")
    weakest = (
        work.loc[work["is_held_prev_close"].fillna(False).astype(bool)]
        .groupby("time")["cycle_relative_return_vs_vnindex"]
        .min()
        .rename("weakest_held_cycle_rel")
    )
    work = work.merge(weakest, on="time", how="left")
    work["marginal_label"] = work["cycle_relative_return_vs_vnindex"] - work["weakest_held_cycle_rel"]
    return work[["time", "ticker", "marginal_label"]].dropna()


def main() -> None:
    llm = pd.read_parquet(
        LLM_PATH,
        columns=[
            "time",
            "ticker",
            "llm_sentiment_raw",
            "llm_new_info_5d",
            "llm_followup_info_5d",
        ],
    ).copy()
    llm["time"] = pd.to_datetime(llm["time"], errors="coerce").dt.normalize()
    active_window = llm.loc[llm["time"].dt.year.between(2018, 2025)].copy()
    nonzero_mask = active_window[["llm_sentiment_raw", "llm_new_info_5d", "llm_followup_info_5d"]].abs().max(axis=1) > 0.0
    active_nonzero_rows = int(nonzero_mask.sum())

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    if active_nonzero_rows == 0:
        summary = {
            "decision": "SKIP",
            "blocked": True,
            "reason": "No nonzero LLM ticker-day rows exist in the active-book years.",
            "active_window": {"start_date": "2018-01-01", "end_date": "2025-12-31"},
            "rows_2018_2025": int(len(active_window)),
            "nonzero_rows_2018_2025": active_nonzero_rows,
            "branch_contract": (
                "Do not run the novelty x attention disagreement audit until xs_llm_news_ticker_day.parquet "
                "contains nonzero active-book coverage."
            ),
        }
        write_run_summary(
            ts=ts,
            mode="research_branch_news_attention_disagreement",
            name="h302_news_attention_disagreement",
            summary=summary,
            artifacts={},
            metadata={"session": 128, "blocked": True},
        )
        print(json.dumps(summary, indent=2))
        return

    llm = active_window.loc[nonzero_mask].copy()
    rolling = pd.read_parquet(
        ROLLING_NEWS_PATH,
        columns=["time", "ticker", "article_count_5d", "article_count_30d", "positive_ratio_5d"],
    ).copy()
    barrier = pd.read_parquet(BARRIER_PATH, columns=["time", "ticker", "actual"]).copy()
    for frame in (rolling, barrier):
        frame["time"] = pd.to_datetime(frame["time"], errors="coerce").dt.normalize()
    rolling = rolling.loc[rolling["time"].dt.year.between(2018, 2025)].copy()
    barrier = barrier.loc[barrier["time"].dt.year.between(2018, 2025)].copy()

    llm["article_count_5d_rank"] = pd.to_numeric(llm["llm_new_info_5d"], errors="coerce")
    panel = llm.merge(rolling, on=["time", "ticker"], how="left", validate="one_to_one")
    panel = panel.merge(barrier, on=["time", "ticker"], how="inner", validate="one_to_one")
    panel["article_count_5d"] = pd.to_numeric(panel["article_count_5d"], errors="coerce").fillna(0.0)
    panel["article_count_5d_rank"] = panel.groupby("time")["article_count_5d"].rank(method="average", pct=True)
    panel["uncrowded_new_score"] = pd.to_numeric(panel["llm_new_info_5d"], errors="coerce") * (1.0 - panel["article_count_5d_rank"])
    panel["attention_disagreement_score"] = (
        pd.to_numeric(panel["llm_sentiment_raw"], errors="coerce") - panel["article_count_5d_rank"]
    )
    panel["novelty_balance_score"] = (
        pd.to_numeric(panel["llm_new_info_5d"], errors="coerce") - pd.to_numeric(panel["llm_followup_info_5d"], errors="coerce")
    ) * (1.0 - panel["article_count_5d_rank"])

    marginal = _build_marginal_panel()
    marginal_panel = panel.merge(marginal, on=["time", "ticker"], how="inner")

    feature_summaries = {}
    for feature in ("uncrowded_new_score", "attention_disagreement_score", "novelty_balance_score"):
        barrier_stats = _summary_from_series(_daily_ic_series(panel, feature, "actual"))
        marginal_stats = _summary_from_series(_daily_ic_series(marginal_panel, feature, "marginal_label"))
        feature_summaries[feature] = {
            "barrier": barrier_stats,
            "marginal": marginal_stats,
        }

    best_feature = max(
        feature_summaries,
        key=lambda name: (
            _safe_float(feature_summaries[name]["barrier"]["mean_ic"]) or float("-inf"),
            _safe_float(feature_summaries[name]["marginal"]["mean_ic"]) or float("-inf"),
        ),
    )
    summary = {
        "decision": "PASSED" if (_safe_float(feature_summaries[best_feature]["barrier"]["mean_ic"]) or 0.0) > 0.01 else "MIXED",
        "blocked": False,
        "best_feature": best_feature,
        "feature_summaries": feature_summaries,
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    panel_path = OUT_DIR / f"{ts}_h302_news_attention_disagreement_panel.parquet"
    details_path = ROOT / "artifacts" / "run_summaries" / f"{ts}_h302_news_attention_disagreement_details.json"
    panel.to_parquet(panel_path, index=False)
    details_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    write_run_summary(
        ts=ts,
        mode="research_branch_news_attention_disagreement",
        name="h302_news_attention_disagreement",
        summary=summary,
        artifacts={"panel": str(panel_path), "details": str(details_path)},
        metadata={"session": 128, "blocked": False},
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
