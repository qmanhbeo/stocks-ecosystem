#!/usr/bin/env python
"""S247: Deep Down Market - bottom quintile vs median split."""
import pandas as pd
import numpy as np
from scipy.stats import spearmanr

C16 = 'data/features/xs_order_pressure_daily.parquet'
LABEL = 'data/features/xs_barrier_vol_1d_hose_full.parquet'

print('='*60)
print('TEST: S247 deep_down_market')
print('='*60)

c16 = pd.read_parquet(C16, columns=['time', 'ticker', 'order_volume_ratio_rank'])
c16['time'] = pd.to_datetime(c16['time'])
c16 = c16[c16['time'].dt.year.isin(range(2015, 2023))]

label = pd.read_parquet(LABEL, columns=['time', 'ticker', 'actual'])
label['time'] = pd.to_datetime(label['time'])
label = label[label['time'].dt.year.isin(range(2015, 2023))]

merged = c16.merge(label, on=['time', 'ticker'], how='inner')
merged = merged.dropna(subset=['order_volume_ratio_rank', 'actual'])

# Market return: average actual per day (not median - use mean for direction)
daily = merged.groupby('time')['actual'].mean().reset_index(name='market_return')
# Direction: negative = down market day
daily['market_direction'] = (daily['market_return'] < 0).astype(int)
# Quintile: bottom 20% of market returns when negative
daily['market_quintile'] = daily['market_return'].rank(pct=True)
merged = merged.merge(daily[['time', 'market_direction', 'market_quintile']], on='time', how='left')

# Down days = market_direction == 0 (negative return)
# Deep down = bottom 20% among ALL days (quintile <= 0.2), not just down days
# The key: does C16 work differently in the worst market days?

def yearly_ic(df):
    results = []
    for year in range(2015, 2023):
        y = df[df['time'].dt.year == year]
        if len(y) > 30:
            # All
            ic_all, _ = spearmanr(y['order_volume_ratio_rank'], y['actual'])
            
            # All down days (negative return)
            down = y[y['market_direction'] == 0]
            ic_down = spearmanr(down['order_volume_ratio_rank'], down['actual'])[0] if len(down) > 30 else np.nan
            
            # Deep down: bottom quintile (market_return <= 0.2)
            deep = y[y['market_quintile'] <= 0.2]
            ic_deep = spearmanr(deep['order_volume_ratio_rank'], deep['actual'])[0] if len(deep) > 30 else np.nan
            
            results.append({
                'year': year, 'ic_all': ic_all, 'ic_down': ic_down, 'ic_deep': ic_deep, 'n': len(y)
            })
    return pd.DataFrame(results)

results = yearly_ic(merged)

print(f'\nResults:')
print(f'{"Year":<6} {"IC_all":>10} {"IC_down":>10} {"IC_deep":>10} {"n":>10}')
print('-'*48)
for _, r in results.iterrows():
    print(f"{int(r['year']):<6} {r['ic_all']:+10.4f} {r['ic_down']:+10.4f} {r['ic_deep']:+10.4f} {int(r['n']):>10,}")

ic_all = results['ic_all'].mean()
ic_down = results['ic_down'].mean()
ic_deep = results['ic_deep'].mean()

print(f'\nAverages:')
print(f'  All markets:  IC = {ic_all:+.4f}')
print(f'  Down days:    IC = {ic_down:+.4f}')
print(f'  Deep down:    IC = {ic_deep:+.4f}')
print(f'  Diff (D-A): {ic_deep - ic_all:+.4f}')

# Verdict
baseline = 0.078
if ic_deep > baseline + 0.03:
    verdict = 'PASSED - deep down days strongest'
    tier = 2
elif ic_down > baseline + 0.02:
    verdict = 'PASSED - down days stronger'
    tier = 2
else:
    verdict = 'WEAK'

print(f'\nVerdict: {verdict}')
print(f'vs C16 baseline: {ic_down - baseline:+.4f} ({((ic_down/baseline)-1)*100:+.0f}%)')

results.to_parquet('/home/manh/stocks-ecosystem/alpha-research-lab/analysis/artifacts/s247_deep_down.parquet', index=False)
print('\nSaved: artifacts/s247_deep_down.parquet')