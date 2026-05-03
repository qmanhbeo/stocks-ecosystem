#!/usr/bin/env python
"""X53v2: Liquid C16 - filter C16 by stock liquidity (price movement)."""
import pandas as pd
import numpy as np
from scipy.stats import spearmanr

S1 = 'data/features/xs_barrier_vol_1d_hose_full.parquet'
ORDER = 'data/order_stats/cafef/order_stats_daily.parquet'

def compute_liquid_c16():
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

    merged['c16_pct'] = merged.groupby('time')['c16'].rank(pct=True)
    merged['move_pct'] = merged.groupby('time')['xs_proba'].rank(pct=True)

    results = []
    for year in range(2015, 2023):
        y = merged[merged['time'].dt.year == year]
        
        all_df = y.dropna(subset=['c16', 'actual'])
        base_ic = spearmanr(all_df['c16'], all_df['actual'])[0]
        
        liquid = y[(y['c16_pct'] > 0.5) & (y['move_pct'] > 0.8)]
        liq_ic = spearmanr(liquid['c16'], liquid['actual'])[0] if len(liquid) > 30 else np.nan
        
        results.append({'year': year, 'baseline': base_ic, 'liquid_c16': liq_ic, 'diff': liq_ic - base_ic, 'n': len(liquid)})

    return pd.DataFrame(results)

if __name__ == '__main__':
    df = compute_liquid_c16()
    print('Liquid C16 (C16>50% + move>80%):')
    print(df.to_string(index=False))
    print(f'\nAvg baseline: {df["baseline"].mean():.4f}')
    print(f'Avg liquid:    {df["liquid_c16"].mean():.4f}')
    print(f'Avg diff:     {df["diff"].mean():+.4f}')
    
    df.to_parquet('alpha-research-lab/analysis/artifacts/x53v2_liquid_c16_results.parquet', index=False)
    print('\nSaved: analysis/artifacts/x53v2_liquid_c16_results.parquet')