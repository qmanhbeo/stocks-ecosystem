#!/usr/bin/env python
"""S244 dividend_signal_momentum - detailed walk-forward."""
import pandas as pd
import numpy as np
from scipy.stats import spearmanr
import glob

ORDER = 'data/order_stats/cafef/order_stats_daily.parquet'
RETURNS = 'data/features/xs_barrier_vol_1d_hose_full.parquet'
DIVIDEND = 'data/dividend_cache/*.parquet'

def load_dividend_dates():
    files = glob.glob(DIVIDEND)
    all_events = []
    for f in files:
        df = pd.read_parquet(f)
        if 'record_date' in df.columns:
            all_events.append(df[['ticker', 'record_date']])
    events = pd.concat(all_events, ignore_index=True)
    events = events.dropna(subset=['record_date'])
    events['record_date'] = pd.to_datetime(events['record_date'])
    events = events[events['record_date'].dt.year.isin(range(2015, 2023))]
    events['has_dividend_30d'] = True
    return events[['ticker', 'record_date', 'has_dividend_30d']]

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
            results.append({'year': year, 'ic': ic, 'n': len(test)})
    return results

def main():
    df = load_data()
    div = load_dividend_dates()
    
    df = df.merge(div, left_on=['ticker', 'time'], right_on=['ticker', 'record_date'], how='left')
    df['has_dividend_30d'] = df['has_dividend_30d'].fillna(False)
    
    with_div = df[df['has_dividend_30d'] == True]
    without_div = df[df['has_dividend_30d'] == False]
    
    print("Dividend proximity test (30d window):")
    print("| Year | With Div | Without Div |")
    print("|------|----------|-------------|")
    
    with_results = wf_ic_by_year(with_div, 'c16')
    without_results = wf_ic_by_year(without_div, 'c16')
    
    for i, year in enumerate(range(2015, 2023)):
        w = with_results[i]['ic'] if i < len(with_results) else np.nan
        wo = without_results[i]['ic'] if i < len(without_results) else np.nan
        print(f"| {year} | {w:.4f} | {wo:.4f} |")
    
    w_avg = np.nanmean([r['ic'] for r in with_results])
    wo_avg = np.nanmean([r['ic'] for r in without_results])
    
    print(f"\n**AVG** | **{w_avg:.4f}** | **{wo_avg:.4f}** |")
    print(f"\nWith dividend: IC={w_avg:.4f}")
    print(f"Without dividend: IC={wo_avg:.4f}")
    print(f"Boost: {((w_avg/wo_avg)-1)*100:+.1f}%")

if __name__ == '__main__':
    main()