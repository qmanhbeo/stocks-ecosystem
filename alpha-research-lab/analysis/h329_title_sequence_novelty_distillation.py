"""
H329 - Title-sequence novelty distillation.

Question:
- Can deterministic title/summary sequence rules recover enough of the LLM
  novelty labels to preserve the saved novelty half-life evidence without
  calling a paid API?

Design:
- use the existing LLM cache as a teacher window only (`2015-09-21` through the
  current frontier)
- rebuild an article-level teacher table from raw CafeF JSONL plus the cached
  LLM novelty labels
- restrict to ticker-tagged articles so the first pass audits novelty
  distillation conditional on an existing ticker mapping
- assign deterministic `new / follow_up / recycled` labels using only:
  - title tokens
  - summary tokens
  - publication date
  - recent same-ticker article sequence state
- evaluate the classifier on a held-out `2017` slice against a naive
  `always_new` baseline
- rebuild ticker-day novelty counts from the deterministic labels and rerun the
  H291-style 1d / 5d / 30d novelty decay contract

This does not change the live branch and does not use `2026+`.
"""

from __future__ import annotations

import json
import math
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data_tools import extract_llm_news_features_legacy as legacy  # noqa: E402
from src.repo_paths import data_path  # noqa: E402
from src.run_summary import write_run_summary  # noqa: E402
from src.standalone_signal_utils import load_ohlcv_wide, load_vni_close, to_long  # noqa: E402


RAW_DIR = data_path("news/cafef/raw")
CACHE_DIR = data_path("llm_cache")
OUT_DIR = ROOT / "artifacts" / "portfolio_baselines"
DETAILS_DIR = ROOT / "artifacts" / "run_summaries"

NOVELTY_ALLOWED = ("new", "follow_up", "recycled")
TARGET_HORIZONS = (1, 5, 30)
LOOKBACK_DAYS = 45
MAX_HISTORY_PER_TICKER = 120
STORY_SIM_THRESHOLD = 0.22
RECYCLED_COMBINED_THRESHOLD = 0.70
RECYCLED_SUMMARY_THRESHOLD = 0.85
RECYCLED_STORY_COUNT_THRESHOLD = 4
FOLLOWUP_STORY_GAP_DAYS = 7
HOLDOUT_YEAR = 2017
PASS_MACRO_F1_DELTA = 0.05
MIXED_MACRO_F1_DELTA = 0.00
PASS_FOLLOWUP_F1 = 0.15
KEY_ALPHA_CONTRACTS = {
    "1d": "follow_up",
    "5d": "follow_up_minus_new",
    "30d": "new",
}

TOKEN_STOPWORDS = {
    "cp",
    "ctcp",
    "cong",
    "ty",
    "co",
    "phan",
    "va",
    "voi",
    "cho",
    "tai",
    "tu",
    "cua",
    "mot",
    "nhung",
    "da",
    "se",
    "sap",
    "sau",
    "khi",
    "duoc",
    "trong",
    "tren",
    "doi",
    "moi",
    "nam",
    "quy",
    "thang",
    "ngay",
    "gia",
    "ma",
    "chung",
    "khoan",
}


def _json_safe(value: object):
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value.relative_to(ROOT))
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if value is pd.NaT:
        return None
    if isinstance(value, np.ndarray):
        return [_json_safe(item) for item in value.tolist()]
    if isinstance(value, np.generic):
        if pd.isna(value):
            return None
        return value.item()
    if isinstance(value, float) and pd.isna(value):
        return None
    return value


def _normalize_text(value: str) -> str:
    text = str(value or "").lower()
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text, flags=re.UNICODE).strip()
    return text


def _tokenize(value: str) -> set[str]:
    tokens = []
    for token in _normalize_text(value).split():
        if len(token) < 3:
            continue
        if token in TOKEN_STOPWORDS:
            continue
        if token.isdigit() and len(token) <= 2:
            continue
        tokens.append(token)
    return set(tokens)


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    union = left | right
    if not union:
        return 0.0
    return float(len(left & right) / len(union))


def _future_excess_return(close: pd.DataFrame, benchmark_close: pd.Series, *, periods: int) -> pd.DataFrame:
    future_stock = close.shift(-int(periods)).div(close).sub(1.0)
    future_benchmark = benchmark_close.shift(-int(periods)).div(benchmark_close).sub(1.0)
    return future_stock.sub(future_benchmark, axis=0)


def _daily_ic_series(df: pd.DataFrame, feature_col: str, target_col: str) -> pd.DataFrame:
    rows = []
    for time, group in df.groupby("time", sort=True):
        clean = group[[feature_col, target_col]].replace([np.inf, -np.inf], np.nan).dropna()
        if len(clean) < 3 or clean[feature_col].nunique() < 2 or clean[target_col].nunique() < 2:
            continue
        rho, p_value = spearmanr(clean[feature_col], clean[target_col])
        if np.isfinite(rho):
            rows.append(
                {
                    "time": pd.to_datetime(time),
                    "ic": float(rho),
                    "p_value": float(p_value),
                    "n": int(len(clean)),
                }
            )
    return pd.DataFrame(rows)


def _summary_from_series(series: pd.DataFrame) -> dict[str, object]:
    if series.empty:
        return {
            "mean_ic": float("nan"),
            "daily_hit_rate": float("nan"),
            "positive_years": 0,
            "years_present": 0,
            "daily_rows": 0,
        }
    yearly = series.assign(year=series["time"].dt.year).groupby("year")["ic"].mean()
    return {
        "mean_ic": float(series["ic"].mean()),
        "daily_hit_rate": float((series["ic"] > 0.0).mean()),
        "positive_years": int((yearly > 0.0).sum()),
        "years_present": int(yearly.shape[0]),
        "daily_rows": int(len(series)),
    }


def load_teacher_articles() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    files = sorted(path for path in CACHE_DIR.glob("*.jsonl") if re.fullmatch(r"\d{4}-\d{2}-\d{2}", path.stem))
    for cache_path in files:
        raw_path = RAW_DIR / f"{cache_path.stem}.jsonl"
        if not raw_path.exists():
            continue
        raw_articles = legacy._load_articles(raw_path)
        filtered = [article for article in raw_articles if legacy._is_financial_article(article)]
        for index, article in enumerate(filtered, start=1):
            article["id"] = f"{cache_path.stem}_{index:04d}"
        raw_by_id = {article["id"]: article for article in filtered}

        with cache_path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                novelty = str(obj.get("information_novelty", "") or "").strip().lower()
                if novelty not in NOVELTY_ALLOWED:
                    continue
                tickers = tuple(sorted({str(ticker).strip().upper() for ticker in (obj.get("tickers") or []) if str(ticker).strip()}))
                if not tickers:
                    continue
                article = raw_by_id.get(str(obj.get("id", "") or "").strip())
                if not article:
                    continue
                title = str(article.get("title") or "")
                summary = str(article.get("summary") or "")
                title_tokens = _tokenize(title)
                summary_tokens = _tokenize(summary)
                if not title_tokens and not summary_tokens:
                    continue
                rows.append(
                    {
                        "time": pd.to_datetime(cache_path.stem),
                        "article_id": str(obj["id"]),
                        "tickers": tickers,
                        "tickers_joined": ",".join(tickers),
                        "ticker_count": int(len(tickers)),
                        "teacher_novelty": novelty,
                        "title": title,
                        "summary": summary,
                        "title_norm": _normalize_text(title),
                        "summary_norm": _normalize_text(summary),
                        "title_tokens": title_tokens,
                        "summary_tokens": summary_tokens,
                    }
                )

    if not rows:
        raise RuntimeError("No teacher novelty articles found in current cache window")

    frame = pd.DataFrame(rows).sort_values(["time", "article_id"]).reset_index(drop=True)
    return frame


def assign_deterministic_novelty(frame: pd.DataFrame) -> pd.DataFrame:
    history_by_ticker: dict[str, list[dict[str, object]]] = defaultdict(list)
    predicted_rows: list[dict[str, object]] = []

    for row in frame.itertuples(index=False):
        tickers = tuple(row.tickers)
        title_tokens = set(row.title_tokens)
        summary_tokens = set(row.summary_tokens)
        title_norm = str(row.title_norm)
        current_time = pd.Timestamp(row.time)

        candidate_map: dict[str, dict[str, object]] = {}
        for ticker in tickers:
            history = history_by_ticker[ticker]
            for candidate in reversed(history[-MAX_HISTORY_PER_TICKER:]):
                if candidate["article_id"] in candidate_map:
                    continue
                gap_days = int((current_time - candidate["time"]).days)
                if gap_days <= 0 or gap_days > LOOKBACK_DAYS:
                    continue
                candidate_map[candidate["article_id"]] = candidate

        best_title_jaccard = 0.0
        best_summary_jaccard = 0.0
        best_combined_similarity = 0.0
        best_story_gap_days: int | None = None
        recent_story_matches_7d = 0
        story_matches_30d = 0
        exact_title_repeat = False

        for candidate in candidate_map.values():
            gap_days = int((current_time - candidate["time"]).days)
            title_jaccard = _jaccard(title_tokens, candidate["title_tokens"])
            summary_jaccard = _jaccard(summary_tokens, candidate["summary_tokens"])
            combined_similarity = 0.70 * title_jaccard + 0.30 * summary_jaccard

            if candidate["title_norm"] and candidate["title_norm"] == title_norm:
                exact_title_repeat = True
            if combined_similarity >= STORY_SIM_THRESHOLD:
                story_matches_30d += 1
                if gap_days <= FOLLOWUP_STORY_GAP_DAYS:
                    recent_story_matches_7d += 1
                if best_story_gap_days is None or gap_days < best_story_gap_days:
                    best_story_gap_days = gap_days

            best_title_jaccard = max(best_title_jaccard, title_jaccard)
            best_summary_jaccard = max(best_summary_jaccard, summary_jaccard)
            best_combined_similarity = max(best_combined_similarity, combined_similarity)

        if (
            exact_title_repeat
            or best_summary_jaccard >= RECYCLED_SUMMARY_THRESHOLD
            or best_combined_similarity >= RECYCLED_COMBINED_THRESHOLD
            or story_matches_30d >= RECYCLED_STORY_COUNT_THRESHOLD
        ):
            deterministic_novelty = "recycled"
        elif best_story_gap_days is not None and best_story_gap_days <= FOLLOWUP_STORY_GAP_DAYS:
            deterministic_novelty = "follow_up"
        else:
            deterministic_novelty = "new"

        predicted_rows.append(
            {
                "time": current_time,
                "article_id": row.article_id,
                "tickers_joined": row.tickers_joined,
                "ticker_count": row.ticker_count,
                "teacher_novelty": row.teacher_novelty,
                "deterministic_novelty": deterministic_novelty,
                "best_title_jaccard": best_title_jaccard,
                "best_summary_jaccard": best_summary_jaccard,
                "best_combined_similarity": best_combined_similarity,
                "best_story_gap_days": best_story_gap_days,
                "recent_story_matches_7d": recent_story_matches_7d,
                "story_matches_30d": story_matches_30d,
                "exact_title_repeat": exact_title_repeat,
                "title": row.title,
                "summary": row.summary,
            }
        )

        history_payload = {
            "article_id": row.article_id,
            "time": current_time,
            "title_tokens": title_tokens,
            "summary_tokens": summary_tokens,
            "title_norm": title_norm,
        }
        for ticker in tickers:
            history_by_ticker[ticker].append(history_payload)

    return pd.DataFrame(predicted_rows)


def _classification_report(frame: pd.DataFrame, actual_col: str, pred_col: str) -> tuple[dict[str, object], pd.DataFrame]:
    labels = list(NOVELTY_ALLOWED)
    confusion = pd.crosstab(frame[actual_col], frame[pred_col], dropna=False)
    confusion = confusion.reindex(index=labels, columns=labels, fill_value=0)

    per_label_rows = []
    recalls = []
    f1s = []
    total = int(confusion.to_numpy().sum())
    correct = 0
    for label in labels:
        tp = int(confusion.loc[label, label])
        correct += tp
        predicted_total = int(confusion[label].sum())
        actual_total = int(confusion.loc[label].sum())
        precision = float(tp / predicted_total) if predicted_total else 0.0
        recall = float(tp / actual_total) if actual_total else 0.0
        f1 = float((2 * precision * recall) / (precision + recall)) if (precision + recall) else 0.0
        per_label_rows.append(
            {
                "label": label,
                "precision": precision,
                "recall": recall,
                "f1": f1,
                "support": actual_total,
                "tp": tp,
                "predicted_total": predicted_total,
            }
        )
        recalls.append(recall)
        f1s.append(f1)

    report = {
        "accuracy": float(correct / total) if total else 0.0,
        "balanced_accuracy": float(np.mean(recalls)) if recalls else 0.0,
        "macro_f1": float(np.mean(f1s)) if f1s else 0.0,
        "row_count": total,
        "per_label": per_label_rows,
        "confusion_matrix": confusion.reset_index().rename(columns={"index": "actual"}).to_dict(orient="records"),
    }
    return report, confusion


def _always_new_baseline(frame: pd.DataFrame) -> pd.DataFrame:
    baseline = frame[[ "time", "teacher_novelty" ]].copy()
    baseline["deterministic_novelty"] = "new"
    return baseline


def _build_novelty_panel(article_labels: pd.DataFrame, label_col: str) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for row in article_labels.itertuples(index=False):
        novelty = str(getattr(row, label_col))
        for ticker in str(row.tickers_joined).split(","):
            ticker = ticker.strip().upper()
            if not ticker:
                continue
            rows.append({"time": pd.Timestamp(row.time), "ticker": ticker, "novelty": novelty})
    if not rows:
        return pd.DataFrame()

    frame = pd.DataFrame(rows)
    pivot = frame.pivot_table(index=["time", "ticker"], columns="novelty", aggfunc="size", fill_value=0).reset_index()
    pivot.columns.name = None
    for column in NOVELTY_ALLOWED:
        if column not in pivot.columns:
            pivot[column] = 0
    pivot["novelty_total"] = pivot[list(NOVELTY_ALLOWED)].sum(axis=1)
    pivot["new_minus_recycled"] = pivot["new"] - pivot["recycled"]
    pivot["follow_up_minus_recycled"] = pivot["follow_up"] - pivot["recycled"]
    pivot["follow_up_minus_new"] = pivot["follow_up"] - pivot["new"]
    return pivot.sort_values(["time", "ticker"]).reset_index(drop=True)


def _evaluate_decay_contract(panel: pd.DataFrame, source_name: str) -> pd.DataFrame:
    close = load_ohlcv_wide(min_rows=120)["close"].sort_index()
    close = close.loc[(close.index.year >= 2015) & (close.index.year <= 2017)].copy()
    benchmark_close = load_vni_close().reindex(close.index)

    feature_rows = []
    features = [
        "new",
        "follow_up",
        "recycled",
        "new_minus_recycled",
        "follow_up_minus_recycled",
        "follow_up_minus_new",
    ]

    for horizon in TARGET_HORIZONS:
        target = _future_excess_return(close, benchmark_close, periods=horizon)
        target_long = to_long(target, f"future_rel_return_{horizon}d")
        target_long["time"] = pd.to_datetime(target_long["time"], errors="coerce")
        target_long = target_long[(target_long["time"].dt.year >= 2015) & (target_long["time"].dt.year <= 2017)].copy()
        merged = panel.merge(target_long, on=["time", "ticker"], how="inner")
        target_col = f"future_rel_return_{horizon}d"
        merged = merged.dropna(subset=[target_col])

        for feature in features:
            series = _daily_ic_series(merged[["time", feature, target_col]].copy(), feature, target_col)
            stats = _summary_from_series(series)
            feature_rows.append(
                {
                    "source_name": source_name,
                    "horizon": f"{horizon}d",
                    "feature_name": feature,
                    "row_count": int(len(merged)),
                    "nonzero_rows": int((pd.to_numeric(merged[feature], errors="coerce").fillna(0.0) != 0.0).sum()),
                    "feature_mean": float(pd.to_numeric(merged[feature], errors="coerce").mean()) if len(merged) else float("nan"),
                    "target_mean": float(pd.to_numeric(merged[target_col], errors="coerce").mean()) if len(merged) else float("nan"),
                    **stats,
                }
            )

    return pd.DataFrame(feature_rows).sort_values(
        by=["source_name", "horizon", "mean_ic", "daily_hit_rate", "positive_years"],
        ascending=[True, True, False, False, False],
        ignore_index=True,
    )


def _lookup_feature_stat(feature_df: pd.DataFrame, source_name: str, horizon: str, feature_name: str) -> dict[str, object]:
    subset = feature_df[
        (feature_df["source_name"] == source_name)
        & (feature_df["horizon"] == horizon)
        & (feature_df["feature_name"] == feature_name)
    ]
    if subset.empty:
        return {}
    return subset.iloc[0].to_dict()


def main() -> None:
    teacher_articles = load_teacher_articles()
    distilled_articles = assign_deterministic_novelty(teacher_articles)

    full_report, full_confusion = _classification_report(
        distilled_articles,
        actual_col="teacher_novelty",
        pred_col="deterministic_novelty",
    )
    holdout = distilled_articles[distilled_articles["time"].dt.year == HOLDOUT_YEAR].copy()
    holdout_report, holdout_confusion = _classification_report(
        holdout,
        actual_col="teacher_novelty",
        pred_col="deterministic_novelty",
    )
    baseline_full, _ = _classification_report(
        _always_new_baseline(distilled_articles),
        actual_col="teacher_novelty",
        pred_col="deterministic_novelty",
    )
    baseline_holdout, _ = _classification_report(
        _always_new_baseline(holdout),
        actual_col="teacher_novelty",
        pred_col="deterministic_novelty",
    )

    teacher_panel = _build_novelty_panel(distilled_articles, "teacher_novelty")
    deterministic_panel = _build_novelty_panel(distilled_articles, "deterministic_novelty")
    teacher_results = _evaluate_decay_contract(teacher_panel, "teacher")
    deterministic_results = _evaluate_decay_contract(deterministic_panel, "deterministic")
    feature_results = pd.concat([teacher_results, deterministic_results], ignore_index=True)

    alpha_contract_rows = []
    preserved_contracts = 0
    for horizon, feature_name in KEY_ALPHA_CONTRACTS.items():
        teacher_row = _lookup_feature_stat(feature_results, "teacher", horizon, feature_name)
        deterministic_row = _lookup_feature_stat(feature_results, "deterministic", horizon, feature_name)
        teacher_ic = float(teacher_row.get("mean_ic", np.nan))
        deterministic_ic = float(deterministic_row.get("mean_ic", np.nan))
        sign_preserved = bool(
            np.isfinite(teacher_ic)
            and np.isfinite(deterministic_ic)
            and teacher_ic != 0.0
            and math.copysign(1.0, deterministic_ic) == math.copysign(1.0, teacher_ic)
        )
        if sign_preserved:
            preserved_contracts += 1
        alpha_contract_rows.append(
            {
                "horizon": horizon,
                "feature_name": feature_name,
                "teacher_mean_ic": teacher_ic,
                "deterministic_mean_ic": deterministic_ic,
                "teacher_hit_rate": teacher_row.get("daily_hit_rate"),
                "deterministic_hit_rate": deterministic_row.get("daily_hit_rate"),
                "teacher_positive_years": teacher_row.get("positive_years"),
                "deterministic_positive_years": deterministic_row.get("positive_years"),
                "sign_preserved": sign_preserved,
            }
        )

    holdout_macro_f1_delta = float(holdout_report["macro_f1"] - baseline_holdout["macro_f1"])
    holdout_follow_row = next(
        (row for row in holdout_report["per_label"] if row["label"] == "follow_up"),
        {"f1": 0.0, "precision": 0.0, "recall": 0.0},
    )
    pass_condition = bool(
        holdout_macro_f1_delta >= PASS_MACRO_F1_DELTA
        and float(holdout_follow_row["f1"]) >= PASS_FOLLOWUP_F1
        and preserved_contracts >= 2
    )
    mixed_condition = bool(
        (holdout_macro_f1_delta > MIXED_MACRO_F1_DELTA and preserved_contracts >= 1)
        or preserved_contracts >= 2
    )
    verdict = "PASSED" if pass_condition else "MIXED" if mixed_condition else "FAILED"

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    DETAILS_DIR.mkdir(parents=True, exist_ok=True)

    articles_path = OUT_DIR / f"{ts}_h329_title_sequence_novelty_distillation_articles.parquet"
    feature_path = OUT_DIR / f"{ts}_h329_title_sequence_novelty_distillation_decay_results.parquet"
    holdout_confusion_path = OUT_DIR / f"{ts}_h329_title_sequence_novelty_distillation_holdout_confusion.parquet"
    details_path = DETAILS_DIR / f"{ts}_h329_title_sequence_novelty_distillation_details.json"

    distilled_articles.to_parquet(articles_path, index=False)
    feature_results.to_parquet(feature_path, index=False)
    holdout_confusion.reset_index().rename(columns={"index": "actual"}).to_parquet(holdout_confusion_path, index=False)

    summary = {
        "verdict": verdict,
        "teacher_window": {
            "date_min": _json_safe(teacher_articles["time"].min()),
            "date_max": _json_safe(teacher_articles["time"].max()),
            "article_rows": int(len(teacher_articles)),
            "days": int(teacher_articles["time"].nunique()),
            "tickers_covered": int(
                len(
                    {
                        ticker
                        for joined in teacher_articles["tickers_joined"]
                        for ticker in str(joined).split(",")
                        if ticker
                    }
                )
            ),
        },
        "classification_full": full_report,
        "classification_holdout_2017": holdout_report,
        "baseline_always_new_full": baseline_full,
        "baseline_always_new_holdout_2017": baseline_holdout,
        "holdout_macro_f1_delta_vs_always_new": holdout_macro_f1_delta,
        "holdout_follow_up_metrics": holdout_follow_row,
        "alpha_contract_rows": alpha_contract_rows,
        "preserved_alpha_contracts": preserved_contracts,
        "deterministic_label_share": _json_safe(
            distilled_articles["deterministic_novelty"].value_counts(normalize=True).sort_index().to_dict()
        ),
        "teacher_label_share": _json_safe(
            distilled_articles["teacher_novelty"].value_counts(normalize=True).sort_index().to_dict()
        ),
        "rule_constants": {
            "lookback_days": LOOKBACK_DAYS,
            "story_sim_threshold": STORY_SIM_THRESHOLD,
            "recycled_combined_threshold": RECYCLED_COMBINED_THRESHOLD,
            "recycled_summary_threshold": RECYCLED_SUMMARY_THRESHOLD,
            "recycled_story_count_threshold": RECYCLED_STORY_COUNT_THRESHOLD,
            "followup_story_gap_days": FOLLOWUP_STORY_GAP_DAYS,
        },
        "artifacts": {
            "articles": str(articles_path.relative_to(ROOT)),
            "feature_results": str(feature_path.relative_to(ROOT)),
            "holdout_confusion": str(holdout_confusion_path.relative_to(ROOT)),
        },
    }
    details_path.write_text(json.dumps(_json_safe(summary), indent=2), encoding="utf-8")

    write_run_summary(
        ts=ts,
        mode="research_branch_title_sequence_novelty_distillation",
        name="h329_title_sequence_novelty_distillation",
        summary=summary,
        artifacts={
            "articles": str(articles_path),
            "feature_results": str(feature_path),
            "holdout_confusion": str(holdout_confusion_path),
            "details": str(details_path),
        },
        metadata={
            "session": 148,
            "holdout_year": HOLDOUT_YEAR,
            "target_horizons": list(TARGET_HORIZONS),
        },
    )

    print("H329 TITLE-SEQUENCE NOVELTY DISTILLATION")
    print(f"Verdict: {verdict}")
    print(
        "Holdout 2017 macro_f1 delta vs always_new:",
        f"{holdout_macro_f1_delta:.4f}",
    )
    print(
        "Holdout follow_up precision / recall / f1:",
        f"{holdout_follow_row['precision']:.4f} / {holdout_follow_row['recall']:.4f} / {holdout_follow_row['f1']:.4f}",
    )
    print("Preserved alpha contracts:", preserved_contracts)
    print(pd.DataFrame(alpha_contract_rows).to_string(index=False))


if __name__ == "__main__":
    main()
