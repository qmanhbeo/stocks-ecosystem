"""
H343 - PhoBERT Semantic Condition Audit (1d Barrier).

Question:
- Do the already-built local PhoBERT semantic heads add downstream predictive
  value before the Ollama residual surface is complete?

Design:
- Use only existing published PhoBERT ticker-day surfaces:
  sentiment, forward-looking, article-scope, and source-type.
- Use the same 1d S1 target surface and 2016-2025 historical window as H342.
- Do not use 2026 data.
- Evaluate a small predeclared BERT-only set:
  - direct forward-looking / scope / source-type intensity
  - sentiment gated by stock scope, forward-looking probability, and official
    source probability
  - a pre-oriented negative-news avoid score
- Restrict each feature to active rows so dense filler zeros do not dominate.

Decision ladder:
- PASS:
  - at least one BERT-only conditioned feature has abs(avg IC) > 0.01,
  - at least 60% positive years in its predeclared orientation,
  - abs(corr with S1) < 0.30,
  - and it beats the H342 best pooled PhoBERT sentiment IC of +0.0082.
- MIXED:
  - no feature clears the full gate, but a feature reaches abs(avg IC) >= 0.008
    with at least 60% positive years or materially narrows the useful news
    state.
- FAIL:
  - no direct or conditioned BERT feature clears the mixed bar.

Next step by outcome:
- PASS -> run a bounded combined-news audit after the Ollama residual completes.
- MIXED -> keep the BERT heads as routing/context features but do not promote
  them as standalone signals yet.
- FAIL -> park BERT-only semantic alpha and wait for the Ollama residual event
  surface before reopening the local-news alpha audit.
"""

from __future__ import annotations

from datetime import datetime
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.repo_paths import data_path
from src.run_summary import write_run_summary
from src.standalone_signal_utils import evaluate_features, load_s1_frame


SENTIMENT_PATH = data_path("features/news/datasets/phobert_ticker_day_sentiment.parquet")
FORWARD_PATH = data_path("features/news/datasets/phobert_forward_looking_ticker_day_features.parquet")
SCOPE_PATH = data_path("features/news/datasets/phobert_article_scope_ticker_day_features.parquet")
SOURCE_PATH = data_path("features/news/datasets/phobert_source_type_ticker_day_features.parquet")

H342_BEST_PHOBERT_IC = 0.008212503095846417
MIXED_ABS_IC_BAR = 0.008

BASE_COLUMNS = ["ticker", "date"]

SOURCE_FEATURES = {
    "direct": [
        "phobert_forward_looking_prob_sum",
        "phobert_forward_looking_prob_5d",
        "phobert_article_scope_stock_news_prob_sum",
        "phobert_article_scope_stock_news_prob_5d",
        "phobert_source_type_official_or_regulatory_prob_sum",
        "phobert_source_type_official_or_regulatory_prob_5d",
    ],
    "conditioned_sentiment": [
        "h343_sentiment_x_stock_scope",
        "h343_sentiment_x_forward",
        "h343_sentiment_x_official",
        "h343_sentiment_x_forward_x_stock_scope",
        "h343_sentiment_x_forward_x_official",
        "h343_bad_news_avoid_forward_stock",
    ],
}


def _read_frame(path: Path, columns: list[str]) -> pd.DataFrame:
    frame = pd.read_parquet(path, columns=columns).copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["ticker"] = frame["ticker"].astype(str).str.upper()
    return frame.dropna(subset=["date", "ticker"])


def _load_bert_daily() -> pd.DataFrame:
    sentiment = _read_frame(
        SENTIMENT_PATH,
        [
            *BASE_COLUMNS,
            "phobert_article_count_1d",
            "phobert_sentiment_score_sum",
            "phobert_prob_neg_mean",
        ],
    )
    forward = _read_frame(
        FORWARD_PATH,
        [
            *BASE_COLUMNS,
            "phobert_forward_looking_article_count_1d",
            "phobert_forward_looking_prob_mean",
            "phobert_forward_looking_prob_sum",
            "phobert_forward_looking_article_count_5d",
            "phobert_forward_looking_prob_5d",
        ],
    )
    scope = _read_frame(
        SCOPE_PATH,
        [
            *BASE_COLUMNS,
            "phobert_article_scope_article_count_1d",
            "phobert_article_scope_stock_news_prob_mean",
            "phobert_article_scope_stock_news_prob_sum",
            "phobert_article_scope_article_count_5d",
            "phobert_article_scope_stock_news_prob_5d",
        ],
    )
    source = _read_frame(
        SOURCE_PATH,
        [
            *BASE_COLUMNS,
            "phobert_source_type_article_count_1d",
            "phobert_source_type_official_or_regulatory_prob_mean",
            "phobert_source_type_official_or_regulatory_prob_sum",
            "phobert_source_type_article_count_5d",
            "phobert_source_type_official_or_regulatory_prob_5d",
        ],
    )

    merged = sentiment.merge(forward, on=BASE_COLUMNS, how="inner", validate="one_to_one")
    merged = merged.merge(scope, on=BASE_COLUMNS, how="inner", validate="one_to_one")
    merged = merged.merge(source, on=BASE_COLUMNS, how="inner", validate="one_to_one")
    merged = merged.rename(columns={"date": "time"})

    sent = pd.to_numeric(merged["phobert_sentiment_score_sum"], errors="coerce").fillna(0.0)
    forward_prob = pd.to_numeric(merged["phobert_forward_looking_prob_mean"], errors="coerce").fillna(0.0)
    stock_prob = pd.to_numeric(merged["phobert_article_scope_stock_news_prob_mean"], errors="coerce").fillna(0.0)
    official_prob = pd.to_numeric(
        merged["phobert_source_type_official_or_regulatory_prob_mean"], errors="coerce"
    ).fillna(0.0)
    neg_prob = pd.to_numeric(merged["phobert_prob_neg_mean"], errors="coerce").fillna(0.0)

    merged["h343_sentiment_x_stock_scope"] = sent * stock_prob
    merged["h343_sentiment_x_forward"] = sent * forward_prob
    merged["h343_sentiment_x_official"] = sent * official_prob
    merged["h343_sentiment_x_forward_x_stock_scope"] = sent * forward_prob * stock_prob
    merged["h343_sentiment_x_forward_x_official"] = sent * forward_prob * official_prob
    # Positive orientation: prefer fewer negative forward-looking stock-news articles.
    merged["h343_bad_news_avoid_forward_stock"] = -neg_prob * forward_prob * stock_prob
    return merged


def _active_mask(frame: pd.DataFrame, feature: str) -> pd.Series:
    if feature.endswith("_5d"):
        if feature.startswith("phobert_forward_looking"):
            return frame["phobert_forward_looking_article_count_5d"].fillna(0.0) > 0.0
        if feature.startswith("phobert_article_scope"):
            return frame["phobert_article_scope_article_count_5d"].fillna(0.0) > 0.0
        if feature.startswith("phobert_source_type"):
            return frame["phobert_source_type_article_count_5d"].fillna(0.0) > 0.0

    direct_count_map = {
        "phobert_forward_looking_prob_sum": "phobert_forward_looking_article_count_1d",
        "phobert_article_scope_stock_news_prob_sum": "phobert_article_scope_article_count_1d",
        "phobert_source_type_official_or_regulatory_prob_sum": "phobert_source_type_article_count_1d",
    }
    if feature in direct_count_map:
        return frame[direct_count_map[feature]].fillna(0.0) > 0.0

    if feature in SOURCE_FEATURES["conditioned_sentiment"]:
        return (
            (frame["phobert_article_count_1d"].fillna(0.0) > 0.0)
            & (frame["phobert_forward_looking_article_count_1d"].fillna(0.0) > 0.0)
            & (frame["phobert_article_scope_article_count_1d"].fillna(0.0) > 0.0)
            & (frame["phobert_source_type_article_count_1d"].fillna(0.0) > 0.0)
        )

    return pd.to_numeric(frame[feature], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0) != 0.0


def _result_rows(frame: pd.DataFrame, feature_cols: list[str], *, total_rows: int) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for feature in feature_cols:
        feature_frame = frame.loc[_active_mask(frame, feature)].copy()
        result = evaluate_features(feature_frame, [feature])[feature]
        coverage_pct = float(len(feature_frame) / total_rows * 100.0) if total_rows else 0.0
        rows.append(
            {
                "feature_name": feature,
                "avg_ic": result.get("avg_ic"),
                "pos_years": result.get("pos_years"),
                "years": result.get("years"),
                "pct_years_positive": result.get("pct_years_positive"),
                "corr_with_s1": result.get("corr_with_s1"),
                "gate_pass": result.get("gate_pass"),
                "coverage_pct": coverage_pct,
                "active_rows": int(len(feature_frame)),
                "yearly": result.get("yearly"),
            }
        )
    return rows


def _best_row(rows: list[dict[str, object]]) -> dict[str, object]:
    return sorted(
        rows,
        key=lambda row: (
            bool(row.get("gate_pass")),
            abs(float(row.get("avg_ic") or 0.0)),
            float(row.get("pct_years_positive") or 0.0),
            -abs(float(row.get("corr_with_s1") or 0.0)),
        ),
        reverse=True,
    )[0]


def main() -> None:
    print("H343 - PhoBERT Semantic Condition Audit (1d Barrier)")
    print("=" * 78)

    s1 = load_s1_frame()[["time", "ticker", "actual", "xs_proba"]].copy()
    s1 = s1.loc[s1["time"].dt.year.between(2016, 2025)].copy()

    bert = _load_bert_daily()
    bert = bert.merge(s1, on=["time", "ticker"], how="inner", validate="one_to_one")
    total_rows = int(len(s1))

    feature_groups: dict[str, list[dict[str, object]]] = {}
    all_rows: list[dict[str, object]] = []
    for group_name, feature_cols in SOURCE_FEATURES.items():
        rows = _result_rows(bert, feature_cols, total_rows=total_rows)
        feature_groups[group_name] = rows
        all_rows.extend(rows)

    best = _best_row(all_rows)
    best_ic = float(best.get("avg_ic") or 0.0)
    best_pct_positive = float(best.get("pct_years_positive") or 0.0)
    best_corr = float(best.get("corr_with_s1") or 0.0)

    full_pass = (
        abs(best_ic) > 0.01
        and best_pct_positive >= 0.60
        and abs(best_corr) < 0.30
        and abs(best_ic) > H342_BEST_PHOBERT_IC
    )
    mixed = (
        not full_pass
        and abs(best_ic) >= MIXED_ABS_IC_BAR
        and best_pct_positive >= 0.60
        and abs(best_corr) < 0.30
    )
    verdict = "PASSED" if full_pass else ("MIXED" if mixed else "FAILED")

    summary = {
        "verdict": verdict,
        "window_years": sorted(int(year) for year in bert["time"].dt.year.unique()),
        "bert_total_rows": int(len(bert)),
        "s1_total_rows": total_rows,
        "h342_best_phobert_ic": H342_BEST_PHOBERT_IC,
        "mixed_abs_ic_bar": MIXED_ABS_IC_BAR,
        "best_feature": best,
        "feature_groups": {
            group_name: [{k: v for k, v in row.items() if k != "yearly"} for row in rows]
            for group_name, rows in feature_groups.items()
        },
        "yearly_details": {
            row["feature_name"]: row.get("yearly", [])
            for row in all_rows
        },
        "branch_ladder": {
            "pass_next": "After Ollama residual completion, run the bounded combined local-news audit.",
            "mixed_next": "Keep BERT heads as routing/context features; do not promote standalone BERT semantic alpha yet.",
            "fail_next": "Park BERT-only semantic alpha until the Ollama event-family residual is available.",
        },
    }

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    path = write_run_summary(
        ts=ts,
        mode="research_branch_phobert_semantic_condition_audit",
        name="h343_phobert_semantic_condition_audit",
        summary=summary,
        artifacts={},
        metadata={"signal": "H343", "family": "news_sentiment"},
    )

    print(
        f"Rows: bert={len(bert)}, s1={total_rows}, years={summary['window_years']}",
        flush=True,
    )
    print(
        f"Best feature: {best['feature_name']} | IC={best_ic:.4f} | "
        f"pos_years={best['pos_years']}/{best['years']} | "
        f"corr_s1={best_corr:.4f} | coverage={best['coverage_pct']:.3f}%",
        flush=True,
    )
    print(f"VERDICT: {verdict}", flush=True)
    print(f"summary: {path}", flush=True)


if __name__ == "__main__":
    main()
