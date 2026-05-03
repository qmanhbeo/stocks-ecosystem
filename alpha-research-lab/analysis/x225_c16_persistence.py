#!/usr/bin/env python
"""X225: C16 Persistence - today's pressure confirms tomorrow."""
import pandas as pd
import numpy as np
from scipy.stats import spearmanr

S1 = 'data/features/xs_barrier_vol_1d_hose_full.parquet'
ORDER = 'data/order_stats/cafef/order_stats_daily.parquet'

print('='*60)
print('TEST: X225 c16_persistence')
print('='*60)

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

# Yesterday's C16
merged['c16_lag1'] = merged.groupby('ticker')['c16'].shift(1)
merged['c16_lag1_confirmed'] = (merged['c16_lag1'] > 0.5).astype(int)

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

# Persisted: today high + yesterday confirmed high
persisted = merged[(merged['c16'] > 0.5) & (merged['c16_lag1'] > 0.5)]
df_pers = yearly_ic(persisted)

# Today only (no filter)
today_only = merged[merged['c16'] > 0.5]
df_today = yearly_ic(today_only)

print(f'\nResults:')
print(f'{"Filter":<25} {"IC":>8} {"n":>10}')
print(f'{"-"*45}')
print(f'{"Baseline":<25} {baseline["ic"].mean():+8.4f} {baseline["n"].sum():>10,}')
print(f'{"C16>50% today":<25} {df_today["ic"].mean():+8.4f} {df_today["n"].sum():>10,}')
print(f'{"C16>50% today AND yesterday":<25} {df_pers["ic"].mean():+8.4f} {df_pers["n"].sum():>10,}')

df_pers.to_parquet('alpha-research-lab/analysis/artifacts/x225_persistence_results.parquet', index=False)
print(f'\nSaved: artifacts/x225_persistence_results.parquet')