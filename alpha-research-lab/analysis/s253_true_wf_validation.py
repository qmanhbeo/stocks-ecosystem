#!/usr/bin/env python
"""S253: True Rolling Walk-Forward IC Validation.

Purpose: validate top signals with TRUE rolling holdout (train T-2,T-1 → test T)
to address skepticism about overfitting in prior runs.

Usage:
    python analysis/s253_true_wf_validation.py --signal insider_lead
    python analysis/s253_true_wf_validation.py --signal consecutive_down
    python analysis/s253_true_wf_validation.py --signal down_market_c16
    python analysis/s253_true_wf_validation.py --signal all
"""
import argparse
import pandas as pd
import numpy as np
from scipy.stats import spearmanr
import glob

ORDER = 'data/order_stats/cafef/order_stats_daily.parquet'
RETURNS = 'data/features/xs_barrier_vol_1d_hose_full.parquet'
INSIDER = 'data/insider_cache/*.parquet'

def load_order_data():
    order = pd.read_parquet(ORDER)
    order['date'] = pd.to_datetime(order['date'])
    order = order[order['date'].dt.year.isin(range(2015, 2023))]
    order['ovr'] = (order['buy_order_volume'] - order['sell_order_volume']) / (order['buy_order_volume'] + order['sell_order_volume'])
    order['c16'] = order.groupby('date')['ovr'].rank(pct=True)
    order['volume_rank'] = order.groupby('date')['buy_order_count'].rank(pct=True)
    order = order.rename(columns={'date': 'time'})
    return order

def load_returns():
    ret = pd.read_parquet(RETURNS, columns=['time', 'ticker', 'actual'])
    ret['time'] = pd.to_datetime(ret['time'])
    ret = ret[ret['time'].dt.year.isin(range(2015, 2023))]
    return ret

def load_insider_data():
    files = glob.glob(INSIDER)
    all_insider = []
    for f in files:
        df = pd.read_parquet(f)
        if 'RealBuyVolume' in df.columns:
            df['net_buy'] = df['RealBuyVolume'] - df['RealSellVolume']
            all_insider.append(df[['ticker', 'published_date', 'net_buy']])
    if not all_insider:
        return pd.DataFrame()
    insider = pd.concat(all_insider, ignore_index=True)
    insider['published_date'] = pd.to_datetime(insider['published_date'])
    insider = insider[insider['published_date'].dt.year.isin(range(2015, 2023))]
    return insider

def rolling_wf_ic(df, signal_col, train_years=[1, 2]):
    """TRUE walk-forward: train on years before T, test on year T.
    
    train_years: list of years to include in training (e.g., [1,2] = T-2, T-1)
    """
    years = sorted(df['time'].dt.year.unique())
    results = []
    
    for i, test_year in enumerate(years):
        train_years_available = [years[j] for j in train_years if j <= i]
        if not train_years_available:
            continue
            
        train = df[df['time'].dt.year.isin(train_years_available)]
        test = df[df['time'].dt.year == test_year]
        
        train = train.dropna(subset=[signal_col, 'actual'])
        test = test.dropna(subset=[signal_col, 'actual'])
        
        if len(train) < 100 or len(test) < 50:
            continue
        
        # Compute signal statistics from training data
        signal_mean = train[signal_col].mean()
        signal_std = train[signal_col].std()
        
        # Apply to test data
        test_copy = test.copy()
        if signal_std > 0:
            test_copy['signal_z'] = (test_copy[signal_col] - signal_mean) / signal_std
        else:
            test_copy['signal_z'] = test_copy[signal_col]
        
        ic, p = spearmanr(test_copy['signal_z'], test_copy['actual'])
        if not np.isnan(ic):
            results.append({
                'train_years': train_years_available,
                'test_year': test_year,
                'ic': ic,
                'p_value': p,
                'n_train': len(train),
                'n_test': len(test_copy)
            })
    
    return results

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--signal', type=str, required=True, 
                      choices=['insider_lead', 'consecutive_down', 'down_market_c16', 'all'])
    args = parser.parse_args()
    
    order = load_order_data()
    ret = load_returns()
    merged = ret.merge(order[['time', 'ticker', 'c16', 'volume_rank']], on=['time', 'ticker'], how='inner')
    merged = merged.dropna(subset=['actual', 'c16'])
    
    # Add market direction
    market_daily = merged.groupby('time')['actual'].mean().reset_index()
    market_daily = market_daily.rename(columns={'actual': 'market_return'})
    market_daily['market_up'] = market_daily['market_return'] > 0.5
    market_daily = market_daily.sort_values('time')
    market_daily['prev_market_up'] = market_daily['market_up'].shift(1)
    merged = merged.merge(market_daily[['time', 'market_up', 'prev_market_up']], on='time')
    
    # Add insider lead signal
    insider = load_insider_data()
    if not insider.empty:
        insider['insider_date'] = insider['published_date'] + pd.Timedelta(days=1)
        insider = insider.rename(columns={'insider_date': 'time'})
        merged = merged.merge(insider[['ticker', 'time', 'net_buy']], on=['ticker', 'time'], how='left')
        merged['insider_lead'] = (merged['net_buy'] > 0).fillna(False)
    
    signals_to_test = [args.signal] if args.signal != 'all' else ['insider_lead', 'consecutive_down', 'down_market_c16']
    
    print("=" * 60)
    print(f"S253: TRUE WALK-FORWARD VALIDATION - {args.signal}")
    print("=" * 60)
    print("Method: Train on T-2,T-1 → Test on T (rolling 1-year holdout)")
    print()
    
    for sig in signals_to_test:
        print(f"\n## {sig}")
        
        if sig == 'insider_lead':
            if insider.empty:
                print("NO INSIDER DATA")
                continue
            df_filtered = merged[merged['insider_lead'] == True].copy()
            signal_col = 'c16'
        elif sig == 'consecutive_down':
            df_filtered = merged[(merged['market_up'] == False) & (merged['prev_market_up'] == False)].copy()
            signal_col = 'c16'
        elif sig == 'down_market_c16':
            df_filtered = merged[merged['market_up'] == False].copy()
            signal_col = 'c16'
        else:
            continue
        
        results = rolling_wf_ic(df_filtered, signal_col, train_years=[1, 2])
        
        if results:
            print(f"| Year | IC | p-value | n_test |")
            print(f"|------|-----|---------|-------|")
            ic_vals = []
            for r in results:
                print(f"| {r['test_year']} | {r['ic']:.4f} | {r['p_value']:.4f} | {r['n_test']} |")
                ic_vals.append(r['ic'])
            
            mean_ic = np.mean(ic_vals)
            std_ic = np.std(ic_vals)
            print(f"| **Mean** | **{mean_ic:.4f}** | - | - |")
            print(f"| Std | {std_ic:.4f} | - | - |")
            
            # Verdict
            if mean_ic > 0.05:
                print(f"**VERDICT: PASSED (IC={mean_ic:.4f} > 0.05)**")
            else:
                print(f"**VERDICT: FAILED (IC={mean_ic:.4f} <= 0.05)**")
        else:
            print("NO DATA")

if __name__ == '__main__':
    main()