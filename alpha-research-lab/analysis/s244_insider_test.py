#!/usr/bin/env python
"""S244 insider_pressure_coherence test."""
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
            df = df[df['net_buy'] > 0]  # insider buying
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

def main():
    df = load_data()
    insider = load_insider_data()
    
    print(f"Insider buy records: {len(insider)}")
    print(f"C16 records: {len(df)}")
    
    # Merge: insider buy on date
    insider = insider.rename(columns={'published_date': 'time'})
    df = df.merge(insider[['ticker', 'time', 'net_buy']], on=['ticker', 'time'], how='left')
    df['insider_buy'] = df['net_buy'].notna()
    
    with_insider = df[df['insider_buy'] == True]
    without_insider = df[df['insider_buy'] == False]
    
    print(f"With insider buy: n={len(with_insider)}")
    print(f"Without insider buy: n={len(without_insider)}")
    
    if len(with_insider) > 50:
        ic, p = spearmanr(with_insider['c16'], with_insider['actual'])
        print(f"IC (insider buy day): {ic:.4f}")
    else:
        print("Insufficient data for insider buy test")
    
    if len(without_insider) > 100:
        ic2, p2 = spearmanr(without_insider['c16'], without_insider['actual'])
        print(f"IC (without insider buy): {ic2:.4f}")

if __name__ == '__main__':
    main()