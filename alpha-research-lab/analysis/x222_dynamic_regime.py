#!/usr/bin/env python
"""X222: Dynamic Liquidity Regime - test C16 by market regime."""
import pandas as pd
import numpy as np
from scipy.stats import spearmanr

S1 = 'data/features/xs_barrier_vol_1d_hose_full.parquet'
ORDER = 'data/order_stats/cafef/order_stats_daily.parquet'

print('='*60)
print('TEST: X222 dynamic_liquidity_regime')
print('='*60)

s1 = pd.read_parquet(S1, columns=['time', 'ticker', 'xs_proba', 'actual'])
s1['time'] = pd.to_datetime(s1['time'])
s1 = s1[s1['time'].dt.year.isin(range(2015, 2023))]

order = pd.read_parquet(ORDER)
order['date'] = pd.to_datetime(order['date'])
order = order[order['date'].dt.year.isin(range(2015, 2023))]
order['ovr'] = (order['buy_order_volume'] - order['sell_order_volume']) / (order['buy_order_volume'] + order['sell_order_volume'])
order['c16'] = order.groupby('date')['ovr'].rank(pct=True)
order = order.rename(columns={'date': 'time'})

merged = s1.merge(order, on=['time', 'ticker'], how='inner')
merged = merged.dropna(subset=['c16', 'actual', 'xs_proba'])

# Market-level liquidity: median xs_proba per day
daily_liq = merged.groupby('time')['xs_proba'].median().reset_index(name='market_liq')
daily_liq['regime'] = (daily_liq['market_liq'] > daily_liq['market_liq'].median()).astype(int)
merged = merged.merge(daily_liq[['time', 'regime']], on='time', how='left')

def yearly_ic(df):
    results = []
    for year in range(2015, 2023):
        y = df[df['time'].dt.year == year]
        if len(y) > 30:
            ic, _ = spearmanr(y['c16'], y['actual'])
            results.append({'year': year, 'ic': ic, 'n': len(y)})
    return pd.DataFrame(results)

# Overall
overall = yearly_ic(merged.dropna(subset=['c16', 'actual']))

# By regime
high_liq = merged[merged['regime'] == 1]
low_liq = merged[merged['regime'] == 0]

df_high = yearly_ic(high_liq)
df_low = yearly_ic(low_liq)

print(f'\nResults:')
print(f'{"Regime":<20} {"IC":>8} {"n":>10}')
print(f'{"-"*40}')
print(f'{"Overall":<20} {overall["ic"].mean():+8.4f} {overall["n"].sum():>10,}')
print(f'{"High market liquidity":<20} {df_high["ic"].mean():+8.4f} {df_high["n"].sum():>10,}')
print(f'{"Low market liquidity":<20} {df_low["ic"].mean():+8.4f} {df_low["n"].sum():>10,}')
print(f'\nDiff (high - low): {df_high["ic"].mean() - df_low["ic"].mean():+.4f}')

# Save
df_high.to_parquet('alpha-research-lab/analysis/artifacts/x222_high_regime.parquet', index=False)
df_low.to_parquet('alpha-research-lab/analysis/artifacts/x222_low_regime.parquet', index=False)
print(f'\nSaved: artifacts/x222_*_regime.parquet')