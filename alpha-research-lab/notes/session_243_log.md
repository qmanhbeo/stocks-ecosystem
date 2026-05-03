# S243 Session Log

**Date**: 2026-05-03
**Focus**: Test S243 calendar + combo hypotheses with walk-forward IC

## Tests Run

### February Mid (Feb 15-28)
- **Claim**: Post-Tet recovery effect
- **Result**: IC=0.0858
- **Baseline**: 0.078
- **Boost**: +10%
- **Verdict**: PASSED

### March Quadrant
- **Claim**: March week position matters
- **Result**: early=0.0643, late=0.0833
- **Boost**: late +7%
- **Verdict**: PASSED (late wins)

### May Effect
- **Claim**: Historical May pattern
- **Result**: IC=0.0805
- **Boost**: +3%
- **Verdict**: WEAK

### September Call
- **Claim**: Back-to-school effect
- **Result**: early=0.0614, late=0.0791
- **Boost**: late +1%
- **Verdict**: WEAK

### October Uncertainty
- **Claim**: October volatility effect
- **Result**: IC=0.0817
- **Boost**: +5%
- **Verdict**: PASSED

### Yearend Window (Dec 20+)
- **Claim**: Last 10 days effect
- **Result**: IC=0.0652
- **Boost**: -16%
- **Verdict**: FAILED (yearend hurts!)

### Monday + January Combo
- **Claim**: Monday × January combo
- **Result**: IC=0.1109
- **Boost**: +42%
- **Verdict**: **STRONG PASSED** (best new finding!)

### Midyear Rebalancing (Jun-Jul)
- **Claim**: June/July rebalancing
- **Result**: IC=0.0711
- **Boost**: -9%
- **Verdict**: FAILED

## Summary Table
| Test | IC | Baseline | Boost | Verdict |
|------|-----|----------|-------|--------|
| monday_jan | 0.1109 | 0.078 | +42% | **STRONG PASSED** |
| february_mid | 0.0858 | 0.078 | +10% | PASSED |
| march_late | 0.0833 | 0.078 | +7% | PASSED |
| monday | 0.0836 | 0.078 | +7% | PASSED |
| october | 0.0817 | 0.078 | +5% | PASSED |
| may | 0.0805 | 0.078 | +3% | WEAK |
| sept_late | 0.0791 | 0.078 | +1% | WEAK |
| march_early | 0.0643 | 0.078 | -18% | FAILED |
| yearend | 0.0652 | 0.078 | -16% | FAILED |
| midyear | 0.0711 | 0.078 | -9% | FAILED |
| sept_early | 0.0614 | 0.078 | -21% | FAILED |

## Reusable Script
- `analysis/x240_wf_ic_test.py` — walk-forward IC test, updated with S243 tests

## Key Discoveries
- **Monday January combo = +42% boost** — NEW STRONG FINDING!
- February works (+10%)
- March late works (+7%)
- October works (+5%)
- Yearend hurts (-16%)
- Midyear rebalancing doesn't work (-9%)

## Next Steps
- Test more combos (triple_storm + jan)
- Consider monday_jan as new entry filter