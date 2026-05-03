#!/usr/bin/env python
"""X55: Lempel-Ziv complexity - test if C16 stronger when tape is repetitive."""
import pandas as pd
import numpy as np
from scipy.stats import spearmanr

# X55: Need tick-level data for LZ complexity
# We don't have tick data, so we can use intraday as proxy (1H files)
# OR skip with note

# Check if 1H intraday exists
import glob
files = glob.glob('data/stock/*_1H_*.parquet')[:5]
print(f'Intraday 1H files sample: {len(files)} found')

# For now, use a proxy: use daily return clustering
# Load barrier with actual
s1 = pd.read_parquet('data/features/xs_barrier_vol_1d_hose_full.parquet', columns=['time', 'ticker', 'actual'])
s1['time'] = pd.to_datetime(s1['time'])
s1 = s1[s1['time'].dt.year.isin(range(2015, 2023))]
s1 = s1.dropna(subset=['actual'])

# Complexity proxy: consecutive up/down days
s1 = s1.sort_values(['ticker', 'time'])
s1['dir'] = np.sign(s1['actual'])
s1['streak'] = s1.groupby('ticker')['dir'].transform(lambda x: (x != x.shift()).cumsum())

# Low complexity = long streaks (repetitive)
s1['is_streak'] = s1['streak'] > 3  # 4+ same-direction days

streak = s1[s1['is_streak']]
no_streak = s1[~s1['is_streak']]

# This is circular - actual IS the input - so can't test properly
print('X55: SKIP - actual return drives streak proxy, circular test')
print('Need tick-level data for real LZ complexity')
print(f'Intraday 1H available as proxy: {len(files)} files')