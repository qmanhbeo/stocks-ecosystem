#!/usr/bin/env python
"""S244 insider_pressure_coherence - LEADING LAG test."""
import pandas as pd
import numpy as np
from scipy.stats import spearmanr
import glob

ORDER = 'data/order_stats/cafef/order_stats_daily.parquet'
RETURNS = 'data/features/xs_barrier_vol_1d_hose_full.parquet'
INSIDER = 'data/insider_cache/*.parquet'

def load_insider_data():
    files = glob.glob(INSIDER)
    all_insider = []
    for f in files:
        df = pd.read_parquet(f)
        if 'RealBuyVolume' in df.columns:
            df['net_buy'] = df['RealBuyVolume'] - df['RealSellVolume']
            all_insider.append(df[['ticker', 'published_date', 'net_buy']])
    insider = pd.concat(all_insider, ignore_index=True)
    insider['published_date'] = pd.to_datetime(insider['published_date'])
    insider = insider[insider['published_date'].dt.year.isin(range(2015, 2023))]
    return insider

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

def wf_ic_by_year(df, signal):
    results = []
    for year in range(2015, 2023):
        test = df[df['time'].dt.year == year]
        test = test.dropna(subset=[signal, 'actual'])
        if len(test) > 50:
            ic, p = spearmanr(test[signal], test['actual'])
            results.append({'year': year, 'ic': ic})
    return results

def main():
    df = load_data()
    insider = load_insider_data()
    
    print("Test: Insider BUY on T-1 predicts C16 signal quality on T")
    
    # Lead: insider on previous day
    insider = insider.rename(columns={'published_date': 'time'})
    insider['next_day'] = insider['time'] + pd.Timedelta(days=1)
    insider = insider.rename(columns={'next_day': 'time_next'})
    
    df = df.merge(insider[['ticker', 'time', 'time_next', 'net_buy']], 
                left_on=['ticker', 'time'], 
                right_on=['ticker', 'time_next'], 
                how='left')
    df['insider_buy_led'] = df['net_buy'] > 0
    
    with_insider = df[df['insider_buy_led'] == True]
    without_insider = df[df['insider_buy_led'] == False]
    
    print(f"With prior insider buy: n={len(with_insider)}")
    print(f"Without prior insider buy: n={len(without_insider)}")
    
    print("\nWalk-forward IC:")
    print("| Year | With Insider Lead | Without |")
    print("|------|-----------------|---------|")
    
    with_results = wf_ic_by_year(with_insider, 'c16') if len(with_insider) > 100 else []
    without_results = wf_ic_by_year(without_insider, 'c16')
    
    for i, year in enumerate(range(2015, 2023)):
        w = with_results[i]['ic'] if i < len(with_results) else np.nan
        wo = without_results[i]['ic'] if i < len(without_results) else np.nan
        print(f"| {year} | {w:.4f} | {wo:.4f} |")
    
    w_avg = np.nanmean([r['ic'] for r in with_results]) if with_results else np.nan
    wo_avg = np.nanmean([r['ic'] for r in without_results])
    
    print(f"\n**AVG** | **{w_avg:.4f}** | **{wo_avg:.4f}** |")
    print(f"\nWith prior insider: IC={w_avg:.4f}")
    print(f"Without prior insider: IC={wo_avg:.4f}")
    if not np.isnan(w_avg):
        print(f"Boost: {((w_avg/wo_avg)-1)*100:+.1f}%")

if __name__ == '__main__':
    main()