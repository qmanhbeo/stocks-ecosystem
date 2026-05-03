#!/usr/bin/env python
"""S251: Consecutive Down Intensity - C16 strength on day 2/3 of market down streak."""
import pandas as pd
import numpy as np
from scipy.stats import spearmanr

C16 = 'data/features/xs_order_pressure_daily.parquet'
LABEL = 'data/features/xs_barrier_vol_1d_hose_full.parquet'

print('='*60)
print('TEST: S251 consecutive_down_intensity')
print('='*60)

c16 = pd.read_parquet(C16, columns=['time', 'ticker', 'order_volume_ratio_rank'])
c16['time'] = pd.to_datetime(c16['time'])
c16 = c16[c16['time'].dt.year.isin(range(2015, 2023))]

label = pd.read_parquet(LABEL, columns=['time', 'ticker', 'actual'])
label['time'] = pd.to_datetime(label['time'])
label = label[label['time'].dt.year.isin(range(2015, 2023))]

merged = c16.merge(label, on=['time', 'ticker'], how='inner')
merged = merged.dropna(subset=['order_volume_ratio_rank', 'actual'])

# Market direction per day
daily = merged.groupby('time')['actual'].median().reset_index(name='market_return')
daily['market_direction'] = (daily['market_return'] < 0).astype(int)
daily = daily.sort_values('time')

# Previous day direction
daily['prev_direction'] = daily['market_direction'].shift(1)
daily['prev2_direction'] = daily['market_direction'].shift(2)

# Consecutive count
daily['streak_1'] = (daily['prev_direction'] == 0).astype(int)  # Previous day was down
daily['streak_2'] = ((daily['prev_direction'] == 0) & (daily['prev2_direction'] == 0)).astype(int)  # 2 days down

merged = merged.merge(daily[['time', 'market_direction', 'streak_1', 'streak_2']], on='time', how='left')

def yearly_ic(df):
    results = []
    for year in range(2015, 2023):
        y = df[df['time'].dt.year == year]
        if len(y) > 30:
            # All
            ic_all, _ = spearmanr(y['order_volume_ratio_rank'], y['actual'])
            
            # Down day (any streak)
            down = y[y['market_direction'] == 0]
            ic_down = spearmanr(down['order_volume_ratio_rank'], down['actual'])[0] if len(down) > 30 else np.nan
            
            # Down day after down day (day 2)
            down_d1 = y[(y['market_direction'] == 0) & (y['streak_1'] == 1)]
            ic_day2 = spearmanr(down_d1['order_volume_ratio_rank'], down_d1['actual'])[0] if len(down_d1) > 30 else np.nan
            
            # Down day after 2 down days (day 3)
            down_d2 = y[(y['market_direction'] == 0) & (y['streak_2'] == 1)]
            ic_day3 = spearmanr(down_d2['order_volume_ratio_rank'], down_d2['actual'])[0] if len(down_d2) > 30 else np.nan
            
            results.append({
                'year': year, 'ic_all': ic_all, 'ic_down': ic_down, 
                'ic_day2': ic_day2, 'ic_day3': ic_day3, 'n': len(y)
            })
    return pd.DataFrame(results)

results = yearly_ic(merged)

print(f'\nResults:')
print(f'{"Year":<6} {"IC_all":>8} {"IC_dn":>8} {"IC_day2":>10} {"IC_day3":>10} {"n":>10}')
print('-'*54)
for _, r in results.iterrows():
    print(f"{int(r['year']):<6} {r['ic_all']:+8.4f} {r['ic_down']:+8.4f} {r['ic_day2']:+10.4f} {r['ic_day3']:+10.4f} {int(r['n']):>10,}")

ic_all = results['ic_all'].mean()
ic_down = results['ic_down'].mean()
ic_day2 = results['ic_day2'].mean()
ic_day3 = results['ic_day3'].mean()

print(f'\nAverages:')
print(f'  All down days:     IC = {ic_down:+.4f}')
print(f'  Day 2 streak:    IC = {ic_day2:+.4f}')
print(f'  Day 3 streak:    IC = {ic_day3:+.4f}')
print(f'  All markets:     IC = {ic_all:+.4f}')

baseline = 0.078
# Check if day 2 or day 3 is stronger than day 1
if ic_day2 > ic_down + 0.03:
    verdict = f'PASSED - day 2 stronger ({ic_day2:+.4f})'
    tier = 2
elif ic_day3 > ic_down + 0.03:
    verdict = f'PASSED - day 3 stronger ({ic_day3:+.4f})'
    tier = 2
elif ic_down > baseline + 0.02:
    verdict = f'PASSED - down day C16 ({ic_down:+.4f})'
    tier = 2
else:
    verdict = 'WEAK'

print(f'\nVerdict: {verdict}')
print(f'vs baseline: {ic_down - baseline:+.4f}')

results.to_parquet('/home/manh/stocks-ecosystem/alpha-research-lab/analysis/artifacts/s251_consecutive_down.parquet', index=False)
print('\nSaved: artifacts/s251_consecutive_down.parquet')