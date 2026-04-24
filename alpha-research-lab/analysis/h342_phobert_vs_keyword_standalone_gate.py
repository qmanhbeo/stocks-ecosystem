"""
H342 - PhoBERT vs Keyword News Standalone Gate (1d Barrier).

Question:
- Does the new whole-article PhoBERT ticker-day surface materially improve on
  the old keyword-news family under the same standalone 1d barrier contract?

Design:
- Use xs_barrier_vol_1d_hose_full.parquet as the canonical target surface
  (`actual`) and `xs_proba` as the S1 reference for orthogonality.
- Compare the completed PhoBERT ticker-day dataset against the historical
  keyword-news daily and rolling baselines on the shared 2016-2025 window.
- Restrict each feature to active rows only (nonzero / non-flat support) so the
  audit measures the informative state rather than dense filler zeros.
- Compute:
  - average daily IC
  - yearly consistency
  - active-row coverage vs the old keyword baselines
  - correlation with S1

Decision ladder:
- PASS:
  - best PhoBERT feature has IC > 0.01
  - at least 60% positive years
  - and beats the best keyword-news baseline on avg IC
- MIXED:
  - best PhoBERT feature clears IC > 0.01 but fails the year bar,
    or only ties / weakly trails keyword while materially improving coverage
- FAIL:
  - no PhoBERT feature clears IC > 0.01, or the family trails keyword cleanly
    without a compensating coverage / robustness gain

Next step by outcome:
- PASS -> test conditioned follow-ups (`phobert-negative-attention-shock`,
  then `phobert-x-order-pressure`)
- MIXED -> keep PhoBERT as offline evidence and narrow to conditioned states
- FAIL -> park the pooled PhoBERT sentiment family and do not expand local-BERT
  work yet
"""

from __future__ import annotations

from datetime import datetime
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.repo_paths import data_path
from src.run_summary import write_run_summary
from src.standalone_signal_utils import evaluate_features, load_s1_frame, spearman_stat


PHOBERT_PATH = data_path("features/news/datasets/phobert_ticker_day_sentiment.parquet")
KEYWORD_DAILY_PATH = data_path("features/xs_news_sentiment_daily.parquet")
KEYWORD_ROLLING_PATH = data_path("features/xs_news_sentiment_rolling.parquet")

PHOBERT_FEATURES = [
    "phobert_sentiment_score_mean",
    "phobert_sentiment_score_sum",
    "phobert_sentiment_conf_weighted_mean",
    "phobert_sentiment_conf_weighted_sum",
    "phobert_sentiment_5d",
    "phobert_sentiment_30d",
]

KEYWORD_FEATURES = [
    "sentiment_score",
    "sentiment_cs_z",
    "sentiment_score_5d",
    "sentiment_score_30d",
]


def _active_mask(frame: pd.DataFrame, feature: str) -> pd.Series:
    if feature == "sentiment_cs_z":
        return frame["article_count"].fillna(0.0) > 0.0
    if feature in {"sentiment_score", "sentiment_score_5d", "sentiment_score_30d"}:
        count_col = "article_count" if feature == "sentiment_score" else (
            "article_count_5d" if feature == "sentiment_score_5d" else "article_count_30d"
        )
        if count_col in frame.columns:
            return frame[count_col].fillna(0.0) > 0.0
    if feature in {
        "phobert_sentiment_score_mean",
        "phobert_sentiment_score_sum",
        "phobert_sentiment_conf_weighted_mean",
        "phobert_sentiment_conf_weighted_sum",
    }:
        return frame["phobert_article_count_1d"].fillna(0.0) > 0.0
    if feature in {"phobert_sentiment_5d", "phobert_sentiment_30d"}:
        count_col = "phobert_article_count_5d" if feature == "phobert_sentiment_5d" else "phobert_article_count_30d"
        return frame[count_col].fillna(0.0) > 0.0
    return pd.to_numeric(frame[feature], errors="coerce").fillna(0.0) != 0.0


def _result_rows(frame: pd.DataFrame, feature_cols: list[str], *, total_rows: int) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for feature in feature_cols:
        feature_frame = frame.loc[_active_mask(frame, feature)].copy()
        feature_rows = evaluate_features(feature_frame, [feature])[feature]
        coverage_pct = float(len(feature_frame) / total_rows * 100.0) if total_rows else 0.0
        rows.append(
            {
                "feature_name": feature,
                "avg_ic": feature_rows.get("avg_ic"),
                "pos_years": feature_rows.get("pos_years"),
                "years": feature_rows.get("years"),
                "pct_years_positive": feature_rows.get("pct_years_positive"),
                "corr_with_s1": feature_rows.get("corr_with_s1"),
                "gate_pass": feature_rows.get("gate_pass"),
                "coverage_pct": coverage_pct,
                "active_rows": int(len(feature_frame)),
                "yearly": feature_rows.get("yearly"),
            }
        )
    return rows


def _best_row(rows: list[dict[str, object]]) -> dict[str, object]:
    ranked = sorted(
        rows,
        key=lambda row: (
            bool(row.get("gate_pass")),
            float(row.get("avg_ic") or float("-inf")),
            float(row.get("pct_years_positive") or float("-inf")),
            -abs(float(row.get("corr_with_s1") or float("inf"))),
        ),
        reverse=True,
    )
    return ranked[0]


def main() -> None:
    print("H342 - PhoBERT vs Keyword News Standalone Gate (1d Barrier)")
    print("=" * 78)

    s1 = load_s1_frame()[["time", "ticker", "actual", "xs_proba"]].copy()

    s1 = s1.loc[s1["time"].dt.year.between(2016, 2025)].copy()

    phobert = pd.read_parquet(PHOBERT_PATH).copy()
    phobert["time"] = pd.to_datetime(phobert["date"], errors="coerce").dt.normalize()
    phobert = phobert.merge(s1, on=["time", "ticker"], how="inner", validate="one_to_one")

    keyword_daily = pd.read_parquet(KEYWORD_DAILY_PATH).copy()
    keyword_daily["time"] = pd.to_datetime(keyword_daily["time"], errors="coerce").dt.normalize()
    keyword_daily = keyword_daily.loc[keyword_daily["time"].dt.year.between(2016, 2025)].copy()

    keyword_rolling = pd.read_parquet(KEYWORD_ROLLING_PATH).copy()
    keyword_rolling["time"] = pd.to_datetime(keyword_rolling["time"], errors="coerce").dt.normalize()
    keyword_rolling = keyword_rolling.merge(s1, on=["time", "ticker"], how="inner", validate="one_to_one")
    keyword = s1.merge(
        keyword_daily[["time", "ticker", "sentiment_score", "sentiment_cs_z", "article_count"]],
        on=["time", "ticker"],
        how="left",
        validate="one_to_one",
    ).merge(
        keyword_rolling[
            ["time", "ticker", "sentiment_score_5d", "sentiment_score_30d", "article_count_5d", "article_count_30d"]
        ],
        on=["time", "ticker"],
        how="left",
        validate="one_to_one",
    )

    print(
        f"PhoBERT rows={len(phobert)}, keyword_daily_rows={len(keyword_daily)}, "
        f"keyword_rolling_rows={len(keyword_rolling)}",
        flush=True,
    )

    total_rows = int(len(s1))
    phobert_rows = _result_rows(phobert, PHOBERT_FEATURES, total_rows=total_rows)
    keyword_rows = _result_rows(keyword, KEYWORD_FEATURES, total_rows=total_rows)

    best_phobert = _best_row(phobert_rows)
    best_keyword = _best_row(keyword_rows)

    overlap = phobert[["time", "ticker", best_phobert["feature_name"]]].merge(
        keyword[["time", "ticker", best_keyword["feature_name"]]],
        on=["time", "ticker"],
        how="inner",
    )
    phobert_keyword_corr = spearman_stat(
        overlap[best_phobert["feature_name"]],
        overlap[best_keyword["feature_name"]],
    )

    phobert_pass = bool(best_phobert.get("gate_pass"))
    phobert_beats_keyword = float(best_phobert.get("avg_ic") or 0.0) > float(best_keyword.get("avg_ic") or 0.0)
    phobert_has_coverage_gain = float(best_phobert.get("coverage_pct") or 0.0) > float(best_keyword.get("coverage_pct") or 0.0)

    if phobert_pass and phobert_beats_keyword:
        verdict = "PASSED"
    elif phobert_pass or (phobert_has_coverage_gain and float(best_phobert.get("avg_ic") or 0.0) > 0.0):
        verdict = "MIXED"
    else:
        verdict = "FAILED"

    summary = {
        "verdict": verdict,
        "window_years": sorted(int(year) for year in phobert["time"].dt.year.unique()),
        "phobert_total_rows": int(len(phobert)),
        "keyword_total_rows": int(len(keyword)),
        "best_phobert_feature": best_phobert,
        "best_keyword_feature": best_keyword,
        "phobert_vs_keyword_corr": phobert_keyword_corr,
        "phobert_table": [{k: v for k, v in row.items() if k != "yearly"} for row in phobert_rows],
        "keyword_table": [{k: v for k, v in row.items() if k != "yearly"} for row in keyword_rows],
        "branch_ladder": {
            "pass_next": "Run phobert-negative-attention-shock, then phobert-x-order-pressure.",
            "mixed_next": "Keep PhoBERT as offline evidence and narrow to conditioned states only.",
            "fail_next": "Park pooled PhoBERT sentiment as a signal family and do not expand local-BERT tasks yet.",
        },
        "yearly_details": {
            "phobert": {row["feature_name"]: row.get("yearly", []) for row in phobert_rows},
            "keyword": {row["feature_name"]: row.get("yearly", []) for row in keyword_rows},
        },
    }

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    path = write_run_summary(
        ts=ts,
        mode="research_branch_phobert_news_gate",
        name="h342_phobert_vs_keyword_standalone_gate",
        summary=summary,
        artifacts={},
        metadata={"signal": "H342", "family": "news_sentiment"},
    )

    print(f"Best PhoBERT: {best_phobert['feature_name']} | IC={best_phobert['avg_ic']:.4f} | "
          f"pos_years={best_phobert['pos_years']}/{best_phobert['years']} | "
          f"coverage={best_phobert['coverage_pct']:.3f}%")
    print(f"Best keyword: {best_keyword['feature_name']} | IC={best_keyword['avg_ic']:.4f} | "
          f"pos_years={best_keyword['pos_years']}/{best_keyword['years']} | "
          f"coverage={best_keyword['coverage_pct']:.3f}%")
    print(f"PhoBERT vs keyword corr: {phobert_keyword_corr:.4f}")
    print(f"VERDICT: {verdict}")
    print(f"summary: {path}")


if __name__ == "__main__":
    main()
