#!/usr/bin/env python
"""X228: C16 Divergence - price direction vs C16 direction."""
import pandas as pd
import numpy as np
from scipy.stats import spearmanr

S1 = 'data/features/xs_barrier_vol_1d_hose_full.parquet'
ORDER = 'data/order_stats/cafef/order_stats_daily.parquet'

print('='*60)
print('TEST: X228 c16_divergence')
print('Hypothesis: Price UP + C16 DOWN = contrarian divergence')
print('='*60)

# Load data
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

# Compute lagged price return (1-day)
merged['ret_lag1'] = merged.groupby('ticker')['actual'].shift(1)
merged = merged.dropna(subset=['ret_lag1', 'c16', 'actual'])

# Create direction flags
merged['price_dir'] = (merged['ret_lag1'] > 0).astype(int)  # 1 = price up yesterday
merged['c16_dir'] = (merged['c16'] > 0.5).astype(int)  # 1 = C16 positive (high buy pressure)

# Divergence cases:
# - price up + c16 down (retail buying, institutions selling = trap)
# - price down + c16 up (retail selling, institutions buying = smart)
merged['divergence'] = merged['price_dir'] != merged['c16_dir']
merged['aligned'] = ~merged['divergence']

print(f'\nTotal rows: {len(merged)}')
print(f'Divergence (price vs C16 disagree): {merged["divergence"].sum()} ({merged["divergence"].mean()*100:.1f}%)')
print(f'Aligned (price vs C16 agree): {merged["aligned"].sum()} ({merged["aligned"].mean()*100:.1f}%)')

def yearly_ic(df, col):
    results = []
    for year in range(2015, 2023):
        y = df[df['time'].dt.year == year]
        if len(y) > 30:
            ic, p = spearmanr(y[col], y['actual'])
            results.append({'year': year, 'ic': ic, 'p': p, 'n': len(y)})
    return pd.DataFrame(results)

# Test 1: All C16 (baseline)
print('\n--- TEST 1: All C16 (baseline) ---')
baseline_ic = yearly_ic(merged, 'c16')
print(f"C16 Baseline: IC = {baseline_ic['ic'].mean():.4f} ± {baseline_ic['ic'].std():.4f}")

# Test 2: Divergence only (disagreement)
print('\n--- TEST 2: Divergence ONLY (price UP + C16 DOWN OR price DOWN + C16 UP) ---')
div_df = merged[merged['divergence']]
if len(div_df) > 100:
    div_ic = yearly_ic(div_df, 'c16')
    print(f"Divergence: IC = {div_ic['ic'].mean():.4f} ± {div_ic['ic'].std():.4f}")
else:
    print(f"Not enough divergence samples: {len(div_df)}")

# Test 3: Aligned only (agreement)
print('\n--- TEST 3: Aligned ONLY (price direction matches C16) ---')
align_df = merged[merged['aligned']]
align_ic = yearly_ic(align_df, 'c16')
print(f"Aligned: IC = {align_ic['ic'].mean():.4f} ± {align_ic['ic'].std():.4f}")

# Test 4: Divergent when price UP but C16 DOWN (retail trap)
print('\n--- TEST 4: Price UP + C16 DOWN (retail trap scenario) ---')
retail_trap = merged[(merged['price_dir'] == 1) & (merged['c16_dir'] == 0)]
if len(retail_trap) > 100:
    trap_ic = yearly_ic(retail_trap, 'c16')
    print(f"Retail Trap: IC = {trap_ic['ic'].mean():.4f} ± {trap_ic['ic'].std():.4f}")

# Test 5: Divergent when price DOWN but C16 UP (institutional smart)
print('\n--- TEST 5: Price DOWN + C16 UP (institutional smart) ---')
inst_smart = merged[(merged['price_dir'] == 0) & (merged['c16_dir'] == 1)]
if len(inst_smart) > 100:
    smart_ic = yearly_ic(inst_smart, 'c16')
    print(f"Institutional Smart: IC = {smart_ic['ic'].mean():.4f} ± {smart_ic['ic'].std():.4f}")

# Summary
print('\n' + '='*60)
print('RESULTS SUMMARY')
print('='*60)
baseline_mean = baseline_ic['ic'].mean()
div_mean = div_ic['ic'].mean() if len(div_df) > 100 else 0
align_mean = align_ic['ic'].mean()

print(f'All C16 (baseline): {baseline_mean:+.4f}')
print(f'Divergence only:     {div_mean:+.4f}')
print(f'Aligned only:     {align_mean:+.4f}')

# Verdict
if len(div_df) > 100:
    if abs(div_mean) > abs(baseline_mean) * 1.1:
        verdict = 'PASSED - divergence beats baseline'
    elif abs(div_mean) < abs(baseline_mean) * 0.9:
        verdict = 'FAILED - divergence worse than baseline'
    else:
        verdict = 'NEUTRAL - no meaningful difference'
else:
    verdict = 'SKIP - not enough samples'

print(f'\nVerdict: {verdict}')
print('='*60)