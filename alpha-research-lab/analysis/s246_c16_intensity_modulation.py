#!/usr/bin/env python
"""S246: C16 Intensity Modulation - very high C16 in down markets only."""
import pandas as pd
import numpy as np
from scipy.stats import spearmanr

C16 = 'data/features/xs_order_pressure_daily.parquet'
LABEL = 'data/features/xs_barrier_vol_1d_hose_full.parquet'

print('='*60)
print('TEST: S246 c16_intensity_modulation')
print('='*60)

c16 = pd.read_parquet(C16, columns=['time', 'ticker', 'order_volume_ratio_rank'])
c16['time'] = pd.to_datetime(c16['time'])
c16 = c16[c16['time'].dt.year.isin(range(2015, 2023))]

label = pd.read_parquet(LABEL, columns=['time', 'ticker', 'actual'])
label['time'] = pd.to_datetime(label['time'])
label = label[label['time'].dt.year.isin(range(2015, 2023))]

merged = c16.merge(label, on=['time', 'ticker'], how='inner')
merged = merged.dropna(subset=['order_volume_ratio_rank', 'actual'])

# Market return per day (use median actual as market proxy)
daily_return = merged.groupby('time')['actual'].median().reset_index(name='market_return')
daily_return['market_state'] = (daily_return['market_return'] > 0).astype(int)
merged = merged.merge(daily_return[['time', 'market_state']], on='time', how='left')

# Very high C16 threshold
merged['c16_extreme'] = (merged['order_volume_ratio_rank'] > 0.9).astype(int)

def yearly_ic(df):
    results = []
    for year in range(2015, 2023):
        y = df[df['time'].dt.year == year]
        if len(y) > 30:
            # All C16
            ic_all, _ = spearmanr(y['order_volume_ratio_rank'], y['actual'])
            
            # Down market only
            down = y[y['market_state'] == 0]
            ic_down = spearmanr(down['order_volume_ratio_rank'], down['actual'])[0] if len(down) > 30 else np.nan
            
            # Down + extreme C16
            down_extreme = down[down['c16_extreme'] == 1]
            ic_down_extreme = spearmanr(down_extreme['order_volume_ratio_rank'], down_extreme['actual'])[0] if len(down_extreme) > 30 else np.nan
            
            # Up + extreme C16
            up = y[y['market_state'] == 1]
            up_extreme = up[up['c16_extreme'] == 1]
            ic_up_extreme = spearmanr(up_extreme['order_volume_ratio_rank'], up_extreme['actual'])[0] if len(up_extreme) > 30 else np.nan
            
            results.append({
                'year': year, 'ic_all': ic_all, 'ic_down': ic_down, 
                'ic_down_extreme': ic_down_extreme, 'ic_up_extreme': ic_up_extreme, 
                'n': len(y)
            })
    return pd.DataFrame(results)

results = yearly_ic(merged)

print(f'\nResults:')
print(f'{"Year":<6} {"IC_all":>10} {"IC_down":>10} {"IC_down_X":>12} {"IC_up_X":>12} {"n":>10}')
print('-'*62)
for _, r in results.iterrows():
    print(f"{int(r['year']):<6} {r['ic_all']:+10.4f} {r['ic_down']:+10.4f} {r['ic_down_extreme']:+12.4f} {r['ic_up_extreme']:+12.4f} {int(r['n']):>10,}")

ic_all = results['ic_all'].mean()
ic_down = results['ic_down'].mean()
ic_down_extreme = results['ic_down_extreme'].mean()
ic_up_extreme = results['ic_up_extreme'].mean()

print(f'\nAverages:')
print(f'  All markets:         IC = {ic_all:+.4f}')
print(f'  Down only:           IC = {ic_down:+.4f}')
print(f'  Down + C16 > 0.9:   IC = {ic_down_extreme:+.4f}')
print(f'  Up + C16 > 0.9:     IC = {ic_up_extreme:+.4f}')
print(f'  Diff (down_X - up_X): {ic_down_extreme - ic_up_extreme:+.4f}')

# Verdict vs Random (0.05 threshold)
baseline = 0.078
if ic_down_extreme > baseline + 0.03:
    verdict = 'PASSED - extreme C16 in down is stronger'
    tier = 2
elif ic_down > baseline + 0.02:
    verdict = 'PASSED - down market C16 is stronger'
    tier = 2
else:
    verdict = 'WEAK - no meaningful boost'

print(f'\nVerdict: {verdict}')
print(f'vs C16 baseline: {ic_down - baseline:+.4f} ({((ic_down/baseline)-1)*100:+.0f}%)')

results.to_parquet('/home/manh/stocks-ecosystem/alpha-research-lab/analysis/artifacts/s246_c16_intensity.parquet', index=False)
print('\nSaved: artifacts/s246_c16_intensity.parquet')