"""
Pre-computed lookups - build once, use many times.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from tqdm import tqdm

CACHE_DIR = Path("/home/manh/stocks-ecosystem/dumb-trading-agent/cache")
PRICE_CACHE_FILE = CACHE_DIR / "price_cache.parquet"
LIQUID_CACHE_FILE = CACHE_DIR / "liquid_lookup.joblib"


def build_liquid_cache(min_volume: int = 500_000, price_change_threshold: float = 0.001):
    """Build {date: set of liquid tickers} - one-time, ~2 min."""
    import joblib
    
    pc = pd.read_parquet(PRICE_CACHE_FILE)
    price_cache = {t: g.set_index("time") for t, g in pc.groupby("ticker")}
    
    # Group by date first for efficiency
    liquid_by_date: dict[str, set[str]] = {}
    
    print("Building liquid cache...", flush=True)
    for ticker, df in tqdm(price_cache.items()):
        dates = sorted(df.index)
        for i, date in enumerate(dates):
            if i < 4:  # Need 5 days
                continue
            try:
                recent = df.iloc[i-4:i+1]  # 5 days
                if len(recent) < 3:
                    continue
                if recent['volume'].mean() < min_volume:
                    continue
                price_change = abs(recent['close'].iloc[-1] - recent['close'].iloc[0]) / recent['close'].iloc[0]
                if price_change >= price_change_threshold:
                    if date not in liquid_by_date:
                        liquid_by_date[date] = set()
                    liquid_by_date[date].add(ticker)
            except:
                pass
    
    print(f"Saving {len(liquid_by_date)} dates", flush=True)
    joblib.dump(liquid_by_date, LIQUID_CACHE_FILE)
    return liquid_by_date


def load_liquid_cache():
    """Load cached liquid lookup or build if missing."""
    import joblib
    
    if LIQUID_CACHE_FILE.exists():
        return joblib.load(LIQUID_CACHE_FILE)
    return build_liquid_cache()


if __name__ == "__main__":
    build_liquid_cache()