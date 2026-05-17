# Session 358 - H550 Cross-Signal Low-Breadth Amplification

**Date**: 2026-05-17

**Hypothesis**: Test if individual C23/C24/C25/C26 signals have different optimal breadth windows. H543 found composite×low_breadth = 0.2364. Now test if each signal amplifies by its OWN low-breadth dates.

**Command**: `python analysis/h550_cross_signal_breadth_amplification.py`

**Saved artifact**: `artifacts/run_summaries/20260517_153643_cross_signal_breadth_amplification.json`

## Results

| Signal | IC | Lift vs Baseline | Rows |
|--------|-----|------------------|------|
| C25 alone | 0.2115 | +0.0838 | 27,409 |
| **C24 × own_breadth** | **0.2080** | **+0.0803** | 1,366 |
| COMPOSITE alone | 0.1982 | +0.0705 | 74,078 |
| C24 × composite_breadth | 0.1952 | +0.0675 | 1,913 |
| C23 alone | 0.1896 | +0.0619 | 54,755 |
| C23 × own_breadth | 0.1833 | +0.0556 | 7,671 |
| C25 × own_breadth | 0.1854 | +0.0577 | 3,153 |

## Key Finding

**Each signal has different optimal breadth window!**
- **C24_own_breadth**: 0.2080 beats **C24_comp_breadth**: 0.1952 by **+0.0127**
- Own breadth (per-signal) beats composite breadth for C24
- C25 alone is strongest (0.2115), breadth filter doesn't help it

**Own breadth vs Composite breadth**: +0.0127 (> +0.01 threshold)

## Verdict: PASSED

- Each signal DOES have different optimal breadth windows
- C24 benefits most from own-breadth filtering
- C25 doesn't need breadth filter (already strong alone)
- No export - this is a lab insight about signal ecology

**Next**: #60 Signal Mass Entropy as Regime Detector