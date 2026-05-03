#!/usr/bin/env python
"""X240: Walk-forward IC test reusable script.

Usage:
    python analysis/x240_wf_ic_test.py --test vol_high          # test high vol regime
    python analysis/x240_wf_ic_test.py --test monday         # test monday
    python analysis/x240_wf_ic_test.py --test tet          # test tet period
"""
import argparse
import pandas as pd
import numpy as np
from scipy.stats import spearmanr

ORDER = 'data/order_stats/cafef/order_stats_daily.parquet'
RETURNS = 'data/features/xs_barrier_vol_1d_hose_full.parquet'

def load_data():
    """Load and merge order stats + returns."""
    order = pd.read_parquet(ORDER)
    order['date'] = pd.to_datetime(order['date'])
    order = order[order['date'].dt.year.isin(range(2015, 2023))]
    order['ovr'] = (order['buy_order_volume'] - order['sell_order_volume']) / (order['buy_order_volume'] + order['sell_order_volume'])
    order['c16'] = order.groupby('date')['ovr'].rank(pct=True)
    order['volume_rank'] = order.groupby('date')['buy_order_count'].rank(pct=True)
    order = order.rename(columns={'date': 'time'})
    
    ret = pd.read_parquet(RETURNS, columns=['time', 'ticker', 'actual'])
    ret['time'] = pd.to_datetime(ret['time'])
    ret = ret[ret['time'].dt.year.isin(range(2015, 2023))]
    
    merged = ret.merge(order[['time', 'ticker', 'c16', 'volume_rank']], on=['time', 'ticker'], how='inner')
    merged = merged.dropna(subset=['actual', 'c16'])
    merged['dayofweek'] = merged['time'].dt.dayofweek
    return merged

def wf_ic(df, signal):
    """Walk-forward IC: train on years before Y, test on year Y."""
    results = []
    for year in range(2015, 2023):
        test = df[df['time'].dt.year == year]
        test = test.dropna(subset=[signal, 'actual'])
        if len(test) > 50:
            ic, p = spearmanr(test[signal], test['actual'])
            if not np.isnan(ic):
                results.append({'year': year, 'ic': ic})
    return np.mean([r['ic'] for r in results]) if results else np.nan

def run_test(test_name):
    """Run named test."""
    df = load_data()
    signal = 'c16'
    
    if test_name == 'vol_high':
        filtered = df[df['volume_rank'] > 0.8]
        ic = wf_ic(filtered, signal)
        return f'vol_rank>0.8: IC={ic:.4f}'
    elif test_name == 'vol_low':
        filtered = df[df['volume_rank'] < 0.2]
        ic = wf_ic(filtered, signal)
        return f'vol_rank<0.2: IC={ic:.4f}'
    elif test_name == 'monday':
        filtered = df[df['dayofweek'] == 0]
        ic = wf_ic(filtered, signal)
        return f'Monday: IC={ic:.4f}'
    elif test_name == 'thursday':
        filtered = df[df['dayofweek'] == 3]
        ic = wf_ic(filtered, signal)
        return f'Thursday: IC={ic:.4f}'
    elif test_name == 'tet':
        tet_dates = pd.to_datetime([
            '2015-02-15', '2016-02-05', '2017-01-24', '2018-02-11', '2019-02-01', '2020-01-24', '2021-02-10', '2022-01-29'
        ])
        filtered = df[df['time'].isin(tet_dates)]
        ic = wf_ic(filtered, signal) if len(filtered) > 100 else np.nan
        return f'Tet period: IC={ic:.4f}'
    elif test_name == 'quarter_start':
        df['month'] = df['time'].dt.month
        df['day'] = df['time'].dt.day
        filtered = df[(df['month'].isin([1, 4, 7, 10])) & (df['day'] <= 5)]
        ic = wf_ic(filtered, signal) if len(filtered) > 100 else np.nan
        return f'quarter_start: IC={ic:.4f}'
    elif test_name == 'quarter_end':
        df['month'] = df['time'].dt.month
        df['day'] = df['time'].dt.day
        df['days_in_month'] = df['time'].dt.days_in_month
        filtered = df[(df['month'].isin([3, 6, 9, 12])) & (df['days_in_month'] - df['day'] <= 5)]
        ic = wf_ic(filtered, signal) if len(filtered) > 100 else np.nan
        return f'quarter_end: IC={ic:.4f}'
    elif test_name == 'january_first_10':
        df['dayofyear'] = df['time'].dt.dayofyear
        filtered = df[df['dayofyear'] <= 10]
        ic = wf_ic(filtered, signal) if len(filtered) > 100 else np.nan
        return f'january_first_10: IC={ic:.4f}'
    elif test_name == 'sector_streak':
        return 'NOT TESTED: requires sector_momentum streak data'
    elif test_name == 'small_cap':
        return 'NOT TESTED: requires market cap data'
    elif test_name == 'volume_vol_combo':
        df['vol_low'] = df['volume_rank'] < 0.3
        df['vol_high'] = df['volume_rank'] > 0.7
        filtered = df[df['vol_low']]
        ic1 = wf_ic(filtered, signal) if len(filtered) > 100 else np.nan
        filtered2 = df[df['vol_high']]
        ic2 = wf_ic(filtered2, signal) if len(filtered2) > 100 else np.nan
        return f'vol_low IC={ic1:.4f}, vol_high IC={ic2:.4f}'
    elif test_name == 'foreign_room_delta':
        return 'NOT TESTED: requires foreign room delta data'
    elif test_name == 'dow_jones_lag':
        return 'NOT TESTED: requires US market overnight data'
    elif test_name == 'turnover_rate':
        return 'NOT TESTED: requires turnover rate data'
    elif test_name == 'market_breadth':
        return 'S238 ALREADY TESTED: A/D Q1-Q2 +30%'
    elif test_name == 'february_effect':
        df['month'] = df['time'].dt.month
        df['day'] = df['time'].dt.day
        filtered = df[(df['month'] == 2) & (df['day'] >= 15)]
        ic = wf_ic(filtered, signal) if len(filtered) > 100 else np.nan
        return f'february_mid: IC={ic:.4f}'
    elif test_name == 'march_quadrant':
        df['month'] = df['time'].dt.month
        df['week'] = df['time'].dt.isocalendar().week
        df['march_week_half'] = np.where(df['week'] <= 10, 'early', 'late')
        ic_early = wf_ic(df[(df['month'] == 3) & (df['march_week_half'] == 'early')], signal)
        ic_late = wf_ic(df[(df['month'] == 3) & (df['march_week_half'] == 'late')], signal)
        return f'march_early={ic_early:.4f}, march_late={ic_late:.4f}'
    elif test_name == 'may_effect':
        df['month'] = df['time'].dt.month
        filtered = df[df['month'] == 5]
        ic = wf_ic(filtered, signal) if len(filtered) > 100 else np.nan
        return f'may: IC={ic:.4f}'
    elif test_name == 'september_call':
        df['month'] = df['time'].dt.month
        df['week'] = df['time'].dt.isocalendar().week
        df['sept_week_half'] = np.where(df['week'] <= 36, 'early', 'late')
        ic_early = wf_ic(df[(df['month'] == 9) & (df['sept_week_half'] == 'early')], signal)
        ic_late = wf_ic(df[(df['month'] == 9) & (df['sept_week_half'] == 'late')], signal)
        return f'sept_early={ic_early:.4f}, sept_late={ic_late:.4f}'
    elif test_name == 'october_uncertainty':
        df['month'] = df['time'].dt.month
        filtered = df[df['month'] == 10]
        ic = wf_ic(filtered, signal) if len(filtered) > 100 else np.nan
        return f'october: IC={ic:.4f}'
    elif test_name == 'yearend_window':
        df['month'] = df['time'].dt.month
        df['day'] = df['time'].dt.day
        filtered = df[(df['month'] == 12) & (df['day'] >= 20)]
        ic = wf_ic(filtered, signal) if len(filtered) > 100 else np.nan
        return f'yearend_20+: IC={ic:.4f}'
    elif test_name == 'c16_monday_jan_combo':
        df['month'] = df['time'].dt.month
        df['dayofyear'] = df['time'].dt.dayofyear
        filtered = df[(df['dayofyear'] <= 10) & (df['dayofweek'] == 0)]
        ic = wf_ic(filtered, signal) if len(filtered) > 100 else np.nan
        return f'monday_jan: IC={ic:.4f}'
    elif test_name == 'triple_storm_plus_jan':
        return 'NOT TESTED: requires market_direction + divergence data'
    elif test_name == 'midyear_rebalancing':
        df['month'] = df['time'].dt.month
        filtered = df[df['month'].isin([6, 7])]
        ic = wf_ic(filtered, signal) if len(filtered) > 100 else np.nan
        return f'midyear: IC={ic:.4f}'
    elif test_name == 'rank_time_acceleration':
        df = df.sort_values(['ticker', 'time'])
        df['rank_c16'] = df.groupby('time')['c16'].rank(pct=True)
        df['rank_c16_5d_lag'] = df.groupby('ticker')['rank_c16'].shift(5)
        df['rank_accel'] = df['rank_c16'] - df['rank_c16_5d_lag']
        df = df.dropna(subset=['rank_accel'])
        if len(df) > 100:
            ic = wf_ic(df, 'rank_accel')
            return f'rank_accel_5d: IC={ic:.4f}'
        return 'rank_accel: insufficient data'
    elif test_name == 'c16_entropy_signal':
        return 'NOT TESTED: requires sector entropy computation'
    elif test_name == 'consecutive_down_days':
        df['market_return'] = df.groupby('time')['actual'].transform('mean')
        df['market_down'] = df['market_return'] < 0
        df = df.sort_values(['ticker', 'time'])
        df['prev_market_down'] = df.groupby('ticker')['market_down'].shift(1)
        df['streak_2d'] = df['market_down'] & df['prev_market_down']
        df = df.dropna(subset=['streak_2d'])
        filtered = df[df['streak_2d']]
        ic = wf_ic(filtered, 'c16') if len(filtered) > 100 else np.nan
        return f'consecutive_2d_down: IC={ic:.4f}'
    elif test_name == 'drawdown_entry_signal':
        return 'NOT TESTED: requires drawdown computation'
    else:
        return f'Unknown test: {test_name}'

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Walk-forward IC test')
    parser.add_argument('--test', default='vol_high', help='Test name')
    args = parser.parse_args()
    print(run_test(args.test))