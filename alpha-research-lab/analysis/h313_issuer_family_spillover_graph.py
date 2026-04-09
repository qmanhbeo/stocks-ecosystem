"""
H313: issuer-family spillover graph audit.

Question:
    When issuer names are ambiguous across related listed entities, does the
    response often spill to family peers strongly enough to justify a
    family-recipient branch instead of exact-ticker routing?
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from path_utils import data_path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.additive_selector_research import resolve_summary_artifact
from src.future_return_research import load_future_rel_5d
from src.news_event_source_research import mask_title_tickers, scan_news_event_archive
from src.research_protocol import ResearchProtocol, phase_mask
from src.run_summary import write_run_summary

from analysis.h309_issuer_lexicon_event_surface import _trim_legal_prefixes


H309_SUMMARY_PATH = ROOT / "artifacts" / "run_summaries" / "latest_research_branch_issuer_lexicon_event_surface.json"
S1_PATH = data_path("features/xs_barrier_vol_1d_hose_full.parquet")
RAW_NEWS_DIR = data_path("news/cafef/raw")
OUT_DIR = ROOT / "artifacts" / "portfolio_baselines"
DETAILS_DIR = ROOT / "artifacts" / "run_summaries"

PROTOCOL = ResearchProtocol(
    dev_start_year=2023,
    dev_end_year=2023,
    validation_start_year=2024,
    validation_end_year=2024,
    confirmation_year=2025,
    forward_start_year=2026,
)

COMMON_BAD = {"viet nam", "binh minh", "da nang", "gia lai", "hung yen", "an giang", "dong nai", "mien nam", "mien bac"}
MIN_ALIAS_SUPPORT = 3
MIN_PHASE_ROWS_PASS = 30
MIN_PHASE_ROWS_MIXED = 15
PANEL_COLUMNS = [
    "article_id",
    "time",
    "expected_ticker",
    "family_alias",
    "peer_count",
    "expected_actual",
    "peer_best_actual",
    "actual_diff_vs_best_peer",
    "expected_fwd5",
    "peer_best_fwd5",
    "fwd5_diff_vs_best_peer",
    "exact_actual_wins",
    "exact_fwd5_wins",
    "title",
]


def _empty_panel() -> pd.DataFrame:
    return pd.DataFrame(columns=PANEL_COLUMNS)


def _load_listing_metadata_path() -> Path:
    return resolve_summary_artifact(H309_SUMMARY_PATH, "listing_metadata")


def _derive_ambiguous_family_aliases(listing: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    filtered = listing.loc[listing["exchange"].astype(str).str.upper().eq("HOSE")].copy()
    for row in filtered.itertuples(index=False):
        cleaned = _trim_legal_prefixes(str(row.organ_name))
        tokens = cleaned.split()
        if len(tokens) < 2:
            continue
        alias = " ".join(tokens[-2:])
        if alias in COMMON_BAD or len(alias.replace(" ", "")) < 8:
            continue
        rows.append({"ticker": str(row.symbol), "family_alias": alias})
    df = pd.DataFrame(rows).drop_duplicates()
    if df.empty:
        return pd.DataFrame(columns=["family_alias", "family_tickers"])
    counts = df.groupby("family_alias")["ticker"].nunique().reset_index(name="ticker_count")
    df = df.merge(counts, on="family_alias", how="left")
    df = df.loc[df["ticker_count"].between(2, 4)].copy()
    grouped = (
        df.groupby("family_alias", as_index=False)
        .agg(family_tickers=("ticker", lambda s: sorted(set(map(str, s)))))
        .sort_values("family_alias")
        .reset_index(drop=True)
    )
    return grouped


def load_panel() -> tuple[pd.DataFrame, pd.DataFrame]:
    listing = pd.read_parquet(_load_listing_metadata_path()).copy()
    listing["symbol"] = listing["symbol"].astype(str).str.upper()
    ambiguous = _derive_ambiguous_family_aliases(listing)
    if ambiguous.empty:
        return _empty_panel(), ambiguous

    allowed_tickers = set(listing.loc[listing["exchange"].astype(str).str.upper().eq("HOSE"), "symbol"].astype(str))
    scan = scan_news_event_archive(
        raw_dir=RAW_NEWS_DIR,
        start_date="2023-01-01",
        end_date="2025-12-31",
        allowed_tickers=allowed_tickers,
    )
    articles = scan.articles.loc[
        scan.articles["has_title_ticker"].fillna(False).astype(bool)
        & scan.articles["has_event_family"].fillna(False).astype(bool)
        & scan.articles["published_at"].notna()
        & scan.articles["title_tickers"].map(len).eq(1)
    ].copy()
    articles["expected_ticker"] = articles["title_tickers"].map(lambda items: str(items[0]))
    articles["masked_title_norm"] = articles["title"].map(mask_title_tickers).astype(str).str.lower()
    articles["masked_title_norm"] = articles["masked_title_norm"].str.replace(r"[^a-z0-9 ]+", " ", regex=True).str.replace(r"\s+", " ", regex=True).str.strip()

    support_rows: list[dict[str, object]] = []
    for alias_row in ambiguous.itertuples(index=False):
        token = f" {alias_row.family_alias} "
        matched = articles.loc[articles["masked_title_norm"].map(lambda text: token in f" {text} ")].copy()
        if matched.empty:
            continue
        support_rows.append(
            {
                "family_alias": str(alias_row.family_alias),
                "family_tickers": list(alias_row.family_tickers),
                "support": int(matched["article_id"].nunique()),
            }
        )
    alias_support = pd.DataFrame(support_rows)
    if alias_support.empty:
        return _empty_panel(), ambiguous
    alias_support = alias_support.loc[alias_support["support"] >= MIN_ALIAS_SUPPORT].copy()
    if alias_support.empty:
        return _empty_panel(), ambiguous

    matched_rows: list[dict[str, object]] = []
    for row in alias_support.itertuples(index=False):
        token = f" {row.family_alias} "
        matched = articles.loc[articles["masked_title_norm"].map(lambda text: token in f" {text} ")].copy()
        for article in matched.itertuples(index=False):
            matched_rows.append(
                {
                    "article_id": str(article.article_id),
                    "time": pd.Timestamp(article.time).normalize(),
                    "expected_ticker": str(article.expected_ticker),
                    "family_alias": str(row.family_alias),
                    "family_tickers": list(row.family_tickers),
                    "title": str(article.title),
                }
            )
    matched_df = pd.DataFrame(matched_rows).drop_duplicates(subset=["article_id", "family_alias"])
    if matched_df.empty:
        return _empty_panel(), alias_support

    actual = pd.read_parquet(S1_PATH, columns=["time", "ticker", "actual"]).copy()
    actual["time"] = pd.to_datetime(actual["time"], errors="coerce").dt.normalize()
    actual = actual.loc[actual["time"].dt.year.between(2023, 2025)].copy()
    future5 = load_future_rel_5d(start_year=2023, end_year=2025).copy()
    market = actual.merge(future5, on=["time", "ticker"], how="inner")
    market_index = market.set_index(["time", "ticker"])

    eval_rows: list[dict[str, object]] = []
    for row in matched_df.itertuples(index=False):
        try:
            expected = market_index.loc[(row.time, row.expected_ticker)]
        except KeyError:
            continue
        peer_tickers = [ticker for ticker in row.family_tickers if ticker != row.expected_ticker]
        peer_frame = market.loc[(market["time"].eq(row.time)) & (market["ticker"].isin(peer_tickers))].copy()
        if peer_frame.empty:
            continue
        peer_best_actual = float(peer_frame["actual"].max())
        peer_best_fwd5 = float(peer_frame["fwd_rel_5d"].max())
        eval_rows.append(
            {
                "article_id": row.article_id,
                "time": row.time,
                "expected_ticker": row.expected_ticker,
                "family_alias": row.family_alias,
                "peer_count": int(len(peer_frame)),
                "expected_actual": float(expected["actual"]),
                "peer_best_actual": peer_best_actual,
                "actual_diff_vs_best_peer": float(expected["actual"] - peer_best_actual),
                "expected_fwd5": float(expected["fwd_rel_5d"]),
                "peer_best_fwd5": peer_best_fwd5,
                "fwd5_diff_vs_best_peer": float(expected["fwd_rel_5d"] - peer_best_fwd5),
                "exact_actual_wins": bool(float(expected["actual"]) >= peer_best_actual),
                "exact_fwd5_wins": bool(float(expected["fwd_rel_5d"]) >= peer_best_fwd5),
                "title": row.title,
            }
        )
    panel = pd.DataFrame(eval_rows)
    if panel.empty:
        panel = _empty_panel()
    return panel, alias_support


def _phase_summary(frame: pd.DataFrame, phase: str) -> dict[str, object]:
    scoped = frame.loc[phase_mask(frame, phase, protocol=PROTOCOL)].copy()
    return {
        "rows": int(len(scoped)),
        "dates": int(scoped["time"].nunique()) if not scoped.empty else 0,
        "family_aliases": int(scoped["family_alias"].nunique()) if not scoped.empty else 0,
        "exact_actual_win_rate": float(scoped["exact_actual_wins"].mean()) if not scoped.empty else None,
        "exact_fwd5_win_rate": float(scoped["exact_fwd5_wins"].mean()) if not scoped.empty else None,
        "actual_diff_vs_best_peer": float(scoped["actual_diff_vs_best_peer"].mean()) if not scoped.empty else None,
        "fwd5_diff_vs_best_peer": float(scoped["fwd5_diff_vs_best_peer"].mean()) if not scoped.empty else None,
    }


def main() -> None:
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    DETAILS_DIR.mkdir(parents=True, exist_ok=True)

    panel, alias_support = load_panel()
    panel_path = OUT_DIR / f"{ts}_h313_issuer_family_spillover_graph_panel.parquet"
    alias_path = OUT_DIR / f"{ts}_h313_issuer_family_spillover_graph_aliases.parquet"
    panel.to_parquet(panel_path, index=False)
    alias_support.to_parquet(alias_path, index=False)

    phase_rows = {phase: _phase_summary(panel, phase) for phase in ("dev", "validation", "confirmation")}
    validation = phase_rows["validation"]
    confirmation = phase_rows["confirmation"]
    pass_condition = bool(
        int(validation.get("rows") or 0) >= MIN_PHASE_ROWS_PASS
        and int(confirmation.get("rows") or 0) >= MIN_PHASE_ROWS_PASS
        and (validation.get("exact_actual_win_rate") or np.inf) < 0.45
        and (confirmation.get("exact_actual_win_rate") or np.inf) < 0.45
        and (validation.get("actual_diff_vs_best_peer") or np.inf) < 0.0
        and (confirmation.get("actual_diff_vs_best_peer") or np.inf) < 0.0
    )
    mixed_condition = bool(
        not pass_condition
        and int(validation.get("rows") or 0) >= MIN_PHASE_ROWS_MIXED
        and int(confirmation.get("rows") or 0) >= MIN_PHASE_ROWS_MIXED
        and (
            (validation.get("exact_actual_win_rate") or np.inf) < 0.5
            or (confirmation.get("exact_actual_win_rate") or np.inf) < 0.5
            or (validation.get("actual_diff_vs_best_peer") or np.inf) < 0.0
            or (confirmation.get("actual_diff_vs_best_peer") or np.inf) < 0.0
        )
    )

    if pass_condition:
        decision = "PASSED"
        branch_decision = "Ambiguous issuer-name events often route to family peers as strongly as or more strongly than the named ticker; a family-recipient branch is justified."
    elif mixed_condition:
        decision = "MIXED"
        branch_decision = "Some issuer-family spillover exists in ambiguous-name cases, but it is too local to justify a broad family-recipient branch yet."
    else:
        decision = "FAILED"
        branch_decision = "The named ticker still dominates most ambiguous-family event responses; the H309 miss cases are mostly mapping noise, not a family spillover branch."

    details = {
        "phase_rows": phase_rows,
        "alias_support": alias_support.to_dict(orient="records"),
        "examples": panel.head(20).to_dict(orient="records"),
    }
    details_path = DETAILS_DIR / f"{ts}_h313_issuer_family_spillover_graph_details.json"
    details_path.write_text(json.dumps(details, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    summary = {
        "decision": decision,
        "branch_decision": branch_decision,
        "ambiguous_family_alias_count": int(len(alias_support)),
        "matched_article_rows": int(len(panel)),
        "validation": phase_rows["validation"],
        "confirmation": phase_rows["confirmation"],
    }
    write_run_summary(
        ts=ts,
        mode="research_branch_issuer_family_spillover_graph",
        name="h313_issuer_family_spillover_graph",
        summary=summary,
        artifacts={"panel": panel_path, "aliases": alias_path, "details": details_path},
        metadata={
            "session": 136,
            "branch_contract": "Only repeated ambiguous-name cases where family peers beat the named ticker can justify a family-recipient branch.",
        },
    )


if __name__ == "__main__":
    main()
