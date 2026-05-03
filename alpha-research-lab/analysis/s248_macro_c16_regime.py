#!/usr/bin/env python
"""S248: Macro-C16 Regime - C16 conditioned on macro regime."""
import pandas as pd
import numpy as np
from scipy.stats import spearmanr

C16 = 'data/features/xs_order_pressure_daily.parquet'
LABEL = 'data/features/xs_barrier_vol_1d_hose_full.parquet'
MACRO = 'data/features/macro_regime_daily.parquet'

print('='*60)
print('TEST: S248 macro_c16_regime')
print('='*60)

c16 = pd.read_parquet(C16, columns=['time', 'ticker', 'order_volume_ratio_rank'])
c16['time'] = pd.to_datetime(c16['time'])
c16 = c16[c16['time'].dt.year.isin(range(2015, 2023))]

label = pd.read_parquet(LABEL, columns=['time', 'ticker', 'actual'])
label['time'] = pd.to_datetime(label['time'])
label = label[label['time'].dt.year.isin(range(2015, 2023))]

macro = pd.read_parquet(MACRO)
macro['time'] = pd.to_datetime(macro['time'])
macro = macro[macro['time'].dt.year.isin(range(2015, 2023))]

merged = c16.merge(label, on=['time', 'ticker'], how='inner')
merged = merged.merge(macro[['time', 'vix_level', 'breadth_score', 'yield_curve']], on='time', how='left')
merged = merged.dropna(subset=['order_volume_ratio_rank', 'actual', 'vix_level'])

# Regime: VIX > 25 = BEAR, VIX < 20 = BULL, 20-25 = TRANSITION
# Also use breadth_score: < 0 = fear, > 0 = greed
merged['vix_regime'] = pd.cut(merged['vix_level'], bins=[0, 20, 25, 100], labels=['BULL', 'TRANSITION', 'BEAR'])
merged['breadth_regime'] = np.where(merged['breadth_score'] < -0.2, 'FEAR', np.where(merged['breadth_score'] > 0.2, 'GREED', 'NEUTRAL'))

# Market state
daily = merged.groupby('time')['actual'].median().reset_index(name='market_return')
daily['market_direction'] = (daily['market_return'] < 0).astype(int)
merged = merged.merge(daily[['time', 'market_direction']], on='time', how='left')

def yearly_ic(df):
    results = []
    for year in range(2015, 2023):
        y = df[df['time'].dt.year == year]
        if len(y) > 30:
            # Baseline
            ic_all, _ = spearmanr(y['order_volume_ratio_rank'], y['actual'])
            
            # VIX regimes
            bull = y[y['vix_regime'] == 'BULL']
            ic_bull = spearmanr(bull['order_volume_ratio_rank'], bull['actual'])[0] if len(bull) > 30 else np.nan
            
            bear = y[y['vix_regime'] == 'BEAR']
            ic_bear = spearmanr(bear['order_volume_ratio_rank'], bear['actual'])[0] if len(bear) > 30 else np.nan
            
            trans = y[y['vix_regime'] == 'TRANSITION']
            ic_trans = spearmanr(trans['order_volume_ratio_rank'], trans['actual'])[0] if len(trans) > 30 else np.nan
            
            # Breadth regimes
            fear = y[y['breadth_regime'] == 'FEAR']
            ic_fear = spearmanr(fear['order_volume_ratio_rank'], fear['actual'])[0] if len(fear) > 30 else np.nan
            
            # In down market separately
            down = y[y['market_direction'] == 0]
            ic_down = spearmanr(down['order_volume_ratio_rank'], down['actual'])[0] if len(down) > 30 else np.nan
            
            results.append({
                'year': year, 'ic_all': ic_all, 'ic_bull': ic_bull, 'ic_bear': ic_bear,
                'ic_trans': ic_trans, 'ic_fear': ic_fear, 'ic_down': ic_down, 'n': len(y)
            })
    return pd.DataFrame(results)

results = yearly_ic(merged)

print(f'\nResults:')
print(f'{"Year":<6} {"IC_all":>8} {"IC_BULL":>8} {"IC_BEAR":>8} {"IC_FEAR":>8} {"n":>10}')
print('-'*52)
for _, r in results.iterrows():
    print(f"{int(r['year']):<6} {r['ic_all']:+8.4f} {r['ic_bull']:+8.4f} {r['ic_bear']:+8.4f} {r['ic_fear']:+8.4f} {int(r['n']):>10,}")

ic_all = results['ic_all'].mean()
ic_bull = results['ic_bull'].mean()
ic_bear = results['ic_bear'].mean()
ic_trans = results['ic_trans'].mean()
ic_fear = results['ic_fear'].mean()
ic_down = results['ic_down'].mean()

print(f'\nAverages:')
print(f'  All markets:     IC = {ic_all:+.4f}')
print(f'  VIX BULL:       IC = {ic_bull:+.4f}')
print(f'  VIX BEAR:       IC = {ic_bear:+.4f}')
print(f'  VIX TRANS:      IC = {ic_trans:+.4f}')
print(f'  Breadth FEAR:    IC = {ic_fear:+.4f}')
print(f'  Down days:      IC = {ic_down:+.4f}')

baseline = 0.078
# Check best regime
best = max(ic_bull, ic_bear, ic_trans, ic_fear)
if best > baseline + 0.03:
    verdict = f'PASSED - regime matters (best: {best:+.4f})'
    tier = 2
elif ic_down > baseline + 0.02:
    verdict = 'PASSED - down market'
    tier = 2
else:
    verdict = 'WEAK - no regime boost'

print(f'\nVerdict: {verdict}')
print(f'vs C16 baseline: {best - baseline:+.4f}')

results.to_parquet('/home/manh/stocks-ecosystem/alpha-research-lab/analysis/artifacts/s248_macro_c16_regime.parquet', index=False)
print('\nSaved: artifacts/s248_macro_c16_regime.parquet')