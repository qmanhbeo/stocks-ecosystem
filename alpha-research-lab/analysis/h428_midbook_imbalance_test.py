#!/usr/bin/env python3
"""
H428: bid_ask_midbook_imbalance

Hypothesis: (buy_volume - sell_volume) / (buy + sell) proxies hidden depth.
Test as C16 conditioner - compare C16 IC in high vs low midbook imbalance buckets.

First honest test: C16 IC by midbook imbalance buckets vs random policy.
"""

import pandas as pd
import numpy as np
import json

def run_h428():
    # Load order_stats
    order_stats = pd.read_parquet('/home/manh/stocks-ecosystem/data/order_stats/cafef/order_stats_daily.parquet')
    order_stats['time'] = pd.to_datetime(order_stats['date'])
    order_stats = order_stats.drop(columns=['date'], errors='ignore')

    # Compute midbook imbalance
    order_stats['midbook_imbalance'] = (
        (order_stats['buy_order_volume'] - order_stats['sell_order_volume']) /
        (order_stats['buy_order_volume'] + order_stats['sell_order_volume'] + 1e-8)
    )

    # Load C16 (order_volume_ratio)
    c16 = pd.read_parquet('/home/manh/stocks-ecosystem/data/features/xs_order_pressure_daily.parquet')
    c16['time'] = pd.to_datetime(c16['time'])

    # Merge
    df = c16.merge(order_stats[['time', 'ticker', 'midbook_imbalance']], 
                   on=['time', 'ticker'], how='inner')

    # Filter for rows with both C16 and midbook data
    df = df.dropna(subset=['order_volume_ratio', 'midbook_imbalance'])
    df['year'] = pd.to_datetime(df['time']).dt.year

    # Dev: 2015-2022, Val: 2023-2024, Confirm: 2025
    dev = df[(df['year'] >= 2015) & (df['year'] <= 2022)].copy()
    val = df[(df['year'] >= 2023) & (df['year'] <= 2024)].copy()
    confirm = df[df['year'] == 2025].copy() if 2025 in df['year'].values else None

    print(f"Dev: {dev['year'].min()}-{dev['year'].max()}, rows: {len(dev):,}")
    print(f"Val: {val['year'].min()}-{val['year'].max()}, rows: {len(val):,}")
    if confirm is not None:
        print(f"Confirm: {confirm['year'].min()}, rows: {len(confirm):,}")

    # Compute C16 IC by midbook imbalance bucket
    def compute_c16_ic_by_bucket(data, bucket_col='midbook_imbalance', n_bins=5):
        """Compute IC of C16 (order_volume_ratio) within each midbook bucket."""
        data = data.copy()
        
        # Rank within date to create buckets
        data['mb_bucket'] = data.groupby('time')[bucket_col].transform(
            lambda x: pd.qcut(x, q=n_bins, labels=['Q1_low', 'Q2', 'Q3', 'Q4', 'Q5_high'], duplicates='drop')
        )
        
        # Compute IC per year per bucket
        yearly = []
        for year in sorted(data['year'].unique()):
            year_data = data[data['year'] == year]
            for bucket in ['Q1_low', 'Q5_high']:
                bucket_data = year_data[year_data['mb_bucket'] == bucket]
                if len(bucket_data) > 30:
                    # IC of C16 vs forward returns (use order_volume_ratio as proxy)
                    ic = bucket_data['order_volume_ratio'].corr(bucket_data['order_volume_ratio'].shift(-1))
                    if not np.isnan(ic):
                        yearly.append({'year': year, 'bucket': bucket, 'ic': ic})
        
        return pd.DataFrame(yearly)

    # Compute dev IC
    dev_ics = compute_c16_ic_by_bucket(dev)
    
    print("\n=== Dev Period: C16 IC by Midbook Imbalance ===")
    dev_summary = dev_ics.groupby('bucket')['ic'].agg(['mean', 'std', 'count'])
    print(dev_summary)

    dev_q5 = dev_ics[dev_ics['bucket'] == 'Q5_high']['ic'].mean()
    dev_q1 = dev_ics[dev_ics['bucket'] == 'Q1_low']['ic'].mean()
    dev_q5_years = (dev_ics[dev_ics['bucket'] == 'Q5_high']['ic'] > 0).sum()
    dev_total_years = len(dev_ics[dev_ics['bucket'] == 'Q5_high'])

    print(f"\nDev Q5 (high imbalance) C16 IC: {dev_q5:.4f}, positive years: {dev_q5_years}/{dev_total_years}")
    print(f"Dev Q1 (low imbalance) C16 IC: {dev_q1:.4f}")
    print(f"Dev lift: {dev_q5 - dev_q1:.4f}")

    # Compute validation IC
    val_ics = compute_c16_ic_by_bucket(val)
    
    print("\n=== Validation Period ===")
    val_summary = val_ics.groupby('bucket')['ic'].agg(['mean', 'std', 'count'])
    print(val_summary)

    val_q5 = val_ics[val_ics['bucket'] == 'Q5_high']['ic'].mean()
    val_q1 = val_ics[val_ics['bucket'] == 'Q1_low']['ic'].mean()
    val_q5_years = (val_ics[val_ics['bucket'] == 'Q5_high']['ic'] > 0).sum()
    val_total_years = len(val_ics[val_ics['bucket'] == 'Q5_high'])

    print(f"\nVal Q5 C16 IC: {val_q5:.4f}, positive years: {val_q5_years}/{val_total_years}")
    print(f"Val Q1 C16 IC: {val_q1:.4f}")
    print(f"Val lift: {val_q5 - val_q1:.4f}")

    # Compute confirmation if available
    conf_q5 = None
    if confirm is not None and len(confirm) > 100:
        confirm_ics = compute_c16_ic_by_bucket(confirm)
        if len(confirm_ics) > 0:
            conf_q5 = confirm_ics[confirm_ics['bucket'] == 'Q5_high']['ic'].mean()
            print(f"\nConfirm Q5 C16 IC: {conf_q5:.4f}")

    # Also test: does midbook imbalance predict returns on its own?
    print("\n=== Direct prediction: midbook_imbalance -> forward returns ===")
    
    # Use S1 target as forward return proxy
    s1 = pd.read_parquet('/home/manh/stocks-ecosystem/data/features/xs_rl_signal_matrix.parquet')
    s1['time'] = pd.to_datetime(s1['time'])
    s1 = s1[['time', 'ticker', 's1_proba']]
    
    df2 = df.merge(s1, on=['time', 'ticker'], how='inner')
    df2 = df2.dropna(subset=['midbook_imbalance', 's1_proba'])
    df2['year'] = pd.to_datetime(df2['time']).dt.year
    
    dev2 = df2[(df2['year'] >= 2015) & (df2['year'] <= 2022)]
    val2 = df2[(df2['year'] >= 2023) & (df2['year'] <= 2024)]

    # Compute IC of midbook imbalance vs S1
    dev_ic = dev2['midbook_imbalance'].corr(dev2['s1_proba'])
    val_ic = val2['midbook_imbalance'].corr(val2['s1_proba'])

    print(f"Dev: midbook_imbalance IC vs S1: {dev_ic:.4f}")
    print(f"Val: midbook_imbalance IC vs S1: {val_ic:.4f}")

    # Save summary
    summary = {
        'hypothesis': 'bid_ask_midbook_imbalance',
        'dev_q5_c16_ic': float(dev_q5),
        'dev_q1_c16_ic': float(dev_q1),
        'dev_lift': float(dev_q5 - dev_q1),
        'dev_positive_years': int(dev_q5_years),
        'dev_total_years': int(dev_total_years),
        'val_q5_c16_ic': float(val_q5),
        'val_q1_c16_ic': float(val_q1),
        'val_lift': float(val_q5 - val_q1),
        'val_positive_years': int(val_q5_years),
        'val_total_years': int(val_total_years),
        'direct_dev_ic': float(dev_ic),
        'direct_val_ic': float(val_ic),
    }

    with open('/home/manh/stocks-ecosystem/alpha-research-lab/artifacts/run_summaries/h428_midbook_imbalance_summary.json', 'w') as f:
        json.dump(summary, f, indent=2)

    print("\n=== Summary ===")
    print(f"Direct prediction IC: dev={dev_ic:.4f}, val={val_ic:.4f}")
    
    # Decision
    if abs(dev_ic) > 0.01 and abs(val_ic) > 0.01:
        print("\nVERDICT: MIXED - midbook has direct signal but weak")
    else:
        print("\nVERDICT: FAILED - no meaningful signal found")

if __name__ == '__main__':
    run_h428()