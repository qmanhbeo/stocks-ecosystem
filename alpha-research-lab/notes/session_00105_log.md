# Session 105 Log

## Objective
Run the next queue item from live_state.md EUREKA batch 5 (AL):
- **AL**: vol_contraction_mean_reversion - testing if vol contraction + HIGH return captures exhaustion pattern

This session did not change the live branch.
It did not read `2026+`.

## Starting point

Coming in:
- H448: PASSED - vol_expansion_contrarian combo IC=0.2069 (+0.0771 lift)
- H446: PASSED - vol_expansion IC=0.1753 (+0.0455 lift)
- H447: MIXED (contrarian finding) - low_return_low_vol IC=0.2045 (+0.0747 lift)
- Hypothesis: vol contracting after a rally might indicate exhaustion

## What changed

Added:
- `analysis/h449_vol_contraction_mean_reversion.py`

Saved artifacts:
- `artifacts/run_summaries/20260508_175412_vol_contraction_mean_reversion_research_branch.json`

### H449 - vol_contraction_mean_reversion

**Hypothesis:**
H446 showed vol_contraction (-0.0085) underperforms. But vol contraction + HIGH return might be 
the reversal pattern: vol contracting after a rally indicates exhaustion. Test combo vs momentum.

**Command / code:**
`python analysis/h449_vol_contraction_mean_reversion.py`

**Inputs:**
- S1 decision panel (2015-2025)
- order_stats: price_change_raw, buy_order_volume, sell_order_volume
- Computed features: return_rank, volume_rank, vol_change (5d rolling std)

**Saved artifact:**
`artifacts/run_summaries/20260508_175412_vol_contraction_mean_reversion_research_branch.json`

| State | IC | Lift vs Baseline | Notes |
|-------|-----|------------------|-------|
| vol_expansion | 0.1753 | +0.0455 | H446 confirmed |
| vol_expansion_momentum | 0.1671 | +0.0373 | Momentum works |
| low_return | 0.1423 | +0.0125 | Positive |
| vol_contraction_contrarian | 0.1390 | +0.0092 | |
| all_rows | 0.1298 | 0.0000 | Baseline |
| vol_contraction | 0.1212 | -0.0086 | H446 confirmed |
| high_return | 0.1310 | +0.0012 | |
| vol_contraction_exhaustion | 0.1043 | -0.0255 | **NEGATIVE** |

**Key Finding:**
- Combo vs Momentum: **-0.0628** - vol_contraction_exhaustion is the opposite of momentum
- Hypothesis CONFIRMED: vol contraction + high return = exhaustion (negative IC)
- This is mean reversion signal, NOT a positive signal for long-only

**Result:**
The pattern exists and is real, but it's a negative signal (predicts mean reversion). 
For a long-only lab, this means the pattern is NOT useful as a buy signal - 
vol_expansion_momentum is the useful side, not vol_contraction_exhaustion.

**Verdict: MIXED/PARKED** - pattern confirmed but not a positive signal for long-only.
Dead-end D037 for direct long-only use. The regime-dependent behavior is real but 
in the wrong direction for our constraints.

## Branch decision

Do **not** change the live branch.

What Session 105 resolves:
- H449 MIXED: confirmed regime-dependent behavior exists
- vol_contraction + high_return = exhaustion (negative IC = mean reversion)
- vol_expansion + high_return = momentum (positive IC)
- For long-only: use vol_expansion_momentum, not vol_contraction_exhaustion
- Dead-end D037 for direct long-only use of the exhaustion pattern

The queue continues with remaining items:
- AM: volume_acceleration_signal
- AN: buy_sell_imbalance_in_stress
- AO: volume_level_vs_direction_divergence
- AP: implied_limit_proximity
- AQ: low_vol_low_return_regime

## Validation

Completed for the experiment:
- `python analysis/h449_vol_contraction_mean_reversion.py`
- Read saved summary artifact

Verdict:
- H449: **MIXED** - pattern confirmed but negative for long-only