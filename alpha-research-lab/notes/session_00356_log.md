# Session 356 - H548 Quiet-State Duration Sweet Spot

**Date**: 2026-05-17

**Hypothesis**: H534 found active state has "longer = stronger". Now test if quiet state (high C16) has OPPOSITE pattern - longer = weaker (decay).

**Command**: `python analysis/h548_quiet_state_duration.py`

**Saved artifact**: `artifacts/run_summaries/20260517_152844_quiet_state_duration_sweet_spot_research_branch.json`

## Results

| State | IC | Lift vs Baseline | Positive Years |
|-------|-----|------------------|----------------|
| all_rows (baseline) | 0.1302 | — | 11/11 |
| **Active state** | | | |
| active_state | 0.1851 | **+0.0549** | 11/11 |
| duration_8pl_active | 0.1835 | **+0.0533** | 11/11 |
| duration_2_3d_active | 0.1884 | **+0.0582** | 11/11 |
| **Quiet state** | | | |
| quiet_state | 0.0859 | **-0.0443** | 11/11 |
| duration_1d_quiet | 0.1193 | -0.0109 | 11/11 |
| duration_8pl_quiet | 0.0749 | **-0.0553** | 11/11 |

## Key Finding: DECAY Pattern Confirmed!

**Quiet state shows DECAY** (opposite of active):
- duration_1d_quiet: IC=0.1193
- duration_8pl_quiet: IC=0.0749
- **Decay magnitude: +0.0444** (1d is stronger than 8+!)

**BUT**: Quiet state is ANTI-PREDICTIVE overall - it's worse than baseline by -0.0443.

**Interpretation**: 
- Active state: longer = stronger (sustained hidden demand builds)
- Quiet state: longer = weaker (signal gets stale)
- BUT quiet_state itself is not a good signal - it's anti-predictive

This validates the hypothesis about opposite duration patterns between active and quiet states, but quiet state is not promotion-worthy.

## Verdict: FAILED

The decay pattern exists within quiet state, but quiet_state overall is worse than baseline. No signal to export.

**Next**: #51 Signal Ignorance as Alpha (test if avoiding weak-signal regimes helps)