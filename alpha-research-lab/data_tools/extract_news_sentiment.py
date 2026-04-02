"""
H89: Extract per-ticker daily news sentiment from cafef JSONL files.

Approach:
- Ticker extraction: parenthetical pattern in titles, e.g. "Hòa Phát (HPG) tăng mạnh"
- Sentiment: keyword-based Vietnamese financial lexicon (no API or model download needed)
- Output: data/features/xs_news_sentiment_daily.parquet
  Columns: time, ticker, sentiment_score, pos_count, neg_count, article_count, positive_ratio

Usage:
    conda run -n stocks python data_tools/extract_news_sentiment.py
    conda run -n stocks python data_tools/extract_news_sentiment.py --start 2020-01-01
    conda run -n stocks python data_tools/extract_news_sentiment.py --dry-run
"""
import sys
import io
import re
import json
import argparse
from pathlib import Path
from path_utils import data_path
from collections import defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import pandas as pd
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
NEWS_DIR  = data_path("news/cafef/raw")
STOCK_DIR = data_path("stock")
OUT_PATH  = data_path("features/xs_news_sentiment_daily.parquet")

# ── Vietnamese financial sentiment lexicon ─────────────────────────────────────
# Positive terms: higher score = more bullish signal
POS_TERMS = [
    "tăng trưởng", "đột phá", "vượt kỳ vọng", "vượt mục tiêu", "cao kỷ lục",
    "lợi nhuận tăng", "doanh thu tăng", "phục hồi mạnh", "tích cực", "khởi sắc",
    "tăng mạnh", "bứt phá", "tốt", "mạnh mẽ", "hiệu quả cao",
    "cổ tức cao", "thưởng cổ phiếu", "mua vào", "kết quả tốt",
    "lãi lớn", "đỉnh cao", "tín hiệu tốt", "kỳ vọng cao",
    "triển vọng tích cực", "tăng", "lãi",
]

# Negative terms
NEG_TERMS = [
    "sụt giảm", "giảm mạnh", "thua lỗ", "lỗ nặng", "khó khăn",
    "tệ", "suy yếu", "suy giảm", "điều chỉnh giảm", "bán tháo",
    "thấp kỷ lục", "lo ngại", "áp lực", "rủi ro cao",
    "nợ xấu", "thoái vốn", "cắt giảm", "đình hoãn", "tạm dừng",
    "vi phạm", "phạt", "kiện tụng", "tranh chấp",
    "giảm lợi nhuận", "doanh thu giảm", "lỗ", "giảm",
]

# Compile regex patterns (longer terms first for greedy matching priority)
POS_TERMS_SORTED = sorted(POS_TERMS, key=len, reverse=True)
NEG_TERMS_SORTED = sorted(NEG_TERMS, key=len, reverse=True)
POS_RE = re.compile("|".join(re.escape(t) for t in POS_TERMS_SORTED), re.IGNORECASE)
NEG_RE = re.compile("|".join(re.escape(t) for t in NEG_TERMS_SORTED), re.IGNORECASE)

# Ticker extraction: UPPERCASE 2-5 chars in parentheses
PAREN_PAT = re.compile(r'\(([A-Z]{2,5})\)')


def load_known_tickers() -> set:
    tickers = set()
    for f in STOCK_DIR.glob("gia_lich_su_*_1D.parquet"):
        sym = f.stem.replace("gia_lich_su_", "").replace("_1D", "")
        tickers.add(sym)
    return tickers


def score_text(text: str) -> tuple[int, int]:
    """Return (pos_count, neg_count) of keyword matches in text."""
    pos = len(POS_RE.findall(text))
    neg = len(NEG_RE.findall(text))
    return pos, neg


def extract_tickers_from_title(title: str, known: set) -> list[str]:
    """Extract ticker symbols from parenthetical mentions in title."""
    found = []
    for m in PAREN_PAT.finditer(title):
        t = m.group(1)
        if t in known:
            found.append(t)
    return found


def process_file(fpath: Path, known_tickers: set) -> list[dict]:
    """Process one daily JSONL file → list of (date, ticker, pos, neg) records."""
    date_str = fpath.stem  # e.g., "2021-03-15"
    records = []
    try:
        with open(fpath, encoding='utf-8', errors='replace') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    art = json.loads(line)
                except json.JSONDecodeError:
                    continue

                title   = str(art.get("title",   "") or "")
                summary = str(art.get("summary", "") or "")
                text    = title + " " + summary

                tickers = extract_tickers_from_title(title, known_tickers)
                if not tickers:
                    continue

                pos, neg = score_text(text)
                for ticker in tickers:
                    records.append({
                        "date":   date_str,
                        "ticker": ticker,
                        "pos":    pos,
                        "neg":    neg,
                    })
    except Exception:
        pass
    return records


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start",   type=str, default="2015-01-01",
                        help="Process files from this date onwards (YYYY-MM-DD).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Process first 100 files only.")
    args = parser.parse_args()

    known_tickers = load_known_tickers()
    print(f"Known tickers: {len(known_tickers)}")

    files = sorted(NEWS_DIR.glob("*.jsonl"))
    files = [f for f in files if f.stem >= args.start and re.match(r'\d{4}-\d{2}-\d{2}', f.stem)]
    print(f"JSONL files to process: {len(files)}")

    if args.dry_run:
        files = files[:100]
        print(f"DRY RUN: processing first {len(files)} files")

    all_records = []
    for i, fpath in enumerate(files):
        recs = process_file(fpath, known_tickers)
        all_records.extend(recs)
        if (i + 1) % 500 == 0:
            print(f"  {i+1}/{len(files)} files processed, {len(all_records):,} records so far")

    print(f"\nTotal article-ticker pairs: {len(all_records):,}")
    if not all_records:
        print("No records found. Check news directory and ticker list.")
        return

    raw_df = pd.DataFrame(all_records)

    # Aggregate: per (date, ticker)
    agg = raw_df.groupby(["date", "ticker"]).agg(
        pos_count    = ("pos", "sum"),
        neg_count    = ("neg", "sum"),
        article_count= ("pos", "count"),
    ).reset_index()

    agg["sentiment_score"] = (agg["pos_count"] - agg["neg_count"]).astype(float)
    agg["positive_ratio"]  = agg["pos_count"] / (agg["pos_count"] + agg["neg_count"] + 1e-9)
    agg["time"]            = pd.to_datetime(agg["date"])
    agg = agg.drop(columns=["date"])
    agg = agg.sort_values(["time", "ticker"]).reset_index(drop=True)

    # Normalize sentiment_score per day (cross-sectional z-score) so it's comparable across days
    def cs_zscore(s):
        std = s.std()
        if std < 1e-9:
            return pd.Series(0.0, index=s.index)
        return (s - s.mean()) / std

    agg["sentiment_cs_z"] = agg.groupby("time")["sentiment_score"].transform(cs_zscore)

    print(f"\nOutput shape: {agg.shape}")
    print(f"Date range: {agg['time'].min().date()} to {agg['time'].max().date()}")
    print(f"Unique tickers: {agg['ticker'].nunique()}")
    print(f"\nArticle counts by ticker (top 20):")
    tc = agg.groupby("ticker")["article_count"].sum().sort_values(ascending=False)
    print(tc.head(20).to_string())
    print(f"\nSentiment score distribution:")
    print(agg["sentiment_score"].describe())

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    agg.to_parquet(OUT_PATH, index=False)
    print(f"\nSaved: {OUT_PATH}")


if __name__ == "__main__":
    main()
