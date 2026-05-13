# Session 221: liquid_braid_stack Test

Date: 2026-05-03
Focus: Test X53 (liquid) + X54 (braid) double filter

## Hypothesis
- Claim: C16 filtered by BOTH high liquidity AND low sector kurtosis = super-signal
- Mechanism: Liquid stocks + unanimous sector pressure = institutional conviction

## Results

| Filter | IC | n | vs Baseline |
|--------|-----|-----|-------------|
| Baseline | +0.0777 | 553,857 | — |
| C16>50% only | +0.0611 | 286,035 | -21% |
| X53 (C16+liquid) | +0.0973 | 55,623 | **+25%** ✅ |
| X54 (C16+braid) | +0.0803 | 124,574 | +3% |
| X53+X54 stack | +0.0683 | 63,094 | -12% ❌ |
| FULL STACK | +0.0634 | 13,353 | -18% ❌ |

## Verdict: MIXED

- X53 (liquid) works alone: +25% IC boost
- X54 (braid) works alone: +3% (weak)
- But stacking FILTERS HURTS: combined is WORSE
- Liquid and braid are SUBSTITUTES, not complements

## Why?

- Both filters reduce sample size substantially
- Over-filtering leaves only random noise
- Should pick ONE, not both

## Scripts

- `analysis/x221_liquid_braid_stack.py` - reusable double-filter test

## Next Steps

- Use X53 ALONE for the liquid filter
- Kill the stack idea
- Move to next branch in queue