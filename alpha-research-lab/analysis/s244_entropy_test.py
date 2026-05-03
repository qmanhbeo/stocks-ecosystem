#!/usr/bin/env python
"""S244 c16_entropy_signal - sector dispersion."""
import pandas as pd
import numpy as np
from scipy.stats import spearmanr

ORDER = 'data/order_stats/cafef/order_stats_daily.parquet'
RETURNS = 'data/features/xs_barrier_vol_1d_hose_full.parquet'

def load_data():
    order = pd.read_parquet(ORDER)
    order['date'] = pd.to_datetime(order['date'])
    order = order[order['date'].dt.year.isin(range(2015, 2023))]
    order['ovr'] = (order['buy_order_volume'] - order['sell_order_volume']) / (order['buy_order_volume'] + order['sell_order_volume'])
    order['c16'] = order.groupby('date')['ovr'].rank(pct=True)
    order = order.rename(columns={'date': 'time'})
    
    ret = pd.read_parquet(RETURNS, columns=['time', 'ticker', 'actual'])
    ret['time'] = pd.to_datetime(ret['time'])
    ret = ret[ret['time'].dt.year.isin(range(2015, 2023))]
    
    merged = ret.merge(order[['time', 'ticker', 'c16']], on=['time', 'ticker'], how='inner')
    merged = merged.dropna(subset=['actual', 'c16'])
    return merged

def main():
    df = load_data()
    
    # Compute sector-level C16 dispersion (std of c16 per day)
    sector_stats = df.groupby('time')['c16'].agg(['std', 'mean']).reset_index()
    sector_stats['c16_entropy'] = sector_stats['std']  # proxy for entropy
    sector_stats = sector_stats.rename(columns={'time': 'time'})
    
    df = df.merge(sector_stats[['time', 'c16_entropy']], on='time')
    
    # Filter: high entropy = high dispersion
    high_entropy = df[df['c16_entropy'] > df['c16_entropy'].median()]
    low_entropy = df[df['c16_entropy'] <= df['c16_entropy'].median()]
    
    print("Sector dispersion test:")
    print(f"High dispersion: n={len(high_entropy)}")
    print(f"Low dispersion: n={len(low_entropy)}")
    
    ic1, p1 = spearmanr(high_entropy['c16'], high_entropy['actual'])
    ic2, p2 = spearmanr(low_entropy['c16'], low_entropy['actual'])
    
    print(f"IC (high dispersion): {ic1:.4f}")
    print(f"IC (low dispersion): {ic2:.4f}")
    print(f"Boost: {((ic1/ic2)-1)*100:+.1f}%")

if __name__ == '__main__':
    main()