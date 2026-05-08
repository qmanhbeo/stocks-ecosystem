"""
H427: volume_attention_budget - Date-Level Concentration Test

Hypothesis: Date-level volume concentration (Herfindahl) acts as a market regime 
indicator that affects ranker activation quality.

Smallest honest test: Compute date-level volume Herfindahl from order_stats,
bucket dates into concentration quartiles, test if S1/Vol+S1 IC differs across
concentration regimes.

Connection: H409-H417 found Vol+S1 is strong; H403 found flow regime matters.
This tests if market-wide attention concentration predicts signal quality.
"""

from __future__ import annotations
import argparse
from pathlib import Path
import sys

import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

S1_DEFAULT_PATH = ROOT / "data" / "features" / "xs_rl_signal_matrix.parquet"
S1_SCORE_COL = "s1_proba"
S1_TARGET_COL = "actual"

BRANCH_NAME = "volume_attention_budget"
MODE = "research_branch"

TEST_YEARS = [2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025]
MIN_YEAR_ROWS = 500


def compute_date_volume_herfindahl(order_stats: pd.DataFrame) -> pd.DataFrame:
    """Compute volume Herfindahl per date."""
    daily = order_stats.copy()
    
    daily['total_volume'] = daily['buy_order_volume'] + daily['sell_order_volume']
    
    date_totals = daily.groupby('date')['total_volume'].sum().reset_index()
    date_totals.columns = ['date', 'date_total_volume']
    
    daily = daily.merge(date_totals, on='date', how='left')
    daily['volume_share'] = daily['total_volume'] / daily['date_total_volume']
    daily['volume_share_sq'] = daily['volume_share'] ** 2
    
    herfindahl = daily.groupby('date')['volume_share_sq'].sum().reset_index()
    herfindahl.columns = ['date', 'volume_herfindahl']
    
    return herfindahl


def load_order_stats() -> pd.DataFrame:
    """Load order stats data."""
    path = ROOT / "data" / "order_stats" / "cafef" / "order_stats_daily.parquet"
    df = pd.read_parquet(path)
    return df


def load_s1_panel() -> pd.DataFrame:
    """Load S1 decision panel."""
    df = pd.read_parquet(S1_DEFAULT_PATH)
    df['date'] = pd.to_datetime(df['time'])
    df = df[df['date'].dt.year.isin(TEST_YEARS)]
    return df


def run_experiment():
    print(f"=== H427: {BRANCH_NAME} ===")
    print("Testing date-level volume concentration as market regime indicator")
    
    order_stats = load_order_stats()
    print(f"Loaded order_stats: {len(order_stats)} rows")
    
    herfindahl = compute_date_volume_herfindahl(order_stats)
    herfindahl['date'] = pd.to_datetime(herfindahl['date'])
    herfindahl = herfindahl[herfindahl['date'].dt.year.isin(TEST_YEARS)]
    print(f"Computed Herfindahl for {len(herfindahl)} dates")
    
    s1_panel = load_s1_panel()
    print(f"Loaded S1 panel: {len(s1_panel)} rows")
    
    s1_panel = s1_panel.merge(herfindahl, on='date', how='left')
    s1_panel = s1_panel.dropna(subset=['volume_herfindahl'])
    print(f"After merge: {len(s1_panel)} rows")
    
    herfindahl_deciles = s1_panel['volume_herfindahl'].quantile([0.2, 0.4, 0.6, 0.8])
    s1_panel['conc_level'] = pd.cut(
        s1_panel['volume_herfindahl'],
        bins=[0, herfindahl_deciles[0.2], herfindahl_deciles[0.4], 
              herfindahl_deciles[0.6], herfindahl_deciles[0.8], 1.0],
        labels=['Q1_low', 'Q2', 'Q3', 'Q4', 'Q5_high']
    )
    
    print(f"\nDate distribution by concentration quartile:")
    print(s1_panel.groupby('conc_level')['date'].nunique())
    
    yearly_results = []
    for year in TEST_YEARS:
        year_df = s1_panel[s1_panel['date'].dt.year == year]
        if len(year_df) < MIN_YEAR_ROWS:
            continue
            
        overall_ic = year_df[S1_SCORE_COL].corr(year_df['actual'])
        
        conc_results = []
        for conc in ['Q1_low', 'Q2', 'Q3', 'Q4', 'Q5_high']:
            conc_df = year_df[year_df['conc_level'] == conc]
            if len(conc_df) >= 50:
                ic = conc_df[S1_SCORE_COL].corr(conc_df['actual'])
                conc_results.append({'concentration': conc, 'ic': ic, 'n': len(conc_df)})
        
        yearly_results.append({
            'year': year,
            'overall_ic': overall_ic,
            'n_rows': len(year_df),
            'concentration_results': conc_results
        })
    
    print("\n=== Yearly IC by Concentration Quartile ===")
    all_conc_ic = {q: [] for q in ['Q1_low', 'Q2', 'Q3', 'Q4', 'Q5_high']}
    
    for result in yearly_results:
        print(f"\n{result['year']}: overall IC = {result['overall_ic']:.4f}, n = {result['n_rows']}")
        for cr in result['concentration_results']:
            print(f"  {cr['concentration']}: IC = {cr['ic']:.4f}, n = {cr['n']}")
            all_conc_ic[cr['concentration']].append(cr['ic'])
    
    print("\n=== Average IC by Concentration Quartile ===")
    conc_summary = []
    for conc, ics in all_conc_ic.items():
        if ics:
            mean_ic = np.mean(ics)
            pos_years = sum(1 for ic in ics if ic > 0)
            print(f"{conc}: mean IC = {mean_ic:.4f}, positive years = {pos_years}/{len(ics)}")
            conc_summary.append({
                'concentration': conc,
                'mean_ic': mean_ic,
                'positive_years': pos_years,
                'total_years': len(ics)
            })
    
    overall_ic_vals = [r['overall_ic'] for r in yearly_results]
    baseline_mean = np.mean(overall_ic_vals)
    baseline_pos = sum(1 for ic in overall_ic_vals if ic > 0)
    print(f"\nBaseline (all dates): mean IC = {baseline_mean:.4f}, positive years = {baseline_pos}/{len(yearly_results)}")
    
    best_conc = max(conc_summary, key=lambda x: x['mean_ic']) if conc_summary else None
    if best_conc:
        lift = best_conc['mean_ic'] - baseline_mean
        print(f"\nBest concentration regime: {best_conc['concentration']}")
        print(f"IC lift vs baseline: {lift:+.4f}")
        
        if best_conc['positive_years'] >= 5 and lift > 0.005:
            verdict = "PASSED"
        elif best_conc['positive_years'] >= 4 and lift > 0.002:
            verdict = "MIXED"
        else:
            verdict = "FAILED"
    else:
        verdict = "FAILED"
        lift = 0.0
    
    print(f"\n=== VERDICT: {verdict} ===")
    print(f"Conclusion: Date-level volume concentration {'does' if verdict == 'PASSED' else 'does not significantly'} predict signal quality")
    
    summary = {
        'branch': BRANCH_NAME,
        'verdict': verdict,
        'baseline_mean_ic': baseline_mean,
        'best_concentration': best_conc['concentration'] if best_conc else None,
        'best_concentration_ic': best_conc['mean_ic'] if best_conc else None,
        'lift_vs_baseline': lift,
        'positive_years': best_conc['positive_years'] if best_conc else 0,
        'total_years': best_conc['total_years'] if best_conc else 0,
    }
    
    output_path = ROOT / "artifacts" / "run_summaries" / f"h427_{BRANCH_NAME}_summary.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    import json
    with open(output_path, 'w') as f:
        json.dump(summary, f, indent=2)
    print(f"\nSaved summary to {output_path}")
    
    return verdict


if __name__ == "__main__":
    run_experiment()