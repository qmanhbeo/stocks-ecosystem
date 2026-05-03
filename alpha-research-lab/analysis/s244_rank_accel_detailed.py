#!/usr/bin/env python
"""S244: Detailed rank_time_acceleration test with per-year IC."""
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
            n = len(test)
            results.append({'year': year, 'ic': ic, 'n': n, 'p': p})
    return results

def main():
    df = load_data()
    df = df.sort_values(['ticker', 'time'])
    df['rank_c16'] = df.groupby('time')['c16'].rank(pct=True)
    df['rank_c16_5d_lag'] = df.groupby('ticker')['rank_c16'].shift(5)
    df['rank_accel'] = df['rank_c16'] - df['rank_c16_5d_lag']
    df = df.dropna(subset=['rank_accel'])
    
    print("Year-by-Year IC comparison:")
    print("| Year | C16 Level | Rank Accel | Delta |")
    print("|------|----------|-----------|-------|")
    
    c16_results = wf_ic_detailed(df, 'c16')
    accel_results = wf_ic_detailed(df, 'rank_accel')
    
    c16_avg = np.mean([r['ic'] for r in c16_results])
    accel_avg = np.mean([r['ic'] for r in accel_results])
    
    for cr, ar in zip(c16_results, accel_results):
        print(f"| {cr['year']} | {cr['ic']:.4f} | {ar['ic']:.4f} | {ar['ic']-cr['ic']:+.4f} |")
    
    print(f"\n**AVG** | **{c16_avg:.4f}** | **{accel_avg:.4f}** | **{accel_avg-c16_avg:+.4f}** |")
    print(f"\nBaseline (C16): IC = {c16_avg:.4f}")
    print(f"Rank acceleration: IC = {accel_avg:.4f}")
    print(f"vs Random (~0): +{accel_avg:.4f}")
    print(f"vs C16: {((accel_avg/c16_avg)-1)*100:+.1f}%")

if __name__ == '__main__':
    main()