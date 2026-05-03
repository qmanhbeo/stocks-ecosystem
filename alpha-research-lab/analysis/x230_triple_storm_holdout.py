#!/usr/bin/env python
"""X230: Triple Storm Holdout Test - test on 2023-2025 data."""
import pandas as pd
import numpy as np
from scipy.stats import spearmanr

S1 = 'data/features/xs_barrier_vol_1d_hose_full.parquet'
ORDER = 'data/order_stats/cafef/order_stats_daily.parquet'

print('='*60)
print('TEST: X230 Triple Storm HOLDOUT')
print('Testing on 2023-2025 (NOT in training)')
print('='*60)

# Training: 2015-2022 (same as before)
# Holdout: 2023-2025

s1 = pd.read_parquet(S1, columns=['time', 'ticker', 'actual'])
s1['time'] = pd.to_datetime(s1['time'])

order = pd.read_parquet(ORDER)
order['date'] = pd.to_datetime(order['date'])
order['ovr'] = (order['buy_order_volume'] - order['sell_order_volume']) / (order['buy_order_volume'] + order['sell_order_volume'])
order['c16'] = order.groupby('date')['ovr'].rank(pct=True)
order = order.rename(columns={'date': 'time'})

merged = s1.merge(order, on=['time', 'ticker'], how='inner')
merged = merged.dropna(subset=['c16', 'actual'])
merged = merged.sort_values(['ticker', 'time'])

# Market state: per-day win rate
daily = merged.groupby('time')['actual'].mean().reset_index(name='win_rate')
daily['market_down'] = (daily['win_rate'] < 0.5).astype(int)
merged = merged.merge(daily[['time', 'market_down']], on='time')

# Liquid
merged['move'] = merged.groupby('ticker')['c16'].transform(lambda x: x.rolling(20, min_periods=10).std())
merged['liquid'] = (merged['move'] > merged['move'].quantile(0.8)).astype(int)

# Divergence
merged['ret_lag1'] = merged.groupby('ticker')['actual'].shift(1)
merged = merged.dropna(subset=['ret_lag1'])
merged['price_dir'] = (merged['ret_lag1'] > 0).astype(int)
merged['c16_dir'] = (merged['c16'] > 0.5).astype(int)
merged['divergence'] = (merged['price_dir'] != merged['c16_dir']).astype(int)

def yearly_ic(df, col='c16', years=range(2015, 2026)):
    results = []
    for year in years:
        y = df[df['time'].dt.year == year]
        if len(y) > 30:
            ic, p = spearmanr(y[col], y['actual'])
            results.append({'year': year, 'ic': ic, 'n': len(y)})
    return pd.DataFrame(results)

# Split by train/holdout
train_years = range(2015, 2023)
holdout_years = range(2023, 2026)

print('\n--- TRAINING (2015-2022) ---')
train = merged[merged['time'].dt.year.isin(train_years)]
train_tests = [
    ('Baseline', train),
    ('Liquid+DOWN', train[(train['liquid']==1) & (train['market_down']==1)]),
    ('Triple Storm', train[(train['liquid']==1) & (train['market_down']==1) & (train['divergence']==1)]),
]
for name, df in train_tests:
    if len(df) > 100:
        ic_df = yearly_ic(df, years=train_years)
        print(f'{name}: IC={ic_df["ic"].mean():.4f} n={len(df)}')

print('\n--- HOLDOUT (2023-2025) ---')
holdout = merged[merged['time'].dt.year.isin(holdout_years)]
print(f'Holdout rows: {len(holdout)}')

holdout_tests = [
    ('Baseline', holdout),
    ('Liquid+DOWN', holdout[(holdout['liquid']==1) & (holdout['market_down']==1)]),
    ('Triple Storm', holdout[(holdout['liquid']==1) & (holdout['market_down']==1) & (holdout['divergence']==1)]),
]
for name, df in holdout_tests:
    if len(df) > 100:
        ic_df = yearly_ic(df, years=holdout_years)
        print(f'{name}: IC={ic_df["ic"].mean():.4f} n={len(df)}')
    else:
        print(f'{name}: SKIP (n={len(df)})')

# Compare train vs holdout
print('\n--- TRAIN vs HOLDOUT COMPARISON ---')
baseline_train = train_tests[0][1]
baseline_holdout = holdout_tests[0][1]
triple_train = train_tests[2][1]
triple_holdout = holdout_tests[2][1]

train_ic = yearly_ic(baseline_train, years=train_years)['ic'].mean()
holdout_ic = yearly_ic(baseline_holdout, years=holdout_years)['ic'].mean()
print(f'Baseline train:   {train_ic:.4f}')
print(f'Baseline holdout: {holdout_ic:.4f}')

if len(triple_train) > 100 and len(triple_holdout) > 100:
    triple_train_ic = yearly_ic(triple_train, years=train_years)['ic'].mean()
    triple_holdout_ic = yearly_ic(triple_holdout, years=holdout_years)['ic'].mean()
    print(f'Triple train:    {triple_train_ic:.4f}')
    print(f'Triple holdout: {triple_holdout_ic:.4f}')
    
    train_pct = (triple_train_ic / train_ic - 1) * 100
    holdout_pct = (triple_holdout_ic / holdout_ic - 1) * 100
    print(f'\\nTriple boost train:   {train_pct:+.0f}%')
    print(f'Triple boost holdout: {holdout_pct:+.0f}%')

# Verdict
if len(triple_holdout) > 100 and holdout_ic > 0:
    if triple_holdout_ic > holdout_ic * 1.1:
        verdict = 'PASSED - holds on holdout!'
    elif triple_holdout_ic < holdout_ic * 0.9:
        verdict = 'FAILED - does NOT hold'
    else:
        verdict = 'NEUTRAL - similar to baseline'
else:
    verdict = 'SKIP - not enough holdout data'

print(f'\nVerdict: {verdict}')
print('='*60)