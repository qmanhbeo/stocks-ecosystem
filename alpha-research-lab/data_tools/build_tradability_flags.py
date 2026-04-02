"""
Build daily tradability flags from shared execution rules.

The output is the canonical producer-side execution artifact for the workspace:
  data/features/execution/tradability_daily.parquet

Columns:
  time
  ticker
  has_volume
  is_ceiling
  is_floor
  can_buy_next_open
  can_sell_next_open

Usage:
    conda run -n stocks python data_tools/build_tradability_flags.py
"""

from __future__ import annotations

import argparse
import glob
from pathlib import Path
import sys

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = REPO_ROOT.parent
SHARED_MARKET_RULES_ROOT = WORKSPACE_ROOT / "shared-market-rules"
if str(SHARED_MARKET_RULES_ROOT) not in sys.path:
    sys.path.insert(0, str(SHARED_MARKET_RULES_ROOT))

from shared_market_rules import compute_tradability_flags

STOCK_DIR = REPO_ROOT / "data" / "stock"
OUT_DIR = REPO_ROOT / "data" / "features" / "execution"
OUT_PATH = OUT_DIR / "tradability_daily.parquet"
EXCLUDE = {"VNINDEX", "VN30"}


def build_tradability_frame(stock_dir: Path = STOCK_DIR) -> pd.DataFrame:
    parts: list[pd.DataFrame] = []
    for file_path in sorted(glob.glob(str(stock_dir / "gia_lich_su_*_1D.parquet"))):
        ticker = Path(file_path).stem.replace("gia_lich_su_", "").replace("_1D", "")
        if ticker in EXCLUDE:
            continue
        df = pd.read_parquet(file_path, columns=["time", "close", "volume"])
        df["time"] = pd.to_datetime(df["time"])
        df = df.sort_values("time").reset_index(drop=True)
        if df.empty:
            continue
        df["ticker"] = ticker
        flags = compute_tradability_flags(df[["time", "ticker", "close", "volume"]].copy())
        parts.append(flags)

    if not parts:
        return pd.DataFrame(
            columns=[
                "time",
                "ticker",
                "has_volume",
                "is_ceiling",
                "is_floor",
                "can_buy_next_open",
                "can_sell_next_open",
            ]
    )
    return pd.concat(parts, ignore_index=True).sort_values(["time", "ticker"]).reset_index(drop=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build shared tradability flags from daily stock files.")
    return parser.parse_args()


def main() -> None:
    parse_args()
    print("Building tradability flags from shared execution rules...")
    tradability = build_tradability_frame()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    tradability.to_parquet(OUT_PATH, index=False)
    print(f"Saved {len(tradability):,} rows -> {OUT_PATH}")


if __name__ == "__main__":
    main()
