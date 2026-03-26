"""
build_news_features.py -- Pre-build daily news sentiment features for FPT from Cafef articles.

Reads all JSONL files in data/news/cafef/raw/ and extracts:
  - How many articles mention FPT that day?
  - What is the sentiment of those articles? (keyword-based)
  - What is the overall market news volume? (proxy for macro sentiment)

Output: data/features/fpt_news_daily.parquet
  date (datetime), fpt_mentions, fpt_title_mentions,
  fpt_sentiment, fpt_pos_count, fpt_neg_count,
  total_articles, news_surge (abnormally high day)

LOOK-AHEAD NOTE: These features will be shifted by 1 day in feature_engineering.py
(today's news predicts tomorrow's opening, not same-day).

Run: conda run -n stocks python src/build_news_features.py
"""
import json
import glob
import os
from pathlib import Path
from datetime import datetime
import pandas as pd
import numpy as np


NEWS_DIR = Path("data/news/cafef/raw")
OUT_DIR  = Path("data/features")
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_FILE = OUT_DIR / "fpt_news_daily.parquet"

# Vietnamese + English financial keywords for sentiment
POS_KEYWORDS = [
    "tăng", "tích cực", "lợi nhuận", "doanh thu", "tăng trưởng", "mạnh",
    "thắng", "tốt", "phát triển", "thành công", "khởi sắc", "cơ hội",
    "hiệu quả", "vượt", "kỷ lục", "tốt nhất", "cao nhất", "tăng mạnh",
    "tăng cao", "ký kết", "hợp đồng", "đầu tư", "mở rộng", "ra mắt",
    "profit", "growth", "revenue", "record", "expand", "deal", "win",
    "tăng vọt", "bứt phá", "kết quả tốt", "vượt kế hoạch",
]
NEG_KEYWORDS = [
    "giảm", "lỗ", "khó khăn", "rủi ro", "thấp", "yếu", "sụt",
    "lo ngại", "áp lực", "giảm sút", "bán tháo", "thua lỗ",
    "nặng nề", "giảm mạnh", "giảm sâu", "cảnh báo", "vi phạm",
    "phạt", "điều tra", "kiện", "nợ", "vỡ nợ", "phá sản",
    "loss", "decline", "drop", "risk", "warning", "probe", "debt",
    "giảm vốn", "thu hẹp", "đóng cửa", "giải thể",
]


def score_text(text: str) -> tuple[int, int]:
    """Return (pos_count, neg_count) keyword hits in text."""
    text_lower = text.lower()
    pos = sum(1 for kw in POS_KEYWORDS if kw in text_lower)
    neg = sum(1 for kw in NEG_KEYWORDS if kw in text_lower)
    return pos, neg


def mentions_fpt(title: str, body: str) -> bool:
    """True if article is explicitly about FPT."""
    combined = (title or "") + " " + (body or "")[:500]
    # Must appear as standalone token-like substring
    return "FPT" in combined or "fpt" in combined.lower()


def process_file(path: str) -> dict:
    """Process one daily JSONL file, return aggregated stats."""
    date_str = Path(path).stem  # YYYY-MM-DD
    total = 0
    fpt_count = 0
    fpt_title_count = 0
    fpt_pos = 0
    fpt_neg = 0

    try:
        pd.Timestamp(date_str)  # validate date format early
    except Exception:
        return None  # skip non-date files

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    art = json.loads(line)
                except json.JSONDecodeError:
                    continue

                total += 1
                title = art.get("title", "") or ""
                body  = art.get("body_text", "") or art.get("summary", "") or ""

                if mentions_fpt(title, body):
                    fpt_count += 1
                    if "FPT" in title or "fpt" in title.lower():
                        fpt_title_count += 1
                    pos, neg = score_text(title + " " + body[:1000])
                    fpt_pos += pos
                    fpt_neg += neg

    except Exception as e:
        print(f"  [WARN] {path}: {e}")
        return None

    sentiment = (fpt_pos - fpt_neg) / (fpt_pos + fpt_neg + 1)  # [-1, 1] approx
    return {
        "date": pd.Timestamp(date_str),
        "fpt_mentions": fpt_count,
        "fpt_title_mentions": fpt_title_count,
        "fpt_pos_count": fpt_pos,
        "fpt_neg_count": fpt_neg,
        "fpt_sentiment": round(sentiment, 4),
        "total_articles": total,
    }


def main():
    files = sorted(glob.glob(str(NEWS_DIR / "*.jsonl")))
    print(f"Found {len(files)} JSONL files")
    if not files:
        print(f"ERROR: No files found in {NEWS_DIR}")
        return

    records = []
    for i, f in enumerate(files):
        if i % 200 == 0:
            print(f"  Processing {i}/{len(files)}: {Path(f).stem}")
        row = process_file(f)
        if row is not None:
            records.append(row)

    df = pd.DataFrame(records).sort_values("date").reset_index(drop=True)

    # Add derived features
    roll_window = 20
    df["fpt_mentions_ma"] = df["fpt_mentions"].rolling(roll_window, min_periods=5).mean()
    df["news_surge"] = (
        df["fpt_mentions"] > df["fpt_mentions_ma"] * 1.5
    ).astype(float)
    df["fpt_sentiment_ma"] = df["fpt_sentiment"].rolling(5, min_periods=2).mean()

    df.to_parquet(OUT_FILE, index=False)
    print(f"\nSaved {len(df)} days to {OUT_FILE}")
    print(f"Date range: {df['date'].min().date()} to {df['date'].max().date()}")
    print(f"\nSample stats:")
    print(f"  Avg FPT mentions/day: {df['fpt_mentions'].mean():.1f}")
    print(f"  Max FPT mentions/day: {df['fpt_mentions'].max()}")
    print(f"  Days with 0 mentions: {(df['fpt_mentions']==0).sum()}")
    print(f"  Avg total articles:   {df['total_articles'].mean():.0f}")


if __name__ == "__main__":
    main()
