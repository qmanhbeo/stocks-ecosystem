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

import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = REPO_ROOT / "data" / "llm_cache"
FEATURE_DIR = REPO_ROOT / "data" / "features"
GRID_PATH = FEATURE_DIR / "xs_barrier_vol_1d_hose_full.parquet"
SECTOR_PATH = FEATURE_DIR / "sector_classification.parquet"

OUT_TICKER = FEATURE_DIR / "xs_llm_news_ticker_day.parquet"
OUT_MARKET = FEATURE_DIR / "xs_llm_news_market_daily.parquet"

EARNINGS_TYPES = {"earnings_beat", "earnings_miss", "earnings_neutral"}
MACRO_TYPES = {"rate_change", "fx_move", "macro_indicator", "policy_positive", "policy_negative"}


def _load_llm_cache(date_from: str, date_to: str) -> pd.DataFrame:
    files = sorted(p for p in CACHE_DIR.glob("*.jsonl") if len(p.stem) == 10)
    if date_from:
        files = [p for p in files if p.stem >= date_from]
    if date_to:
        files = [p for p in files if p.stem <= date_to]

    rows = []
    for p in files:
        date = pd.to_datetime(p.stem)
        with p.open("r", encoding="utf-8", errors="replace") as f:
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
                        "sentiment": obj.get("sentiment"),
                        "confidence": obj.get("confidence"),
                        "event_type": obj.get("event_type"),
                        "magnitude": obj.get("magnitude"),
                        "is_forward_looking": obj.get("is_forward_looking"),
                        "market_tone": obj.get("market_tone"),
                    }
                )

    if not rows:
        return pd.DataFrame(columns=["time", "id", "tickers", "sentiment", "confidence", "event_type", "magnitude", "is_forward_looking", "market_tone"])

    df = pd.DataFrame(rows)

    for c in ["sentiment", "confidence", "magnitude", "market_tone"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["is_forward_looking"] = df["is_forward_looking"].map({True: 1.0, False: 0.0})
    df["event_type"] = df["event_type"].astype(str).str.strip().str.lower().replace({"none": np.nan, "nan": np.nan, "": np.nan})
    return df


def _load_grid() -> pd.DataFrame:
    grid = pd.read_parquet(GRID_PATH, columns=["time", "ticker"]).drop_duplicates()
    grid["time"] = pd.to_datetime(grid["time"])
    return grid.sort_values(["time", "ticker"]).reset_index(drop=True)


def _build_ticker_day(df: pd.DataFrame, grid: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        out = grid.copy()
        for c in [
            "llm_sentiment_raw", "llm_confidence", "llm_sentiment_conf_weighted",
            "llm_sentiment_5d", "llm_sentiment_30d", "llm_insider_buy_5d",
            "llm_insider_sell_5d", "llm_contract_win_5d", "llm_legal_issue_5d",
            "llm_earnings_event_5d", "llm_is_forward_looking", "llm_magnitude_5d",
        ]:
            out[c] = 0.0
        return out

    x = df.explode("tickers").rename(columns={"tickers": "ticker"})
    x["ticker"] = x["ticker"].astype(str).str.strip().str.upper()
    x = x[x["ticker"].str.len() > 0].copy()
    if x.empty:
        return _build_ticker_day(pd.DataFrame(), grid)

    x["sent_conf"] = x["sentiment"] * x["confidence"]
    x["sent_weighted"] = np.where(
        x["confidence"] > 0,
        x["sent_conf"] / x["confidence"],
        0.0,
    )
    x["evt_insider_buy"] = (x["event_type"] == "insider_buy").astype(float)
    x["evt_insider_sell"] = (x["event_type"] == "insider_sell").astype(float)
    x["evt_contract_win"] = (x["event_type"] == "contract_win").astype(float)
    x["evt_legal_issue"] = (x["event_type"] == "legal_issue").astype(float)
    x["evt_earnings"] = x["event_type"].isin(EARNINGS_TYPES).astype(float)

    g = (
        x.groupby(["time", "ticker"], as_index=False)
        .agg(
            llm_sentiment_raw=("sentiment", "mean"),
            llm_confidence=("confidence", "max"),
            llm_sentiment_conf_weighted=("sent_weighted", "mean"),
            llm_is_forward_looking=("is_forward_looking", "mean"),
            llm_magnitude_daily=("magnitude", "mean"),
            evt_insider_buy=("evt_insider_buy", "sum"),
            evt_insider_sell=("evt_insider_sell", "sum"),
            evt_contract_win=("evt_contract_win", "sum"),
            evt_legal_issue=("evt_legal_issue", "sum"),
            evt_earnings=("evt_earnings", "sum"),
        )
    )

    out = grid.merge(g, on=["time", "ticker"], how="left")
    for c in [
        "llm_sentiment_raw", "llm_confidence", "llm_sentiment_conf_weighted",
        "llm_is_forward_looking", "llm_magnitude_daily",
        "evt_insider_buy", "evt_insider_sell", "evt_contract_win", "evt_legal_issue", "evt_earnings",
    ]:
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
    ]
    out = out[keep]
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
    days = pd.DataFrame({"time": sorted(grid["time"].unique())})
    if df.empty:
        out = days.copy()
        for c in [
            "daily_market_tone", "daily_market_tone_5d", "daily_market_tone_30d", "market_tone_momentum",
            "frac_positive_news", "frac_negative_news", "uncertainty_index", "frac_forward_looking",
            "frac_earnings_news", "frac_macro_news", "sector_banking_tone", "sector_realestate_tone",
            "sector_tech_tone", "event_diversity", "avg_magnitude",
        ]:
            out[c] = 0.0
        return out

    d = df.copy()
    d["is_pos"] = (d["sentiment"] == 1).astype(float)
    d["is_neg"] = (d["sentiment"] == -1).astype(float)
    d["is_uncertain"] = (d["confidence"] == 0).astype(float)
    d["is_earnings"] = d["event_type"].isin(EARNINGS_TYPES).astype(float)
    d["is_macro"] = d["event_type"].isin(MACRO_TYPES).astype(float)

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

    out = days.merge(daily, on="time", how="left")
    out = out.merge(sec_bank, on="time", how="left")
    out = out.merge(sec_re, on="time", how="left")
    out = out.merge(sec_tech, on="time", how="left")

    out = out.sort_values("time").reset_index(drop=True)
    for c in out.columns:
        if c == "time":
            continue
        out[c] = out[c].ffill().fillna(0.0)

    out["daily_market_tone_5d"] = out["daily_market_tone"].rolling(5, min_periods=1).mean()
    out["daily_market_tone_30d"] = out["daily_market_tone"].rolling(30, min_periods=1).mean()
    out["market_tone_momentum"] = out["daily_market_tone_5d"] - out["daily_market_tone_30d"]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date-from", type=str, default="")
    ap.add_argument("--date-to", type=str, default="")
    args = ap.parse_args()

    FEATURE_DIR.mkdir(parents=True, exist_ok=True)
    grid = _load_grid()
    llm = _load_llm_cache(args.date_from, args.date_to)

    ticker_day = _build_ticker_day(llm, grid)
    market_day = _build_market_daily(llm, grid)

    ticker_day.to_parquet(OUT_TICKER, index=False)
    market_day.to_parquet(OUT_MARKET, index=False)

    print(f"LLM cache rows: {len(llm):,}")
    print(f"Ticker-day output: {len(ticker_day):,} rows -> {OUT_TICKER}")
    print(f"Market-daily output: {len(market_day):,} rows -> {OUT_MARKET}")
    print("NaN check (market):", int(market_day.drop(columns=["time"]).isna().sum().sum()))


if __name__ == "__main__":
    main()
