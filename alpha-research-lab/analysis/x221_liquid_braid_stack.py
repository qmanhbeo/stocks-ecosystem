#!/usr/bin/env python
"""X221: Liquid+Braid Stack - double filter (C16>50% + move>80% + sector kurtosis<20%)."""
import pandas as pd
import numpy as np
from scipy.stats import spearmanr, kurtosis

S1 = 'data/features/xs_barrier_vol_1d_hose_full.parquet'
ORDER = 'data/order_stats/cafef/order_stats_daily.parquet'
SECTOR = 'data/features/sector_classification.parquet'

print('='*60)
print('TEST: X221 liquid_braid_stack')
print('='*60)

# Load data
s1 = pd.read_parquet(S1, columns=['time', 'ticker', 'xs_proba', 'actual'])
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
merged = merged.dropna(subset=['c16', 'actual', 'xs_proba'])

# Movement percentile
merged['move_pct'] = merged.groupby('time')['xs_proba'].rank(pct=True)

# Sector kurtosis per day
daily_kurt = merged.groupby('time').apply(lambda g: kurtosis(g['c16'].dropna()) if len(g['c16'].dropna()) > 10 else np.nan)
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

# Test combinations
baseline = merged.dropna(subset=['c16', 'actual'])
c16_only = merged[merged['c16'] > 0.5]
x53 = merged[(merged['c16'] > 0.5) & (merged['move_pct'] > 0.8)]
x54 = merged[merged['kurt_pct'] < 0.2]
x53_x54 = merged[(merged['c16'] > 0.5) & (merged['kurt_pct'] < 0.2)]
stack = merged[(merged['c16'] > 0.5) & (merged['move_pct'] > 0.8) & (merged['kurt_pct'] < 0.2)]

df_base = yearly_ic(baseline)
df_c16 = yearly_ic(c16_only)
df_x53 = yearly_ic(x53)
df_x54 = yearly_ic(x54)
df_x53_x54 = yearly_ic(x53_x54)
df_stack = yearly_ic(stack)

print(f'\nResults:')
print(f'{"Filter":<20} {"IC":>8} {"n":>10}')
print(f'{"-"*40}')
print(f'{"Baseline":<20} {df_base["ic"].mean():+8.4f} {df_base["n"].sum():>10,}')

print(f'{"C16>50% only":<20} {df_c16["ic"].mean():+8.4f} {df_c16["n"].sum():>10,}')
print(f'{"X53 (C16+liquid)":<20} {df_x53["ic"].mean():+8.4f} {df_x53["n"].sum():>10,}')
print(f'{"X54 (C16+braid)":<20} {df_x54["ic"].mean():+8.4f} {df_x54["n"].sum():>10,}')
print(f'{"X53+X54 stack":<20} {df_x53_x54["ic"].mean():+8.4f} {df_x53_x54["n"].sum():>10,}')
print(f'{"FULL STACK":<20} {df_stack["ic"].mean():+8.4f} {df_stack["n"].sum():>10,}')

# Save artifact
df_stack.to_parquet('alpha-research-lab/analysis/artifacts/x221_liquid_braid_stack.parquet', index=False)
print(f'\nSaved: artifacts/x221_liquid_braid_stack.parquet')