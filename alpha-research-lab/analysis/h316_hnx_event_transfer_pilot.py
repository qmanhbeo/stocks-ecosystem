"""
H316: HNX event transfer pilot.

Question:
    Does the H309 issuer-validated event mapping contract transfer cleanly to
    HNX company-event titles, or is the event branch still effectively HOSE-only?
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
from path_utils import data_path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.additive_selector_research import resolve_summary_artifact
from src.news_event_source_research import (
    build_alias_expanded_news_event_bundle,
    build_strict_title_alias_map,
    evaluate_title_alias_map_holdout,
    scan_news_event_archive,
)
from src.run_summary import write_run_summary

from analysis.h309_issuer_lexicon_event_surface import (
    _build_metadata_candidate_aliases,
    _build_title_training_frame,
    _validate_metadata_aliases,
)


H309_SUMMARY_PATH = ROOT / "artifacts" / "run_summaries" / "latest_research_branch_issuer_lexicon_event_surface.json"
RAW_NEWS_DIR = data_path("news/cafef/raw")
OUT_DIR = ROOT / "artifacts" / "timing_data"
DETAILS_DIR = ROOT / "artifacts" / "run_summaries"

START_DATE = "2023-01-01"
END_DATE = "2025-12-31"
ALIAS_TRAIN_END_DATE = "2024-12-31"
ALIAS_HOLDOUT_START_DATE = "2025-01-01"
METADATA_MIN_SUPPORT = 2
METADATA_MIN_DOMINANCE = 0.9
MIN_HOLDOUT_ROWS = 30


def _load_listing_metadata_path() -> Path:
    return resolve_summary_artifact(H309_SUMMARY_PATH, "listing_metadata")


def main() -> None:
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    DETAILS_DIR.mkdir(parents=True, exist_ok=True)

    listing = pd.read_parquet(_load_listing_metadata_path()).copy()
    listing["symbol"] = listing["symbol"].astype(str).str.upper()
    listing["exchange"] = listing["exchange"].astype(str).str.upper()
    listing = listing.loc[listing["exchange"].isin({"HNX", "XHNF"})].copy()
    allowed_tickers = set(listing["symbol"].dropna().astype(str).unique().tolist())

    scan = scan_news_event_archive(
        raw_dir=RAW_NEWS_DIR,
        start_date=START_DATE,
        end_date=END_DATE,
        allowed_tickers=allowed_tickers,
    )
    training_titles = _build_title_training_frame(
        scan.articles,
        train_start_date=START_DATE,
        train_end_date=ALIAS_TRAIN_END_DATE,
    )
    strict_alias_map = build_strict_title_alias_map(
        scan,
        train_start_date=START_DATE,
        train_end_date=ALIAS_TRAIN_END_DATE,
        min_support=3,
        min_dominance=0.9,
    )
    strict_holdout_df, strict_holdout_summary = evaluate_title_alias_map_holdout(
        scan,
        strict_alias_map,
        holdout_start_date=ALIAS_HOLDOUT_START_DATE,
        holdout_end_date=END_DATE,
    )

    metadata_candidates = _build_metadata_candidate_aliases(listing=listing, allowed_tickers=allowed_tickers)
    metadata_alias_map = _validate_metadata_aliases(
        metadata_candidates,
        training_titles,
        min_support=METADATA_MIN_SUPPORT,
        min_dominance=METADATA_MIN_DOMINANCE,
    )
    combined_alias_map = pd.concat([strict_alias_map, metadata_alias_map], ignore_index=True)
    combined_alias_map = combined_alias_map.drop_duplicates(subset=["alias", "ticker"], keep="first").reset_index(drop=True)
    combined_holdout_df, combined_holdout_summary = evaluate_title_alias_map_holdout(
        scan,
        combined_alias_map,
        holdout_start_date=ALIAS_HOLDOUT_START_DATE,
        holdout_end_date=END_DATE,
    )
    combined_bundle, combined_assignments = build_alias_expanded_news_event_bundle(scan, combined_alias_map)

    strict_alias_map_path = OUT_DIR / f"{ts}_h316_hnx_event_transfer_pilot_strict_alias_map.parquet"
    metadata_alias_map_path = OUT_DIR / f"{ts}_h316_hnx_event_transfer_pilot_metadata_alias_map.parquet"
    combined_alias_map_path = OUT_DIR / f"{ts}_h316_hnx_event_transfer_pilot_combined_alias_map.parquet"
    combined_holdout_path = OUT_DIR / f"{ts}_h316_hnx_event_transfer_pilot_combined_holdout.parquet"
    combined_assignments_path = OUT_DIR / f"{ts}_h316_hnx_event_transfer_pilot_combined_assignments.parquet"
    strict_alias_map.to_parquet(strict_alias_map_path, index=False)
    metadata_alias_map.to_parquet(metadata_alias_map_path, index=False)
    combined_alias_map.to_parquet(combined_alias_map_path, index=False)
    combined_holdout_df.to_parquet(combined_holdout_path, index=False)
    combined_assignments.to_parquet(combined_assignments_path, index=False)

    holdout_rows = int(combined_holdout_summary.get("holdout_rows") or 0)
    strict_share = float(strict_holdout_summary.get("assigned_share") or 0.0)
    combined_share = float(combined_holdout_summary.get("assigned_share") or 0.0)
    combined_precision = combined_holdout_summary.get("assigned_precision")

    if holdout_rows < MIN_HOLDOUT_ROWS:
        decision = "SKIP"
        branch_decision = "HNX event-title coverage is still too thin for an honest transfer judgment."
    elif combined_precision is not None and float(combined_precision) >= 0.97 and (combined_share - strict_share) >= 0.05:
        decision = "PASSED"
        branch_decision = "The issuer-validated event mapping contract transfers cleanly to HNX titles; the branch is worth a later HNX price-model pilot."
    elif combined_precision is not None and float(combined_precision) >= 0.95 and combined_share > strict_share:
        decision = "MIXED"
        branch_decision = "HNX event mapping is directionally viable, but still not clean enough to justify a broader HNX alpha branch yet."
    else:
        decision = "FAILED"
        branch_decision = "The H309 event mapping contract does not transfer cleanly enough to HNX titles."

    details = {
        "hnx_ticker_count": int(len(allowed_tickers)),
        "training_title_rows": int(len(training_titles)),
        "strict_holdout_summary": strict_holdout_summary,
        "combined_holdout_summary": combined_holdout_summary,
        "metadata_candidate_alias_count": int(len(metadata_candidates)),
        "validated_metadata_alias_count": int(len(metadata_alias_map)),
        "combined_summary": combined_bundle.summary,
        "new_holdout_assignments": combined_holdout_df.loc[
            combined_holdout_df["predicted_ticker"].notna()
            & ~combined_holdout_df["article_id"].isin(
                strict_holdout_df.loc[strict_holdout_df["predicted_ticker"].notna(), "article_id"]
            )
        ].head(20).to_dict(orient="records"),
    }
    details_path = DETAILS_DIR / f"{ts}_h316_hnx_event_transfer_pilot_details.json"
    details_path.write_text(json.dumps(details, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    summary = {
        "decision": decision,
        "skipped": decision == "SKIP",
        "branch_decision": branch_decision,
        "hnx_ticker_count": int(len(allowed_tickers)),
        "training_title_rows": int(len(training_titles)),
        "strict_holdout_summary": strict_holdout_summary,
        "combined_holdout_summary": combined_holdout_summary,
        "validated_metadata_alias_count": int(len(metadata_alias_map)),
        "combined_unique_articles": int(combined_bundle.summary.get("candidate_unique_articles", 0)),
        "combined_unique_tickers": int(combined_bundle.summary.get("candidate_unique_tickers", 0)),
    }
    write_run_summary(
        ts=ts,
        mode="research_branch_hnx_event_transfer_pilot",
        name="h316_hnx_event_transfer_pilot",
        summary=summary,
        artifacts={
            "strict_alias_map": strict_alias_map_path,
            "metadata_alias_map": metadata_alias_map_path,
            "combined_alias_map": combined_alias_map_path,
            "combined_holdout": combined_holdout_path,
            "combined_assignments": combined_assignments_path,
            "details": details_path,
        },
        metadata={
            "session": 136,
            "branch_contract": "HNX transfer only advances if issuer-validated mapping maintains high holdout precision with enough coverage to matter.",
        },
    )


if __name__ == "__main__":
    main()
