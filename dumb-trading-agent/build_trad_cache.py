"""
Build pre-computed caches - run once.
"""

import signals as s
import pandas as pd
import joblib
from pathlib import Path

CACHE_DIR = Path("/home/manh/stocks-ecosystem/dumb-trading-agent/cache")
TRAD_CACHE_FILE = CACHE_DIR / "trad_lookup.joblib"

print("Building tradability cache...")

# Load raw data
c16 = s.load_order_pressure(start='2019-01-01', end='2025-12-31')
trad_df = c16[['time', 'ticker', 'can_buy_next_open']].copy()

# Build dict
trad_lookup = {}
for _, row in trad_df.iterrows():
    key = (row['ticker'], row['time'])
    trad_lookup[key] = row['can_buy_next_open']

print(f"Saving {len(trad_lookup)} entries")
joblib.dump(trad_lookup, TRAD_CACHE_FILE)
print(f"Saved: {TRAD_CACHE_FILE}")