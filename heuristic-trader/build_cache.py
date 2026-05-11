"""
Pre-computed lookups - build once, use many times.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from tqdm import tqdm

_DEFAULT_CACHE_DIR = Path(__file__).parent / "cache"
CACHE_DIR = _DEFAULT_CACHE_DIR
PRICE_CACHE_FILE = CACHE_DIR / "price_cache.parquet"
LIQUID_CACHE_FILE = CACHE_DIR / "liquid_lookup.joblib"


def build_liquid_cache(min_volume: int = 500_000, price_change_threshold: float = 0.001):
    """Build {date: set of liquid tickers} - one-time, ~2 min.
    
    HARD RULE: "No exact ticker-date row, no claim."
    - Cache must match runtime filter semantics EXACTLY
    - Cache is part of research logic, NOT a mere optimization
    - Cache promotion requires parity test pass
    - Missing date = no entry (fail closed, no fallback)
    
    Must exactly match check_liquid() semantics in backtest.py:
    - Window: max(0, idx-5) to idx+1 (up to 6 rows)
    - Min rows: 3
    - Volume: mean >= min_volume
    - Price change: only if >=2 rows, abs(close_last-close_first)/close_first >= price_change_threshold
    """
    import joblib
    
    pc = pd.read_parquet(PRICE_CACHE_FILE)
    price_cache = {t: g.set_index("time") for t, g in pc.groupby("ticker")}
    
    # Group by date first for efficiency
    liquid_by_date: dict[str, set[str]] = {}
    
    print("Building liquid cache...", flush=True)
    for ticker, df in tqdm(price_cache.items()):
        dates = sorted(df.index)
        for idx, date in enumerate(dates):
            # Match check_liquid() exactly: start_idx = max(0, idx-5)
            start_idx = max(0, idx - 5)
            try:
                recent = df.iloc[start_idx:idx+1]  # Up to 6 rows, matches check_liquid
                if len(recent) < 3:
                    continue
                if recent['volume'].mean() < min_volume:
                    continue
                # Price change check: only if >= 2 rows (matches check_liquid)
                if len(recent) >= 2:
                    price_change = abs(recent['close'].iloc[-1] - recent['close'].iloc[0]) / recent['close'].iloc[0]
                    if price_change < price_change_threshold:
                        continue
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