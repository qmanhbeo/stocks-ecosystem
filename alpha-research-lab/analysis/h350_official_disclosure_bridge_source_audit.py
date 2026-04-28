"""
H350: official-disclosure bridge source audit.

Question:
    Is the newly wired HNX official-disclosure surface ready to support an
    official-source bridge experiment, or is it still acquisition-limited?

Design:
    - source audit only; no alpha labels and no predictive IC
    - treat 2026 rows as monitor-only and exclude them from predictive
      readiness counts
    - inspect the current HNX raw disclosure contract, HOSE matrix overlap,
      transaction extract readiness, and manifest scope
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from path_utils import data_path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.run_summary import write_run_summary  # noqa: E402


HNX_ROOT = data_path("official_disclosures/hnx")
UNIVERSE_PATH = HNX_ROOT / "issuer_universe.parquet"
NEWS_PATH = HNX_ROOT / "issuer_news.parquet"
ATTACHMENTS_PATH = HNX_ROOT / "issuer_news_attachments.parquet"
TRANSACTION_DISCLOSURES_PATH = HNX_ROOT / "issuer_transaction_disclosures.parquet"
TRANSACTION_EXTRACTS_PATH = HNX_ROOT / "issuer_transaction_attachment_extracts.parquet"
MANIFEST_PATH = HNX_ROOT / "manifest.json"
MATRIX_PATH = data_path("features/xs_rl_signal_matrix.parquet")
DETAILS_DIR = ROOT / "artifacts" / "run_summaries"

PREDICTIVE_END = pd.Timestamp("2025-12-31")
MIN_READY_PREDICTIVE_ROWS = 500
MIN_READY_PREDICTIVE_TICKERS = 50
MIN_READY_TRANSACTION_ROWS = 25


def _json_safe(value: object):
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, np.ndarray):
        return [_json_safe(item) for item in value.tolist()]
    if isinstance(value, np.generic):
        if pd.isna(value):
            return None
        return value.item()
    if isinstance(value, float) and pd.isna(value):
        return None
    return value


def _read_parquet_or_empty(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path).copy()


def _read_manifest() -> dict[str, object]:
    if not MANIFEST_PATH.exists():
        return {}
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _normalize_ticker(frame: pd.DataFrame) -> pd.DataFrame:
    if "ticker" not in frame.columns:
        return frame
    work = frame.copy()
    work["ticker"] = work["ticker"].astype(str).str.upper()
    return work


def _published_time(frame: pd.DataFrame) -> pd.Series:
    for column in ("published_at", "article_published_at", "listing_published_at", "published_date"):
        if column in frame.columns:
            return pd.to_datetime(frame[column], errors="coerce", utc=True).dt.tz_convert(None).dt.normalize()
    return pd.Series(pd.NaT, index=frame.index)


def _frame_stats(frame: pd.DataFrame, *, date_column_source: bool = True) -> dict[str, object]:
    if frame.empty:
        return {
            "rows": 0,
            "tickers": 0,
            "date_min": None,
            "date_max": None,
            "predictive_rows_pre_2026": 0,
            "predictive_tickers_pre_2026": 0,
            "predictive_dates_pre_2026": 0,
        }
    work = _normalize_ticker(frame)
    dates = _published_time(work) if date_column_source else pd.Series(pd.NaT, index=work.index)
    predictive = work.loc[dates.notna() & (dates <= PREDICTIVE_END)].copy()
    predictive_dates = dates.loc[predictive.index]
    return {
        "rows": int(len(work)),
        "tickers": int(work["ticker"].nunique()) if "ticker" in work.columns else 0,
        "date_min": None if dates.dropna().empty else pd.Timestamp(dates.dropna().min()).date().isoformat(),
        "date_max": None if dates.dropna().empty else pd.Timestamp(dates.dropna().max()).date().isoformat(),
        "predictive_rows_pre_2026": int(len(predictive)),
        "predictive_tickers_pre_2026": int(predictive["ticker"].nunique()) if "ticker" in predictive.columns else 0,
        "predictive_dates_pre_2026": int(pd.Series(predictive_dates).nunique()) if len(predictive_dates) else 0,
    }


def _load_matrix_tickers() -> set[str]:
    matrix = pd.read_parquet(MATRIX_PATH, columns=["time", "ticker"]).copy()
    matrix["time"] = pd.to_datetime(matrix["time"], errors="coerce").dt.normalize()
    matrix = matrix.loc[matrix["time"].dt.year.between(2015, 2025)].copy()
    return set(matrix["ticker"].astype(str).str.upper().dropna().unique().tolist())


def _audit() -> tuple[dict[str, object], dict[str, object]]:
    manifest = _read_manifest()
    universe = _normalize_ticker(_read_parquet_or_empty(UNIVERSE_PATH))
    news = _normalize_ticker(_read_parquet_or_empty(NEWS_PATH))
    attachments = _normalize_ticker(_read_parquet_or_empty(ATTACHMENTS_PATH))
    transaction_disclosures = _normalize_ticker(_read_parquet_or_empty(TRANSACTION_DISCLOSURES_PATH))
    transaction_extracts = _normalize_ticker(_read_parquet_or_empty(TRANSACTION_EXTRACTS_PATH))
    matrix_tickers = _load_matrix_tickers()

    universe_tickers = set(universe["ticker"].dropna().astype(str).str.upper().tolist()) if "ticker" in universe else set()
    news_tickers = set(news["ticker"].dropna().astype(str).str.upper().tolist()) if "ticker" in news else set()
    transaction_tickers = (
        set(transaction_extracts["ticker"].dropna().astype(str).str.upper().tolist())
        if "ticker" in transaction_extracts
        else set()
    )

    news_stats = _frame_stats(news)
    attachment_stats = _frame_stats(attachments)
    transaction_disclosure_stats = _frame_stats(transaction_disclosures)
    transaction_extract_stats = _frame_stats(transaction_extracts)

    manifest_target_tickers = manifest.get("target_tickers")
    manifest_resolved_target_tickers = manifest.get("resolved_target_tickers")
    max_tickers = manifest.get("max_tickers")
    latest_outputs_scoped = bool(max_tickers is not None and int(max_tickers or 0) > 0)

    source_ready = (
        int(news_stats["predictive_rows_pre_2026"]) >= MIN_READY_PREDICTIVE_ROWS
        and int(news_stats["predictive_tickers_pre_2026"]) >= MIN_READY_PREDICTIVE_TICKERS
    )
    transaction_ready = int(transaction_extract_stats["predictive_rows_pre_2026"]) >= MIN_READY_TRANSACTION_ROWS
    hose_bridge_ready = len(universe_tickers & matrix_tickers) >= MIN_READY_PREDICTIVE_TICKERS

    blockers: list[str] = []
    if not source_ready:
        blockers.append("insufficient_pre_2026_disclosure_history")
    if latest_outputs_scoped:
        blockers.append("latest_outputs_are_sample_scoped_not_append_only_history")
    if not transaction_ready:
        blockers.append("no_pre_2026_transaction_extract_surface")
    if not hose_bridge_ready:
        blockers.append("hnx_universe_has_insufficient_hose_matrix_overlap")

    if source_ready and (transaction_ready or hose_bridge_ready):
        verdict = "PASSED"
        branch_decision = (
            "Official disclosure source is ready for a narrow bridge pilot. The next test may build timing states before IC."
        )
    elif source_ready:
        verdict = "MIXED"
        branch_decision = (
            "Official disclosure history exists, but transaction extraction or HOSE bridge coverage is not ready."
        )
    else:
        verdict = "SKIPPED"
        branch_decision = (
            "Official-disclosure bridge remains acquisition-limited. Do not run alpha IC until broader pre-2026 history exists."
        )

    summary = {
        "verdict": verdict,
        "skipped": verdict == "SKIPPED",
        "branch_decision": branch_decision,
        "blockers": blockers,
        "universe_rows": int(len(universe)),
        "universe_tickers": int(len(universe_tickers)),
        "universe_market_bucket_counts": universe["market_bucket"].value_counts(dropna=False).to_dict()
        if "market_bucket" in universe.columns
        else {},
        "matrix_tickers_2015_2025": int(len(matrix_tickers)),
        "universe_overlap_with_matrix_tickers": int(len(universe_tickers & matrix_tickers)),
        "news_rows": int(news_stats["rows"]),
        "news_tickers": int(news_stats["tickers"]),
        "news_date_min": news_stats["date_min"],
        "news_date_max": news_stats["date_max"],
        "news_pre_2026_rows": int(news_stats["predictive_rows_pre_2026"]),
        "news_pre_2026_tickers": int(news_stats["predictive_tickers_pre_2026"]),
        "news_pre_2026_dates": int(news_stats["predictive_dates_pre_2026"]),
        "attachment_rows": int(attachment_stats["rows"]),
        "transaction_disclosure_rows": int(transaction_disclosure_stats["rows"]),
        "transaction_extract_rows": int(transaction_extract_stats["rows"]),
        "transaction_extract_pre_2026_rows": int(transaction_extract_stats["predictive_rows_pre_2026"]),
        "transaction_extract_tickers": int(len(transaction_tickers)),
        "manifest_run_mode": manifest.get("run_mode"),
        "manifest_target_tickers": manifest_target_tickers,
        "manifest_resolved_target_tickers": manifest_resolved_target_tickers,
        "manifest_max_tickers": max_tickers,
        "manifest_notes": manifest.get("notes", []),
    }
    details = {
        "summary": summary,
        "paths": {
            "universe": UNIVERSE_PATH,
            "news": NEWS_PATH,
            "attachments": ATTACHMENTS_PATH,
            "transaction_disclosures": TRANSACTION_DISCLOSURES_PATH,
            "transaction_extracts": TRANSACTION_EXTRACTS_PATH,
            "manifest": MANIFEST_PATH,
            "matrix": MATRIX_PATH,
        },
        "manifest": manifest,
        "news_stats": news_stats,
        "attachment_stats": attachment_stats,
        "transaction_disclosure_stats": transaction_disclosure_stats,
        "transaction_extract_stats": transaction_extract_stats,
        "sample_news_rows": news.head(10).to_dict(orient="records") if not news.empty else [],
    }
    return summary, details


def main() -> None:
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    DETAILS_DIR.mkdir(parents=True, exist_ok=True)
    summary, details = _audit()
    details_path = DETAILS_DIR / f"{ts}_h350_official_disclosure_bridge_source_audit_details.json"
    details_path.write_text(json.dumps(_json_safe(details), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary_path = write_run_summary(
        ts=ts,
        mode="research_branch_official_disclosure_bridge_source_audit",
        name="h350_official_disclosure_bridge_source_audit",
        summary=summary,
        artifacts={"details": str(details_path)},
        metadata={
            "branch_contract": (
                "Source audit only. Exclude 2026 rows from predictive readiness and do not compute alpha IC."
            ),
            "predictive_end": PREDICTIVE_END.date().isoformat(),
        },
    )
    print("\nH350: OFFICIAL-DISCLOSURE BRIDGE SOURCE AUDIT")
    print(json.dumps(_json_safe(summary), indent=2, sort_keys=True))
    print(f"summary={summary_path}")


if __name__ == "__main__":
    main()
