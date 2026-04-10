"""
H331 - deterministic event-family router audit.

Question:
- Can lexical rules recover enough of the higher-value non-novelty teacher
  fields to preserve the strongest 5d LLM-state buckets better than the dead
  keyword-news baseline?

Design:
- rebuild a ticker-tagged teacher article table from CafeF raw JSONL plus the
  cached LLM labels on the current `2015-2017` nonzero window
- test four field families:
  - `source_authority`
  - `expectation_alignment`
  - `impact_scope`
  - a sparse focused `event_type` subset with enough support
- assign deterministic labels from title / summary / body / source-domain
  lexical rules only
- evaluate held-out `2017` field classification versus a train-majority
  baseline
- rebuild ticker-day count features from both teacher and deterministic labels,
  audit their `5d` excess-return ICs, and check whether the strongest teacher
  field champions keep their sign
- compare the best deterministic feature magnitude with the old keyword-news
  baseline from `xs_news_sentiment_daily.parquet`

Verdict rule:
- PASS:
  - preserve at least `3 / 4` eligible field champions
  - improve held-out macro-F1 by at least `0.05` on at least two dense fields
  - best deterministic feature absolute IC exceeds the best keyword baseline by
    at least `0.005`
- MIXED:
  - preserve at least `2 / 4` eligible field champions
  - improve held-out macro-F1 by at least `0.05` on at least one dense field
  - best deterministic feature absolute IC exceeds the best keyword baseline
- FAILED otherwise

This does not change the live branch and does not use `2026+`.
"""

from __future__ import annotations

import json
import math
import re
import sys
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis import h329_title_sequence_novelty_distillation as h329  # noqa: E402
from data_tools import extract_llm_news_features_legacy as legacy  # noqa: E402
from src.repo_paths import data_path  # noqa: E402
from src.run_summary import write_run_summary  # noqa: E402
from src.standalone_signal_utils import load_ohlcv_wide, load_vni_close, to_long  # noqa: E402


RAW_DIR = data_path("news/cafef/raw")
CACHE_DIR = data_path("llm_cache")
KEYWORD_PATH = data_path("features/xs_news_sentiment_daily.parquet")
OUT_DIR = ROOT / "artifacts" / "portfolio_baselines"
DETAILS_DIR = ROOT / "artifacts" / "run_summaries"

HOLDOUT_YEAR = 2017
TARGET_HORIZON = 5
MIN_FIELD_NONZERO_ROWS = 20
PASS_SIGN_PRESERVED = 3
MIXED_SIGN_PRESERVED = 2
PASS_MACRO_F1_DELTA = 0.05
PASS_DENSE_IMPROVEMENTS = 2
MIXED_DENSE_IMPROVEMENTS = 1
PASS_KEYWORD_IC_DELTA = 0.005

FOCUS_EVENT_TYPES = (
    "management_change",
    "merger_acquisition",
    "partnership",
    "expansion",
    "earnings_miss",
    "legal_issue",
)


@dataclass(frozen=True)
class FieldSpec:
    labels: tuple[str, ...]
    dense: bool


FIELD_SPECS = {
    "source_authority": FieldSpec(
        labels=("media_report", "management", "official", "analyst", "rumor_source"),
        dense=True,
    ),
    "expectation_alignment": FieldSpec(
        labels=("beats", "misses", "meets"),
        dense=True,
    ),
    "impact_scope": FieldSpec(
        labels=("stock", "sector", "market"),
        dense=True,
    ),
    "event_type": FieldSpec(
        labels=FOCUS_EVENT_TYPES,
        dense=False,
    ),
}

OFFICIAL_DOMAIN_HINTS = (
    "hose",
    "hnx",
    "upcom",
    "ssc",
    "vsd",
    "mof",
    "gov",
    "moit",
)
OFFICIAL_PHRASES = (
    "cong bo thong tin",
    "bao cao tai chinh",
    "bctc",
    "nghi quyet",
    "tai lieu dai hoi",
    "dhcd",
    "dai hoi dong co dong",
    "hoi dong quan tri",
    "hdqt",
    "so giao dich",
    "uy ban chung khoan",
    "ubck",
    "thong qua",
    "dang ky giao dich",
    "thong bao",
    "quyet dinh",
)
MANAGEMENT_PHRASES = (
    "chu tich",
    "tong giam doc",
    "pho tong giam doc",
    "ceo",
    "cfo",
    "ban lanh dao",
    "lanh dao cong ty",
    "lanh dao doanh nghiep",
    "theo lanh dao",
    "ong ",
    "ba ",
    "cho biet",
    "chia se",
    "tiet lo",
    "nhan dinh",
)
ANALYST_PHRASES = (
    "khuyen nghi",
    "bao cao phan tich",
    "bao cao chien luoc",
    "research",
    "phan tich",
    "ctck",
    "chuyen gia",
    "theo danh gia",
    "theo bao cao cua",
)
ANALYST_DOMAIN_HINTS = (
    "ssi",
    "vndirect",
    "hsc",
    "vcsc",
    "fpts",
    "bsc",
    "mbs",
    "kbsv",
)
RUMOR_PHRASES = (
    "tin don",
    "don doan",
    "ro tin",
    "hanh lang",
    "chua kiem chung",
    "nghe noi",
    "theo tin",
    "rumor",
)

MISSES_PHRASES = (
    "khong dat ke hoach",
    "chua dat ke hoach",
    "khong hoan thanh",
    "thap hon ke hoach",
    "duoi ky vong",
    "hut muc tieu",
    "hut ke hoach",
    "giam manh",
    "sut giam",
    "thua lo",
    "lo rong",
    "bao lo",
    "lo quy",
    "khong dat chi tieu",
)
BEATS_PHRASES = (
    "vuot ke hoach",
    "vuot chi tieu",
    "vuot muc tieu",
    "vuot ky vong",
    "vuot du bao",
    "cao hon ke hoach",
    "vuot xa",
    "but pha",
    "dot bien",
)
MEETS_PHRASES = (
    "dat ke hoach",
    "hoan thanh ke hoach",
    "hoan thanh chi tieu",
    "dat chi tieu",
    "dat muc tieu",
    "dung ke hoach",
    "kip dat ke hoach",
)

MARKET_PHRASES = (
    "vn index",
    "vnindex",
    "hnx index",
    "upcom index",
    "thi truong",
    "ttck",
    "toan thi truong",
    "nha dau tu",
    "chi so",
    "thanh khoan thi truong",
    "dong loat",
    "khoi ngoai",
)
SECTOR_PHRASES = (
    "nganh",
    "nhom co phieu",
    "nhom ngan hang",
    "nhom bat dong san",
    "nhom dau khi",
    "nhom thep",
    "nhom chung khoan",
    "doanh nghiep nganh",
    "co phieu nganh",
    "ngan hang",
    "bat dong san",
    "dau khi",
    "thep",
    "bao hiem",
    "hang khong",
    "det may",
    "thuy san",
    "phan bon",
    "vat lieu xay dung",
)

LEGAL_PHRASES = (
    "bi phat",
    "xu phat",
    "khoi to",
    "dieu tra",
    "truy thu",
    "vi pham",
    "cuong che",
    "dinh chi",
    "tam dung",
    "kien",
    "tranh chap",
)
MANAGEMENT_CHANGE_PHRASES = (
    "bo nhiem",
    "mien nhiem",
    "tu nhiem",
    "thoi chuc",
    "roi ghe",
    "thay tong giam doc",
    "thay ceo",
    "thay chu tich",
    "bau bo sung",
    "kien toan nhan su",
    "nhan su cap cao",
)
MERGER_PHRASES = (
    "sap nhap",
    "mua lai",
    "thau tom",
    "m a",
    "m&a",
    "hop nhat",
    "chao mua",
    "nhan chuyen nhuong",
    "cong ty con",
)
PARTNERSHIP_PHRASES = (
    "hop tac",
    "ky ket hop tac",
    "ky thoa thuan",
    "bien ban ghi nho",
    "ghi nho hop tac",
    "mou",
    "bat tay",
    "hop tac chien luoc",
)
EXPANSION_PHRASES = (
    "mo rong",
    "khoi cong",
    "dong tho",
    "xay dung nha may",
    "nang cong suat",
    "khanh thanh",
    "khai truong",
    "mo ban",
    "du an moi",
    "nha may moi",
    "ra mat du an",
)
EARNINGS_CONTEXT_PHRASES = (
    "loi nhuan",
    "doanh thu",
    "lnst",
    "lntt",
    "ket qua kinh doanh",
    "quy ",
    "nam ",
)


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


def _strip_ascii(value: str) -> str:
    text = str(value or "").replace("đ", "d").replace("Đ", "D")
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w\s]", " ", text.lower(), flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text, flags=re.UNICODE).strip()
    return text


def _contains_any(text: str, phrases: tuple[str, ...]) -> bool:
    return any(phrase in text for phrase in phrases)


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
                tickers = tuple(sorted({str(ticker).strip().upper() for ticker in (obj.get("tickers") or []) if str(ticker).strip()}))
                if not tickers:
                    continue
                article = raw_by_id.get(str(obj.get("id", "") or "").strip())
                if not article:
                    continue

                teacher_values = {}
                for field, spec in FIELD_SPECS.items():
                    value = str(obj.get(field, "") or "").strip().lower()
                    if value in spec.labels:
                        teacher_values[field] = value
                    else:
                        teacher_values[field] = None

                if not any(teacher_values.values()):
                    continue

                title = str(article.get("title") or "")
                summary = str(article.get("summary") or "")
                body = str(article.get("body") or "")
                combined = " ".join(part for part in [title, summary, body] if part).strip()
                if not combined:
                    continue

                rows.append(
                    {
                        "time": pd.to_datetime(cache_path.stem),
                        "article_id": str(obj["id"]),
                        "tickers": tickers,
                        "tickers_joined": ",".join(tickers),
                        "ticker_count": int(len(tickers)),
                        "source_domain": str(obj.get("source_domain") or ""),
                        "title": title,
                        "summary": summary,
                        "body": body,
                        "text_ascii": _strip_ascii(combined),
                        "title_ascii": _strip_ascii(title),
                        "summary_ascii": _strip_ascii(summary),
                        "domain_ascii": _strip_ascii(str(obj.get("source_domain") or "")),
                        **{f"teacher_{field}": value for field, value in teacher_values.items()},
                    }
                )

    if not rows:
        raise RuntimeError("No teacher event-family articles found in current cache window")
    return pd.DataFrame(rows).sort_values(["time", "article_id"]).reset_index(drop=True)


def _predict_source_authority(row: pd.Series) -> str:
    text = str(row["text_ascii"])
    domain = str(row["domain_ascii"])
    title = str(row["title_ascii"])
    summary = str(row["summary_ascii"])

    if _contains_any(text, RUMOR_PHRASES):
        return "rumor_source"
    if _contains_any(text, ANALYST_PHRASES) or any(hint in domain for hint in ANALYST_DOMAIN_HINTS):
        return "analyst"
    if _contains_any(text, OFFICIAL_PHRASES) or any(hint in domain for hint in OFFICIAL_DOMAIN_HINTS):
        return "official"
    if _contains_any(title + " " + summary, MANAGEMENT_PHRASES):
        return "management"
    return "media_report"


def _predict_expectation_alignment(row: pd.Series) -> str:
    text = str(row["text_ascii"])
    if _contains_any(text, MISSES_PHRASES):
        return "misses"
    if _contains_any(text, BEATS_PHRASES):
        return "beats"
    if _contains_any(text, MEETS_PHRASES):
        return "meets"
    return "other"


def _predict_impact_scope(row: pd.Series) -> str:
    text = str(row["text_ascii"])
    ticker_count = int(row["ticker_count"])
    if _contains_any(text, MARKET_PHRASES) or ticker_count >= 6:
        return "market"
    if _contains_any(text, SECTOR_PHRASES) or ticker_count >= 3:
        return "sector"
    return "stock"


def _predict_event_type(row: pd.Series) -> str:
    text = str(row["text_ascii"])
    if _contains_any(text, LEGAL_PHRASES):
        return "legal_issue"
    if _contains_any(text, MANAGEMENT_CHANGE_PHRASES):
        return "management_change"
    if _contains_any(text, MERGER_PHRASES):
        return "merger_acquisition"
    if _contains_any(text, PARTNERSHIP_PHRASES):
        return "partnership"
    if _contains_any(text, EXPANSION_PHRASES):
        return "expansion"
    if _contains_any(text, MISSES_PHRASES) and _contains_any(text, EARNINGS_CONTEXT_PHRASES):
        return "earnings_miss"
    return "other"


def assign_deterministic_labels(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["deterministic_source_authority"] = out.apply(_predict_source_authority, axis=1)
    out["deterministic_expectation_alignment"] = out.apply(_predict_expectation_alignment, axis=1)
    out["deterministic_impact_scope"] = out.apply(_predict_impact_scope, axis=1)
    out["deterministic_event_type"] = out.apply(_predict_event_type, axis=1)
    return out


def _classification_report(frame: pd.DataFrame, actual_col: str, pred_col: str, labels: tuple[str, ...]) -> dict[str, object]:
    work = frame[[actual_col, pred_col]].copy()
    work[actual_col] = work[actual_col].fillna("__missing__")
    work[pred_col] = work[pred_col].fillna("__missing__")
    confusion = pd.crosstab(work[actual_col], work[pred_col], dropna=False)
    extra_pred_cols = [column for column in confusion.columns if column not in labels]
    confusion = confusion.reindex(index=list(labels), columns=list(labels) + extra_pred_cols, fill_value=0)

    total = int(confusion.loc[list(labels)].to_numpy().sum())
    per_label_rows = []
    recalls = []
    f1s = []
    correct = 0
    for label in labels:
        tp = int(confusion.loc[label, label]) if label in confusion.columns else 0
        correct += tp
        predicted_total = int(confusion[label].sum()) if label in confusion.columns else 0
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

    return {
        "accuracy": float(correct / total) if total else 0.0,
        "balanced_accuracy": float(np.mean(recalls)) if recalls else 0.0,
        "macro_f1": float(np.mean(f1s)) if f1s else 0.0,
        "row_count": total,
        "per_label": per_label_rows,
        "confusion_matrix": confusion.reset_index().rename(columns={"index": "actual"}).to_dict(orient="records"),
    }


def _majority_baseline(train_series: pd.Series, size: int) -> str:
    counts = train_series.dropna().value_counts()
    if counts.empty:
        return ""
    return str(counts.idxmax())


def build_feature_panel(frame: pd.DataFrame, *, source_prefix: str) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for row in frame.itertuples(index=False):
        tickers = tuple(str(row.tickers_joined).split(","))
        for ticker in tickers:
            ticker = ticker.strip().upper()
            if not ticker:
                continue
            for field, spec in FIELD_SPECS.items():
                label = getattr(row, f"{source_prefix}_{field}")
                if label not in spec.labels:
                    continue
                rows.append(
                    {
                        "time": pd.Timestamp(row.time),
                        "ticker": ticker,
                        "feature_name": f"{field}__{label}",
                        "value": 1,
                    }
                )
    if not rows:
        return pd.DataFrame()

    panel = pd.DataFrame(rows)
    pivot = panel.pivot_table(index=["time", "ticker"], columns="feature_name", values="value", aggfunc="sum", fill_value=0).reset_index()
    pivot.columns.name = None
    return pivot.sort_values(["time", "ticker"]).reset_index(drop=True)


def _evaluate_feature_panel(panel: pd.DataFrame, source_name: str) -> pd.DataFrame:
    close = load_ohlcv_wide(min_rows=120)["close"].sort_index()
    close = close.loc[(close.index.year >= 2015) & (close.index.year <= 2017)].copy()
    benchmark_close = load_vni_close().reindex(close.index)
    target = h329._future_excess_return(close, benchmark_close, periods=TARGET_HORIZON)
    target_long = to_long(target, f"future_rel_return_{TARGET_HORIZON}d")
    target_long["time"] = pd.to_datetime(target_long["time"], errors="coerce")
    target_long = target_long[(target_long["time"].dt.year >= 2015) & (target_long["time"].dt.year <= 2017)].copy()

    merged = panel.merge(target_long, on=["time", "ticker"], how="inner")
    target_col = f"future_rel_return_{TARGET_HORIZON}d"
    merged[target_col] = pd.to_numeric(merged[target_col], errors="coerce").replace([np.inf, -np.inf], np.nan)
    merged = merged.dropna(subset=[target_col])
    if merged.empty:
        return pd.DataFrame()

    feature_cols = [column for column in merged.columns if column not in {"time", "ticker", target_col}]
    rows = []
    for feature in feature_cols:
        series = h329._daily_ic_series(merged[["time", feature, target_col]].copy(), feature, target_col)
        stats = h329._summary_from_series(series)
        rows.append(
            {
                "source_name": source_name,
                "feature_name": feature,
                "field_name": feature.split("__", 1)[0],
                "label_name": feature.split("__", 1)[1],
                "row_count": int(len(merged)),
                "nonzero_rows": int((pd.to_numeric(merged[feature], errors="coerce").fillna(0.0) != 0.0).sum()),
                "feature_mean": float(pd.to_numeric(merged[feature], errors="coerce").mean()),
                "target_mean": float(pd.to_numeric(merged[target_col], errors="coerce").mean()),
                **stats,
            }
        )
    result = pd.DataFrame(rows).sort_values(
        by=["field_name", "mean_ic", "daily_hit_rate", "positive_years"],
        ascending=[True, False, False, False],
        ignore_index=True,
    )
    result["abs_mean_ic"] = result["mean_ic"].abs()
    return result


def _evaluate_keyword_baseline() -> tuple[dict[str, object], pd.DataFrame]:
    news = pd.read_parquet(KEYWORD_PATH, columns=["ticker", "time", "sentiment_score", "positive_ratio"]).copy()
    news["time"] = pd.to_datetime(news["time"], errors="coerce")
    news = news[(news["time"].dt.year >= 2015) & (news["time"].dt.year <= 2017)].copy()

    close = load_ohlcv_wide(min_rows=120)["close"].sort_index()
    close = close.loc[(close.index.year >= 2015) & (close.index.year <= 2017)].copy()
    benchmark_close = load_vni_close().reindex(close.index)
    target = h329._future_excess_return(close, benchmark_close, periods=TARGET_HORIZON)
    target_long = to_long(target, f"future_rel_return_{TARGET_HORIZON}d")
    target_long["time"] = pd.to_datetime(target_long["time"], errors="coerce")
    target_long = target_long[(target_long["time"].dt.year >= 2015) & (target_long["time"].dt.year <= 2017)].copy()

    panel = news.merge(target_long, on=["time", "ticker"], how="inner")
    target_col = f"future_rel_return_{TARGET_HORIZON}d"
    panel[target_col] = pd.to_numeric(panel[target_col], errors="coerce").replace([np.inf, -np.inf], np.nan)
    panel = panel.dropna(subset=[target_col])
    rows = []
    for feature in ["sentiment_score", "positive_ratio"]:
        series = h329._daily_ic_series(panel[["time", feature, target_col]].copy(), feature, target_col)
        stats = h329._summary_from_series(series)
        rows.append(
            {
                "feature_name": feature,
                "mean_ic": float(stats["mean_ic"]),
                "abs_mean_ic": float(abs(stats["mean_ic"])) if np.isfinite(stats["mean_ic"]) else float("nan"),
                "daily_hit_rate": float(stats["daily_hit_rate"]),
                "positive_years": int(stats["positive_years"]),
                "daily_rows": int(stats["daily_rows"]),
                "row_count": int(len(panel)),
            }
        )
    result = pd.DataFrame(rows).sort_values(by=["abs_mean_ic", "daily_hit_rate"], ascending=[False, False], ignore_index=True)
    best = result.iloc[0].to_dict()
    return best, result


def main() -> None:
    teacher_articles = load_teacher_articles()
    articles = assign_deterministic_labels(teacher_articles)

    field_metric_rows = []
    field_reports = {}
    dense_improvements = 0
    for field, spec in FIELD_SPECS.items():
        teacher_col = f"teacher_{field}"
        pred_col = f"deterministic_{field}"
        actual_rows = articles[articles[teacher_col].isin(spec.labels)].copy()
        holdout = actual_rows[actual_rows["time"].dt.year == HOLDOUT_YEAR].copy()
        train = actual_rows[actual_rows["time"].dt.year < HOLDOUT_YEAR].copy()
        majority_label = _majority_baseline(train[teacher_col], len(holdout))
        holdout["baseline_pred"] = majority_label if majority_label else "other"

        det_report = _classification_report(holdout, teacher_col, pred_col, spec.labels)
        baseline_report = _classification_report(holdout, teacher_col, "baseline_pred", spec.labels)
        macro_delta = float(det_report["macro_f1"] - baseline_report["macro_f1"])
        if spec.dense and macro_delta >= PASS_MACRO_F1_DELTA:
            dense_improvements += 1

        field_metric_rows.append(
            {
                "field_name": field,
                "row_count": int(len(actual_rows)),
                "holdout_rows": int(len(holdout)),
                "majority_label": majority_label,
                "det_macro_f1": float(det_report["macro_f1"]),
                "baseline_macro_f1": float(baseline_report["macro_f1"]),
                "macro_f1_delta": macro_delta,
                "det_accuracy": float(det_report["accuracy"]),
                "det_balanced_accuracy": float(det_report["balanced_accuracy"]),
                "dense_field": bool(spec.dense),
            }
        )
        field_reports[field] = {
            "deterministic": det_report,
            "baseline": baseline_report,
        }

    teacher_panel = build_feature_panel(articles, source_prefix="teacher")
    deterministic_panel = build_feature_panel(articles, source_prefix="deterministic")
    teacher_features = _evaluate_feature_panel(teacher_panel, "teacher")
    deterministic_features = _evaluate_feature_panel(deterministic_panel, "deterministic")
    if teacher_features.empty or deterministic_features.empty:
        raise RuntimeError("Event-family router feature panel is empty")

    keyword_best, keyword_table = _evaluate_keyword_baseline()

    field_champions = []
    eligible_champions = 0
    preserved_champions = 0
    for field, spec in FIELD_SPECS.items():
        teacher_field = teacher_features[
            (teacher_features["field_name"] == field) & (teacher_features["nonzero_rows"] >= MIN_FIELD_NONZERO_ROWS)
        ].copy()
        if teacher_field.empty:
            field_champions.append({"field_name": field, "eligible": False})
            continue
        teacher_field["abs_mean_ic"] = teacher_field["mean_ic"].abs()
        teacher_best = teacher_field.sort_values(
            by=["abs_mean_ic", "daily_hit_rate", "positive_years"],
            ascending=[False, False, False],
            ignore_index=True,
        ).iloc[0]
        det_match = deterministic_features[
            (deterministic_features["field_name"] == field)
            & (deterministic_features["label_name"] == teacher_best["label_name"])
        ]
        det_row = det_match.iloc[0].to_dict() if not det_match.empty else {}
        teacher_ic = float(teacher_best["mean_ic"])
        det_ic = float(det_row.get("mean_ic", np.nan))
        sign_preserved = bool(
            np.isfinite(teacher_ic)
            and np.isfinite(det_ic)
            and teacher_ic != 0.0
            and math.copysign(1.0, det_ic) == math.copysign(1.0, teacher_ic)
        )
        eligible_champions += 1
        if sign_preserved:
            preserved_champions += 1
        field_champions.append(
            {
                "field_name": field,
                "eligible": True,
                "teacher_feature": str(teacher_best["feature_name"]),
                "teacher_mean_ic": teacher_ic,
                "teacher_nonzero_rows": int(teacher_best["nonzero_rows"]),
                "deterministic_mean_ic": det_ic,
                "sign_preserved": sign_preserved,
            }
        )

    deterministic_features["abs_mean_ic"] = deterministic_features["mean_ic"].abs()
    best_deterministic = deterministic_features.sort_values(
        by=["abs_mean_ic", "daily_hit_rate", "positive_years"],
        ascending=[False, False, False],
        ignore_index=True,
    ).iloc[0].to_dict()
    best_det_abs_ic = float(best_deterministic["abs_mean_ic"])
    best_keyword_abs_ic = float(keyword_best["abs_mean_ic"])

    pass_condition = bool(
        preserved_champions >= PASS_SIGN_PRESERVED
        and dense_improvements >= PASS_DENSE_IMPROVEMENTS
        and best_det_abs_ic > best_keyword_abs_ic + PASS_KEYWORD_IC_DELTA
    )
    mixed_condition = bool(
        preserved_champions >= MIXED_SIGN_PRESERVED
        and dense_improvements >= MIXED_DENSE_IMPROVEMENTS
        and best_det_abs_ic > best_keyword_abs_ic
    )
    verdict = "PASSED" if pass_condition else "MIXED" if mixed_condition else "FAILED"

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    DETAILS_DIR.mkdir(parents=True, exist_ok=True)

    article_path = OUT_DIR / f"{ts}_h331_deterministic_event_family_router_articles.parquet"
    feature_path = OUT_DIR / f"{ts}_h331_deterministic_event_family_router_feature_results.parquet"
    field_metrics_path = OUT_DIR / f"{ts}_h331_deterministic_event_family_router_field_metrics.parquet"
    keyword_path = OUT_DIR / f"{ts}_h331_deterministic_event_family_router_keyword_baseline.parquet"
    details_path = DETAILS_DIR / f"{ts}_h331_deterministic_event_family_router_audit_details.json"

    articles.to_parquet(article_path, index=False)
    pd.concat([teacher_features, deterministic_features], ignore_index=True).to_parquet(feature_path, index=False)
    pd.DataFrame(field_metric_rows).to_parquet(field_metrics_path, index=False)
    keyword_table.to_parquet(keyword_path, index=False)

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
        "field_metrics": _json_safe(field_metric_rows),
        "field_reports": _json_safe(field_reports),
        "field_champions": _json_safe(field_champions),
        "eligible_field_champions": int(eligible_champions),
        "preserved_field_champions": int(preserved_champions),
        "dense_field_macro_improvements": int(dense_improvements),
        "best_deterministic_feature": _json_safe(best_deterministic),
        "best_keyword_baseline": _json_safe(keyword_best),
        "keyword_baseline_table": _json_safe(keyword_table.to_dict(orient="records")),
        "artifacts": {
            "articles": str(article_path.relative_to(ROOT)),
            "feature_results": str(feature_path.relative_to(ROOT)),
            "field_metrics": str(field_metrics_path.relative_to(ROOT)),
            "keyword_baseline": str(keyword_path.relative_to(ROOT)),
        },
    }
    details_path.write_text(json.dumps(_json_safe(summary), indent=2), encoding="utf-8")

    write_run_summary(
        ts=ts,
        mode="research_branch_deterministic_event_family_router_audit",
        name="h331_deterministic_event_family_router_audit",
        summary=summary,
        artifacts={
            "articles": str(article_path),
            "feature_results": str(feature_path),
            "field_metrics": str(field_metrics_path),
            "keyword_baseline": str(keyword_path),
            "details": str(details_path),
        },
        metadata={
            "session": 150,
            "holdout_year": HOLDOUT_YEAR,
            "target_horizon": TARGET_HORIZON,
        },
    )

    print("H331 DETERMINISTIC EVENT-FAMILY ROUTER AUDIT")
    print(f"Verdict: {verdict}")
    print("Preserved field champions:", f"{preserved_champions} / {eligible_champions}")
    print("Dense field macro-F1 improvements:", dense_improvements)
    print(
        "Best deterministic feature vs keyword baseline abs IC:",
        f"{best_det_abs_ic:.4f} vs {best_keyword_abs_ic:.4f}",
    )
    print(pd.DataFrame(field_metric_rows).to_string(index=False))
    print(pd.DataFrame(field_champions).to_string(index=False))


if __name__ == "__main__":
    main()
