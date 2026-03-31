from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd


TITLE_TICKER_PATTERN = re.compile(r"\(([A-Z0-9]{2,5})\)")
EVENT_FAMILY_PATTERNS = {
    "earnings_company": (
        r"\bbctc\b",
        r"bao cao tai chinh",
        r"ket qua kinh doanh",
        r"loi nhuan",
        r"doanh thu",
        r"uoc.*loi nhuan",
    ),
    "shareholder_meeting": (
        r"dhdcd",
        r"dhcd",
        r"dai hoi dong co dong",
        r"dai hoi co dong",
        r"\bagm\b",
        r"\begm\b",
    ),
    "rights_issuance": (
        r"quyen mua",
        r"phat hanh",
        r"chao ban",
        r"esop",
        r"tang von",
        r"phat hanh them",
    ),
    "board_management": (
        r"\bhdqt\b",
        r"nghi quyet",
        r"bo nhiem",
        r"mien nhiem",
        r"tong giam doc",
        r"chu tich",
    ),
    "buyback": (
        r"mua lai co phieu",
        r"co phieu quy",
    ),
}
COMPILED_EVENT_PATTERNS = {
    family: tuple(re.compile(pattern) for pattern in patterns)
    for family, patterns in EVENT_FAMILY_PATTERNS.items()
}
ALIAS_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
ALIAS_GENERIC_TOKENS = {
    "bao",
    "cao",
    "bctc",
    "co",
    "dong",
    "cp",
    "cong",
    "ty",
    "doanh",
    "nghiep",
    "hdqt",
    "dhdcd",
    "dhcd",
    "ket",
    "qua",
    "kinh",
    "doanh",
    "loi",
    "nhuan",
    "doanh",
    "thu",
    "quy",
    "nam",
    "nghi",
    "quyet",
    "bo",
    "nhiem",
    "mien",
    "tong",
    "giam",
    "doc",
    "chu",
    "tich",
    "quyen",
    "mua",
    "phat",
    "hanh",
    "them",
    "tang",
    "von",
    "tai",
    "cua",
    "sau",
    "khi",
    "voi",
    "gia",
    "mat",
    "trieu",
}
V1_COMPANY_PROXY_COLUMNS = (
    "dividend_window_pre_20d",
    "dividend_window_post_5d",
    "issuance_window_pre_20d",
    "issuance_window_post_5d",
    "recent_insider_filing_5d",
    "recent_insider_filing_20d",
    "recent_major_holder_filing_5d",
    "recent_major_holder_filing_20d",
    "recent_any_filing_5d",
    "recent_any_filing_20d",
)


@dataclass(frozen=True)
class CandidateNewsEventBundle:
    article_events: pd.DataFrame
    daily_flags: pd.DataFrame
    summary: dict[str, object]
    family_summary: pd.DataFrame


@dataclass(frozen=True)
class NewsEventArchiveScan:
    articles: pd.DataFrame
    summary: dict[str, object]


def strip_vi(text: str) -> str:
    value = str(text).replace("đ", "d").replace("Đ", "D")
    return unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii").lower()


def extract_title_tickers(title: str, *, allowed_tickers: set[str] | None = None) -> list[str]:
    tickers = sorted(set(TITLE_TICKER_PATTERN.findall(str(title or "").upper())))
    if allowed_tickers is not None:
        tickers = [ticker for ticker in tickers if ticker in allowed_tickers]
    return tickers


def classify_event_families(*, title: str, summary: str = "", body_text: str = "") -> list[str]:
    text = strip_vi(" ".join([title or "", summary or "", body_text or ""]))
    families = [
        family
        for family, patterns in COMPILED_EVENT_PATTERNS.items()
        if any(pattern.search(text) for pattern in patterns)
    ]
    return sorted(set(families))


def iter_news_archive_paths(raw_dir: Path, *, start_date: str, end_date: str) -> list[Path]:
    return sorted(
        path
        for path in Path(raw_dir).glob("*.jsonl")
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", path.stem) and start_date <= path.stem <= end_date
    )


def build_candidate_news_event_bundle(
    *,
    raw_dir: Path,
    start_date: str,
    end_date: str,
    allowed_tickers: set[str] | None = None,
) -> CandidateNewsEventBundle:
    rows: list[dict[str, object]] = []
    total_articles = 0
    title_ticker_articles = 0
    timestamped_articles = 0
    qualified_articles: set[str] = set()

    for path in iter_news_archive_paths(raw_dir, start_date=start_date, end_date=end_date):
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                try:
                    article = json.loads(line)
                except json.JSONDecodeError:
                    continue
                total_articles += 1
                title = str(article.get("title", "") or "")
                tickers = extract_title_tickers(title, allowed_tickers=allowed_tickers)
                if tickers:
                    title_ticker_articles += 1
                if not tickers:
                    continue
                published_at = pd.to_datetime(article.get("published_at"), errors="coerce", utc=True)
                if pd.notna(published_at):
                    timestamped_articles += 1
                families = classify_event_families(
                    title=title,
                    summary=str(article.get("summary", "") or ""),
                    body_text=str(article.get("body_text", "") or "")[:1200],
                )
                if not families or pd.isna(published_at):
                    continue
                local_ts = published_at.tz_convert(None)
                signal_date = local_ts.normalize()
                article_id = str(article.get("article_id", "") or "").strip() or f"{path.stem}:{title[:40]}"
                qualified_articles.add(article_id)
                for ticker in tickers:
                    for family in families:
                        rows.append(
                            {
                                "article_id": article_id,
                                "published_at": local_ts,
                                "time": signal_date,
                                "ticker": ticker,
                                "event_family": family,
                                "title": title,
                                "url": str(article.get("url", "") or ""),
                            }
                        )

    article_events = pd.DataFrame(rows)
    if article_events.empty:
        empty_daily = pd.DataFrame(columns=["time", "ticker", "has_company_event_article"])
        empty_family = pd.DataFrame(columns=["event_family", "article_rows", "unique_articles", "unique_tickers"])
        return CandidateNewsEventBundle(
            article_events=article_events,
            daily_flags=empty_daily,
            summary={
                "archive_window": {"start_date": start_date, "end_date": end_date},
                "total_articles_scanned": int(total_articles),
                "title_ticker_articles": int(title_ticker_articles),
                "timestamped_title_ticker_articles": int(timestamped_articles),
                "candidate_article_rows": 0,
                "candidate_unique_articles": 0,
                "candidate_unique_tickers": 0,
                "timestamp_coverage": 0.0,
                "family_qualified_article_share": 0.0,
            },
            family_summary=empty_family,
        )

    article_events = article_events.sort_values(["published_at", "ticker", "event_family", "article_id"]).reset_index(drop=True)
    family_summary = (
        article_events.groupby("event_family", as_index=False)
        .agg(
            article_rows=("article_id", "size"),
            unique_articles=("article_id", "nunique"),
            unique_tickers=("ticker", "nunique"),
            first_timestamp=("published_at", "min"),
            last_timestamp=("published_at", "max"),
        )
        .sort_values(["unique_tickers", "article_rows", "event_family"], ascending=[False, False, True])
        .reset_index(drop=True)
    )

    daily_flags = (
        article_events.assign(has_company_event_article=1)
        .pivot_table(
            index=["time", "ticker"],
            columns="event_family",
            values="has_company_event_article",
            aggfunc="max",
            fill_value=0,
        )
        .reset_index()
    )
    daily_flags["has_company_event_article"] = 1
    family_columns = [column for column in daily_flags.columns if column not in {"time", "ticker", "has_company_event_article"}]
    for family in EVENT_FAMILY_PATTERNS:
        if family not in daily_flags.columns:
            daily_flags[family] = 0
    ordered_columns = ["time", "ticker", "has_company_event_article"] + list(EVENT_FAMILY_PATTERNS.keys())
    daily_flags = daily_flags[ordered_columns].sort_values(["ticker", "time"]).reset_index(drop=True)

    unique_articles = int(article_events["article_id"].nunique())
    summary = {
        "archive_window": {"start_date": start_date, "end_date": end_date},
        "total_articles_scanned": int(total_articles),
        "title_ticker_articles": int(title_ticker_articles),
        "timestamped_title_ticker_articles": int(timestamped_articles),
        "candidate_article_rows": int(len(article_events)),
        "candidate_unique_articles": unique_articles,
        "candidate_unique_tickers": int(article_events["ticker"].nunique()),
        "timestamp_coverage": float(timestamped_articles / title_ticker_articles) if title_ticker_articles else 0.0,
        "family_qualified_article_share": float(len(qualified_articles) / title_ticker_articles) if title_ticker_articles else 0.0,
    }
    return CandidateNewsEventBundle(
        article_events=article_events,
        daily_flags=daily_flags,
        summary=summary,
        family_summary=family_summary,
    )


def summarize_recent_event_window_coverage(
    *,
    panel: pd.DataFrame,
    daily_flags: pd.DataFrame,
    windows: tuple[int, ...] = (1, 5, 20),
) -> dict[str, object]:
    work = panel[["time", "ticker"]].copy()
    work["time"] = pd.to_datetime(work["time"], errors="coerce").dt.normalize()
    merged = work.merge(daily_flags, on=["time", "ticker"], how="left")
    fill_map = {column: 0 for column in merged.columns if column not in {"time", "ticker"}}
    merged = merged.fillna(fill_map).sort_values(["ticker", "time"]).reset_index(drop=True)

    coverage_summary: dict[str, object] = {}
    signal_columns = [column for column in daily_flags.columns if column not in {"time", "ticker"}]
    for window in windows:
        for column in signal_columns:
            recent_column = f"recent_{column}_{window}d"
            merged[recent_column] = (
                merged.groupby("ticker")[column]
                .rolling(window=window, min_periods=1)
                .sum()
                .reset_index(level=0, drop=True)
            )
            coverage_summary[recent_column] = float(merged[recent_column].gt(0).mean())
    return coverage_summary


def scan_news_event_archive(
    *,
    raw_dir: Path,
    start_date: str,
    end_date: str,
    allowed_tickers: set[str] | None = None,
) -> NewsEventArchiveScan:
    rows: list[dict[str, object]] = []
    total_articles = 0
    title_ticker_articles = 0
    timestamped_title_ticker_articles = 0

    for path in iter_news_archive_paths(raw_dir, start_date=start_date, end_date=end_date):
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                try:
                    article = json.loads(line)
                except json.JSONDecodeError:
                    continue
                total_articles += 1
                title = str(article.get("title", "") or "")
                tickers = extract_title_tickers(title, allowed_tickers=allowed_tickers)
                if tickers:
                    title_ticker_articles += 1
                published_at = pd.to_datetime(article.get("published_at"), errors="coerce", utc=True)
                if tickers and pd.notna(published_at):
                    timestamped_title_ticker_articles += 1
                families = classify_event_families(
                    title=title,
                    summary=str(article.get("summary", "") or ""),
                    body_text=str(article.get("body_text", "") or "")[:1200],
                )
                if not tickers and not families:
                    continue
                local_ts = published_at.tz_convert(None) if pd.notna(published_at) else pd.NaT
                signal_date = local_ts.normalize() if pd.notna(local_ts) else pd.NaT
                article_id = str(article.get("article_id", "") or "").strip() or f"{path.stem}:{title[:40]}"
                rows.append(
                    {
                        "article_id": article_id,
                        "published_at": local_ts,
                        "time": signal_date,
                        "title": title,
                        "url": str(article.get("url", "") or ""),
                        "archive_date": path.stem,
                        "title_tickers": tuple(sorted(tickers)),
                        "event_families": tuple(sorted(set(families))),
                        "has_title_ticker": bool(tickers),
                        "has_event_family": bool(families),
                    }
                )

    articles = pd.DataFrame(rows)
    if articles.empty:
        articles = pd.DataFrame(
            columns=[
                "article_id",
                "published_at",
                "time",
                "title",
                "url",
                "archive_date",
                "title_tickers",
                "event_families",
                "has_title_ticker",
                "has_event_family",
            ]
        )
    summary = {
        "archive_window": {"start_date": start_date, "end_date": end_date},
        "total_articles_scanned": int(total_articles),
        "title_ticker_articles": int(title_ticker_articles),
        "timestamped_title_ticker_articles": int(timestamped_title_ticker_articles),
    }
    return NewsEventArchiveScan(articles=articles, summary=summary)


def _build_family_summary(article_events: pd.DataFrame) -> pd.DataFrame:
    if article_events.empty:
        return pd.DataFrame(columns=["event_family", "article_rows", "unique_articles", "unique_tickers"])
    return (
        article_events.groupby("event_family", as_index=False)
        .agg(
            article_rows=("article_id", "size"),
            unique_articles=("article_id", "nunique"),
            unique_tickers=("ticker", "nunique"),
            first_timestamp=("published_at", "min"),
            last_timestamp=("published_at", "max"),
        )
        .sort_values(["unique_tickers", "article_rows", "event_family"], ascending=[False, False, True])
        .reset_index(drop=True)
    )


def _build_daily_flags(article_events: pd.DataFrame) -> pd.DataFrame:
    if article_events.empty:
        return pd.DataFrame(columns=["time", "ticker", "has_company_event_article", *EVENT_FAMILY_PATTERNS.keys()])
    daily_flags = (
        article_events.assign(has_company_event_article=1)
        .pivot_table(
            index=["time", "ticker"],
            columns="event_family",
            values="has_company_event_article",
            aggfunc="max",
            fill_value=0,
        )
        .reset_index()
    )
    daily_flags["has_company_event_article"] = 1
    for family in EVENT_FAMILY_PATTERNS:
        if family not in daily_flags.columns:
            daily_flags[family] = 0
    ordered_columns = ["time", "ticker", "has_company_event_article"] + list(EVENT_FAMILY_PATTERNS.keys())
    return daily_flags[ordered_columns].sort_values(["ticker", "time"]).reset_index(drop=True)


def build_candidate_news_event_bundle_from_scan(scan: NewsEventArchiveScan) -> CandidateNewsEventBundle:
    relevant = scan.articles.loc[
        scan.articles["has_title_ticker"].fillna(False).astype(bool)
        & scan.articles["has_event_family"].fillna(False).astype(bool)
        & scan.articles["published_at"].notna()
    ].copy()
    rows: list[dict[str, object]] = []
    qualified_articles: set[str] = set()
    for row in relevant.itertuples(index=False):
        qualified_articles.add(str(row.article_id))
        for ticker in row.title_tickers:
            for family in row.event_families:
                rows.append(
                    {
                        "article_id": str(row.article_id),
                        "published_at": row.published_at,
                        "time": row.time,
                        "ticker": str(ticker),
                        "event_family": str(family),
                        "title": str(row.title),
                        "url": str(row.url),
                        "linkage_mode": "title_ticker",
                    }
                )

    article_events = pd.DataFrame(rows)
    if article_events.empty:
        return CandidateNewsEventBundle(
            article_events=article_events,
            daily_flags=_build_daily_flags(article_events),
            summary={
                **scan.summary,
                "candidate_article_rows": 0,
                "candidate_unique_articles": 0,
                "candidate_unique_tickers": 0,
                "timestamp_coverage": 0.0,
                "family_qualified_article_share": 0.0,
            },
            family_summary=_build_family_summary(article_events),
        )

    article_events = article_events.sort_values(["published_at", "ticker", "event_family", "article_id"]).reset_index(drop=True)
    title_ticker_articles = int(scan.summary.get("title_ticker_articles", 0))
    timestamped_title_ticker_articles = int(scan.summary.get("timestamped_title_ticker_articles", 0))
    summary = {
        **scan.summary,
        "candidate_article_rows": int(len(article_events)),
        "candidate_unique_articles": int(article_events["article_id"].nunique()),
        "candidate_unique_tickers": int(article_events["ticker"].nunique()),
        "timestamp_coverage": float(timestamped_title_ticker_articles / title_ticker_articles) if title_ticker_articles else 0.0,
        "family_qualified_article_share": float(len(qualified_articles) / title_ticker_articles) if title_ticker_articles else 0.0,
    }
    return CandidateNewsEventBundle(
        article_events=article_events,
        daily_flags=_build_daily_flags(article_events),
        summary=summary,
        family_summary=_build_family_summary(article_events),
    )


def _normalize_alias_title(title: str) -> str:
    text = TITLE_TICKER_PATTERN.sub(" ", str(title or ""))
    text = strip_vi(text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _iter_title_ticker_prefixes(title: str, ticker: str) -> Iterable[str]:
    raw_title = str(title or "")
    for match in TITLE_TICKER_PATTERN.finditer(raw_title.upper()):
        if match.group(1) != str(ticker).upper():
            continue
        prefix = _normalize_alias_title(raw_title[: match.start()])
        if prefix:
            yield prefix


def extract_title_alias_candidates(title: str, ticker: str) -> list[str]:
    aliases: set[str] = set()
    for prefix in _iter_title_ticker_prefixes(title, ticker):
        tokens = ALIAS_TOKEN_PATTERN.findall(prefix)
        if len(tokens) < 2:
            continue
        tail = tokens[-6:]
        for width in range(2, min(4, len(tail)) + 1):
            alias_tokens = tail[-width:]
            if alias_tokens[0] in ALIAS_GENERIC_TOKENS:
                continue
            if all(token in ALIAS_GENERIC_TOKENS for token in alias_tokens):
                continue
            alias = " ".join(alias_tokens)
            if len(alias.replace(" ", "")) < 6:
                continue
            aliases.add(alias)
    return sorted(aliases)


def build_strict_title_alias_map(
    scan: NewsEventArchiveScan,
    *,
    train_start_date: str,
    train_end_date: str,
    min_support: int = 3,
    min_dominance: float = 0.9,
) -> pd.DataFrame:
    if scan.articles.empty:
        return pd.DataFrame(columns=["alias", "ticker", "support", "total_support", "dominance", "token_count"])
    train = scan.articles.loc[
        scan.articles["has_title_ticker"].fillna(False).astype(bool)
        & scan.articles["has_event_family"].fillna(False).astype(bool)
        & scan.articles["published_at"].notna()
        & (pd.to_datetime(scan.articles["time"], errors="coerce") >= pd.Timestamp(train_start_date))
        & (pd.to_datetime(scan.articles["time"], errors="coerce") <= pd.Timestamp(train_end_date))
    ].copy()
    rows: list[dict[str, object]] = []
    for row in train.itertuples(index=False):
        for ticker in row.title_tickers:
            for alias in extract_title_alias_candidates(str(row.title), str(ticker)):
                rows.append({"alias": alias, "ticker": str(ticker), "article_id": str(row.article_id)})
    alias_rows = pd.DataFrame(rows)
    if alias_rows.empty:
        return pd.DataFrame(columns=["alias", "ticker", "support", "total_support", "dominance", "token_count"])

    support = (
        alias_rows.groupby(["alias", "ticker"], as_index=False)
        .agg(support=("article_id", "nunique"))
        .sort_values(["alias", "support", "ticker"], ascending=[True, False, True])
        .reset_index(drop=True)
    )
    support["total_support"] = support.groupby("alias")["support"].transform("sum")
    support["dominance"] = support["support"] / support["total_support"]
    support["token_count"] = support["alias"].str.split().str.len()

    kept_rows: list[dict[str, object]] = []
    for _, frame in support.groupby("alias", sort=False):
        frame = frame.sort_values(["support", "dominance", "ticker"], ascending=[False, False, True]).reset_index(drop=True)
        if frame.empty:
            continue
        if len(frame) > 1 and int(frame.loc[0, "support"]) == int(frame.loc[1, "support"]):
            continue
        top = frame.iloc[0]
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
            }
        )
    if not kept_rows:
        return pd.DataFrame(columns=["alias", "ticker", "support", "total_support", "dominance", "token_count"])
    return pd.DataFrame(kept_rows).sort_values(
        ["token_count", "support", "dominance", "alias"],
        ascending=[False, False, False, True],
    ).reset_index(drop=True)


def mask_title_tickers(title: str) -> str:
    masked = TITLE_TICKER_PATTERN.sub(" ", str(title or ""))
    return re.sub(r"\s+", " ", masked).strip()


def assign_title_alias_ticker(title: str, alias_map: pd.DataFrame) -> str | None:
    if alias_map.empty:
        return None
    normalized_title = f" {_normalize_alias_title(title)} "
    matches = alias_map.loc[alias_map["alias"].map(lambda alias: f" {alias} " in normalized_title)].copy()
    if matches.empty:
        return None
    matches = matches.sort_values(
        ["token_count", "support", "dominance", "alias"],
        ascending=[False, False, False, True],
    ).reset_index(drop=True)
    best = matches.iloc[0]
    tied = matches.loc[
        (matches["token_count"] == best["token_count"])
        & (matches["support"] == best["support"])
        & (matches["dominance"] == best["dominance"])
    ]
    if tied["ticker"].nunique() > 1:
        return None
    return str(best["ticker"])


def evaluate_title_alias_map_holdout(
    scan: NewsEventArchiveScan,
    alias_map: pd.DataFrame,
    *,
    holdout_start_date: str,
    holdout_end_date: str,
) -> tuple[pd.DataFrame, dict[str, object]]:
    if scan.articles.empty:
        empty = pd.DataFrame(columns=["article_id", "masked_title", "expected_ticker", "predicted_ticker", "correct"])
        return empty, {"holdout_rows": 0, "assigned_rows": 0, "assigned_share": 0.0, "assigned_precision": None}

    holdout = scan.articles.loc[
        scan.articles["has_title_ticker"].fillna(False).astype(bool)
        & scan.articles["has_event_family"].fillna(False).astype(bool)
        & scan.articles["published_at"].notna()
        & scan.articles["title_tickers"].map(len).eq(1)
        & (pd.to_datetime(scan.articles["time"], errors="coerce") >= pd.Timestamp(holdout_start_date))
        & (pd.to_datetime(scan.articles["time"], errors="coerce") <= pd.Timestamp(holdout_end_date))
    ].copy()
    rows: list[dict[str, object]] = []
    for row in holdout.itertuples(index=False):
        expected_ticker = str(row.title_tickers[0])
        masked_title = mask_title_tickers(str(row.title))
        predicted_ticker = assign_title_alias_ticker(masked_title, alias_map)
        rows.append(
            {
                "article_id": str(row.article_id),
                "masked_title": masked_title,
                "expected_ticker": expected_ticker,
                "predicted_ticker": predicted_ticker,
                "correct": bool(predicted_ticker == expected_ticker) if predicted_ticker is not None else None,
            }
        )
    evaluation = pd.DataFrame(rows)
    assigned = evaluation.loc[evaluation["predicted_ticker"].notna()].copy()
    precision = float(assigned["correct"].astype(bool).mean()) if not assigned.empty else None
    return evaluation, {
        "holdout_rows": int(len(evaluation)),
        "assigned_rows": int(len(assigned)),
        "assigned_share": float(len(assigned) / len(evaluation)) if len(evaluation) else 0.0,
        "assigned_precision": precision,
    }


def build_alias_expanded_news_event_bundle(
    scan: NewsEventArchiveScan,
    alias_map: pd.DataFrame,
) -> tuple[CandidateNewsEventBundle, pd.DataFrame]:
    seed_bundle = build_candidate_news_event_bundle_from_scan(scan)
    if scan.articles.empty or alias_map.empty:
        empty_assignments = pd.DataFrame(columns=["article_id", "time", "ticker", "title", "published_at", "matched_alias"])
        return seed_bundle, empty_assignments

    assignments: list[dict[str, object]] = []
    expanded_rows: list[dict[str, object]] = []
    candidates = scan.articles.loc[
        scan.articles["has_event_family"].fillna(False).astype(bool)
        & ~scan.articles["has_title_ticker"].fillna(False).astype(bool)
        & scan.articles["published_at"].notna()
    ].copy()
    for row in candidates.itertuples(index=False):
        predicted_ticker = assign_title_alias_ticker(str(row.title), alias_map)
        if predicted_ticker is None:
            continue
        normalized_title = f" {_normalize_alias_title(str(row.title))} "
        matched = alias_map.loc[
            alias_map["ticker"].eq(predicted_ticker)
            & alias_map["alias"].map(lambda alias: f" {alias} " in normalized_title)
        ].sort_values(["token_count", "support", "dominance", "alias"], ascending=[False, False, False, True])
        matched_alias = str(matched.iloc[0]["alias"]) if not matched.empty else None
        assignments.append(
            {
                "article_id": str(row.article_id),
                "time": row.time,
                "ticker": predicted_ticker,
                "title": str(row.title),
                "published_at": row.published_at,
                "matched_alias": matched_alias,
            }
        )
        for family in row.event_families:
            expanded_rows.append(
                {
                    "article_id": str(row.article_id),
                    "published_at": row.published_at,
                    "time": row.time,
                    "ticker": predicted_ticker,
                    "event_family": str(family),
                    "title": str(row.title),
                    "url": str(row.url),
                    "linkage_mode": "title_alias",
                }
            )

    assignment_df = pd.DataFrame(assignments)
    article_events = seed_bundle.article_events.copy()
    if expanded_rows:
        added = pd.DataFrame(expanded_rows)
        article_events = pd.concat([article_events, added], ignore_index=True)
        article_events = article_events.drop_duplicates(
            subset=["article_id", "published_at", "time", "ticker", "event_family"]
        ).sort_values(["published_at", "ticker", "event_family", "article_id"]).reset_index(drop=True)

    summary = {
        **seed_bundle.summary,
        "linkage_modes": {
            "title_ticker_rows": int(seed_bundle.article_events.shape[0]),
            "title_alias_rows": int(len(expanded_rows)),
            "title_alias_unique_articles": int(assignment_df["article_id"].nunique()) if not assignment_df.empty else 0,
            "title_alias_unique_tickers": int(assignment_df["ticker"].nunique()) if not assignment_df.empty else 0,
        },
        "candidate_article_rows": int(len(article_events)),
        "candidate_unique_articles": int(article_events["article_id"].nunique()) if not article_events.empty else 0,
        "candidate_unique_tickers": int(article_events["ticker"].nunique()) if not article_events.empty else 0,
    }
    bundle = CandidateNewsEventBundle(
        article_events=article_events,
        daily_flags=_build_daily_flags(article_events),
        summary=summary,
        family_summary=_build_family_summary(article_events),
    )
    return bundle, assignment_df


def summarize_company_event_novelty_vs_v1(
    *,
    daily_flags: pd.DataFrame,
    event_surface_v1: pd.DataFrame,
) -> dict[str, object]:
    if daily_flags.empty:
        return {
            "candidate_daily_rows": 0,
            "novel_daily_rows_vs_v1": 0,
            "novel_daily_share_vs_v1": None,
            "rows_with_v1_company_proxy": 0,
            "family_novelty": {},
        }
    news = daily_flags.copy()
    news["time"] = pd.to_datetime(news["time"], errors="coerce").dt.normalize()
    v1 = event_surface_v1[["time", "ticker", *V1_COMPANY_PROXY_COLUMNS]].copy()
    v1["time"] = pd.to_datetime(v1["time"], errors="coerce").dt.normalize()
    merged = news.merge(v1, on=["time", "ticker"], how="left")
    proxy_columns = [column for column in V1_COMPANY_PROXY_COLUMNS if column in merged.columns]
    if proxy_columns:
        merged[proxy_columns] = merged[proxy_columns].apply(pd.to_numeric, errors="coerce").fillna(0.0)
        merged["v1_has_company_proxy"] = merged[proxy_columns].gt(0.0).any(axis=1)
    else:
        merged["v1_has_company_proxy"] = False
    merged["is_novel_vs_v1"] = ~merged["v1_has_company_proxy"]

    family_novelty: dict[str, dict[str, object]] = {}
    for family in EVENT_FAMILY_PATTERNS:
        if family not in merged.columns:
            continue
        family_rows = merged.loc[pd.to_numeric(merged[family], errors="coerce").fillna(0).gt(0)].copy()
        family_novelty[family] = {
            "rows": int(len(family_rows)),
            "novel_rows": int(family_rows["is_novel_vs_v1"].sum()) if not family_rows.empty else 0,
            "novel_share": float(family_rows["is_novel_vs_v1"].mean()) if not family_rows.empty else None,
        }
    return {
        "candidate_daily_rows": int(len(merged)),
        "novel_daily_rows_vs_v1": int(merged["is_novel_vs_v1"].sum()),
        "novel_daily_share_vs_v1": float(merged["is_novel_vs_v1"].mean()) if not merged.empty else None,
        "rows_with_v1_company_proxy": int(merged["v1_has_company_proxy"].sum()),
        "family_novelty": family_novelty,
    }


def compute_event_density_gate(
    *,
    daily_flags: pd.DataFrame,
    panel: pd.DataFrame,
    window: int,
    threshold: int,
) -> dict[str, object]:
    work = daily_flags[["time", "ticker", "has_company_event_article"]].copy()
    work["time"] = pd.to_datetime(work["time"], errors="coerce").dt.normalize()
    work = work.sort_values(["ticker", "time"]).reset_index(drop=True)
    density = (
        work.groupby("ticker")["has_company_event_article"]
        .rolling(window=window, min_periods=1)
        .sum()
        .reset_index(level=0, drop=True)
    )
    work["event_density"] = density
    gate_col = f"event_density_{window}d"
    work[gate_col] = work["event_density"] >= threshold

    panel_work = panel[["time", "ticker"]].copy()
    panel_work["time"] = pd.to_datetime(panel_work["time"], errors="coerce").dt.normalize()
    merged = panel_work.merge(work[["time", "ticker", gate_col]], on=["time", "ticker"], how="left")
    merged[gate_col] = merged[gate_col].fillna(False).astype(bool)
    total_rows = int(len(merged))
    gating_rows = int(merged[gate_col].sum())
    gating_share = float(merged[gate_col].mean()) if total_rows else 0.0
    return {
        "window": window,
        "threshold": threshold,
        "candidate_rows": total_rows,
        "gating_rows": gating_rows,
        "gating_share": gating_share,
        "coverage": float(gating_rows / total_rows) if total_rows else 0.0,
    }
