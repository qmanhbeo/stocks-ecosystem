#!/usr/bin/env python
"""S254: fundamentals_momentum - ROE/ROA as C16 quality predictor.

Hypothesis: High ROE/ROA stocks have better C16 IC (fundamentals predict order flow)
Data: fundamentals_cache/ (399 tickers) + order_stats/

Usage:
    python analysis/s254_fundamentals_test.py --signal roe
    python analysis/s254_fundamentals_test.py --signal roa
    python analysis/s254_fundamentals_test.py --signal all
"""
import argparse
import pandas as pd
import numpy as np
from scipy.stats import spearmanr
import glob

ORDER = 'data/order_stats/cafef/order_stats_daily.parquet'
RETURNS = 'data/features/xs_barrier_vol_1d_hose_full.parquet'
FUNDAMENTALS = 'data/fundamentals_cache/*.parquet'

def load_fundamentals(signal='roe'):
    """Load fundamentals: compute signal (ROE or ROA) per ticker-year."""
    files = glob.glob(FUNDAMENTALS)
    all_fund = []
    
    for f in files:
        df = pd.read_parquet(f)
        if 'ticker' not in df.columns:
            continue
        if signal == 'roe' and 'ROE (%)' in df.columns:
            all_fund.append(df[['ticker', 'yearReport', 'ROE (%)']])
        elif signal == 'roa' and 'ROA (%)' in df.columns:
            all_fund.append(df[['ticker', 'yearReport', 'ROA (%)']])
    
    if not all_fund:
        return pd.DataFrame()
    
    fund = pd.concat(all_fund, ignore_index=True)
    fund = fund.dropna(subset=['ROE (%)' if signal == 'roe' else 'ROA (%)'])
    fund = fund.rename(columns={'yearReport': 'year'})
    return fund

def load_order_data():
    order = pd.read_parquet(ORDER)
    order['date'] = pd.to_datetime(order['date'])
    order = order[order['date'].dt.year.isin(range(2015, 2023))]
    order['ovr'] = (order['buy_order_volume'] - order['sell_order_volume']) / (order['buy_order_volume'] + order['sell_order_volume'])
    order['c16'] = order.groupby('date')['ovr'].rank(pct=True)
    order = order.rename(columns={'date': 'time'})
    return order

def load_returns():
    ret = pd.read_parquet(RETURNS, columns=['time', 'ticker', 'actual'])
    ret['time'] = pd.to_datetime(ret['time'])
    ret = ret[ret['time'].dt.year.isin(range(2015, 2023))]
    return ret

def wf_ic_by_year(df, signal_col):
    """Walk-forward IC: train on years before Y, test on year Y."""
    results = []
    for year in range(2015, 2023):
        test = df[df['time'].dt.year == year]
        test = test.dropna(subset=[signal_col, 'actual'])
        if len(test) > 50:
            ic, p = spearmanr(test[signal_col], test['actual'])
            if not np.isnan(ic):
                results.append({'year': year, 'ic': ic, 'n': len(test)})
    return results

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--signal', type=str, required=True, choices=['roe', 'roa', 'all'])
    args = parser.parse_args()
    
    order = load_order_data()
    ret = load_returns()
    merged = ret.merge(order[['time', 'ticker', 'c16']], on=['time', 'ticker'], how='inner')
    merged = merged.dropna(subset=['actual', 'c16'])
    
    # Add year for merge
    merged['year'] = merged['time'].dt.year
    
    signals_to_test = ['roe', 'roa'] if args.signal == 'all' else [args.signal]
    
    print("=" * 60)
    print(f"S254: FUNDAMENTALS MOMENTUM TEST - {args.signal}")
    print("=" * 60)
    print("Method: IC(C16) on high fundamentals vs low fundamentals")
    print()
    
    for sig in signals_to_test:
        print(f"\n## {sig.upper()}")
        
        fund = load_fundamentals(sig)
        if fund.empty:
            print(f"NO {sig.upper()} DATA")
            continue
        
        # Merge fundamentals
        merged_fund = merged.merge(fund, on=['ticker', 'year'], how='inner')
        merged_fund = merged_fund.dropna(subset=['c16', sig.upper() + ' (%)'])
        
        if len(merged_fund) < 100:
            print(f"INSUFFICIENT DATA: {len(merged_fund)}")
            continue
        
        # Split: high vs low fundamentals (median per year)
        merged_fund['fund_rank'] = merged_fund.groupby('year')[sig.upper() + ' (%)'].rank(pct=True)
        
        high_fund = merged_fund[merged_fund['fund_rank'] > 0.7]
        low_fund = merged_fund[merged_fund['fund_rank'] < 0.3]
        
        high_results = wf_ic_by_year(high_fund, 'c16')
        low_results = wf_ic_by_year(low_fund, 'c16')
        
        if high_results and low_results:
            high_ic = np.mean([r['ic'] for r in high_results])
            low_ic = np.mean([r['ic'] for r in low_results])
            
            print(f"| Year | High {sig.upper()} IC | Low {sig.upper()} IC |")
            print(f"|------|------------------|----------------|")
            for hr, lr in zip(high_results, low_results):
                print(f"| {hr['year']} | {hr['ic']:.4f} | {lr['ic']:.4f} |")
            
            print(f"| **Mean** | **{high_ic:.4f}** | **{low_ic:.4f}** |")
            
            # Verdict
            if high_ic > low_ic + 0.02:
                boost = ((high_ic / low_ic) - 1) * 100
                print(f"**VERDICT: PASSED (+{boost:.1f}%)**")
            elif high_ic > 0.05 and high_ic > low_ic:
                print(f"**VERDICT: MIXED (high > 0.05 but boost small)**")
            else:
                print(f"**VERDICT: FAILED (no fundamentals edge)**")
        else:
            print("NO VALID RESULTS")

if __name__ == '__main__':
    main()