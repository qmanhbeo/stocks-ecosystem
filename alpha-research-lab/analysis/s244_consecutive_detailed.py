#!/usr/bin/env python
"""Detailed consecutive down days test."""
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

def wf_ic_detailed(df, signal):
    results = []
    for year in range(2015, 2023):
        test = df[df['time'].dt.year == year]
        test = test.dropna(subset=[signal, 'actual'])
        if len(test) > 50:
            ic, p = spearmanr(test[signal], test['actual'])
            results.append({'year': year, 'ic': ic, 'n': len(test)})
    return results

def main():
    df = load_data()
    
    # Market return per day
    df['market_return'] = df.groupby('time')['actual'].transform('mean')
    df['market_down'] = df['market_return'] < 0
    
    # Sort and compute lag
    df = df.sort_values(['ticker', 'time'])
    df['prev_market_down'] = df.groupby('ticker')['market_down'].shift(1)
    
    # Single day down vs consecutive
    df['single_down'] = df['market_down']
    df['streak_2d'] = df['market_down'] & df['prev_market_down']
    
    # Test both
    results = []
    for name, filter_col in [('single_day_down', 'single_down'), ('consecutive_2d', 'streak_2d')]:
        filtered = df[df[filter_col] == True]
        filtered = filtered.dropna(subset=['c16', 'actual'])
        n = len(filtered)
        if n > 100:
            ic_results = wf_ic_detailed(filtered, 'c16')
            avg_ic = np.mean([r['ic'] for r in ic_results])
            results.append((name, n, avg_ic))
            print(f"{name}: n={n}, IC={avg_ic:.4f}")
        else:
            print(f"{name}: n={n} - insufficient")

if __name__ == '__main__':
    main()