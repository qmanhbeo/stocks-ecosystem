#!/usr/bin/env python
"""X232: Triple Storm universal amplifier test.

Usage:
    python x232_triple_test.py                    # test default signals
    python x232_triple_test.py --signals c4 c12 c13   # test specific signals
    python x232_triple_test.py --matrix --signals c4 c12 c13  # use signal matrix
"""
import argparse
import pandas as pd
import numpy as np
from scipy.stats import spearmanr

S1 = 'data/features/xs_barrier_vol_1d_hose_full.parquet'
ORDER = 'data/order_stats/cafef/order_stats_daily.parquet'
MATRIX = 'data/features/xs_rl_signal_matrix.parquet'

def build_triple_filters(merged, signal_for_liquid='c16'):
    """Build Triple Storm conditions: liquid + down + divergence."""
    # Market state
    daily = merged.groupby('time')['actual'].mean().reset_index(name='win_rate')
    daily['market_down'] = (daily['win_rate'] < 0.5).astype(int)
    merged = merged.merge(daily[['time', 'market_down']], on='time')
    
    # Liquid - use provided signal column for liquid calculation
    sig_col = signal_for_liquid if signal_for_liquid in merged.columns else 's1_proba'
    merged['move'] = merged.groupby('ticker')[sig_col].transform(
        lambda x: x.rolling(20, min_periods=10).std())
    merged['liquid'] = (merged['move'] > merged['move'].quantile(0.8)).astype(int)
    
    # Divergence
    merged['ret_lag1'] = merged.groupby('ticker')['actual'].shift(1)
    merged = merged.dropna(subset=['ret_lag1'])
    merged['price_dir'] = (merged['ret_lag1'] > 0).astype(int)
    merged['c16_dir'] = (merged[sig_col] > 0.5).astype(int)
    merged['divergence'] = (merged['price_dir'] != merged['c16_dir']).astype(int)
    
    merged['triple'] = (merged['liquid']==1) & (merged['market_down']==1) & (merged['divergence']==1)
    merged['dual'] = (merged['liquid']==1) & (merged['market_down']==1)
    return merged

def walk_forward_ic(df, signal_col):
    """Compute IC per year, then average."""
    results = []
    for year in range(2015, 2023):
        test = df[df['time'].dt.year == year]
        if len(test) > 100:
            test = test.dropna(subset=[signal_col, 'actual'])
            if len(test) > 50:
                ic, p = spearmanr(test[signal_col], test['actual'])
                if not np.isnan(ic):
                    results.append({'year': year, 'ic': ic, 'n': len(test)})
    return pd.DataFrame(results)

def test_signal_from_matrix(signals, signal_for_liquid='s1_proba'):
    """Test signals from signal matrix."""
    cols = ['time', 'ticker', 'actual', signal_for_liquid] + signals
    df = pd.read_parquet(MATRIX, columns=cols)
    df['time'] = pd.to_datetime(df['time'])
    df = df[df['time'].dt.year.isin(range(2015, 2023))]
    df = df.dropna(subset=['actual'])
    df = build_triple_filters(df, signal_for_liquid)
    
    results = []
    for sig in signals:
        if sig not in df.columns:
            print(f'{sig}: NOT FOUND')
            continue
            
        wf_base = walk_forward_ic(df, sig)
        base_ic = wf_base['ic'].mean()
        
        wf_triple = walk_forward_ic(df[df['triple']==1], sig)
        triple_ic = wf_triple['ic'].mean() if len(wf_triple) > 0 else np.nan
        
        boost = (triple_ic / base_ic - 1) * 100 if base_ic > 0 and not np.isnan(triple_ic) else np.nan
        
        n = df['triple'].sum()
        verdict = 'PASSED' if boost > 20 else 'FAILED'
        print(f'{sig}: base={base_ic:.4f}, triple={triple_ic:.4f}, boost={boost:.0f}%, n={n} [{verdict}]')
        
        results.append({
            'signal': sig, 'base_ic': base_ic, 'triple_ic': triple_ic,
            'boost': boost, 'n': n, 'pass': boost > 20
        })
    return results

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Test signals with Triple Storm')
    parser.add_argument('--signals', nargs='+', default=['c4_oc_asym_5d', 'c12_gap_absorb_3', 'c13_compress_blowoff_2'],
                    help='Signal columns to test')
    parser.add_argument('--matrix', action='store_true', help='Use signal matrix (default: use order_stats')
    parser.add_argument('--liquid-signal', default='s1_proba', help='Signal for liquid calculation')
    args = parser.parse_args()
    
    results = test_signal_from_matrix(args.signals, args.liquid_signal)
    print(f"\nDone tested {len(results)} signals")