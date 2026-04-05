"""
H281: LLM news sentiment gate audit.

This is the smallest honest pass for the queued llm-news-gate branch.
It evaluates the built LLM ticker-day sentiment surface against the
1-day barrier label and compares the best candidate with the legacy
keyword-news baseline C1.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.run_summary import write_run_summary
from src.standalone_signal_utils import daily_ic, load_s1_frame, spearman_stat, yearly_ic, summarize_ic

LLM_PATH = REPO_ROOT / "data/features/xs_llm_news_ticker_day.parquet"
C1_PATH = REPO_ROOT / "data/features/xs_news_sentiment_daily.parquet"

LLM_CANDIDATES = [
    "llm_sentiment_raw",
    "llm_sentiment_conf_weighted",
    "llm_sentiment_5d",
    "llm_sentiment_30d",
    "llm_magnitude_5d",
]

C1_CANDIDATES = [
    "sentiment_score",
    "sentiment_cs_z",
]


def _safe_yearly_summary(frame: pd.DataFrame, feature_col: str) -> dict[str, object]:
    rows = yearly_ic(frame, feature_col, "actual")
    clean_rows = [row for row in rows if pd.notna(row.get("ic"))]
    summary = summarize_ic(clean_rows)
    summary["yearly"] = rows
    summary["corr_with_s1"] = spearman_stat(frame[feature_col], frame["xs_proba"])
    return summary


def _result_row(
    frame: pd.DataFrame,
    feature_col: str,
    *,
    compare_frame: pd.DataFrame | None = None,
    compare_feature_col: str | None = None,
) -> dict[str, object]:
    summary = _safe_yearly_summary(frame, feature_col)
    compare_corr = None
    compare_rows = 0
    if compare_frame is not None and compare_feature_col and compare_feature_col in compare_frame.columns:
        merged = compare_frame[["time", "ticker", compare_feature_col]].merge(
            frame[["time", "ticker", feature_col]],
            on=["time", "ticker"],
            how="inner",
            suffixes=("_cmp", ""),
        )
        if not merged.empty:
            compare_corr = spearman_stat(merged[compare_feature_col], merged[feature_col])
            compare_rows = int(len(merged))

    return {
        "feature_name": feature_col,
        "avg_ic": summary.get("avg_ic"),
        "pct_years_positive": summary.get("pct_years_positive"),
        "years": summary.get("years"),
        "pos_years": summary.get("pos_years"),
        "corr_with_s1": summary.get("corr_with_s1"),
        "corr_with_c1": compare_corr,
        "compare_rows": compare_rows,
        "gate_pass": bool(
            (summary.get("avg_ic") or 0.0) > 0.01
            and (summary.get("pct_years_positive") or 0.0) >= 0.60
            and abs(compare_corr or 0.0) < 0.30
        ),
        "yearly": summary.get("yearly"),
    }


def main() -> None:
    s1 = load_s1_frame()[["time", "ticker", "xs_proba", "actual"]]
    llm = pd.read_parquet(LLM_PATH)
    llm["time"] = pd.to_datetime(llm["time"], errors="coerce").dt.normalize()
    llm = llm.merge(s1, on=["time", "ticker"], how="inner")
    llm = llm.loc[llm["time"].dt.year.between(2015, 2025)].copy()

    c1 = pd.read_parquet(C1_PATH)
    c1["time"] = pd.to_datetime(c1["time"], errors="coerce").dt.normalize()
    c1 = c1.merge(s1, on=["time", "ticker"], how="inner")
    c1 = c1.loc[c1["time"].dt.year.between(2016, 2025)].copy()

    candidate_rows = [_result_row(llm, col, compare_frame=c1, compare_feature_col="sentiment_score") for col in LLM_CANDIDATES]
    c1_rows = [_result_row(c1, col) for col in C1_CANDIDATES]

    candidate_df = pd.DataFrame(candidate_rows).sort_values(
        by=["gate_pass", "avg_ic", "pct_years_positive", "corr_with_s1"],
        ascending=[False, False, False, True],
        ignore_index=True,
    )
    c1_df = pd.DataFrame(c1_rows).sort_values(
        by=["avg_ic", "pct_years_positive", "corr_with_s1"],
        ascending=[False, False, True],
        ignore_index=True,
    )

    best = candidate_df.iloc[0].to_dict()
    llm_result = {
        "verdict": "PASSED" if bool(best["gate_pass"]) else "MIXED" if float(best["avg_ic"] or 0.0) > 0 else "FAILED",
        "best_candidate": {
            "feature_name": best["feature_name"],
            "avg_ic": best["avg_ic"],
            "pct_years_positive": best["pct_years_positive"],
            "years": best["years"],
            "pos_years": best["pos_years"],
            "corr_with_s1": best["corr_with_s1"],
            "corr_with_c1": best["corr_with_c1"],
            "compare_rows": best["compare_rows"],
            "gate_pass": best["gate_pass"],
        },
        "candidate_table": candidate_df.drop(columns=["yearly"]).to_dict(orient="records"),
        "c1_table": c1_df.drop(columns=["yearly"]).to_dict(orient="records"),
        "candidate_rows": int(len(llm)),
        "c1_rows": int(len(c1)),
        "candidate_years": sorted(int(y) for y in llm["time"].dt.year.unique()),
        "c1_years": sorted(int(y) for y in c1["time"].dt.year.unique()),
    }

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    out_dir = REPO_ROOT / "artifacts" / "portfolio_baselines"
    out_dir.mkdir(parents=True, exist_ok=True)
    results_path = out_dir / f"{ts}_h281_llm_news_gate_results.parquet"
    details_path = REPO_ROOT / "artifacts" / "run_summaries" / f"{ts}_h281_llm_news_gate_summary.json"
    candidate_df.drop(columns=["yearly"]).to_parquet(results_path, index=False)
    details_path.write_text(json.dumps(llm_result, indent=2), encoding="utf-8")

    write_run_summary(
        ts=ts,
        mode="signal_library_llm_news_gate",
        name="h281_llm_news_gate_audit",
        summary=llm_result,
        artifacts={
            "results": str(results_path),
            "details": str(details_path),
        },
        metadata={
            "session": 110,
            "candidate_count": len(LLM_CANDIDATES),
            "c1_baseline_count": len(C1_CANDIDATES),
        },
    )

    print("H281 LLM news gate")
    print(candidate_df.drop(columns=["yearly"]).to_string(index=False))
    print("\nC1 baseline")
    print(c1_df.drop(columns=["yearly"]).to_string(index=False))


if __name__ == "__main__":
    main()
