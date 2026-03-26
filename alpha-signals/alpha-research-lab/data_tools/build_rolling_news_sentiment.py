"""
H96: Build rolling news sentiment features to fix sparsity in H89.

Problem: xs_news_sentiment_daily.parquet covers only ~0.8% of (day, ticker) pairs.
Fix: expand to full (trading_day, ticker) grid and compute 5d / 30d rolling windows.

Output: data/features/xs_news_sentiment_rolling.parquet
Columns: time, ticker,
  sentiment_score_5d    -- rolling 5-trading-day sum of sentiment_score
  sentiment_score_30d   -- rolling 30-trading-day sum of sentiment_score
  article_count_5d      -- rolling 5d sum of article_count
  article_count_30d     -- rolling 30d sum of article_count
  positive_ratio_5d     -- rolling 5d mean of positive_ratio (nan-skipping)
  has_news_5d           -- fraction of last 5 days with any article
  has_news_30d          -- fraction of last 30 days with any article

Usage:
    python data_tools/build_rolling_news_sentiment.py
    python data_tools/build_rolling_news_sentiment.py --dry-run
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT   = Path(__file__).resolve().parents[1]
IN_PATH     = REPO_ROOT / "data" / "features" / "xs_news_sentiment_daily.parquet"
STOCK_DIR   = REPO_ROOT / "data" / "stock"
OUT_PATH    = REPO_ROOT / "data" / "features" / "xs_news_sentiment_rolling.parquet"


def get_trading_days() -> pd.DatetimeIndex:
    """Union of all trading dates across all HOSE parquet files."""
    dates = set()
    for fpath in STOCK_DIR.glob("gia_lich_su_*_1D.parquet"):
        try:
            df = pd.read_parquet(fpath, columns=["time"])
            df["time"] = pd.to_datetime(df["time"])
            dates.update(df["time"].dt.normalize().tolist())
        except Exception:
            continue
    return pd.DatetimeIndex(sorted(dates))


def get_known_tickers() -> list[str]:
    tickers = []
    for f in STOCK_DIR.glob("gia_lich_su_*_1D.parquet"):
        sym = f.stem.replace("gia_lich_su_", "").replace("_1D", "")
        tickers.append(sym)
    return sorted(set(tickers))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Process only first 50 tickers for a quick sanity check")
    args = parser.parse_args()

    print("Loading daily sentiment...")
    sent = pd.read_parquet(IN_PATH)
    sent["time"] = pd.to_datetime(sent["time"]).dt.normalize()
    sent = sent[["time", "ticker", "sentiment_score", "article_count", "positive_ratio"]]
    print(f"  Input: {sent.shape[0]:,} rows, {sent['ticker'].nunique()} tickers, "
          f"{sent['time'].min().date()} – {sent['time'].max().date()}")

    print("Building full trading-day grid...")
    trading_days = get_trading_days()
    known_tickers = get_known_tickers()
    if args.dry_run:
        known_tickers = known_tickers[:50]
        print(f"  DRY RUN: {len(known_tickers)} tickers")
    print(f"  Trading days: {len(trading_days)}, tickers: {len(known_tickers)}")

    # Full grid
    grid = pd.MultiIndex.from_product([trading_days, known_tickers],
                                      names=["time", "ticker"])
    grid_df = pd.DataFrame(index=grid).reset_index()
    grid_df["time"] = pd.to_datetime(grid_df["time"])

    # Merge daily sentiment onto the full grid (sparse → dense)
    merged = grid_df.merge(sent, on=["time", "ticker"], how="left")
    # NaN means no news on that (day, ticker) → fill with 0
    merged["sentiment_score"]  = merged["sentiment_score"].fillna(0.0)
    merged["article_count"]    = merged["article_count"].fillna(0.0)
    merged["positive_ratio"]   = merged["positive_ratio"].fillna(0.0)
    merged["has_news"]         = (merged["article_count"] > 0).astype(float)
    merged = merged.sort_values(["ticker", "time"]).reset_index(drop=True)

    print("Computing rolling features per ticker...")
    # Sort by ticker then time so rolling windows are applied correctly per ticker
    merged = merged.sort_values(["ticker", "time"]).reset_index(drop=True)
    grp = merged.groupby("ticker")

    def roll_sum(col, w):
        return grp[col].transform(lambda s: s.rolling(w, min_periods=1).sum())

    def roll_mean(col, w):
        return grp[col].transform(lambda s: s.rolling(w, min_periods=1).mean())

    merged["sentiment_score_5d"]  = roll_sum("sentiment_score", 5)
    merged["sentiment_score_30d"] = roll_sum("sentiment_score", 30)
    merged["article_count_5d"]    = roll_sum("article_count",   5)
    merged["article_count_30d"]   = roll_sum("article_count",   30)
    merged["positive_ratio_5d"]   = roll_mean("positive_ratio", 5)
    merged["has_news_5d"]         = roll_mean("has_news",       5)
    merged["has_news_30d"]        = roll_mean("has_news",       30)
    result = merged

    ROLLING_COLS = [
        "sentiment_score_5d", "sentiment_score_30d",
        "article_count_5d",   "article_count_30d",
        "positive_ratio_5d",  "has_news_5d", "has_news_30d",
    ]
    out = result[["time", "ticker"] + ROLLING_COLS].copy()
    out = out.sort_values(["time", "ticker"]).reset_index(drop=True)

    # Coverage check
    total_rows = len(out)
    nonzero_5d  = (out["article_count_5d"] > 0).sum()
    nonzero_30d = (out["article_count_30d"] > 0).sum()
    print(f"\nCoverage after rolling:")
    print(f"  article_count_5d  > 0: {nonzero_5d:,} / {total_rows:,} = {100*nonzero_5d/total_rows:.1f}%")
    print(f"  article_count_30d > 0: {nonzero_30d:,} / {total_rows:,} = {100*nonzero_30d/total_rows:.1f}%")
    print(f"\nSentiment score 5d distribution:")
    print(out["sentiment_score_5d"].describe())
    print(f"\nSentiment score 30d distribution:")
    print(out["sentiment_score_30d"].describe())

    if not args.dry_run:
        OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        out.to_parquet(OUT_PATH, index=False)
        print(f"\nSaved: {OUT_PATH}  ({out.shape[0]:,} rows)")
    else:
        print("\nDRY RUN: not saving output")


if __name__ == "__main__":
    main()
