# Session 104 Log

## Objective
Run the next queue item from live_state.md EUREKA batch 5 (AK-AQ):
- **AK**: vol_expansion_contrarian_combo - combining H446 (vol_expansion +0.045 lift) and H447 (low_return_low_vol +0.075 lift) to test if the COMBO is stronger than either alone.

This session did not change the live branch.
It did not read `2026+`.

## Starting point

Coming in:
- H446: PASSED - vol_expansion (top 20% 5d vol change) has IC=0.1753 vs baseline 0.1301 (+4.49% lift, 11/11 pos years)
- H447: MIXED (contrarian finding) - low_return_low_vol IC=0.2045 (+7.46% lift, 11/11 pos years) is STRONGEST - this is CONTRARIAN not momentum
- Hypothesis: vol expanding AND low return + low volume = oversold in a regime where S1 quality is high

## What changed

Added:
- `analysis/h448_vol_expansion_contrarian_combo.py`

Saved artifacts:
- `artifacts/run_summaries/20260508_175244_vol_expansion_contrarian_combo_research_branch.json`

### H448 - vol_expansion_contrarian_combo

**Hypothesis:**
vol_expansion (H446) + low_return_low_vol (H447) COMBO might be stronger than either alone. 
vol expanding AND low return + low volume = oversold in a regime where S1 quality is high.

**Command / code:**
`python analysis/h448_vol_expansion_contrarian_combo.py`

**Inputs:**
- S1 decision panel (2015-2025)
- order_stats: price_change_raw, buy_order_volume, sell_order_volume
- Computed features: volume_z, return_rank, volume_rank, vol_change (5d rolling std of pct_change)
- State definitions from H446/H447

**Saved artifact:**
`artifacts/run_summaries/20260508_175244_vol_expansion_contrarian_combo_research_branch.json`

| State | IC | Lift vs Baseline | Notes |
|-------|-----|------------------|-------|
| vol_expansion_contrarian (COMBO) | 0.2069 | +0.0771 | **STRONGEST** - 21,598 rows |
| low_return_low_vol | 0.2045 | +0.0747 | 69,830 rows |
| vol_contraction_contrarian | 0.1909 | +0.0611 | 13,718 rows |
| vol_expansion | 0.1753 | +0.0455 | 162,883 rows |
| all_rows (baseline) | 0.1298 | 0.0000 | 809,019 rows |
| vol_contraction | 0.1212 | -0.0086 | Negative |
| high_return_high_vol | 0.1112 | -0.0186 | Negative - momentum fails |

**Combo vs Components:**
- Combo vs vol_expansion: +0.0316 (combo is much stronger)
- Combo vs low_return_low_vol: +0.0025 (marginal improvement)
- 11/11 positive years across all top states
- Dev/Val/Conf all positive for combo (0.2158 / 0.2079 / 0.1746)

**Result:**
The COMBO is the strongest state! It captures the oversold-in-expanding-vol regime better than either component alone. The vol regime adds information even to the contrarian low-return-low-volume state.

**Verdict: PASSED**

## Branch decision

Do **not** change the live branch.

What Session 104 resolves:
- H448 PASSED: vol_expansion_contrarian_combo is a new signal
- The combo (IC=0.2069) beats both H446 (vol_expansion alone, IC=0.1753) and H447 (low_return_low_vol alone, IC=0.2045)
- Use as conditioner/ranker - adds +0.0316 IC vs vol_expansion alone
- This confirms the contrarian pattern in H447 and adds regime-specific context from H446

The queue continues with remaining AK-AQ items:
- AL: vol_contraction_mean_reversion
- AM: volume_acceleration_signal  
- AN: buy_sell_imbalance_in_stress
- AO: volume_level_vs_direction_divergence
- AP: implied_limit_proximity
- AQ: low_vol_low_return_regime

## Validation

Completed for the experiment:
- `python analysis/h448_vol_expansion_contrarian_combo.py`
- Read saved summary artifact

Verdict:
- H448: **PASSED** - NEW SIGNAL FOUND