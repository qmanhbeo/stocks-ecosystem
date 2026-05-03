#!/usr/bin/env python
"""X227: C16 Acceleration - rate of change matters more than level."""
import pandas as pd
import numpy as np
from scipy.stats import spearmanr

S1 = 'data/features/xs_barrier_vol_1d_hose_full.parquet'
ORDER = 'data/order_stats/cafef/order_stats_daily.parquet'

print('='*60)
print('TEST: X227 c16_acceleration')
print('Hypothesis: C16 velocity matters MORE than level')
print('='*60)

# Load and prepare data
s1 = pd.read_parquet(S1, columns=['time', 'ticker', 'actual'])
s1['time'] = pd.to_datetime(s1['time'])
s1 = s1[s1['time'].dt.year.isin(range(2015, 2023))]

order = pd.read_parquet(ORDER)
order['date'] = pd.to_datetime(order['date'])
order = order[order['date'].dt.year.isin(range(2015, 2023))]
order['ovr'] = (order['buy_order_volume'] - order['sell_order_volume']) / (order['buy_order_volume'] + order['sell_order_volume'])
order['c16'] = order.groupby('date')['ovr'].rank(pct=True)
order = order.rename(columns={'date': 'time'})

merged = s1.merge(order, on=['time', 'ticker'], how='inner')
merged = merged.dropna(subset=['c16', 'actual'])
merged = merged.sort_values(['ticker', 'time'])

# Compute C16 ROC (5-day rate of change)
merged['c16_lag5'] = merged.groupby('ticker')['c16'].shift(5)
merged['c16_roc'] = (merged['c16'] - merged['c16_lag5']) / (merged['c16_lag5'].clip(lower=0.01))

# Handleinf/NaN
merged = merged.dropna(subset=['c16', 'c16_roc', 'actual'])

def yearly_ic(df, col):
    results = []
    for year in range(2015, 2023):
        y = df[df['time'].dt.year == year]
        if len(y) > 30:
            ic, p = spearmanr(y[col], y['actual'])
            results.append({'year': year, 'ic': ic, 'p': p, 'n': len(y)})
    return pd.DataFrame(results)

# Test 1: C16 level (baseline)
print('\n--- TEST 1: C16 Level (baseline) ---')
level_ic = yearly_ic(merged, 'c16')
print(level_ic.to_string(index=False))
level_mean = level_ic['ic'].mean()
level_std = level_ic['ic'].std()
print(f'C16 Level: IC = {level_mean:.4f} ± {level_std:.4f}')

# Test 2: C16 ROC (acceleration)
print('\n--- TEST 2: C16 ROC (acceleration) ---')
roc_ic = yearly_ic(merged, 'c16_roc')
print(roc_ic.to_string(index=False))
roc_mean = roc_ic['ic'].mean()
roc_std = roc_ic['ic'].std()
print(f'C16 ROC: IC = {roc_mean:.4f} ± {roc_std:.4f}')

# Test 3: Combined (level + ROC)
merged['c16_combined'] = merged['c16'] * 0.5 + merged['c16_roc'].fillna(0) * 0.5
print('\n--- TEST 3: C16 Combined ---')
combined_ic = yearly_ic(merged, 'c16_combined')
print(combined_ic.to_string(index=False))
combined_mean = combined_ic['ic'].mean()
combined_std = combined_ic['ic'].std()
print(f'C16 Combined: IC = {combined_mean:.4f} ± {combined_std:.4f}')

# Summary
print('\n' + '='*60)
print('RESULTS SUMMARY')
print('='*60)
diff = roc_mean - level_mean
pct_change = (diff / abs(level_mean)) * 100 if level_mean != 0 else 0
print(f'C16 Level:   {level_mean:+.4f} (baseline)')
print(f'C16 ROC:     {roc_mean:+.4f} (diff: {diff:+.4f}, {pct_change:+.1f}%)')
print(f'C16 Combined: {combined_mean:+.4f}')

# Verdict
if abs(roc_mean) > abs(level_mean) * 1.1:
    verdict = 'PASSED - ROC beats level'
elif abs(roc_mean) < abs(level_mean) * 0.9:
    verdict = 'FAILED - ROC worse than level'
else:
    verdict = 'NEUTRAL - no meaningful difference'

print(f'\nVerdict: {verdict}')
print('='*60)