"""
H96: Rolling/Lagged News Sentiment Features

Problem: H89 keyword news sentiment is too sparse (0.8% of day-ticker pairs have news).
Signal fires on isolated days → high noise, low consistency.

Solution: Aggregate daily sentiment over rolling windows to capture:
- Sustained positive sentiment (more reliable than single-day spikes)
- Sentiment momentum (improving vs deteriorating news flow)
- Smoother signal with less daily noise

Output: data/features/xs_news_sentiment_rolling.parquet
Columns: time, ticker, sentiment_rolling_5d, sentiment_rolling_30d,
         article_count_rolling_5d, article_count_rolling_30d,
         sentiment_momentum_5d (5d - 30d)

Usage:
    conda run -n stocks python data_tools/build_rolling_news_features.py
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import pandas as pd
import numpy as np
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_PATH  = REPO_ROOT / "data" / "features" / "xs_news_sentiment_rolling.parquet"
SENT_PATH = REPO_ROOT / "data" / "features" / "xs_news_sentiment_daily.parquet"


def build_rolling_features():
    print("Loading existing news sentiment data...")
    df = pd.read_parquet(SENT_PATH)
    df["time"] = pd.to_datetime(df["time"])
    df = df.sort_values(["ticker", "time"]).reset_index(drop=True)

    print(f"  Loaded {len(df):,} records, {df['ticker'].nunique()} tickers, "
          f"{df['time'].nunique()} unique days")
    print(f"  Date range: {df['time'].min().date()} to {df['time'].max().date()}")

    # Create a complete ticker × time grid (all trading days)
    # Get all trading days from the sentiment data across ALL tickers
    all_days = df["time"].unique()
    all_tickers = df["ticker"].unique()
    print(f"  Building complete grid: {len(all_tickers)} tickers × {len(all_days)} days")

    # For rolling aggregation we need a complete daily index per ticker
    # Start from each ticker's first news date and forward-fill the sentiment
    # (days without news = 0 sentiment = neutral)
    results = []

    for ticker, grp in df.groupby("ticker"):
        grp = grp.sort_values("time")

        # Resample to daily: on news days use the sentiment values,
        # on non-news days forward-fill with 0 (neutral, no signal)
        start = grp["time"].min()
        end = grp["time"].max()
        daily_idx = pd.date_range(start=start, end=end, freq="B")  # business days

        daily_df = pd.DataFrame({"time": daily_idx})
        daily_df["ticker"] = ticker

        # Merge sentiment data
        merged = daily_df.merge(
            grp[["time", "sentiment_score", "article_count", "sentiment_cs_z", "positive_ratio"]],
            on="time",
            how="left"
        )

        # Fill NaN (no news) with 0 for sentiment score and 0 for article count
        # positive_ratio fills with 0.5 (neutral)
        merged["sentiment_score"] = merged["sentiment_score"].fillna(0)
        merged["article_count"] = merged["article_count"].fillna(0)
        merged["sentiment_cs_z"] = merged["sentiment_cs_z"].fillna(0)
        merged["positive_ratio"] = merged["positive_ratio"].fillna(0.5)

        # Rolling features (backward-looking, no look-ahead)
        # 5-day rolling sum of sentiment score
        merged["sentiment_rolling_5d"] = (
            merged["sentiment_score"]
            .rolling(window=5, min_periods=1)
            .sum()
            .shift(1)  # exclude current day to avoid look-ahead
        )

        # 30-day rolling sum of sentiment score
        merged["sentiment_rolling_30d"] = (
            merged["sentiment_score"]
            .rolling(window=30, min_periods=1)
            .sum()
            .shift(1)
        )

        # Article count rolling sums (news volume)
        merged["article_count_rolling_5d"] = (
            merged["article_count"]
            .rolling(window=5, min_periods=1)
            .sum()
            .shift(1)
        )

        merged["article_count_rolling_30d"] = (
            merged["article_count"]
            .rolling(window=30, min_periods=1)
            .sum()
            .shift(1)
        )

        # Sentiment momentum: short-term minus medium-term
        # Positive = improving sentiment, Negative = deteriorating
        merged["sentiment_momentum_5d"] = (
            merged["sentiment_rolling_5d"] - merged["sentiment_rolling_30d"] / 6
        )

        # Cross-sectional z-score of rolling sentiment (per day, across tickers)
        # This normalizes so that +1 means top-decile recent sentiment that day
        def cs_zscore(s):
            std = s.std()
            if std < 1e-9:
                return pd.Series(0.0, index=s.index)
            return (s - s.mean()) / std

        merged["sentiment_rolling_5d_z"] = merged.groupby("time")["sentiment_rolling_5d"].transform(
            cs_zscore
        )
        merged["sentiment_rolling_30d_z"] = merged.groupby("time")["sentiment_rolling_30d"].transform(
            cs_zscore
        )

        results.append(merged[[
            "time", "ticker",
            "sentiment_rolling_5d", "sentiment_rolling_30d",
            "article_count_rolling_5d", "article_count_rolling_30d",
            "sentiment_momentum_5d",
            "sentiment_rolling_5d_z", "sentiment_rolling_30d_z"
        ]])

    out = pd.concat(results, ignore_index=True)
    out = out.dropna(subset=["sentiment_rolling_5d", "sentiment_rolling_30d"])
    out = out.sort_values(["time", "ticker"]).reset_index(drop=True)

    # Final cross-sectional z on the rolling sentiment (within each day, rank-normalize)
    # This makes it comparable across days regardless of market news volume
    print(f"\nOutput shape: {out.shape}")
    print(f"Date range: {out['time'].min().date()} to {out['time'].max().date()}")
    print(f"Unique tickers: {out['ticker'].nunique()}")

    print("\nRolling sentiment stats (5d):")
    print(out["sentiment_rolling_5d"].describe())
    print("\nRolling sentiment stats (30d):")
    print(out["sentiment_rolling_30d"].describe())

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(OUT_PATH, index=False)
    print(f"\nSaved: {OUT_PATH}")


if __name__ == "__main__":
    build_rolling_features()
