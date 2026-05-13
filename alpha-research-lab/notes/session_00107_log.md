# Session 107 Log

## Objective
Run the next queue item from live_state.md EUREKA batch 5 (AN):
- **AN**: buy_sell_imbalance_in_stress - testing buy_sell_volume_imbalance × vol_regime

This session did not change the live branch.
It did not read `2026+`.

## Starting point

Coming in:
- H448: PASSED - vol_expansion_contrarian combo IC=0.2069 (+0.0771 lift)
- H449: MIXED - vol_contraction_exhaustion negative IC
- H450: MIXED - volume acceleration secondary to volume level
- Hypothesis: imbalance works differently in vol_expansion vs vol_contraction

## What changed

Added:
- `analysis/h451_buy_sell_imbalance_in_stress.py`

Saved artifacts:
- `artifacts/run_summaries/20260508_175605_buy_sell_imbalance_in_stress_research_branch.json`

### H451 - buy_sell_imbalance_in_stress

**Hypothesis:**
order_stats has buy_sell_volume_imbalance. Does it work differently in vol_expansion 
vs vol_contraction regimes? Imbalance might signal hidden depth in stress (expansion), 
crowd in calm (contraction). Test imbalance × vol_regime vs forward IC.

**Command / code:**
`python analysis/h451_buy_sell_imbalance_in_stress.py`

**Inputs:**
- S1 decision panel (2015-2025)
- order_stats: buy_sell_volume_imbalance, computed vol_change (5d rolling std)

**Saved artifact:**
`artifacts/run_summaries/20260508_175605_buy_sell_imbalance_in_stress_research_branch.json`

| State | IC | Lift vs Baseline | Notes |
|-------|-----|------------------|-------|
| **buy_heavy_expansion** | **0.1809** | **+0.0508** | **STRONGEST - NEW SIGNAL** |
| vol_expansion | 0.1756 | +0.0455 | |
| imbalance_neutral | 0.1516 | +0.0215 | |
| buy_heavy | 0.1353 | +0.0052 | |
| all_rows | 0.1301 | 0.0000 | Baseline |
| vol_contraction | 0.1206 | -0.0095 | |
| buy_heavy_contraction | 0.1109 | -0.0192 | Negative in contraction |
| sell_heavy_expansion | 0.0854 | -0.0447 | Always negative |
| sell_heavy_contraction | 0.0854 | -0.0447 | |
| sell_heavy | 0.0816 | -0.0485 | |

**Key Finding:**
- **buy_expansion vs buy_contraction: +0.0699** - buy-heavy works MUCH better in expansion!
- Sell-heavy is always negative - no regime benefit
- buy_heavy_expansion beats both vol_expansion alone (+0.0455) and buy_heavy alone (+0.0052)

**Result:**
NEW SIGNAL! buy_heavy_expansion combines the two positive factors (buy-heavy imbalance 
and vol expansion) into a stronger combined state (+0.0508 lift). This is a regime-dependent 
imbalance signal that only works in vol expansion periods.

**Verdict: PASSED** - NEW SIGNAL (F393)

## Branch decision

Do **not** change the live branch.

What Session 107 resolves:
- H451 PASSED: buy_heavy_expansion is a new signal with +0.0508 IC lift
- Adds to the signal library: regime-dependent imbalance in expansion is real
- Use as conditioner: buy-heavy imbalance only works in vol expansion periods

The queue continues with remaining items:
- AO: volume_level_vs_direction_divergence
- AP: implied_limit_proximity
- AQ: low_vol_low_return_regime

## Validation

Completed for the experiment:
- `python analysis/h451_buy_sell_imbalance_in_stress.py`
- Read saved summary artifact

Verdict:
- H451: **PASSED** - NEW SIGNAL FOUND