#!/usr/bin/env python
"""X223: Sector Convergence Contrarian - high C16 in fragmented sector."""
import pandas as pd
import numpy as np
from scipy.stats import spearmanr, kurtosis

S1 = 'data/features/xs_barrier_vol_1d_hose_full.parquet'
ORDER = 'data/order_stats/cafef/order_stats_daily.parquet'
SECTOR = 'data/features/sector_classification.parquet'

print('='*60)
print('TEST: X223 sector_convergence_contrarian')
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
merged = merged.dropna(subset=['c16', 'actual'])

# Sector kurtosis per day
daily_kurt = merged.groupby('time').apply(lambda g: kurtosis(g['c16'].dropna()) if len(g) > 10 else np.nan, include_groups=False)
daily_kurt = daily_kurt.reset_index(name='kurtosis')
daily_kurt['kurt_pct'] = daily_kurt['kurtosis'].rank(pct=True)
merged = merged.merge(daily_kurt[['time', 'kurt_pct']], on='time', how='left')

def yearly_ic(df):
    results = []
    for year in range(2015, 2023):
        y = df[df['time'].dt.year == year]
        if len(y) > 30:
            ic, _ = spearmanr(y['c16'], y['actual'])
            results.append({'year': year, 'ic': ic, 'n': len(y)})
    return pd.DataFrame(results)

# Baseline
baseline = yearly_ic(merged.dropna(subset=['c16', 'actual']))

# High sector kurtosis = fragmented sector
fragmented = merged[merged['kurt_pct'] > 0.8]
df_frag = yearly_ic(fragmented)

# High C16 IN fragmented sector = contrarian
contrarian = merged[(merged['kurt_pct'] > 0.8) & (merged['c16'] > 0.5)]
df_contra = yearly_ic(contrarian)

print(f'\nResults:')
print(f'{"Filter":<25} {"IC":>8} {"n":>10}')
print(f'{"-"*45}')
print(f'{"Baseline":<25} {baseline["ic"].mean():+8.4f} {baseline["n"].sum():>10,}')
print(f'{"Fragmented sector only":<25} {df_frag["ic"].mean():+8.4f} {df_frag["n"].sum():>10,}')
print(f'{"High C16 in fragmented":<25} {df_contra["ic"].mean():+8.4f} {df_contra["n"].sum():>10,}')

df_contra.to_parquet('alpha-research-lab/analysis/artifacts/x223_contrarian_results.parquet', index=False)
print(f'\nSaved: artifacts/x223_contrarian_results.parquet')