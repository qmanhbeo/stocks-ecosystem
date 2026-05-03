#!/usr/bin/env python
"""S244 consecutive down days test - FIXED with barrier direction."""
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
    
    # Barrier: >0.5 = UP, <0.5 = DOWN
    market_daily = df.groupby('time')['actual'].mean().reset_index()
    market_daily = market_daily.rename(columns={'actual': 'market_return'})
    market_daily['market_up'] = market_daily['market_return'] > 0.5  # median barrier
    
    market_daily = market_daily.sort_values('time')
    market_daily['prev_market_up'] = market_daily['market_up'].shift(1)
    
    # Merge back
    df = df.merge(market_daily[['time', 'market_up', 'prev_market_up']], on='time')
    
    # Filter down days (< 0.5 = underperform)
    down_df = df[df['market_up'] == False]  # underperform days
    streak_df = df[(df['market_up'] == False) & (df['prev_market_up'] == False)]  # consecutive down
    
    base_results = wf_ic_by_year(df, 'c16')
    down_results = wf_ic_by_year(down_df, 'c16') if len(down_df) > 100 else []
    streak_results = wf_ic_by_year(streak_df, 'c16') if len(streak_df) > 100 else []
    
    print("Market underperform streak test (barrier < 0.5):")
    print("| Year | All | Underperform | Consecutive |")
    print("|------|-----|-------------|------------|")
    
    for i, year in enumerate(range(2015, 2023)):
        b = base_results[i]['ic'] if i < len(base_results) else np.nan
        d = down_results[i]['ic'] if i < len(down_results) else np.nan
        s = streak_results[i]['ic'] if i < len(streak_results) else np.nan
        print(f"| {year} | {b:.4f} | {d:.4f} | {s:.4f} |")
    
    b_avg = np.nanmean([r['ic'] for r in base_results])
    d_avg = np.nanmean([r['ic'] for r in down_results]) if down_results else np.nan
    s_avg = np.nanmean([r['ic'] for r in streak_results]) if streak_results else np.nan
    
    print(f"\n**AVG** | **{b_avg:.4f}** | **{d_avg:.4f}** | **{s_avg:.4f}** |")
    print(f"\nBaseline: IC={b_avg:.4f}")
    print(f"Underperform days: IC={d_avg:.4f} ({((d_avg/b_avg)-1)*100:+.1f}%)")
    print(f"Consecutive underperform: IC={s_avg:.4f} ({((s_avg/b_avg)-1)*100:+.1f}%)")

if __name__ == '__main__':
    main()