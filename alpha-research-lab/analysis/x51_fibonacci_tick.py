#!/usr/bin/env python
"""X51: Fibonacci Tick - test if C16 stronger when price near whole number."""
import pandas as pd
import numpy as np
from scipy.stats import spearmanr

order = pd.read_parquet('data/order_stats/cafef/order_stats_daily.parquet')
order['date'] = pd.to_datetime(order['date'])
order = order[order['date'].dt.year.isin(range(2015, 2023))]

order['ovr'] = (order['buy_order_volume'] - order['sell_order_volume']) / (order['buy_order_volume'] + order['sell_order_volume'])
order['c16'] = order.groupby('date')['ovr'].rank(pct=True)

price_files = {}
def get_price(ticker):
    if ticker not in price_files:
        try:
            price_files[ticker] = pd.read_parquet(f'data/stock/gia_lich_su_{ticker}_1D.parquet', columns=['time', 'close'])
        except:
            return None
    return price_files[ticker]

results = {'baseline': [], 'near_whole': [], 'far_whole': []}

for date in order['date'].unique()[:200]:  # sample 200 days
    day = order[order['date'] == date]
    prices = get_price(day['ticker'].iloc[0])
    if prices is None:
        continue
    prices = prices[prices['time'] == date.strftime('%Y-%m-%d')]
    if prices.empty:
        continue
    close = prices['close'].iloc[0]
    
    # Distance to whole number in %
    pct = (close % 1) / close * 100
    near = pct < 0.618  # 1/phi
    
    for _, row in day.iterrows():
        p = get_price(row['ticker'])
        if p is None:
            continue
        pt = p[p['time'] == date.strftime('%Y-%m-%d')]
        if pt.empty:
            continue
        c = pt['close'].iloc[0]
        dist = (c % 1) / c * 100
        is_near = dist < 0.618
        
        try:
            ic, _ = spearmanr([row['c16']], [row['ovr']])
            results['baseline'].append(ic)
            if is_near:
                results['near_whole'].append(ic)
            else:
                results['far_whole'].append(ic)
        except:
            pass

print(f'X51: Fibonacci Tick')
print(f'Baseline: {np.mean(results["baseline"]):.4f} (n={len(results["baseline"])})')
print(f'Near whole (0.618%): {np.mean(results["near_whole"]):.4f} (n={len(results["near_whole"])})')
print(f'Far whole: {np.mean(results["far_whole"]):.4f} (n={len(results["far_whole"])})')

pd.DataFrame([results]).to_parquet('alpha-research-lab/analysis/artifacts/x51_fibonacci_tick_results.parquet', index=False)
print('Saved: analysis/artifacts/x51_fibonacci_tick_results.parquet')