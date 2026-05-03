#!/usr/bin/env python
"""X54: Braid Divergence - sector-wide pressure unanimity filter."""
import pandas as pd
import numpy as np
from scipy.stats import spearmanr, kurtosis

S1 = 'data/features/xs_barrier_vol_1d_hose_full.parquet'
ORDER = 'data/order_stats/cafef/order_stats_daily.parquet'
SECTOR = 'data/features/sector_classification.parquet'

def compute_braid_c16():
    s1 = pd.read_parquet(S1, columns=['time', 'ticker', 'actual'])
    s1['time'] = pd.to_datetime(s1['time'])
    s1 = s1[s1['time'].dt.year.isin(range(2015, 2023))]

    sector = pd.read_parquet(SECTOR)
    sector = sector.rename(columns={'symbol': 'ticker'})
    s1 = s1.merge(sector[['ticker', 'icb_name3']], on='ticker', how='inner')

    order = pd.read_parquet(ORDER)
    order['date'] = pd.to_datetime(order['date'])
    order = order[order['date'].dt.year.isin(range(2015, 2023))]
    order['ovr'] = (order['buy_order_volume'] - order['sell_order_volume']) / (order['buy_order_volume'] + order['sell_order_volume'])
    order['c16'] = order.groupby('date')['ovr'].rank(pct=True)
    order = order.rename(columns={'date': 'time'})

    s1 = s1.merge(order, on=['time', 'ticker'], how='inner')
    s1 = s1.dropna(subset=['c16', 'actual', 'icb_name3'])

    daily_kurt = []
    for d, g in s1.groupby('time'):
        k = kurtosis(g['c16'].dropna())
        daily_kurt.append({'time': d, 'kurtosis': k})

    daily_kurt = pd.DataFrame(daily_kurt)
    daily_kurt['kurt_pct'] = daily_kurt['kurtosis'].rank(pct=True)
    s1 = s1.merge(daily_kurt[['time', 'kurt_pct']], on='time', how='left')

    results = []
    for year in range(2015, 2023):
        y = s1[s1['time'].dt.year == year]
        
        all_df = y.dropna(subset=['c16', 'actual'])
        base_ic = spearmanr(all_df['c16'], all_df['actual'])[0]
        
        unanimous = y[y['kurt_pct'] < 0.2]
        uni_ic = spearmanr(unanimous['c16'], unanimous['actual'])[0] if len(unanimous) > 30 else np.nan
        
        results.append({'year': year, 'baseline': base_ic, 'unanimous': uni_ic, 'diff': uni_ic - base_ic})

    return pd.DataFrame(results)

if __name__ == '__main__':
    df = compute_braid_c16()
    print('Braid Divergence (low sector kurtosis):')
    print(df.to_string(index=False))
    print(f'\nAvg baseline:   {df["baseline"].mean():.4f}')
    print(f'Avg unanimous: {df["unanimous"].mean():.4f}')
    print(f'Avg diff:      {df["diff"].mean():+.4f}')
    
    df.to_parquet('alpha-research-lab/analysis/artifacts/x54_braid_divergence_results.parquet', index=False)
    print('\nSaved: analysis/artifacts/x54_braid_divergence_results.parquet')