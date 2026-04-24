"""
Build ticker-day and market-daily LLM news features from per-day cache JSONL files.

Input:
- data/llm_cache/YYYY-MM-DD.jsonl

Outputs:
- data/features/xs_llm_news_ticker_day.parquet
- data/features/xs_llm_news_market_daily.parquet
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from path_utils import data_path

import numpy as np
import pandas as pd

try:
    from job_status import JobStatusTracker
except ModuleNotFoundError:
    from data_tools.job_status import JobStatusTracker

try:
    from stock_refresh_utils import atomic_write_parquet
except ModuleNotFoundError:
    from data_tools.stock_refresh_utils import atomic_write_parquet


REPO_ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = data_path("llm_cache")
FEATURE_DIR = data_path("features")
GRID_PATH = FEATURE_DIR / "xs_barrier_vol_1d_hose_full.parquet"
SECTOR_PATH = FEATURE_DIR / "sector_classification.parquet"

OUT_TICKER = FEATURE_DIR / "xs_llm_news_ticker_day.parquet"
OUT_MARKET = FEATURE_DIR / "xs_llm_news_market_daily.parquet"
STAGE_ROOT = FEATURE_DIR / "_llm_news_build_stage"
STAGE_TICKER_DAILY_DIR = STAGE_ROOT / "ticker_day_daily"
STAGE_MARKET_DAILY_DIR = STAGE_ROOT / "market_daily"

EARNINGS_TYPES = {"earnings_beat", "earnings_miss", "earnings_neutral"}
MACRO_TYPES = {"rate_change", "fx_move", "macro_indicator", "policy_positive", "policy_negative"}
EVENT_TYPES = {
    "earnings_beat", "earnings_miss", "earnings_neutral", "revenue_growth",
    "revenue_decline", "guidance_raise", "guidance_cut", "dividend_announce",
    "debt_issue", "debt_concern", "rights_issue", "buyback", "merger_acquisition",
    "divestiture", "ipo_listing", "management_change", "insider_buy", "insider_sell",
    "contract_win", "contract_loss", "partnership", "expansion", "legal_issue",
    "regulatory_approval", "regulatory_block", "policy_positive", "policy_negative",
    "rate_change", "fx_move", "commodity_price", "macro_indicator",
    "index_inclusion", "index_exclusion", "other", "no_event",
}
EXPECTATION_ALIGNMENTS = {"beats", "meets", "misses", "not_applicable"}
INFORMATION_NOVELTIES = {"new", "follow_up", "recycled", "unclear"}
MACRO_THEMES = {
    "rates", "fx", "liquidity", "credit", "real_estate", "banking",
    "exports", "commodities", "energy", "public_investment", "regulation",
    "geopolitics", "consumption", "technology", "industrials", "none",
}
SOURCE_AUTHORITIES = {"official", "management", "media_report", "analyst", "rumor_source", "unclear"}
CAUSAL_IMPACT_LABELS = {
    "revenue_positive", "revenue_negative", "cost_positive", "cost_negative",
    "financing_positive", "financing_negative", "regulatory_positive",
    "regulatory_negative", "sentiment_only", "mixed", "none",
}
VN_MARKET_OPEN_MINUTE = 9 * 60
VN_MARKET_CLOSE_MINUTE = 14 * 60 + 45

LIST_COLUMNS = ["tickers", "related_tickers", "named_persons"]
ENUM_COLUMNS = [
    "event_type",
    "impact_scope",
    "expectation_alignment",
    "information_novelty",
    "macro_theme",
    "source_authority",
    "causal_impact_label",
    "event_time_type",
]
BOOL_COLUMNS = ["is_forward_looking", "is_rumor", "article_has_numbers", "article_mentions_percent"]
NUMERIC_COLUMNS = ["sentiment", "confidence", "magnitude", "market_tone", "surprise_direction", "article_text_length"]
TEXT_COLUMNS = ["published_at", "source_domain", "id", "llm_error"]
TICKER_DAILY_COLUMNS = [
    "time",
    "ticker",
    "llm_sentiment_raw",
    "llm_confidence",
    "llm_sentiment_conf_weighted",
    "llm_is_forward_looking",
    "llm_magnitude_daily",
    "llm_surprise_daily",
    "llm_is_rumor_daily",
    "llm_is_market_daily",
    "llm_is_stock_daily",
    "evt_insider_buy",
    "evt_insider_sell",
    "evt_contract_win",
    "evt_legal_issue",
    "evt_earnings",
    "llm_related_sentiment_daily",
    "llm_expectation_beats_daily",
    "llm_expectation_misses_daily",
    "llm_new_info_daily",
    "llm_followup_info_daily",
    "llm_official_source_daily",
    "llm_rumor_source_daily",
    "llm_causal_rev_pos_daily",
    "llm_causal_rev_neg_daily",
    "llm_causal_financing_neg_daily",
    "llm_theme_real_estate_daily",
    "llm_theme_banking_daily",
    "llm_theme_regulation_daily",
]
MARKET_DAILY_COLUMNS = [
    "time",
    "daily_market_tone",
    "frac_positive_news",
    "frac_negative_news",
    "uncertainty_index",
    "frac_forward_looking",
    "frac_earnings_news",
    "frac_macro_news",
    "avg_magnitude",
    "event_diversity",
    "avg_surprise",
    "frac_rumor",
    "frac_market_scope",
    "frac_expectation_beats",
    "frac_expectation_misses",
    "frac_new_information",
    "frac_official_source",
    "frac_rumor_source",
    "frac_regulation_theme",
    "frac_real_estate_theme",
    "frac_banking_theme",
    "frac_causal_financing_negative",
    "sector_banking_tone",
    "sector_realestate_tone",
    "sector_tech_tone",
]


def _normalize_enum_series(series: pd.Series, allowed: set[str]) -> pd.Series:
    values = series.astype("string").str.strip().str.lower()
    return values.where(values.isin(allowed))


def _normalize_bool_series(series: pd.Series) -> pd.Series:
    return series.map({True: 1.0, False: 0.0}).astype("float64")


def _parse_event_time_type(value: object) -> str:
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return "unknown"
    if getattr(ts, "tzinfo", None) is not None:
        ts = ts.tz_convert("Asia/Ho_Chi_Minh")
    else:
        ts = ts.tz_localize("Asia/Ho_Chi_Minh")
    minute_of_day = ts.hour * 60 + ts.minute
    if minute_of_day < VN_MARKET_OPEN_MINUTE:
        return "pre_market"
    if minute_of_day <= VN_MARKET_CLOSE_MINUTE:
        return "intraday"
    return "post_market"


def _ensure_cache_schema(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for column in LIST_COLUMNS:
        if column not in out.columns:
            out[column] = [[] for _ in range(len(out))]
        else:
            out[column] = out[column].map(lambda value: value if isinstance(value, list) else [])
    for column in TEXT_COLUMNS:
        if column not in out.columns:
            out[column] = None
    for column in ENUM_COLUMNS:
        if column not in out.columns:
            out[column] = None
    for column in BOOL_COLUMNS:
        if column not in out.columns:
            out[column] = np.nan
    for column in NUMERIC_COLUMNS:
        if column not in out.columns:
            out[column] = np.nan
    if "time" in out.columns:
        out["time"] = pd.to_datetime(out["time"], errors="coerce")
    for column in NUMERIC_COLUMNS:
        out[column] = pd.to_numeric(out[column], errors="coerce")
    for column in BOOL_COLUMNS:
        out[column] = _normalize_bool_series(out[column])
    out["event_type"] = _normalize_enum_series(out["event_type"], EVENT_TYPES)
    out["impact_scope"] = _normalize_enum_series(out["impact_scope"], {"stock", "sector", "market"})
    out["expectation_alignment"] = _normalize_enum_series(out["expectation_alignment"], EXPECTATION_ALIGNMENTS)
    out["information_novelty"] = _normalize_enum_series(out["information_novelty"], INFORMATION_NOVELTIES)
    out["macro_theme"] = _normalize_enum_series(out["macro_theme"], MACRO_THEMES)
    out["source_authority"] = _normalize_enum_series(out["source_authority"], SOURCE_AUTHORITIES)
    out["causal_impact_label"] = _normalize_enum_series(out["causal_impact_label"], CAUSAL_IMPACT_LABELS)
    if "event_time_type" in out.columns:
        out["event_time_type"] = _normalize_enum_series(out["event_time_type"], {"pre_market", "intraday", "post_market", "unknown"})
        out["event_time_type"] = out["event_time_type"].where(
            out["event_time_type"].notna(),
            out["published_at"].map(_parse_event_time_type),
        )
    else:
        out["event_time_type"] = out["published_at"].map(_parse_event_time_type)
    if "source_domain" in out.columns:
        out["source_domain"] = out["source_domain"].astype("string").str.strip().str.lower().replace({"nan": pd.NA, "none": pd.NA})
    return out


def _load_llm_cache(date_from: str, date_to: str) -> pd.DataFrame:
    files = _iter_cache_files(date_from, date_to)

    rows = []
    for p in files:
        rows.extend(_load_cache_file_rows(p))

    if not rows:
        return pd.DataFrame(columns=[
            "time", "id", "tickers", "related_tickers", "sentiment", "confidence",
            "event_type", "magnitude", "is_forward_looking", "market_tone",
            "is_rumor", "surprise_direction", "impact_scope", "named_persons",
            "expectation_alignment", "information_novelty", "macro_theme",
            "source_authority", "causal_impact_label", "published_at",
            "source_domain", "event_time_type", "article_text_length",
            "article_has_numbers", "article_mentions_percent",
        ])

    return _ensure_cache_schema(pd.DataFrame(rows))


def _iter_cache_files(date_from: str, date_to: str) -> list[Path]:
    files = sorted(p for p in CACHE_DIR.glob("*.jsonl") if len(p.stem) == 10)
    if date_from:
        files = [p for p in files if p.stem >= date_from]
    if date_to:
        files = [p for p in files if p.stem <= date_to]
    return files


def _load_cache_file_rows(path: Path) -> list[dict[str, object]]:
    date = pd.to_datetime(path.stem)
    rows: list[dict[str, object]] = []
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            rows.append(
                {
                    "time": date,
                    "id": obj.get("id"),
                    "tickers": obj.get("tickers") if isinstance(obj.get("tickers"), list) else [],
                    "related_tickers": obj.get("related_tickers") if isinstance(obj.get("related_tickers"), list) else [],
                    "sentiment": obj.get("sentiment"),
                    "confidence": obj.get("confidence"),
                    "event_type": obj.get("event_type"),
                    "magnitude": obj.get("magnitude"),
                    "is_forward_looking": obj.get("is_forward_looking"),
                    "market_tone": obj.get("market_tone"),
                    "is_rumor": obj.get("is_rumor"),
                    "surprise_direction": obj.get("surprise_direction"),
                    "impact_scope": obj.get("impact_scope"),
                    "named_persons": obj.get("named_persons") if isinstance(obj.get("named_persons"), list) else [],
                    "expectation_alignment": obj.get("expectation_alignment"),
                    "information_novelty": obj.get("information_novelty"),
                    "macro_theme": obj.get("macro_theme"),
                    "source_authority": obj.get("source_authority"),
                    "causal_impact_label": obj.get("causal_impact_label"),
                    "published_at": obj.get("published_at"),
                    "source_domain": obj.get("source_domain"),
                    "event_time_type": obj.get("event_time_type"),
                    "article_text_length": obj.get("article_text_length"),
                    "article_has_numbers": obj.get("article_has_numbers"),
                    "article_mentions_percent": obj.get("article_mentions_percent"),
                }
            )
    return rows


def _load_grid() -> pd.DataFrame:
    grid = pd.read_parquet(GRID_PATH, columns=["time", "ticker"]).drop_duplicates()
    grid["time"] = pd.to_datetime(grid["time"])
    return grid.sort_values(["time", "ticker"]).reset_index(drop=True)


def _build_ticker_day(df: pd.DataFrame, grid: pd.DataFrame) -> pd.DataFrame:
    daily = _build_ticker_day_daily(df)
    return _finalize_ticker_day(daily, grid)


def _empty_ticker_day_daily() -> pd.DataFrame:
    return pd.DataFrame(columns=TICKER_DAILY_COLUMNS)


def _build_ticker_day_daily(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return _empty_ticker_day_daily()
    x = df.explode("tickers").rename(columns={"tickers": "ticker"})
    x["ticker"] = x["ticker"].astype(str).str.strip().str.upper()
    x = x[x["ticker"].str.len() > 0].copy()
    if x.empty:
        return _empty_ticker_day_daily()

    x["sent_conf"] = x["sentiment"].fillna(0) * x["confidence"].fillna(0)
    x["sent_weighted"] = np.where(
        x["confidence"].fillna(0) > 0,
        x["sent_conf"] / x["confidence"].fillna(1),
        0.0,
    )
    x["evt_insider_buy"] = (x["event_type"] == "insider_buy").astype(float)
    x["evt_insider_sell"] = (x["event_type"] == "insider_sell").astype(float)
    x["evt_contract_win"] = (x["event_type"] == "contract_win").astype(float)
    x["evt_legal_issue"] = (x["event_type"] == "legal_issue").astype(float)
    x["evt_earnings"] = x["event_type"].isin(EARNINGS_TYPES).astype(float)
    x["is_market_news"] = (x["impact_scope"] == "market").astype(float)
    x["is_stock_news"] = (x["impact_scope"] == "stock").astype(float)
    x["exp_beats"] = (x["expectation_alignment"] == "beats").astype(float)
    x["exp_misses"] = (x["expectation_alignment"] == "misses").astype(float)
    x["novel_new"] = (x["information_novelty"] == "new").astype(float)
    x["novel_followup"] = (x["information_novelty"] == "follow_up").astype(float)
    x["source_official"] = (x["source_authority"] == "official").astype(float)
    x["source_rumor"] = (x["source_authority"] == "rumor_source").astype(float)
    x["causal_rev_pos"] = (x["causal_impact_label"] == "revenue_positive").astype(float)
    x["causal_rev_neg"] = (x["causal_impact_label"] == "revenue_negative").astype(float)
    x["causal_financing_neg"] = (x["causal_impact_label"] == "financing_negative").astype(float)
    x["theme_real_estate"] = (x["macro_theme"] == "real_estate").astype(float)
    x["theme_banking"] = (x["macro_theme"] == "banking").astype(float)
    x["theme_regulation"] = (x["macro_theme"] == "regulation").astype(float)
    x["surprise"] = x["surprise_direction"].fillna(0)
    x["rumor"] = x["is_rumor"].fillna(0)

    daily = (
        x.groupby(["time", "ticker"], as_index=False)
        .agg(
            llm_sentiment_raw=("sentiment", "mean"),
            llm_confidence=("confidence", "max"),
            llm_sentiment_conf_weighted=("sent_weighted", "mean"),
            llm_is_forward_looking=("is_forward_looking", "mean"),
            llm_magnitude_daily=("magnitude", "mean"),
            llm_surprise_daily=("surprise", "mean"),
            llm_is_rumor_daily=("rumor", "mean"),
            llm_is_market_daily=("is_market_news", "mean"),
            llm_is_stock_daily=("is_stock_news", "mean"),
            evt_insider_buy=("evt_insider_buy", "sum"),
            evt_insider_sell=("evt_insider_sell", "sum"),
            evt_contract_win=("evt_contract_win", "sum"),
            evt_legal_issue=("evt_legal_issue", "sum"),
            evt_earnings=("evt_earnings", "sum"),
            llm_expectation_beats_daily=("exp_beats", "sum"),
            llm_expectation_misses_daily=("exp_misses", "sum"),
            llm_new_info_daily=("novel_new", "sum"),
            llm_followup_info_daily=("novel_followup", "sum"),
            llm_official_source_daily=("source_official", "sum"),
            llm_rumor_source_daily=("source_rumor", "sum"),
            llm_causal_rev_pos_daily=("causal_rev_pos", "sum"),
            llm_causal_rev_neg_daily=("causal_rev_neg", "sum"),
            llm_causal_financing_neg_daily=("causal_financing_neg", "sum"),
            llm_theme_real_estate_daily=("theme_real_estate", "sum"),
            llm_theme_banking_daily=("theme_banking", "sum"),
            llm_theme_regulation_daily=("theme_regulation", "sum"),
        )
    )

    rel_daily = pd.DataFrame(columns=["time", "ticker", "llm_related_sentiment_daily"])
    if "related_tickers" in df.columns:
        rel = df[["time", "related_tickers", "sentiment", "confidence"]].copy()
        rel = rel.explode("related_tickers").rename(columns={"related_tickers": "ticker"})
        rel["ticker"] = rel["ticker"].astype(str).str.strip().str.upper()
        rel = rel[rel["ticker"].str.len() > 0].copy()
        if not rel.empty:
            rel["sent_conf"] = rel["sentiment"].fillna(0) * rel["confidence"].fillna(0)
            rel["sent_weighted"] = np.where(
                rel["confidence"].fillna(0) > 0,
                rel["sent_conf"] / rel["confidence"].fillna(1),
                0.0,
            )
            rel_daily = rel.groupby(["time", "ticker"], as_index=False).agg(
                llm_related_sentiment_daily=("sent_weighted", "mean"),
            )
    daily = daily.merge(rel_daily, on=["time", "ticker"], how="left")
    return daily.reindex(columns=TICKER_DAILY_COLUMNS, fill_value=0.0)


def _finalize_ticker_day(daily: pd.DataFrame, grid: pd.DataFrame) -> pd.DataFrame:
    ZERO_COLS = [
        "llm_sentiment_raw", "llm_confidence", "llm_sentiment_conf_weighted",
        "llm_sentiment_5d", "llm_sentiment_30d",
        "llm_insider_buy_5d", "llm_insider_sell_5d", "llm_contract_win_5d",
        "llm_legal_issue_5d", "llm_earnings_event_5d",
        "llm_is_forward_looking", "llm_magnitude_5d",
        "llm_surprise_5d", "llm_is_rumor_5d",
        "llm_related_sentiment_5d",
        "llm_market_news_5d", "llm_stock_news_5d",
        "llm_expectation_beats_5d", "llm_expectation_misses_5d",
        "llm_new_info_5d", "llm_followup_info_5d",
        "llm_official_source_5d", "llm_rumor_source_5d",
        "llm_causal_rev_pos_5d", "llm_causal_rev_neg_5d", "llm_causal_financing_neg_5d",
        "llm_theme_real_estate_5d", "llm_theme_banking_5d", "llm_theme_regulation_5d",
    ]
    if daily.empty:
        out = grid.copy()
        for c in ZERO_COLS:
            out[c] = 0.0
        return out

    out = grid.merge(daily, on=["time", "ticker"], how="left")
    daily_cols = [
        "llm_sentiment_raw", "llm_confidence", "llm_sentiment_conf_weighted",
        "llm_is_forward_looking", "llm_magnitude_daily", "llm_surprise_daily",
        "llm_is_rumor_daily", "llm_is_market_daily", "llm_is_stock_daily",
        "evt_insider_buy", "evt_insider_sell", "evt_contract_win", "evt_legal_issue", "evt_earnings",
        "llm_related_sentiment_daily",
        "llm_expectation_beats_daily", "llm_expectation_misses_daily",
        "llm_new_info_daily", "llm_followup_info_daily",
        "llm_official_source_daily", "llm_rumor_source_daily",
        "llm_causal_rev_pos_daily", "llm_causal_rev_neg_daily", "llm_causal_financing_neg_daily",
        "llm_theme_real_estate_daily", "llm_theme_banking_daily", "llm_theme_regulation_daily",
    ]
    for c in daily_cols:
        out[c] = out[c].fillna(0.0)

    grp = out.groupby("ticker", group_keys=False)
    out["llm_sentiment_5d"] = grp["llm_sentiment_conf_weighted"].transform(lambda s: s.rolling(5, min_periods=1).sum())
    out["llm_sentiment_30d"] = grp["llm_sentiment_conf_weighted"].transform(lambda s: s.rolling(30, min_periods=1).sum())
    out["llm_insider_buy_5d"] = grp["evt_insider_buy"].transform(lambda s: s.rolling(5, min_periods=1).sum())
    out["llm_insider_sell_5d"] = grp["evt_insider_sell"].transform(lambda s: s.rolling(5, min_periods=1).sum())
    out["llm_contract_win_5d"] = grp["evt_contract_win"].transform(lambda s: s.rolling(5, min_periods=1).sum())
    out["llm_legal_issue_5d"] = grp["evt_legal_issue"].transform(lambda s: s.rolling(5, min_periods=1).sum())
    out["llm_earnings_event_5d"] = grp["evt_earnings"].transform(lambda s: s.rolling(5, min_periods=1).sum())
    out["llm_magnitude_5d"] = grp["llm_magnitude_daily"].transform(lambda s: s.rolling(5, min_periods=1).mean())
    out["llm_surprise_5d"] = grp["llm_surprise_daily"].transform(lambda s: s.rolling(5, min_periods=1).sum())
    out["llm_is_rumor_5d"] = grp["llm_is_rumor_daily"].transform(lambda s: s.rolling(5, min_periods=1).mean())
    out["llm_related_sentiment_5d"] = grp["llm_related_sentiment_daily"].transform(lambda s: s.rolling(5, min_periods=1).sum())
    out["llm_market_news_5d"] = grp["llm_is_market_daily"].transform(lambda s: s.rolling(5, min_periods=1).sum())
    out["llm_stock_news_5d"] = grp["llm_is_stock_daily"].transform(lambda s: s.rolling(5, min_periods=1).sum())
    out["llm_expectation_beats_5d"] = grp["llm_expectation_beats_daily"].transform(lambda s: s.rolling(5, min_periods=1).sum())
    out["llm_expectation_misses_5d"] = grp["llm_expectation_misses_daily"].transform(lambda s: s.rolling(5, min_periods=1).sum())
    out["llm_new_info_5d"] = grp["llm_new_info_daily"].transform(lambda s: s.rolling(5, min_periods=1).sum())
    out["llm_followup_info_5d"] = grp["llm_followup_info_daily"].transform(lambda s: s.rolling(5, min_periods=1).sum())
    out["llm_official_source_5d"] = grp["llm_official_source_daily"].transform(lambda s: s.rolling(5, min_periods=1).sum())
    out["llm_rumor_source_5d"] = grp["llm_rumor_source_daily"].transform(lambda s: s.rolling(5, min_periods=1).sum())
    out["llm_causal_rev_pos_5d"] = grp["llm_causal_rev_pos_daily"].transform(lambda s: s.rolling(5, min_periods=1).sum())
    out["llm_causal_rev_neg_5d"] = grp["llm_causal_rev_neg_daily"].transform(lambda s: s.rolling(5, min_periods=1).sum())
    out["llm_causal_financing_neg_5d"] = grp["llm_causal_financing_neg_daily"].transform(lambda s: s.rolling(5, min_periods=1).sum())
    out["llm_theme_real_estate_5d"] = grp["llm_theme_real_estate_daily"].transform(lambda s: s.rolling(5, min_periods=1).sum())
    out["llm_theme_banking_5d"] = grp["llm_theme_banking_daily"].transform(lambda s: s.rolling(5, min_periods=1).sum())
    out["llm_theme_regulation_5d"] = grp["llm_theme_regulation_daily"].transform(lambda s: s.rolling(5, min_periods=1).sum())

    keep = [
        "time", "ticker",
        "llm_sentiment_raw",
        "llm_confidence",
        "llm_sentiment_conf_weighted",
        "llm_sentiment_5d",
        "llm_sentiment_30d",
        "llm_insider_buy_5d",
        "llm_insider_sell_5d",
        "llm_contract_win_5d",
        "llm_legal_issue_5d",
        "llm_earnings_event_5d",
        "llm_is_forward_looking",
        "llm_magnitude_5d",
        "llm_surprise_5d",
        "llm_is_rumor_5d",
        "llm_related_sentiment_5d",
        "llm_market_news_5d",
        "llm_stock_news_5d",
        "llm_expectation_beats_5d",
        "llm_expectation_misses_5d",
        "llm_new_info_5d",
        "llm_followup_info_5d",
        "llm_official_source_5d",
        "llm_rumor_source_5d",
        "llm_causal_rev_pos_5d",
        "llm_causal_rev_neg_5d",
        "llm_causal_financing_neg_5d",
        "llm_theme_real_estate_5d",
        "llm_theme_banking_5d",
        "llm_theme_regulation_5d",
    ]
    out = out[keep].copy()
    for c in keep[2:]:
        out[c] = out[c].fillna(0.0)
    return out


def _sector_sets() -> tuple[set[str], set[str], set[str]]:
    if not SECTOR_PATH.exists():
        return set(), set(), set()
    s = pd.read_parquet(SECTOR_PATH)

    def _to_set(mask: pd.Series) -> set[str]:
        return set(s.loc[mask, "symbol"].astype(str).str.upper())

    s2 = s["icb_name2"].astype(str).str.lower()
    s3 = s["icb_name3"].astype(str).str.lower()
    s4 = s["icb_name4"].astype(str).str.lower()

    bank = _to_set(s2.str.contains("ngân hàng", na=False) | s2.str.contains("ngan hang", na=False))
    real_estate = _to_set(
        s2.str.contains("bất động sản", na=False)
        | s2.str.contains("bat dong san", na=False)
        | s3.str.contains("bất động sản", na=False)
        | s3.str.contains("bat dong san", na=False)
    )
    tech = _to_set(
        s2.str.contains("công nghệ", na=False)
        | s2.str.contains("cong nghe", na=False)
        | s3.str.contains("phần mềm", na=False)
        | s3.str.contains("phan mem", na=False)
        | s4.str.contains("công nghệ", na=False)
        | s4.str.contains("cong nghe", na=False)
    )
    return bank, real_estate, tech


def _build_market_daily(df: pd.DataFrame, grid: pd.DataFrame) -> pd.DataFrame:
    daily = _build_market_daily_inputs(df)
    return _finalize_market_daily(daily, grid)


def _empty_market_daily_inputs() -> pd.DataFrame:
    return pd.DataFrame(columns=MARKET_DAILY_COLUMNS)


def _build_market_daily_inputs(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return _empty_market_daily_inputs()

    d = df.copy()
    d["is_pos"] = (d["sentiment"] == 1).astype(float)
    d["is_neg"] = (d["sentiment"] == -1).astype(float)
    d["is_uncertain"] = (d["confidence"] == 0).astype(float)
    d["is_earnings"] = d["event_type"].isin(EARNINGS_TYPES).astype(float)
    d["is_macro"] = d["event_type"].isin(MACRO_TYPES).astype(float)
    d["surprise"] = d["surprise_direction"].fillna(0) if "surprise_direction" in d.columns else 0.0
    d["rumor"] = d["is_rumor"].fillna(0) if "is_rumor" in d.columns else 0.0
    d["is_market_scope"] = (d["impact_scope"] == "market").astype(float) if "impact_scope" in d.columns else 0.0
    d["expectation_beats"] = (d["expectation_alignment"] == "beats").astype(float)
    d["expectation_misses"] = (d["expectation_alignment"] == "misses").astype(float)
    d["novel_new"] = (d["information_novelty"] == "new").astype(float)
    d["source_official"] = (d["source_authority"] == "official").astype(float)
    d["source_rumor"] = (d["source_authority"] == "rumor_source").astype(float)
    d["macro_regulation"] = (d["macro_theme"] == "regulation").astype(float)
    d["macro_real_estate"] = (d["macro_theme"] == "real_estate").astype(float)
    d["macro_banking"] = (d["macro_theme"] == "banking").astype(float)
    d["causal_financing_negative"] = (d["causal_impact_label"] == "financing_negative").astype(float)

    daily = (
        d.groupby("time", as_index=False)
        .agg(
            daily_market_tone=("market_tone", "mean"),
            frac_positive_news=("is_pos", "mean"),
            frac_negative_news=("is_neg", "mean"),
            uncertainty_index=("is_uncertain", "mean"),
            frac_forward_looking=("is_forward_looking", "mean"),
            frac_earnings_news=("is_earnings", "mean"),
            frac_macro_news=("is_macro", "mean"),
            avg_magnitude=("magnitude", "mean"),
            event_diversity=("event_type", lambda s: float(s.dropna().nunique())),
            avg_surprise=("surprise", "mean"),
            frac_rumor=("rumor", "mean"),
            frac_market_scope=("is_market_scope", "mean"),
            frac_expectation_beats=("expectation_beats", "mean"),
            frac_expectation_misses=("expectation_misses", "mean"),
            frac_new_information=("novel_new", "mean"),
            frac_official_source=("source_official", "mean"),
            frac_rumor_source=("source_rumor", "mean"),
            frac_regulation_theme=("macro_regulation", "mean"),
            frac_real_estate_theme=("macro_real_estate", "mean"),
            frac_banking_theme=("macro_banking", "mean"),
            frac_causal_financing_negative=("causal_financing_negative", "mean"),
        )
    )

    bank, real_estate, tech = _sector_sets()
    x = d.explode("tickers").rename(columns={"tickers": "ticker"})
    x["ticker"] = x["ticker"].astype(str).str.upper()
    x = x[x["ticker"].str.len() > 0].copy()

    def _sector_mean(tickers: set[str], col_name: str) -> pd.DataFrame:
        if not tickers or x.empty:
            return pd.DataFrame({"time": [], col_name: []})
        m = x[x["ticker"].isin(tickers)].groupby("time", as_index=False)["sentiment"].mean()
        return m.rename(columns={"sentiment": col_name})

    sec_bank = _sector_mean(bank, "sector_banking_tone")
    sec_re = _sector_mean(real_estate, "sector_realestate_tone")
    sec_tech = _sector_mean(tech, "sector_tech_tone")

    out = daily.merge(sec_bank, on="time", how="left")
    out = out.merge(sec_re, on="time", how="left")
    out = out.merge(sec_tech, on="time", how="left")
    return out.reindex(columns=MARKET_DAILY_COLUMNS, fill_value=0.0)


def _finalize_market_daily(daily: pd.DataFrame, grid: pd.DataFrame) -> pd.DataFrame:
    days = pd.DataFrame({"time": sorted(grid["time"].unique())})
    if daily.empty:
        out = days.copy()
        for c in [
            "daily_market_tone", "daily_market_tone_5d", "daily_market_tone_30d", "market_tone_momentum",
            "frac_positive_news", "frac_negative_news", "uncertainty_index", "frac_forward_looking",
            "frac_earnings_news", "frac_macro_news", "sector_banking_tone", "sector_realestate_tone",
            "sector_tech_tone", "event_diversity", "avg_magnitude",
            "frac_expectation_beats", "frac_expectation_misses", "frac_new_information",
            "frac_official_source", "frac_rumor_source", "frac_regulation_theme",
            "frac_real_estate_theme", "frac_banking_theme", "frac_causal_financing_negative",
        ]:
            out[c] = 0.0
        return out

    out = days.merge(daily, on="time", how="left")

    out = out.sort_values("time").reset_index(drop=True)
    for c in out.columns:
        if c == "time":
            continue
        out[c] = out[c].ffill().fillna(0.0)

    out["daily_market_tone_5d"] = out["daily_market_tone"].rolling(5, min_periods=1).mean()
    out["daily_market_tone_30d"] = out["daily_market_tone"].rolling(30, min_periods=1).mean()
    out["market_tone_momentum"] = out["daily_market_tone_5d"] - out["daily_market_tone_30d"]
    return out


def _stage_file_path(stage_dir: Path, day: str) -> Path:
    return stage_dir / f"{day}.parquet"


def _stage_is_current(stage_path: Path, cache_path: Path) -> bool:
    return stage_path.exists() and stage_path.stat().st_mtime >= cache_path.stat().st_mtime


def _concat_stage_frames(stage_dir: Path, files: list[Path], expected_columns: list[str]) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for cache_path in files:
        stage_path = _stage_file_path(stage_dir, cache_path.stem)
        if not stage_path.exists():
            continue
        frames.append(pd.read_parquet(stage_path))
    if not frames:
        return pd.DataFrame(columns=expected_columns)
    return pd.concat(frames, ignore_index=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date-from", type=str, default="")
    ap.add_argument("--date-to", type=str, default="")
    args = ap.parse_args()

    FEATURE_DIR.mkdir(parents=True, exist_ok=True)
    STAGE_TICKER_DAILY_DIR.mkdir(parents=True, exist_ok=True)
    STAGE_MARKET_DAILY_DIR.mkdir(parents=True, exist_ok=True)
    tracker = JobStatusTracker(
        "build_llm_news_features",
        artifacts={
            "ticker_output": OUT_TICKER,
            "market_output": OUT_MARKET,
            "ticker_stage_dir": STAGE_TICKER_DAILY_DIR,
            "market_stage_dir": STAGE_MARKET_DAILY_DIR,
        },
    )
    grid = _load_grid()
    files = _iter_cache_files(args.date_from, args.date_to)
    if not files:
        tracker.write(
            status="complete",
            phase="idle",
            progress={"cache_files": 0, "reason": "no_matching_cache_files"},
        )
        print("No input files matched date filters.")
        return

    tracker.write(
        status="running",
        phase="stage",
        progress={
            "cache_files": len(files),
            "completed_days": [],
            "current_day": None,
            "staged_days": 0,
            "skipped_stage_days": 0,
        },
    )

    staged_days = 0
    skipped_stage_days = 0
    completed_days: list[str] = []
    total_stage_rows = 0
    for index, cache_path in enumerate(files, start=1):
        ticker_stage_path = _stage_file_path(STAGE_TICKER_DAILY_DIR, cache_path.stem)
        market_stage_path = _stage_file_path(STAGE_MARKET_DAILY_DIR, cache_path.stem)
        if _stage_is_current(ticker_stage_path, cache_path) and _stage_is_current(market_stage_path, cache_path):
            skipped_stage_days += 1
            completed_days.append(cache_path.stem)
            tracker.write(
                status="running",
                phase="stage",
                progress={
                    "cache_files": len(files),
                    "completed_days": completed_days,
                    "current_day": None,
                    "staged_days": staged_days,
                    "skipped_stage_days": skipped_stage_days,
                    "current_index": index,
                },
            )
            continue

        llm_day = _ensure_cache_schema(pd.DataFrame(_load_cache_file_rows(cache_path)))
        ticker_daily = _build_ticker_day_daily(llm_day)
        market_daily = _build_market_daily_inputs(llm_day)
        atomic_write_parquet(ticker_daily, ticker_stage_path)
        atomic_write_parquet(market_daily, market_stage_path)
        staged_days += 1
        completed_days.append(cache_path.stem)
        total_stage_rows += int(len(llm_day))
        print(
            f"Staged LLM day {index}/{len(files)}: {cache_path.stem} "
            f"cache_rows={len(llm_day):,} ticker_rows={len(ticker_daily):,} market_rows={len(market_daily):,}",
            flush=True,
        )
        tracker.write(
            status="running",
            phase="stage",
            progress={
                "cache_files": len(files),
                "completed_days": completed_days,
                "current_day": cache_path.stem,
                "staged_days": staged_days,
                "skipped_stage_days": skipped_stage_days,
                "current_index": index,
                "stage_cache_rows": total_stage_rows,
            },
        )

    tracker.write(
        status="running",
        phase="finalize",
        progress={
            "cache_files": len(files),
            "completed_days": completed_days,
            "current_day": None,
            "staged_days": staged_days,
            "skipped_stage_days": skipped_stage_days,
        },
    )
    ticker_daily = _concat_stage_frames(STAGE_TICKER_DAILY_DIR, files, TICKER_DAILY_COLUMNS)
    market_daily = _concat_stage_frames(STAGE_MARKET_DAILY_DIR, files, MARKET_DAILY_COLUMNS)
    ticker_day = _finalize_ticker_day(ticker_daily, grid)
    market_day = _finalize_market_daily(market_daily, grid)

    atomic_write_parquet(ticker_day, OUT_TICKER)
    atomic_write_parquet(market_day, OUT_MARKET)

    tracker.write(
        status="complete",
        phase="complete",
        progress={
            "cache_files": len(files),
            "completed_days": completed_days,
            "staged_days": staged_days,
            "skipped_stage_days": skipped_stage_days,
            "ticker_day_rows": int(len(ticker_day)),
            "market_day_rows": int(len(market_day)),
        },
        throughput={
            "stage_days_per_run": staged_days,
            "cache_files_reused": skipped_stage_days,
        },
    )

    print(f"LLM cache files: {len(files):,}")
    print(f"Ticker-day output: {len(ticker_day):,} rows -> {OUT_TICKER}")
    print(f"Market-daily output: {len(market_day):,} rows -> {OUT_MARKET}")
    print("NaN check (market):", int(market_day.drop(columns=["time"]).isna().sum().sum()))


if __name__ == "__main__":
    main()
