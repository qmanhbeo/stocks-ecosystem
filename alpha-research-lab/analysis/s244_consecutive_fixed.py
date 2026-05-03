#!/usr/bin/env python
"""Detailed consecutive down days test - FIXED."""
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
    
    # Market return per day (mean across all tickers)
    market_daily = df.groupby('time')['actual'].mean().reset_index()
    market_daily['market_return'] = market_daily['actual']
    market_daily['market_down'] = market_daily['market_return'] < 0
    
    # Shift market direction BY TIME, not ticker
    market_daily = market_daily.sort_values('time')
    market_daily['prev_market_down'] = market_daily['market_down'].shift(1)
    
    df = df.merge(market_daily[['time', 'market_down', 'prev_market_down']], on='time')
    
    # Test single day down vs consecutive 2-day down
    print("Market-down streak test:")
    print("| Year | All Days | Single Down | Consecutive 2d |")
    print("|------|----------|------------|-----------------|")
    
    baseline_results = wf_ic_by_year(df, 'c16')
    
    single_filter = df[df['market_down'] == True]
    single_results = wf_ic_by_year(single_filter, 'c16') if len(single_filter) > 100 else []
    
    streak_filter = df[(df['market_down'] == True) & (df['prev_market_down'] == True)]
    streak_results = wf_ic_by_year(streak_filter, 'c16') if len(streak_filter) > 100 else []
    
    for i, year in enumerate(range(2015, 2023)):
        b_ic = baseline_results[i]['ic'] if i < len(baseline_results) else np.nan
        s_ic = single_results[i]['ic'] if i < len(single_results) else np.nan
        st_ic = streak_results[i]['ic'] if i < len(streak_results) else np.nan
        print(f"| {year} | {b_ic:.4f} | {s_ic:.4f} | {st_ic:.4f} |")
    
    b_avg = np.nanmean([r['ic'] for r in baseline_results])
    s_avg = np.nanmean([r['ic'] for r in single_results]) if single_results else np.nan
    st_avg = np.nanmean([r['ic'] for r in streak_results]) if streak_results else np.nan
    
    print(f"\n**AVG** | **{b_avg:.4f}** | **{s_avg:.4f}** | **{st_avg:.4f}** |")
    print(f"\nBaseline (all): IC={b_avg:.4f}")
    print(f"Market down: IC={s_avg:.4f} ({((s_avg/b_avg)-1)*100:+.1f}%)")
    print(f"Consecutive 2d down: IC={st_avg:.4f} ({((st_avg/b_avg)-1)*100:+.1f}%)")

if __name__ == '__main__':
    main()