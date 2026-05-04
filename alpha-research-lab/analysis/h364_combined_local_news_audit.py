"""
H364 - Combined Local News Surface Audit.

Question:
- After the guarded Ollama residual event-family surface is complete, does the
  combined local-news stack produce a fixed, confirmation-aware signal that is
  stronger than the BERT-only H343/H344 evidence?

Design:
- Use only local-news producer surfaces:
  PhoBERT sentiment, forward-looking, article-scope, source-type, and the
  guarded Ollama event-family residual.
- Require the guarded Ollama checkpoint manifest to be complete before running.
  Accept either the old explicit 2025 cutoff input cache or the current
  authorized full Ollama backfill; the audit itself filters all feature frames
  to 2016-2025 before merging to S1.
- Use the 1d S1 target and the locked historical split:
  dev 2016-2022, validation 2023-2024, confirmation 2025.
- Do not use 2026 data.
- Evaluate a small fixed feature set:
  direct Ollama event-family intensities and BERT x Ollama interaction states.

Decision ladder:
- PASS:
  - best fixed feature has dev avg IC > 0.01,
  - validation avg IC > 0.01,
  - confirmation IC > 0.01,
  - abs(corr with S1) < 0.30,
  - and validation/confirmation both have enough active rows.
- MIXED:
  - dev and validation pass, confirmation is positive but <= 0.01, or the
    feature clearly narrows a useful state without confirmation strength.
- FAIL:
  - validation fails, confirmation is non-positive, or the audit is too sparse.
"""

from __future__ import annotations

from datetime import datetime
import json
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
OLLAMA_PATH = data_path("features/news/datasets/ollama_guarded_ticker_day_features.parquet")
OLLAMA_CHECKPOINT_MANIFEST_PATH = data_path(
    "features/news/datasets/ollama_guarded_checkpoint/ollama_guarded_checkpoint_manifest.json"
)
OLLAMA_INPUT_MANIFEST_PATH = data_path("features/news/datasets/ollama_guarded_input_manifest.json")

BASE_COLUMNS = ["ticker", "date"]
DEV_YEARS = set(range(2016, 2023))
VALIDATION_YEARS = {2023, 2024}
CONFIRMATION_YEARS = {2025}
MIN_VALIDATION_ROWS = 2_000
MIN_CONFIRMATION_ROWS = 800

COMPANY_EVENT_COLUMNS = [
    "ollama_guarded_event_family_earnings_share",
    "ollama_guarded_event_family_dividend_share",
    "ollama_guarded_event_family_guidance_share",
    "ollama_guarded_event_family_capital_raise_or_debt_share",
    "ollama_guarded_event_family_mna_or_asset_share",
    "ollama_guarded_event_family_regulatory_or_legal_share",
    "ollama_guarded_event_family_other_company_event_share",
]

DIRECT_OLLAMA_FEATURES = [
    "ollama_guarded_confidence_mean",
    "ollama_guarded_event_family_earnings_share",
    "ollama_guarded_event_family_dividend_share",
    "ollama_guarded_event_family_guidance_share",
    "ollama_guarded_event_family_capital_raise_or_debt_share",
    "ollama_guarded_event_family_mna_or_asset_share",
    "ollama_guarded_event_family_regulatory_or_legal_share",
    "ollama_guarded_event_family_macro_or_sector_share",
    "h364_ollama_avoid_macro_or_sector_share",
    "h364_ollama_company_event_share",
    "h364_ollama_earnings_guidance_share",
    "h364_ollama_corporate_action_share",
]

INTERACTION_FEATURES = [
    "h364_official_sentiment_x_company_event",
    "h364_official_sentiment_x_earnings_guidance",
    "h364_stock_sentiment_x_company_event",
    "h364_forward_official_company_event",
    "h364_bad_news_avoid_official_company_event",
]


def _load_json(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _max_published_at_exceeds_lockbox(raw_value: str) -> bool:
    if not raw_value:
        return False
    max_published_at = pd.Timestamp(raw_value)
    if max_published_at.tzinfo is None:
        max_published_at = max_published_at.tz_localize("UTC")
    cutoff = pd.Timestamp("2025-12-31T23:59:59+07:00")
    return bool(max_published_at.tz_convert("UTC") > cutoff.tz_convert("UTC"))


def _validate_ollama_ready() -> tuple[bool, list[str], dict[str, object]]:
    checkpoint_manifest = _load_json(OLLAMA_CHECKPOINT_MANIFEST_PATH)
    input_manifest = _load_json(OLLAMA_INPUT_MANIFEST_PATH)
    blockers: list[str] = []
    if checkpoint_manifest.get("status") != "complete":
        blockers.append(
            "guarded Ollama checkpoint is not complete: "
            f"{checkpoint_manifest.get('completed_batch_count', 0)} / "
            f"{checkpoint_manifest.get('total_batches', 'unknown')}"
        )
    if not OLLAMA_PATH.exists():
        blockers.append(f"missing Ollama ticker-day dataset: {OLLAMA_PATH}")
    max_published_at = str(input_manifest.get("max_published_at") or "")
    if max_published_at and _max_published_at_exceeds_lockbox(max_published_at):
        blockers.append(f"Ollama input cache cutoff exceeds 2025 lockbox: {max_published_at}")
    input_scope = "locked_2025_cutoff" if max_published_at else "authorized_full_backfill"
    return not blockers, blockers, {
        "checkpoint_manifest": checkpoint_manifest,
        "input_manifest": input_manifest,
        "ollama_input_scope": input_scope,
        "audit_year_filter": "2016-2025",
    }


def _read_frame(path: Path, columns: list[str]) -> pd.DataFrame:
    frame = pd.read_parquet(path, columns=columns).copy()
    frame["time"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["ticker"] = frame["ticker"].astype(str).str.upper()
    frame = frame.drop(columns=["date"])
    frame = frame.dropna(subset=["time", "ticker"])
    return frame.loc[frame["time"].dt.year.between(2016, 2025)].copy()


def _numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(0.0, index=frame.index)
    return pd.to_numeric(frame[column], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0)


def _load_local_news_daily() -> pd.DataFrame:
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
        ],
    )
    scope = _read_frame(
        SCOPE_PATH,
        [
            *BASE_COLUMNS,
            "phobert_article_scope_article_count_1d",
            "phobert_article_scope_stock_news_prob_mean",
        ],
    )
    source = _read_frame(
        SOURCE_PATH,
        [
            *BASE_COLUMNS,
            "phobert_source_type_article_count_1d",
            "phobert_source_type_official_or_regulatory_prob_mean",
        ],
    )
    ollama = _read_frame(
        OLLAMA_PATH,
        [
            *BASE_COLUMNS,
            "ollama_guarded_article_count_1d",
            "ollama_guarded_confidence_mean",
            *COMPANY_EVENT_COLUMNS,
            "ollama_guarded_event_family_macro_or_sector_share",
        ],
    )

    merged = sentiment.merge(forward, on=["time", "ticker"], how="outer", validate="one_to_one")
    merged = merged.merge(scope, on=["time", "ticker"], how="outer", validate="one_to_one")
    merged = merged.merge(source, on=["time", "ticker"], how="outer", validate="one_to_one")
    merged = merged.merge(ollama, on=["time", "ticker"], how="outer", validate="one_to_one")
    for column in merged.columns:
        if column not in {"time", "ticker"}:
            merged[column] = _numeric(merged, column)
    return merged


def _add_fixed_features(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    sent = _numeric(frame, "phobert_sentiment_score_sum")
    neg_prob = _numeric(frame, "phobert_prob_neg_mean")
    forward_prob = _numeric(frame, "phobert_forward_looking_prob_mean")
    stock_prob = _numeric(frame, "phobert_article_scope_stock_news_prob_mean")
    official_prob = _numeric(frame, "phobert_source_type_official_or_regulatory_prob_mean")

    company_event = sum(_numeric(frame, column) for column in COMPANY_EVENT_COLUMNS).clip(lower=0.0, upper=1.0)
    earnings_guidance = (
        _numeric(frame, "ollama_guarded_event_family_earnings_share")
        + _numeric(frame, "ollama_guarded_event_family_guidance_share")
    ).clip(lower=0.0, upper=1.0)
    corporate_action = (
        _numeric(frame, "ollama_guarded_event_family_dividend_share")
        + _numeric(frame, "ollama_guarded_event_family_capital_raise_or_debt_share")
        + _numeric(frame, "ollama_guarded_event_family_mna_or_asset_share")
        + _numeric(frame, "ollama_guarded_event_family_regulatory_or_legal_share")
    ).clip(lower=0.0, upper=1.0)
    macro_or_sector = _numeric(frame, "ollama_guarded_event_family_macro_or_sector_share")

    frame["h364_ollama_company_event_share"] = company_event
    frame["h364_ollama_earnings_guidance_share"] = earnings_guidance
    frame["h364_ollama_corporate_action_share"] = corporate_action
    frame["h364_ollama_avoid_macro_or_sector_share"] = -macro_or_sector
    frame["h364_official_sentiment_x_company_event"] = sent * official_prob * company_event
    frame["h364_official_sentiment_x_earnings_guidance"] = sent * official_prob * earnings_guidance
    frame["h364_stock_sentiment_x_company_event"] = sent * stock_prob * company_event
    frame["h364_forward_official_company_event"] = forward_prob * official_prob * company_event
    # Positive orientation: prefer fewer negative forward-looking official company-event articles.
    frame["h364_bad_news_avoid_official_company_event"] = -neg_prob * forward_prob * official_prob * company_event
    return frame


def _active_mask(frame: pd.DataFrame, feature: str) -> pd.Series:
    ollama_active = _numeric(frame, "ollama_guarded_article_count_1d") > 0.0
    if feature in DIRECT_OLLAMA_FEATURES:
        return ollama_active
    if feature in INTERACTION_FEATURES:
        return (
            ollama_active
            & (_numeric(frame, "phobert_article_count_1d") > 0.0)
            & (_numeric(frame, "phobert_forward_looking_article_count_1d") > 0.0)
            & (_numeric(frame, "phobert_article_scope_article_count_1d") > 0.0)
            & (_numeric(frame, "phobert_source_type_article_count_1d") > 0.0)
        )
    return _numeric(frame, feature) != 0.0


def _phase_summary(yearly: list[dict[str, object]], years: set[int]) -> dict[str, object]:
    rows = [row for row in yearly if int(row["year"]) in years]
    ics = [float(row["ic"]) for row in rows]
    return {
        "years": sorted(int(row["year"]) for row in rows),
        "rows": int(sum(int(row["n"]) for row in rows)),
        "avg_ic": float(np.mean(ics)) if ics else None,
        "pos_years": int(sum(1 for ic in ics if ic > 0.0)),
        "year_count": int(len(ics)),
        "yearly": rows,
    }


def _feature_result(frame: pd.DataFrame, feature: str, *, total_rows: int) -> dict[str, object]:
    feature_frame = frame.loc[_active_mask(frame, feature)].copy()
    result = evaluate_features(feature_frame, [feature])[feature]
    yearly = result.get("yearly") or []
    phases = {
        "dev": _phase_summary(yearly, DEV_YEARS),
        "validation": _phase_summary(yearly, VALIDATION_YEARS),
        "confirmation": _phase_summary(yearly, CONFIRMATION_YEARS),
    }
    validation_rows = int(phases["validation"]["rows"])
    confirmation_rows = int(phases["confirmation"]["rows"])
    dev_ic = float(phases["dev"]["avg_ic"] or 0.0)
    validation_ic = float(phases["validation"]["avg_ic"] or 0.0)
    confirmation_ic = float(phases["confirmation"]["avg_ic"] or 0.0)
    corr = float(result.get("corr_with_s1") or 0.0)
    enough_rows = validation_rows >= MIN_VALIDATION_ROWS and confirmation_rows >= MIN_CONFIRMATION_ROWS
    pass_gate = (
        dev_ic > 0.01
        and validation_ic > 0.01
        and confirmation_ic > 0.01
        and abs(corr) < 0.30
        and enough_rows
    )
    mixed_gate = (
        not pass_gate
        and dev_ic > 0.01
        and validation_ic > 0.01
        and confirmation_ic > 0.0
        and abs(corr) < 0.30
        and enough_rows
    )
    return {
        "feature_name": feature,
        "avg_ic": result.get("avg_ic"),
        "pos_years": result.get("pos_years"),
        "years": result.get("years"),
        "pct_years_positive": result.get("pct_years_positive"),
        "corr_with_s1": result.get("corr_with_s1"),
        "coverage_pct": float(len(feature_frame) / total_rows * 100.0) if total_rows else 0.0,
        "active_rows": int(len(feature_frame)),
        "phase_details": phases,
        "enough_validation_confirmation_rows": bool(enough_rows),
        "pass_gate": bool(pass_gate),
        "mixed_gate": bool(mixed_gate),
        "yearly": yearly,
    }


def _best_row(rows: list[dict[str, object]]) -> dict[str, object]:
    return sorted(
        rows,
        key=lambda row: (
            bool(row.get("pass_gate")),
            bool(row.get("mixed_gate")),
            float(row["phase_details"]["confirmation"]["avg_ic"] or 0.0),
            float(row["phase_details"]["validation"]["avg_ic"] or 0.0),
            float(row.get("avg_ic") or 0.0),
        ),
        reverse=True,
    )[0]


def main() -> None:
    print("H364 - Combined Local News Surface Audit")
    print("=" * 78)

    ready, blockers, manifest_payload = _validate_ollama_ready()
    if not ready:
        raise RuntimeError("H364 blocked until Ollama residual is complete: " + "; ".join(blockers))

    s1 = load_s1_frame()[["time", "ticker", "actual", "xs_proba"]].copy()
    s1 = s1.loc[s1["time"].dt.year.between(2016, 2025)].copy()
    news = _add_fixed_features(_load_local_news_daily())
    merged = news.merge(s1, on=["time", "ticker"], how="inner", validate="one_to_one")
    total_rows = int(len(s1))

    feature_groups = {
        "direct_ollama": DIRECT_OLLAMA_FEATURES,
        "bert_x_ollama": INTERACTION_FEATURES,
    }
    group_results: dict[str, list[dict[str, object]]] = {}
    all_rows: list[dict[str, object]] = []
    for group_name, features in feature_groups.items():
        rows = [_feature_result(merged, feature, total_rows=total_rows) for feature in features]
        group_results[group_name] = rows
        all_rows.extend(rows)

    best = _best_row(all_rows)
    verdict = "PASSED" if best.get("pass_gate") else ("MIXED" if best.get("mixed_gate") else "FAILED")
    serializable_groups = {
        group_name: [{key: value for key, value in row.items() if key != "yearly"} for row in rows]
        for group_name, rows in group_results.items()
    }

    summary = {
        "verdict": verdict,
        "window_years": sorted(int(year) for year in merged["time"].dt.year.unique()),
        "news_rows": int(len(news)),
        "merged_rows": int(len(merged)),
        "s1_total_rows": total_rows,
        "min_validation_rows": MIN_VALIDATION_ROWS,
        "min_confirmation_rows": MIN_CONFIRMATION_ROWS,
        "best_feature": best,
        "feature_groups": serializable_groups,
        "yearly_details": {row["feature_name"]: row.get("yearly", []) for row in all_rows},
        "ollama_checkpoint_status": {
            "status": manifest_payload["checkpoint_manifest"].get("status"),
            "completed_batch_count": manifest_payload["checkpoint_manifest"].get("completed_batch_count"),
            "total_batches": manifest_payload["checkpoint_manifest"].get("total_batches"),
        },
        "ollama_input_scope": manifest_payload["ollama_input_scope"],
        "audit_year_filter": manifest_payload["audit_year_filter"],
        "ollama_input_manifest": manifest_payload["input_manifest"],
        "branch_ladder": {
            "pass_next": "Run one fixed portfolio/consumer integration audit for the best combined local-news feature.",
            "mixed_next": "Keep the combined local-news state as offline context; do not promote standalone.",
            "fail_next": "Park combined local-news standalone alpha under the current S1 target.",
        },
    }

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    path = write_run_summary(
        ts=ts,
        mode="research_branch_combined_local_news_audit",
        name="h364_combined_local_news_audit",
        summary=summary,
        artifacts={
            "ollama_checkpoint_manifest": str(OLLAMA_CHECKPOINT_MANIFEST_PATH),
            "ollama_input_manifest": str(OLLAMA_INPUT_MANIFEST_PATH),
        },
        metadata={"signal": "H364", "family": "news_sentiment"},
    )

    phase = best["phase_details"]
    print(
        f"Rows: news={len(news)}, merged={len(merged)}, s1={total_rows}, years={summary['window_years']}",
        flush=True,
    )
    print(
        f"Best feature: {best['feature_name']} | dev={float(phase['dev']['avg_ic'] or 0.0):.4f} | "
        f"validation={float(phase['validation']['avg_ic'] or 0.0):.4f} | "
        f"confirmation={float(phase['confirmation']['avg_ic'] or 0.0):.4f} | "
        f"corr_s1={float(best.get('corr_with_s1') or 0.0):.4f} | "
        f"coverage={float(best.get('coverage_pct') or 0.0):.3f}%",
        flush=True,
    )
    print(f"VERDICT: {verdict}", flush=True)
    print(f"summary: {path}", flush=True)


if __name__ == "__main__":
    main()
