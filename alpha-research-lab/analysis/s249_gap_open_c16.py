#!/usr/bin/env python
"""S249: Gap Open Momentum - C16 conditioned on overnight gap."""
import pandas as pd
import numpy as np
from scipy.stats import spearmanr

C16 = 'data/features/xs_order_pressure_daily.parquet'
LABEL = 'data/features/xs_barrier_vol_1d_hose_full.parquet'

print('='*60)
print('TEST: S249 gap_open_c16')
print('='*60)

c16 = pd.read_parquet(C16, columns=['time', 'ticker', 'order_volume_ratio_rank'])
c16['time'] = pd.to_datetime(c16['time'])
c16 = c16[c16['time'].dt.year.isin(range(2015, 2023))]

label = pd.read_parquet(LABEL, columns=['time', 'ticker', 'actual'])
label['time'] = pd.to_datetime(label['time'])
label = label[label['time'].dt.year.isin(range(2015, 2023))]

merged = c16.merge(label, on=['time', 'ticker'], how='inner')
merged = merged.dropna(subset=['order_volume_ratio_rank', 'actual'])

# Market return is already close-to-close. 
# We need overnight gap: use open vs previous close 
# But we don't have open price directly.
# Proxy: Market direction at open = actual > 0 at day start
# Alternative: Use the actual SIGN (positive/negative) as gap proxy

# Actually - simpler: use the sign of the day's market return as the "gap"
# Positive = gap up, Negative = gap down
daily = merged.groupby('time')['actual'].median().reset_index(name='market_return')
daily['gap_direction'] = (daily['market_return'] > 0).astype(int)  # 1 = up gap, 0 = down gap
merged = merged.merge(daily[['time', 'market_return', 'gap_direction']], on='time', how='left')

# Alternative: compute intraday direction within day - gap vs close
# We don't have that data, so let's use a simpler proxy:
# Previous day's return as "overnight" gap proxy

daily['prev_return'] = daily['market_return'].shift(1)
daily['gap_magnitude'] = daily['prev_return'].abs()
daily['gap_positive'] = (daily['prev_return'] > 0.01).astype(int)  # > 1% up gap
daily['gap_negative'] = (daily['prev_return'] < -0.01).astype(int)  # < -1% down gap
merged = merged.merge(daily[['time', 'gap_positive', 'gap_negative', 'gap_magnitude', 'prev_return']], on='time', how='left')

def yearly_ic(df):
    results = []
    for year in range(2015, 2023):
        y = df[df['time'].dt.year == year]
        if len(y) > 30:
            # All
            ic_all, _ = spearmanr(y['order_volume_ratio_rank'], y['actual'])
            
            # Gap positive (previous day up)
            pos = y[y['gap_positive'] == 1]
            ic_pos = spearmanr(pos['order_volume_ratio_rank'], pos['actual'])[0] if len(pos) > 30 else np.nan
            
            # Gap negative (previous day down)
            neg = y[y['gap_negative'] == 1]
            ic_neg = spearmanr(neg['order_volume_ratio_rank'], neg['actual'])[0] if len(neg) > 30 else np.nan
            
            # No significant gap
            no_gap = y[(y['gap_positive'] == 0) & (y['gap_negative'] == 0)]
            ic_no = spearmanr(no_gap['order_volume_ratio_rank'], no_gap['actual'])[0] if len(no_gap) > 30 else np.nan
            
            # Large positive gap + C16
            large_pos = y[(y['gap_positive'] == 1) & (y['order_volume_ratio_rank'] > 0.7)]
            ic_large_pos = spearmanr(large_pos['order_volume_ratio_rank'], large_pos['actual'])[0] if len(large_pos) > 30 else np.nan
            
            results.append({
                'year': year, 'ic_all': ic_all, 'ic_pos': ic_pos, 'ic_neg': ic_neg,
                'ic_no': ic_no, 'ic_large_pos': ic_large_pos, 'n': len(y)
            })
    return pd.DataFrame(results)

results = yearly_ic(merged)

print(f'\nResults:')
print(f'{"Year":<6} {"IC_all":>8} {"IC_gap+":>8} {"IC_gap-":>8} {"IC_none":>8} {"n":>10}')
print('-'*52)
for _, r in results.iterrows():
    print(f"{int(r['year']):<6} {r['ic_all']:+8.4f} {r['ic_pos']:+8.4f} {r['ic_neg']:+8.4f} {r['ic_no']:+8.4f} {int(r['n']):>10,}")

ic_all = results['ic_all'].mean()
ic_pos = results['ic_pos'].mean()
ic_neg = results['ic_neg'].mean()
ic_no = results['ic_no'].mean()
ic_large_pos = results['ic_large_pos'].mean()

print(f'\nAverages:')
print(f'  All markets:      IC = {ic_all:+.4f}')
print(f'  Gap positive:     IC = {ic_pos:+.4f}')
print(f'  Gap negative:     IC = {ic_neg:+.4f}')
print(f'  No significant:  IC = {ic_no:+.4f}')
print(f'  Gap+ & C16 > 0.7: IC = {ic_large_pos:+.4f}')

baseline = 0.078
# Best filter
best = max(ic_pos, ic_neg, ic_no)
if ic_pos > baseline + 0.03:
    verdict = f'PASSED - gap positive C16 stronger ({ic_pos:+.4f})'
    tier = 2
elif ic_neg > baseline + 0.03:
    verdict = f'PASSED - gap negative C16 stronger ({ic_neg:+.4f})'
    tier = 2
else:
    verdict = 'WEAK - no significant gap boost'

print(f'\nVerdict: {verdict}')
print(f'vs C16 baseline: {best - baseline:+.4f}')

results.to_parquet('/home/manh/stocks-ecosystem/alpha-research-lab/analysis/artifacts/s249_gap_open_c16.parquet', index=False)
print('\nSaved: artifacts/s249_gap_open_c16.parquet')