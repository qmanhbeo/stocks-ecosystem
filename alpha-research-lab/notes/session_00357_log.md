# Session 357 - H549 Signal Ignorance as Alpha

**Date**: 2026-05-17

**Hypothesis**: Test if composite of weak-signal regimes (high_breadth, ultra_negative, floor_pressure) forms an "ignore" signal that avoids degraded IC periods.

**Command**: `python analysis/h549_signal_ignorance_alpha.py`

**Saved artifact**: `artifacts/run_summaries/20260517_153449_signal_ignorance_alpha.json`

## Results

| Regime | IC | Lift vs Baseline | Rows |
|--------|-----|------------------|------|
| baseline (all) | 0.1277 | — | 821,764 |
| with_ignore_regime | 0.1149 | -0.0127 | 164,924 |
| without_ignore_regime | 0.1306 | +0.0029 | 656,840 |
| high_breadth alone | 0.1149 | -0.0127 | 164,924 |

## Key Finding

**High-breadth dates have WORSE IC** (confirms H525):
- With high_breadth: IC=0.1149 (-0.0127 vs baseline)
- Without high_breadth: IC=0.1306 (+0.0029 vs baseline)

**Effect is WEAK**: The +0.0029 lift is below the +0.01 threshold.

**Data availability**: Ultra_negative and floor_pressure data not available to test - only high_breadth could be evaluated.

## Verdict: MIXED

- High_breadth IS a weak-signal regime (confirms H525)
- Effect size is too small for actionable ignore signal (+0.0029 < +0.01)
- No export to heuristic-trader warranted

**Next**: #59 Cross-Signal Low-Breadth Amplification (test if C23/C24/C25/C26 each have different optimal breadth windows)