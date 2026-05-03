#!/usr/bin/env python
"""X226: Market-State Dependent C16 - up vs down markets."""
import pandas as pd
import numpy as np
from scipy.stats import spearmanr

S1 = 'data/features/xs_barrier_vol_1d_hose_full.parquet'
ORDER = 'data/order_stats/cafef/order_stats_daily.parquet'

print('='*60)
print('TEST: X226 market_state_c16')
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

# Market return per day (use median actual as market proxy)
daily_return = merged.groupby('time')['actual'].median().reset_index(name='market_return')
daily_return['market_state'] = (daily_return['market_return'] > 0).astype(int)
merged = merged.merge(daily_return[['time', 'market_state']], on='time', how='left')

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

# In UP markets
up_market = merged[merged['market_state'] == 1]
df_up = yearly_ic(up_market)

# In DOWN markets
down_market = merged[merged['market_state'] == 0]
df_down = yearly_ic(down_market)

print(f'\nResults:')
print(f'{"Filter":<25} {"IC":>8} {"n":>10}')
print(f'{"-"*45}')
print(f'{"Baseline (all)":<25} {baseline["ic"].mean():+8.4f} {baseline["n"].sum():>10,}')
print(f'{"Market UP days":<25} {df_up["ic"].mean():+8.4f} {df_up["n"].sum():>10,}')
print(f'{"Market DOWN days":<25} {df_down["ic"].mean():+8.4f} {df_down["n"].sum():>10,}')
print(f'\nDiff (up - down): {df_up["ic"].mean() - df_down["ic"].mean():+.4f}')

df_up.to_parquet('alpha-research-lab/analysis/artifacts/x226_up_market.parquet', index=False)
df_down.to_parquet('alpha-research-lab/analysis/artifacts/x226_down_market.parquet', index=False)
print(f'\nSaved: artifacts/x226_*_market.parquet')