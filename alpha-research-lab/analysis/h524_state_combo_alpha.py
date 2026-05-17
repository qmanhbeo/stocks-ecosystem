#!/usr/bin/env python3
"""
H524 - State Combination Alpha Test

Test if simultaneous multiple states (e.g., onset+amplified together, 
C23+C24) capture information that individual states miss.

Hypothesis: H507-H521 tested states in isolation. Combo states are untested.
If multiple states fire together, it may indicate stronger/larger alpha regime.
"""

import sys
sys.path.insert(0, "/home/manh/stocks-ecosystem/alpha-research-lab")

import numpy as np
import pandas as pd
from datetime import datetime
from scipy.stats import spearmanr
from pathlib import Path

from src.experiment_contract import (
    ExperimentSpec,
    build_experiment_context,
    load_s1_decision_panel,
    safe_spearman,
    yearly_ic,
    summarize_ic_rows,
    phase_ic,
    require_columns,
    state_mask,
    normalize_time_ticker,
    restrict_years,
)
from src.repo_paths import artifact_path, data_path


def load_signals() -> pd.DataFrame:
    """Load S1 and C16 signals and merge."""
    # Load S1 panel
    s1_path = data_path("features/xs_barrier_vol_1d_hose_full.parquet")
    s1_df = pd.read_parquet(s1_path, columns=["time", "ticker", "xs_proba", "actual"])
    s1_df = normalize_time_ticker(s1_df, source="S1 panel")
    s1_df = restrict_years(s1_df, start_year=2015, end_year=2025, source="S1 panel")
    s1_df = s1_df.rename(columns={"xs_proba": "s1_xs_proba", "actual": "s1_barrier_hit_1d"})
    
    # Load C16 signals
    c16_path = data_path("features/xs_order_pressure_daily.parquet")
    c16_cols = ["time", "ticker", "order_volume_ratio", "order_volume_ratio_rank", 
                "order_pressure_available", "can_buy_next_open"]
    c16_df = pd.read_parquet(c16_path, columns=c16_cols)
    c16_df = normalize_time_ticker(c16_df, source="C16 panel")
    c16_df = restrict_years(c16_df, start_year=2015, end_year=2025, source="C16 panel")
    
    # Merge
    df = s1_df.merge(c16_df, on=["time", "ticker"], how="inner")
    print(f"Merged panel: {len(df)} rows, years {df['time'].dt.year.min()}-{df['time'].dt.year.max()}")
    
    return df


def create_signal_states(df: pd.DataFrame) -> pd.DataFrame:
    """Create signal state columns from available signals."""
    result = df.copy()
    
    # Create state bins based on order_volume_ratio_rank
    # These approximate the latent states discovered in H507-H515
    if "order_volume_ratio_rank" in result.columns:
        rank = result["order_volume_ratio_rank"]
        
        # state_router: lowest pressure (strongest signal in C23)
        result["state_router"] = (rank < 0.1).astype(int)
        
        # state_amplified: second lowest pressure  
        result["state_amplified"] = ((rank >= 0.1) & (rank < 0.25)).astype(int)
        
        # state_onset: mid-low pressure
        result["state_onset"] = ((rank >= 0.25) & (rank < 0.5)).astype(int)
        
        # state_carry: mid-high pressure
        result["state_carry"] = ((rank >= 0.5) & (rank < 0.75)).astype(int)
        
        # state_quiet: highest pressure (baseline/no signal)
        result["state_quiet"] = (rank >= 0.75).astype(int)
        
        # C23-style: low pressure (top 20% = illiquid)
        result["c23_low_pressure"] = (rank < 0.2).astype(int)
        
        # C23-style strong: lowest 10%
        result["c23_strong"] = (rank < 0.1).astype(int)
    
    return result


def compute_combo_states(df: pd.DataFrame) -> pd.DataFrame:
    """Compute intersection/combo states."""
    result = df.copy()
    
    # === UNION COMBOS (OR logic - any state active) ===
    
    # Combo 1: onset + amplified (both are active states, not quiet)
    if "state_onset" in result.columns and "state_amplified" in result.columns:
        result["union_onset_amplified"] = (
            (result["state_onset"] == 1) | (result["state_amplified"] == 1)
        ).astype(int)
    
    # Combo 2: onset + router (strong C23 signals together)
    if "state_onset" in result.columns and "state_router" in result.columns:
        result["union_onset_router"] = (
            (result["state_onset"] == 1) | (result["state_router"] == 1)
        ).astype(int)
    
    # Combo 3: amplified + router (strong signal together)
    if "state_amplified" in result.columns and "state_router" in result.columns:
        result["union_amplified_router"] = (
            (result["state_amplified"] == 1) | (result["state_router"] == 1)
        ).astype(int)
    
    # Combo 4: router only (strongest C23 signal)
    if "state_router" in result.columns:
        result["union_router_only"] = result["state_router"]
    
    # Combo 5: all active (onset + amplified + router + carry)
    active_cols = [c for c in ["state_onset", "state_amplified", "state_router", "state_carry"] 
                  if c in result.columns]
    if active_cols:
        result["union_all_active"] = (result[active_cols].max(axis=1)).astype(int)
    
    # Combo 6: router + carry (persistent high signal)
    if "state_router" in result.columns and "state_carry" in result.columns:
        result["union_router_carry"] = (
            (result["state_router"] == 1) | (result["state_carry"] == 1)
        ).astype(int)
    
    # === INTERSECTION COMBOS (AND logic - BOTH states must be true) ===
    # These are more restrictive but may capture stronger regime
    
    # Intersection: onset AND amplified (impossible since they're mutually exclusive quintiles)
    # But we can test: router AND some other feature
    
    # Test: router + high volume (persistent + high activity)
    if "state_router" in result.columns and "order_volume_ratio" in result.columns:
        vol_median = result["order_volume_ratio"].median()
        result["intersect_router_highvol"] = (
            (result["state_router"] == 1) & 
            (result["order_volume_ratio"] > vol_median)
        ).astype(int)
    
    # Test: quiet + low volume (contrarian: quiet but illiquid)
    if "state_quiet" in result.columns and "order_volume_ratio" in result.columns:
        vol_median = result["order_volume_ratio"].median()
        result["intersect_quiet_lowvol"] = (
            (result["state_quiet"] == 1) & 
            (result["order_volume_ratio"] < vol_median)
        ).astype(int)
    
    # Test: router + can_buy (filter for buyable)
    if "state_router" in result.columns and "can_buy_next_open" in result.columns:
        result["intersect_router_buyable"] = (
            (result["state_router"] == 1) & 
            (result["can_buy_next_open"] == True)
        ).astype(int)
    
    # Test: quiet + can_buy (contrarian + buyable)
    if "state_quiet" in result.columns and "can_buy_next_open" in result.columns:
        result["intersect_quiet_buyable"] = (
            (result["state_quiet"] == 1) & 
            (result["can_buy_next_open"] == True)
        ).astype(int)
    
    return result


def evaluate_state_detailed(df: pd.DataFrame, state_col: str, score_col: str, target_col: str, 
                            min_rows: int) -> dict:
    """Evaluate IC for a single state with yearly breakdown."""
    require_columns(df, [state_col, score_col, target_col], context=f"state {state_col}")
    
    # Filter to rows where state is active
    subset = df.loc[df[state_col] == 1].copy()
    if len(subset) < min_rows:
        return {"state": state_col, "rows": len(subset), "ic": None, "p_value": None, 
                "positive_years": 0, "total_years": 0}
    
    pooled = safe_spearman(subset, score_col, target_col, min_rows=min_rows)
    years = yearly_ic(subset, score_col, target_col, min_year_rows=min_rows)
    summary = summarize_ic_rows(years)
    
    # Phase IC breakdown (dev: 2015-2022, validation: 2023-2024, confirmation: 2025)
    years_series = pd.to_datetime(subset["time"], errors="coerce").dt.year
    dev_subset = subset.loc[years_series.between(2015, 2022)]
    val_subset = subset.loc[years_series.isin([2023, 2024])]
    conf_subset = subset.loc[years_series == 2025]
    
    dev_ic = safe_spearman(dev_subset, score_col, target_col, min_rows=min_rows)["ic"]
    val_ic = safe_spearman(val_subset, score_col, target_col, min_rows=min_rows)["ic"]
    conf_ic = safe_spearman(conf_subset, score_col, target_col, min_rows=min_rows)["ic"]
    
    return {
        "state": state_col,
        "pooled_rows": pooled["rows"],
        "pooled_ic": pooled["ic"],
        "pooled_p_value": pooled["p_value"],
        "positive_years": summary["positive_years"],
        "total_years": summary["years"],
        "pct_positive_years": summary["pct_positive_years"],
        "dev_ic": dev_ic,
        "validation_ic": val_ic,
        "confirmation_ic": conf_ic,
        "yearly_ics": {int(y["year"]): y["ic"] for y in years if y.get("ic") is not None}
    }


def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = artifact_path("run_summaries")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Load S1 and C16 signals
    print("Loading S1 and C16 signals...")
    df = load_signals()
    
    # Create states
    df = create_signal_states(df)
    df = compute_combo_states(df)
    
    score_col = "s1_xs_proba"
    target_col = "s1_barrier_hit_1d"
    min_rows = 500
    
    # Define states to test
    individual_states = ["state_router", "state_amplified", "state_onset", "state_carry", 
                        "state_quiet", "c23_low_pressure", "c23_strong"]
    union_combo_states = ["union_onset_amplified", "union_onset_router", "union_amplified_router", 
                   "union_router_only", "union_all_active", "union_router_carry"]
    intersect_combo_states = ["intersect_router_highvol", "intersect_quiet_lowvol", 
                              "intersect_router_buyable", "intersect_quiet_buyable"]
    
    # Filter to states that exist
    individual_states = [s for s in individual_states if s in df.columns]
    union_combo_states = [s for s in union_combo_states if s in df.columns]
    intersect_combo_states = [s for s in intersect_combo_states if s in df.columns]
    combo_states = union_combo_states + intersect_combo_states
    
    print(f"\nTesting {len(individual_states)} individual states and {len(combo_states)} combo states")
    
    results = []
    
    # Test all_rows baseline
    baseline = safe_spearman(df, score_col, target_col, min_rows=min_rows)
    baseline_years = yearly_ic(df, score_col, target_col, min_year_rows=min_rows)
    baseline_summary = summarize_ic_rows(baseline_years)
    results.append({
        "state": "all_rows_baseline",
        "pooled_rows": baseline["rows"],
        "pooled_ic": baseline["ic"],
        **baseline_summary
    })
    print(f"Baseline all_rows: IC={baseline['ic']:.4f}, rows={baseline['rows']}")
    
    # Test individual states
    print("\n--- Individual States ---")
    for state in individual_states:
        result = evaluate_state_detailed(df, state, score_col, target_col, min_rows)
        results.append(result)
        pos_years = result.get("positive_years", 0)
        total_years = result.get("total_years", 0)
        ic_val = result.get("pooled_ic")
        ic_str = f"{ic_val:.4f}" if ic_val is not None else "N/A"
        print(f"{state}: IC={ic_str}, rows={result.get('pooled_rows', 0)}, pos={pos_years}/{total_years} yrs")
    
    # Test union combo states  
    print("\n--- Union Combo States (OR logic) ---")
    for state in union_combo_states:
        result = evaluate_state_detailed(df, state, score_col, target_col, min_rows)
        results.append(result)
        pos_years = result.get("positive_years", 0)
        total_years = result.get("total_years", 0)
        ic_val = result.get("pooled_ic")
        ic_str = f"{ic_val:.4f}" if ic_val is not None else "N/A"
        print(f"{state}: IC={ic_str}, rows={result.get('pooled_rows', 0)}, pos={pos_years}/{total_years} yrs")
    
    # Test intersection combo states
    print("\n--- Intersection Combo States (AND logic) ---")
    for state in intersect_combo_states:
        result = evaluate_state_detailed(df, state, score_col, target_col, min_rows)
        results.append(result)
        pos_years = result.get("positive_years", 0)
        total_years = result.get("total_years", 0)
        ic_val = result.get("pooled_ic")
        ic_str = f"{ic_val:.4f}" if ic_val is not None else "N/A"
        print(f"{state}: IC={ic_str}, rows={result.get('pooled_rows', 0)}, pos={pos_years}/{total_years} yrs")
    
    # Find best individual and best combos
    individual_results = [r for r in results if r["state"] in individual_states]
    union_combo_results = [r for r in results if r["state"] in union_combo_states]
    intersect_combo_results = [r for r in results if r["state"] in intersect_combo_states]
    
    best_individual = max(individual_results, key=lambda x: x.get("pooled_ic") or 0)
    best_union_combo = max(union_combo_results, key=lambda x: x.get("pooled_ic") or 0) if union_combo_results else None
    best_intersect_combo = max(intersect_combo_results, key=lambda x: x.get("pooled_ic") or 0) if intersect_combo_results else None
    
    print(f"\n=== SUMMARY ===")
    print(f"Best individual: {best_individual['state']} IC={best_individual.get('pooled_ic', 'N/A'):.4f}")
    if best_union_combo:
        print(f"Best union combo: {best_union_combo['state']} IC={best_union_combo.get('pooled_ic', 'N/A'):.4f}")
    if best_intersect_combo:
        print(f"Best intersect combo: {best_intersect_combo['state']} IC={best_intersect_combo.get('pooled_ic', 'N/A'):.4f}")
    
    baseline_ic = baseline["ic"]
    print(f"Baseline all_rows: IC={baseline_ic:.4f}")
    
    # Determine the overall best combo (union or intersection)
    all_combos = []
    if best_union_combo:
        all_combos.append(best_union_combo)
    if best_intersect_combo:
        all_combos.append(best_intersect_combo)
    best_combo = max(all_combos, key=lambda x: x.get("pooled_ic") or 0) if all_combos else None
    
    # Compute lift: combo vs best individual
    lift = None
    if best_individual.get("pooled_ic") and best_combo:
        lift = best_combo["pooled_ic"] - best_individual["pooled_ic"]
        print(f"Lift (best combo vs best individual): {lift:+.4f}")
    
    if best_combo and best_combo.get("pooled_ic"):
        baseline_lift = best_combo["pooled_ic"] - baseline_ic
        print(f"Lift (best combo vs baseline): {baseline_lift:+.4f}")
        print(f"Phase ICs: dev={best_combo.get('dev_ic', 'N/A'):.4f}, val={best_combo.get('validation_ic', 'N/A'):.4f}, conf={best_combo.get('confirmation_ic', 'N/A'):.4f}")
    
    # Save results (convert dict column to string for parquet compatibility)
    for r in results:
        if "yearly_ics" in r and isinstance(r["yearly_ics"], dict):
            r["yearly_ics"] = str(r["yearly_ics"])
    results_df = pd.DataFrame(results)
    results_path = output_dir / f"{ts}_state_combo_alpha_results.parquet"
    results_df.to_parquet(results_path, index=False)
    print(f"\nSaved results to {results_path}")
    
    # Write JSON summary
    import json
    summary = {
        "hypothesis": "State Combination Alpha - test if simultaneous multiple states capture info individual states miss",
        "best_individual": best_individual["state"],
        "best_individual_ic": best_individual.get("pooled_ic"),
        "best_individual_pos_years": best_individual.get("positive_years"),
        "best_individual_total_years": best_individual.get("total_years"),
        "best_union_combo": best_union_combo["state"] if best_union_combo else None,
        "best_union_combo_ic": best_union_combo.get("pooled_ic") if best_union_combo else None,
        "best_intersect_combo": best_intersect_combo["state"] if best_intersect_combo else None,
        "best_intersect_combo_ic": best_intersect_combo.get("pooled_ic") if best_intersect_combo else None,
        "best_combo": best_combo["state"] if best_combo else None,
        "best_combo_ic": best_combo.get("pooled_ic") if best_combo else None,
        "best_combo_pos_years": best_combo.get("positive_years") if best_combo else None,
        "lift_combo_vs_individual": lift,
        "baseline_ic": baseline_ic,
        "total_states_tested": len(individual_states) + len(union_combo_states) + len(intersect_combo_states),
    }
    
    # Add phase ICs if available
    if best_combo:
        summary["phase_ic"] = {
            "dev": best_combo.get("dev_ic"),
            "validation": best_combo.get("validation_ic"),
            "confirmation": best_combo.get("confirmation_ic"),
        }
    
    summary_path = output_dir / f"{ts}_state_combo_alpha_research_branch.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"Saved summary to {summary_path}")
    
    return summary


if __name__ == "__main__":
    main()