"""
H309: issuer-lexicon event-surface audit.

Question:
    Can issuer metadata from vnstock widen the H301 CafeF company-event mapping
    materially while keeping masked-title holdout precision high enough to
    justify a deeper event-v2 follow-up?
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import Counter
from datetime import datetime
from pathlib import Path

import pandas as pd
from path_utils import data_path

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = ROOT.parent
SHARED_MARKET_RULES_ROOT = WORKSPACE_ROOT / "shared-market-rules"
if str(SHARED_MARKET_RULES_ROOT) not in sys.path:
    sys.path.insert(0, str(SHARED_MARKET_RULES_ROOT))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.continuation_exit_research import build_continuation_dataset
from src.news_event_source_research import (
    _normalize_alias_title,
    build_alias_expanded_news_event_bundle,
    evaluate_title_alias_map_holdout,
    mask_title_tickers,
    scan_news_event_archive,
    summarize_recent_event_window_coverage,
)
from src.run_summary import write_run_summary

from vnstock import Listing


RAW_NEWS_DIR = data_path("news/cafef/raw")
RL_MATRIX_PATH = data_path("features/xs_rl_signal_matrix.parquet")
TRADABILITY_PATH = data_path("features/execution/tradability_daily.parquet")
STOCK_DIR = data_path("stock")
BENCHMARK_PATH = STOCK_DIR / "gia_lich_su_VNINDEX_1D.parquet"
H301_SUMMARY_PATH = ROOT / "artifacts" / "run_summaries" / "latest_research_branch_cafef_event_surface_v2_pilot.json"
OUT_DIR = ROOT / "artifacts" / "timing_data"
DETAILS_DIR = ROOT / "artifacts" / "run_summaries"

START_DATE = "2023-01-01"
END_DATE = "2025-12-31"
ALIAS_TRAIN_END_DATE = "2024-12-31"
ALIAS_HOLDOUT_START_DATE = "2025-01-01"
METADATA_MIN_SUPPORT = 2
METADATA_MIN_DOMINANCE = 0.9

LEGAL_PREFIX_PHRASES = (
    "cong ty co phan",
    "cong ty cp",
    "ctcp",
    "tap doan",
    "tong cong ty",
    "ngan hang thuong mai co phan",
    "ngan hang tmcp",
    "commercial joint stock bank",
    "joint stock commercial bank",
    "joint stock company",
    "corporation",
    "holdings",
    "group",
)
VN_LEGAL_TOKENS = {"cong", "ty", "co", "phan", "ctcp", "tap", "doan", "tong", "ngan", "hang", "tmcp"}
EN_GENERIC_TOKENS = {
    "bank",
    "capital",
    "commercial",
    "communications",
    "company",
    "corporation",
    "development",
    "estate",
    "group",
    "holdings",
    "industrial",
    "international",
    "investment",
    "investments",
    "joint",
    "jsc",
    "land",
    "mobile",
    "plastics",
    "real",
    "retail",
    "rubber",
    "service",
    "services",
    "shipping",
    "steel",
    "stock",
    "technology",
    "world",
}
COMMON_ALIAS_TOKENS = VN_LEGAL_TOKENS | EN_GENERIC_TOKENS | {
    "an",
    "bac",
    "binh",
    "city",
    "corp",
    "da",
    "dong",
    "gia",
    "giang",
    "hung",
    "kan",
    "lai",
    "len",
    "minh",
    "nai",
    "nam",
    "nang",
    "nhuan",
    "phu",
    "quoc",
    "te",
    "thai",
    "tien",
    "viet",
    "yen",
    "nguyen",
}
RAW_TOKEN_PATTERN = re.compile(r"[A-Za-zÀ-ỹ0-9]+")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-news-dir", type=str, default=str(RAW_NEWS_DIR))
    parser.add_argument("--matrix", type=str, default=str(RL_MATRIX_PATH))
    parser.add_argument("--tradability", type=str, default=str(TRADABILITY_PATH))
    parser.add_argument("--stock-dir", type=str, default=str(STOCK_DIR))
    parser.add_argument("--benchmark", type=str, default=str(BENCHMARK_PATH))
    parser.add_argument("--h301-summary", type=str, default=str(H301_SUMMARY_PATH))
    parser.add_argument("--start-date", type=str, default=START_DATE)
    parser.add_argument("--end-date", type=str, default=END_DATE)
    parser.add_argument("--alias-train-end-date", type=str, default=ALIAS_TRAIN_END_DATE)
    parser.add_argument("--alias-holdout-start-date", type=str, default=ALIAS_HOLDOUT_START_DATE)
    parser.add_argument("--metadata-min-support", type=int, default=METADATA_MIN_SUPPORT)
    parser.add_argument("--metadata-min-dominance", type=float, default=METADATA_MIN_DOMINANCE)
    parser.add_argument("--portfolio-notional-vnd", type=float, default=100_000_000.0)
    parser.add_argument("--round-trip-cost", type=float, default=0.003)
    parser.add_argument("--required-holding-age", type=int, default=3)
    parser.add_argument(
        "--issuer-metadata-path",
        type=str,
        default="",
        help="Optional cached parquet with symbol/organ_name/en_organ_name/exchange.",
    )
    return parser.parse_args()


def strip_vi(text: str) -> str:
    value = str(text).replace("đ", "d").replace("Đ", "D")
    return unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii").lower()


def _trim_legal_prefixes(text: str) -> str:
    value = _normalize_alias_title(text)
    changed = True
    while changed and value:
        changed = False
        for prefix in LEGAL_PREFIX_PHRASES:
            token = f"{prefix} "
            if value.startswith(token):
                value = value[len(token):].strip()
                changed = True
    return value


def _single_token_is_brand(raw_token: str, *, english: bool) -> bool:
    normalized = strip_vi(raw_token)
    if len(normalized) < 5:
        return False
    if normalized in COMMON_ALIAS_TOKENS:
        return False
    if raw_token.isupper() and len(raw_token) >= 4:
        return True
    if raw_token[:1].isupper() and any(ch.isupper() for ch in raw_token[1:]):
        return True
    if english and raw_token[:1].isupper() and raw_token[1:].islower() and normalized not in EN_GENERIC_TOKENS:
        return True
    return False


def _issuer_alias_candidates(vn_name: str, en_name: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for source_name, text in (("organ_name", vn_name), ("en_organ_name", en_name)):
        cleaned = _trim_legal_prefixes(text)
        tokens = cleaned.split()
        for width in range(2, min(4, len(tokens)) + 1):
            alias = " ".join(tokens[-width:])
            alias_tokens = alias.split()
            if len(alias.replace(" ", "")) < 6:
                continue
            if all(token in COMMON_ALIAS_TOKENS for token in alias_tokens):
                continue
            rows.append(
                {
                    "alias": alias,
                    "alias_source": f"{source_name}_suffix_{width}",
                    "token_count": len(alias_tokens),
                }
            )

    for raw_token in RAW_TOKEN_PATTERN.findall(str(vn_name or "")):
        if _single_token_is_brand(raw_token, english=False):
            rows.append(
                {
                    "alias": strip_vi(raw_token),
                    "alias_source": "organ_name_brand_token",
                    "token_count": 1,
                }
            )
    for raw_token in RAW_TOKEN_PATTERN.findall(str(en_name or "")):
        if _single_token_is_brand(raw_token, english=True):
            rows.append(
                {
                    "alias": strip_vi(raw_token),
                    "alias_source": "en_organ_name_brand_token",
                    "token_count": 1,
                }
            )

    if not rows:
        return rows

    deduped: dict[tuple[str, str], dict[str, object]] = {}
    for row in rows:
        key = (str(row["alias"]), str(row["alias_source"]))
        deduped[key] = row
    return sorted(
        deduped.values(),
        key=lambda item: (-int(item["token_count"]), str(item["alias"])),
    )


def _load_h301_paths(summary_path: Path) -> dict[str, Path]:
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    artifacts = payload.get("artifacts", {})
    resolved: dict[str, Path] = {}
    for key, value in artifacts.items():
        path = ROOT / str(value)
        resolved[key] = path
    required = {"alias_map"}
    missing = [key for key in required if key not in resolved or not resolved[key].exists()]
    if missing:
        raise FileNotFoundError(f"Missing H301 artifact(s): {missing}")
    return resolved


def _load_or_fetch_listing(*, cached_path: Path | None) -> tuple[pd.DataFrame, str]:
    if cached_path is not None and cached_path.exists():
        listing = pd.read_parquet(cached_path).copy()
        source = "cached_parquet"
    else:
        listing = Listing().symbols_by_exchange().copy()
        source = "vnstock_listing_symbols_by_exchange"
    for column in ("symbol", "organ_name", "en_organ_name", "exchange"):
        if column not in listing.columns:
            listing[column] = ""
    listing["symbol"] = listing["symbol"].fillna("").astype(str).str.strip().str.upper()
    listing["organ_name"] = listing["organ_name"].fillna("").astype(str).str.strip()
    listing["en_organ_name"] = listing["en_organ_name"].fillna("").astype(str).str.strip()
    listing["exchange"] = listing["exchange"].fillna("").astype(str).str.strip().str.upper()
    listing = listing[["symbol", "organ_name", "en_organ_name", "exchange"]].drop_duplicates("symbol")
    return listing.sort_values("symbol").reset_index(drop=True), source


def _build_metadata_candidate_aliases(*, listing: pd.DataFrame, allowed_tickers: set[str]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    filtered = listing.loc[
        listing["exchange"].eq("HOSE") & listing["symbol"].isin(allowed_tickers)
    ].copy()
    for row in filtered.itertuples(index=False):
        for alias_row in _issuer_alias_candidates(row.organ_name, row.en_organ_name):
            rows.append(
                {
                    "ticker": str(row.symbol),
                    "alias": str(alias_row["alias"]),
                    "alias_source": str(alias_row["alias_source"]),
                    "token_count": int(alias_row["token_count"]),
                    "organ_name": str(row.organ_name),
                    "en_organ_name": str(row.en_organ_name),
                }
            )

    candidate_df = pd.DataFrame(rows)
    if candidate_df.empty:
        return pd.DataFrame(
            columns=[
                "ticker",
                "alias",
                "alias_source",
                "token_count",
                "organ_name",
                "en_organ_name",
                "alias_ticker_count",
            ]
        )
    candidate_df = candidate_df.drop_duplicates(subset=["ticker", "alias"]).reset_index(drop=True)
    alias_ticker_count = candidate_df.groupby("alias")["ticker"].transform("nunique")
    candidate_df["alias_ticker_count"] = alias_ticker_count.astype(int)
    candidate_df = candidate_df.loc[candidate_df["alias_ticker_count"].eq(1)].copy()
    return candidate_df.sort_values(
        ["token_count", "alias_source", "ticker", "alias"],
        ascending=[False, True, True, True],
    ).reset_index(drop=True)


def _build_title_training_frame(scan_articles: pd.DataFrame, *, train_start_date: str, train_end_date: str) -> pd.DataFrame:
    train = scan_articles.loc[
        scan_articles["has_title_ticker"].fillna(False).astype(bool)
        & scan_articles["has_event_family"].fillna(False).astype(bool)
        & scan_articles["published_at"].notna()
        & scan_articles["title_tickers"].map(len).eq(1)
        & (pd.to_datetime(scan_articles["time"], errors="coerce") >= pd.Timestamp(train_start_date))
        & (pd.to_datetime(scan_articles["time"], errors="coerce") <= pd.Timestamp(train_end_date))
    ].copy()
    if train.empty:
        return pd.DataFrame(columns=["article_id", "expected_ticker", "normalized_masked_title"])
    train["expected_ticker"] = train["title_tickers"].map(lambda items: str(items[0]))
    train["normalized_masked_title"] = train["title"].map(mask_title_tickers).map(
        lambda title: f" {_normalize_alias_title(title)} "
    )
    return train[["article_id", "expected_ticker", "normalized_masked_title"]].reset_index(drop=True)


def _validate_metadata_aliases(
    candidate_aliases: pd.DataFrame,
    training_titles: pd.DataFrame,
    *,
    min_support: int,
    min_dominance: float,
) -> pd.DataFrame:
    empty = pd.DataFrame(columns=["alias", "ticker", "support", "total_support", "dominance", "token_count", "alias_source"])
    if candidate_aliases.empty or training_titles.empty:
        return empty

    title_rows = list(training_titles.itertuples(index=False))
    support_rows: list[dict[str, object]] = []
    for candidate in candidate_aliases.itertuples(index=False):
        token = f" {candidate.alias} "
        ticker_support: Counter[str] = Counter()
        for title_row in title_rows:
            if token in title_row.normalized_masked_title:
                ticker_support[str(title_row.expected_ticker)] += 1
        if not ticker_support:
            continue
        for ticker, support in ticker_support.items():
            support_rows.append(
                {
                    "alias": str(candidate.alias),
                    "ticker": str(ticker),
                    "support": int(support),
                    "token_count": int(candidate.token_count),
                    "alias_source": str(candidate.alias_source),
                }
            )

    support_df = pd.DataFrame(support_rows)
    if support_df.empty:
        return empty

    support_df["total_support"] = support_df.groupby("alias")["support"].transform("sum")
    support_df["dominance"] = support_df["support"] / support_df["total_support"]

    kept_rows: list[dict[str, object]] = []
    for _, frame in support_df.groupby("alias", sort=False):
        ranked = frame.sort_values(["support", "dominance", "ticker"], ascending=[False, False, True]).reset_index(drop=True)
        if ranked.empty:
            continue
        if len(ranked) > 1 and int(ranked.loc[0, "support"]) == int(ranked.loc[1, "support"]):
            continue
        top = ranked.iloc[0]
        if int(top["support"]) < int(min_support):
            continue
        if float(top["dominance"]) < float(min_dominance):
            continue
        kept_rows.append(
            {
                "alias": str(top["alias"]),
                "ticker": str(top["ticker"]),
                "support": int(top["support"]),
                "total_support": int(top["total_support"]),
                "dominance": float(top["dominance"]),
                "token_count": int(top["token_count"]),
                "alias_source": str(top["alias_source"]),
            }
        )
    if not kept_rows:
        return empty
    return pd.DataFrame(kept_rows).sort_values(
        ["token_count", "support", "dominance", "alias"],
        ascending=[False, False, False, True],
    ).reset_index(drop=True)


def _coverage_snapshot(coverage: dict[str, object]) -> dict[str, float | None]:
    keys = (
        "recent_has_company_event_article_1d",
        "recent_has_company_event_article_5d",
        "recent_has_company_event_article_20d",
    )
    return {key: float(coverage.get(key)) if coverage.get(key) is not None else None for key in keys}


def _decision_from_metrics(*, strict_holdout: dict[str, object], combined_holdout: dict[str, object], strict_coverage: dict[str, object], combined_coverage: dict[str, object]) -> tuple[str, str, dict[str, float | None]]:
    strict_share = float(strict_holdout.get("assigned_share") or 0.0)
    combined_share = float(combined_holdout.get("assigned_share") or 0.0)
    combined_precision = combined_holdout.get("assigned_precision")
    strict_cov_5d = float(strict_coverage.get("recent_has_company_event_article_5d") or 0.0)
    combined_cov_5d = float(combined_coverage.get("recent_has_company_event_article_5d") or 0.0)
    assigned_share_uplift = combined_share - strict_share
    coverage_5d_uplift = combined_cov_5d - strict_cov_5d

    comparison = {
        "assigned_share_uplift": assigned_share_uplift,
        "coverage_5d_uplift": coverage_5d_uplift,
        "combined_precision": float(combined_precision) if combined_precision is not None else None,
    }

    if combined_precision is not None and float(combined_precision) >= 0.97 and assigned_share_uplift >= 0.05 and coverage_5d_uplift >= 0.005:
        return (
            "PASSED",
            "Issuer metadata clears the H301 mapping ceiling: combined precision stays high while both holdout assignment share and held-row coverage improve materially.",
            comparison,
        )
    if combined_precision is not None and float(combined_precision) >= 0.95 and (assigned_share_uplift >= 0.03 or coverage_5d_uplift >= 0.002):
        return (
            "MIXED",
            "Issuer metadata helps the event-v2 mapping, but the combined lexicon still falls short of a clean reopening bar on precision or coverage lift.",
            comparison,
        )
    return (
        "FAILED",
        "Issuer metadata does not widen H301 cleanly enough; the coverage gain is too small or the combined matcher loses too much holdout precision.",
        comparison,
    )


def main() -> None:
    args = parse_args()
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    DETAILS_DIR.mkdir(parents=True, exist_ok=True)

    h301_paths = _load_h301_paths(Path(args.h301_summary))
    strict_alias_map = pd.read_parquet(h301_paths["alias_map"]).copy()

    matrix = pd.read_parquet(Path(args.matrix), columns=["time", "ticker"]).copy()
    matrix["time"] = pd.to_datetime(matrix["time"], errors="coerce").dt.normalize()
    matrix = matrix.loc[
        (matrix["time"] >= pd.Timestamp(args.start_date))
        & (matrix["time"] <= pd.Timestamp(args.end_date))
    ].copy()
    allowed_tickers = set(matrix["ticker"].dropna().astype(str).unique().tolist())

    scan = scan_news_event_archive(
        raw_dir=Path(args.raw_news_dir),
        start_date=str(args.start_date),
        end_date=str(args.end_date),
        allowed_tickers=allowed_tickers,
    )
    training_titles = _build_title_training_frame(
        scan.articles,
        train_start_date=str(args.start_date),
        train_end_date=str(args.alias_train_end_date),
    )

    listing_cache_path = Path(args.issuer_metadata_path) if args.issuer_metadata_path else None
    listing, listing_source = _load_or_fetch_listing(cached_path=listing_cache_path)
    listing_out_path = OUT_DIR / f"{ts}_h309_issuer_lexicon_event_surface_listing_metadata.parquet"
    listing.to_parquet(listing_out_path, index=False)

    metadata_candidates = _build_metadata_candidate_aliases(listing=listing, allowed_tickers=allowed_tickers)
    metadata_candidates_path = OUT_DIR / f"{ts}_h309_issuer_lexicon_event_surface_candidate_aliases.parquet"
    metadata_candidates.to_parquet(metadata_candidates_path, index=False)

    metadata_alias_map = _validate_metadata_aliases(
        metadata_candidates,
        training_titles,
        min_support=int(args.metadata_min_support),
        min_dominance=float(args.metadata_min_dominance),
    )
    metadata_alias_map_path = OUT_DIR / f"{ts}_h309_issuer_lexicon_event_surface_metadata_alias_map.parquet"
    metadata_alias_map.to_parquet(metadata_alias_map_path, index=False)

    combined_alias_map = pd.concat([strict_alias_map, metadata_alias_map], ignore_index=True)
    combined_alias_map = combined_alias_map.drop_duplicates(subset=["alias", "ticker"], keep="first").sort_values(
        ["token_count", "support", "dominance", "alias"],
        ascending=[False, False, False, True],
    ).reset_index(drop=True)
    combined_alias_map_path = OUT_DIR / f"{ts}_h309_issuer_lexicon_event_surface_combined_alias_map.parquet"
    combined_alias_map.to_parquet(combined_alias_map_path, index=False)

    strict_holdout_df, strict_holdout_summary = evaluate_title_alias_map_holdout(
        scan,
        strict_alias_map,
        holdout_start_date=str(args.alias_holdout_start_date),
        holdout_end_date=str(args.end_date),
    )
    metadata_holdout_df, metadata_holdout_summary = evaluate_title_alias_map_holdout(
        scan,
        metadata_alias_map,
        holdout_start_date=str(args.alias_holdout_start_date),
        holdout_end_date=str(args.end_date),
    )
    combined_holdout_df, combined_holdout_summary = evaluate_title_alias_map_holdout(
        scan,
        combined_alias_map,
        holdout_start_date=str(args.alias_holdout_start_date),
        holdout_end_date=str(args.end_date),
    )

    holdout_path = OUT_DIR / f"{ts}_h309_issuer_lexicon_event_surface_combined_holdout.parquet"
    combined_holdout_df.to_parquet(holdout_path, index=False)

    strict_bundle, strict_assignments = build_alias_expanded_news_event_bundle(scan, strict_alias_map)
    metadata_bundle, metadata_assignments = build_alias_expanded_news_event_bundle(scan, metadata_alias_map)
    combined_bundle, combined_assignments = build_alias_expanded_news_event_bundle(scan, combined_alias_map)
    assignments_path = OUT_DIR / f"{ts}_h309_issuer_lexicon_event_surface_combined_assignments.parquet"
    combined_assignments.to_parquet(assignments_path, index=False)

    continuation = build_continuation_dataset(
        matrix_path=Path(args.matrix),
        tradability_path=Path(args.tradability),
        stock_dir=Path(args.stock_dir),
        benchmark_path=Path(args.benchmark),
        start_year=pd.Timestamp(args.start_date).year,
        end_year=pd.Timestamp(args.end_date).year,
        required_holding_age=int(args.required_holding_age),
        initial_notional_vnd=float(args.portfolio_notional_vnd),
        round_trip_cost=float(args.round_trip_cost),
    )
    strict_coverage = summarize_recent_event_window_coverage(
        panel=continuation.panel,
        daily_flags=strict_bundle.daily_flags,
        windows=(1, 5, 20),
    )
    combined_coverage = summarize_recent_event_window_coverage(
        panel=continuation.panel,
        daily_flags=combined_bundle.daily_flags,
        windows=(1, 5, 20),
    )

    decision, branch_decision, comparison = _decision_from_metrics(
        strict_holdout=strict_holdout_summary,
        combined_holdout=combined_holdout_summary,
        strict_coverage=strict_coverage,
        combined_coverage=combined_coverage,
    )

    baseline_assigned_ids = set(
        strict_holdout_df.loc[strict_holdout_df["predicted_ticker"].notna(), "article_id"].astype(str).tolist()
    )
    new_holdout = combined_holdout_df.loc[
        combined_holdout_df["predicted_ticker"].notna()
        & ~combined_holdout_df["article_id"].astype(str).isin(baseline_assigned_ids)
    ].copy()
    new_holdout["is_correct"] = new_holdout["predicted_ticker"].eq(new_holdout["expected_ticker"])

    details = {
        "listing_source": listing_source,
        "listing_rows": int(len(listing)),
        "hose_listing_rows": int(listing["exchange"].eq("HOSE").sum()),
        "allowed_ticker_count": int(len(allowed_tickers)),
        "training_title_rows": int(len(training_titles)),
        "metadata_candidate_alias_count": int(len(metadata_candidates)),
        "metadata_validated_alias_count": int(len(metadata_alias_map)),
        "metadata_alias_source_counts": metadata_alias_map["alias_source"].value_counts().to_dict() if not metadata_alias_map.empty else {},
        "strict_holdout_summary": strict_holdout_summary,
        "metadata_holdout_summary": metadata_holdout_summary,
        "combined_holdout_summary": combined_holdout_summary,
        "strict_coverage_snapshot": _coverage_snapshot(strict_coverage),
        "combined_coverage_snapshot": _coverage_snapshot(combined_coverage),
        "new_holdout_assignment_count": int(len(new_holdout)),
        "new_holdout_correct_count": int(new_holdout["is_correct"].sum()) if not new_holdout.empty else 0,
        "new_holdout_examples": new_holdout.loc[:, ["masked_title", "expected_ticker", "predicted_ticker", "is_correct"]]
        .head(20)
        .to_dict(orient="records"),
        "combined_holdout_wrong_examples": combined_holdout_df.loc[
            combined_holdout_df["predicted_ticker"].notna()
            & combined_holdout_df["predicted_ticker"].ne(combined_holdout_df["expected_ticker"]),
            ["masked_title", "expected_ticker", "predicted_ticker"],
        ]
        .head(20)
        .to_dict(orient="records"),
        "top_validated_metadata_aliases": metadata_alias_map.head(40).to_dict(orient="records") if not metadata_alias_map.empty else [],
        "comparison": comparison,
    }
    details_path = DETAILS_DIR / f"{ts}_h309_issuer_lexicon_event_surface_details.json"
    details_path.write_text(json.dumps(details, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    summary = {
        "decision": decision,
        "branch_decision": branch_decision,
        "strict_holdout_summary": strict_holdout_summary,
        "metadata_holdout_summary": metadata_holdout_summary,
        "combined_holdout_summary": combined_holdout_summary,
        "strict_coverage_snapshot": _coverage_snapshot(strict_coverage),
        "combined_coverage_snapshot": _coverage_snapshot(combined_coverage),
        "pilot_article_lift": {
            "strict_unique_articles": int(strict_bundle.summary.get("candidate_unique_articles", 0)),
            "metadata_unique_articles": int(metadata_bundle.summary.get("candidate_unique_articles", 0)),
            "combined_unique_articles": int(combined_bundle.summary.get("candidate_unique_articles", 0)),
            "combined_minus_strict_unique_articles": int(combined_bundle.summary.get("candidate_unique_articles", 0))
            - int(strict_bundle.summary.get("candidate_unique_articles", 0)),
        },
        "validated_metadata_alias_count": int(len(metadata_alias_map)),
        "new_holdout_assignment_count": int(len(new_holdout)),
        "new_holdout_correct_count": int(new_holdout["is_correct"].sum()) if not new_holdout.empty else 0,
        "comparison": comparison,
    }
    artifacts = {
        "listing_metadata": listing_out_path,
        "metadata_candidate_aliases": metadata_candidates_path,
        "metadata_alias_map": metadata_alias_map_path,
        "combined_alias_map": combined_alias_map_path,
        "combined_holdout": holdout_path,
        "combined_assignments": assignments_path,
        "details": details_path,
    }
    write_run_summary(
        ts=ts,
        mode="research_branch_issuer_lexicon_event_surface",
        name="h309_issuer_lexicon_event_surface",
        summary=summary,
        artifacts=artifacts,
        metadata={
            "session": 135,
            "branch_contract": "Issuer metadata can only reopen event-v2 mapping if combined holdout precision stays high while H301 assignment share and held-row coverage lift materially.",
        },
    )


if __name__ == "__main__":
    main()
