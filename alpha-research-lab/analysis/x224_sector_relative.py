#!/usr/bin/env python
"""X224: Sector-Relative C16 - C16 adjusted by sector median."""
import pandas as pd
import numpy as np
from scipy.stats import spearmanr

S1 = 'data/features/xs_barrier_vol_1d_hose_full.parquet'
ORDER = 'data/order_stats/cafef/order_stats_daily.parquet'
SECTOR = 'data/features/sector_classification.parquet'

print('='*60)
print('TEST: X224 sector_relative_c16')
print('='*60)

s1 = pd.read_parquet(S1, columns=['time', 'ticker', 'actual'])
s1['time'] = pd.to_datetime(s1['time'])
s1 = s1[s1['time'].dt.year.isin(range(2015, 2023))]

sector = pd.read_parquet(SECTOR).rename(columns={'symbol': 'ticker'})
s1 = s1.merge(sector[['ticker', 'icb_name3']], on='ticker', how='inner')

order = pd.read_parquet(ORDER)
order['date'] = pd.to_datetime(order['date'])
order = order[order['date'].dt.year.isin(range(2015, 2023))]
order['ovr'] = (order['buy_order_volume'] - order['sell_order_volume']) / (order['buy_order_volume'] + order['sell_order_volume'])
order['c16'] = order.groupby('date')['ovr'].rank(pct=True)
order = order.rename(columns={'date': 'time'})

merged = s1.merge(order, on=['time', 'ticker'], how='inner')
merged = merged.dropna(subset=['c16', 'actual', 'icb_name3'])

# Sector median C16 per day
sector_median = merged.groupby(['time', 'icb_name3'])['c16'].transform('median')
merged['c16_sector_rel'] = merged['c16'] - sector_median

def yearly_ic(df, col='c16'):
    results = []
    for year in range(2015, 2023):
        y = df[df['time'].dt.year == year]
        if len(y) > 30:
            ic, _ = spearmanr(y[col], y['actual'])
            results.append({'year': year, 'ic': ic, 'n': len(y)})
    return pd.DataFrame(results)

# Baseline
baseline = yearly_ic(merged.dropna(subset=['c16', 'actual']))

# Sector-relative C16
sector_rel = merged.dropna(subset=['c16_sector_rel', 'actual'])
df_srel = yearly_ic(sector_rel, 'c16_sector_rel')

# Compare: absolute vs relative
print(f'\nResults:')
print(f'{"Filter":<25} {"IC":>8} {"n":>10}')
print(f'{"-"*45}')
print(f'{"Baseline (absolute)":<25} {baseline["ic"].mean():+8.4f} {baseline["n"].sum():>10,}')
print(f'{"Sector-relative":<25} {df_srel["ic"].mean():+8.4f} {df_srel["n"].sum():>10,}')
print(f'\nDiff: {df_srel["ic"].mean() - baseline["ic"].mean():+.4f}')

df_srel.to_parquet('alpha-research-lab/analysis/artifacts/x224_sector_rel_results.parquet', index=False)
print(f'\nSaved: artifacts/x224_sector_rel_results.parquet')