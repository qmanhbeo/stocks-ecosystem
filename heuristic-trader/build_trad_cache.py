"""
Build pre-computed caches - run once.
"""

import signals as s
import pandas as pd
import joblib
from pathlib import Path

_DEFAULT_CACHE_DIR = Path(__file__).parent / "cache"
CACHE_DIR = _DEFAULT_CACHE_DIR
TRAD_CACHE_FILE = CACHE_DIR / "trad_lookup.joblib"

print("Building tradability cache...")

# Load raw data
# NOTE: Changed from 2019-01-01 to 2015-01-01 on 2026-05-11
# Investigation showed can_buy_next_open has full coverage from 2007 onward
# 2019 was an accidental hardcoded boundary, not a data-quality boundary
# 2015 matches S1 signal matrix start, enabling clean execution validation
c16 = s.load_order_pressure(start='2015-01-01', end='2025-12-31')
trad_df = c16[['time', 'ticker', 'can_buy_next_open']].copy()

# Build dict
trad_lookup = {}
for _, row in trad_df.iterrows():
    key = (row['ticker'], row['time'])
    trad_lookup[key] = row['can_buy_next_open']

print(f"Saving {len(trad_lookup)} entries")
joblib.dump(trad_lookup, TRAD_CACHE_FILE)
print(f"Saved: {TRAD_CACHE_FILE}")