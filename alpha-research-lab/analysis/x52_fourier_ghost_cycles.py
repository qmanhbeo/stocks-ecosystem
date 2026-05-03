#!/usr/bin/env python
"""X52: Fourier Ghost Cycles - test if C16 daily IC has hidden frequency."""
import pandas as pd
import numpy as np
from scipy.stats import spearmanr

order = pd.read_parquet('data/order_stats/cafef/order_stats_daily.parquet')
order['date'] = pd.to_datetime(order['date'])
order = order[order['date'].dt.year.isin(range(2015, 2023))]

order['ovr'] = (order['buy_order_volume'] - order['sell_order_volume']) / (order['buy_order_volume'] + order['sell_order_volume'])
order['c16'] = order.groupby('date')['ovr'].rank(pct=True)

daily_ics = []
for d, g in order.groupby('date'):
    g = g.dropna(subset=['c16', 'buy_sell_volume_imbalance'])
    if len(g) > 10:
        try:
            ic, _ = spearmanr(g['c16'], g['buy_sell_volume_imbalance'])
            daily_ics.append({'date': d, 'ic': ic})
        except:
            pass

daily_ic_series = pd.DataFrame(daily_ics).set_index('date')['ic'].sort_index()
n = len(daily_ic_series)

results = {'baseline': daily_ic_series.mean()}

for cycle in [3.5, 7, 14, 21]:
    phase = (np.arange(n) * cycle) % 1
    aligned = daily_ic_series[(phase < 0.25) | (phase > 0.75)]
    misaligned = daily_ic_series[(phase >= 0.25) & (phase <= 0.75)]
    results[f'{cycle}d_aligned'] = aligned.mean()
    results[f'{cycle}d_misaligned'] = misaligned.mean()
    results[f'{cycle}d_diff'] = aligned.mean() - misaligned.mean()

for k, v in results.items():
    print(f'{k}: {v:.4f}')

pd.DataFrame([results]).to_parquet('alpha-research-lab/analysis/artifacts/x52_fourier_cycles_results.parquet', index=False)
print('Saved: analysis/artifacts/x52_fourier_cycles_results.parquet')