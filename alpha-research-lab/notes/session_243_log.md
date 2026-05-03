# S243 Session Log

**Date**: 2026-05-03
**Focus**: Test S243 calendar + combo hypotheses with walk-forward IC

## Reference Baselines (Walk-Forward IC)
- Random: ~0.00 (noise)
- C16: +0.078 
- S1: +0.149 (best published signal - primary for RL)

## Tests Run

### February Mid (Feb 15-28)
- **Claim**: Post-Tet recovery effect
- **Result**: IC=0.0858
- **vs Random**: +0.09 (real signal)
- **vs S1**: -0.06 (below best)
- **Verdict**: REAL SIGNAL

### March Quadrant
- **Claim**: March week position matters
- **Result**: early=0.0643, late=0.0833
- **vs Random**: +0.06 to +0.08
- **Verdict**: March late is real signal

### May Effect
- **Claim**: Historical May pattern
- **Result**: IC=0.0805
- **vs Random**: +0.08 (marginal)
- **Verdict**: WEAK

### September Call
- **Claim**: Back-to-school effect
- **Result**: early=0.0614, late=0.0791
- **vs Random**: +0.06 to +0.08
- **Verdict**: WEAK

### October Uncertainty
- **Claim**: October volatility effect
- **Result**: IC=0.0817
- **vs Random**: +0.08 (real signal)
- **Verdict**: REAL SIGNAL

### Yearend Window (Dec 20+)
- **Claim**: Last 10 days effect
- **Result**: IC=0.0652
- **vs Random**: +0.07 (still real, but weak)
- **Verdict**: WEAK/FAILED

### Monday + January Combo
- **Claim**: Monday × January combo
- **Result**: IC=0.1109
- **vs Random**: +0.11 (STRONG signal)
- **vs S1**: -0.04 (close to best!)
- **Verdict**: REAL SIGNAL - closest to S1

### Midyear Rebalancing (Jun-Jul)
- **Claim**: June/July rebalancing
- **Result**: IC=0.0711
- **vs Random**: +0.07 (barely real)
- **Verdict**: FAILED

## Summary Table (Honest)
| Test | IC | vs Random | vs S1 | Verdict |
|------|-----|----------|-------|--------|
| monday_jan | 0.1109 | +0.11 | -0.04 | REAL - close to S1 |
| february_mid | 0.0858 | +0.09 | -0.06 | REAL |
| march_late | 0.0833 | +0.08 | -0.07 | REAL |
| monday | 0.0836 | +0.08 | -0.07 | REAL |
| october | 0.0817 | +0.08 | -0.07 | REAL |
| may | 0.0805 | +0.08 | -0.07 | WEAK |
| sept_late | 0.0791 | +0.08 | -0.07 | WEAK |
| yearend | 0.0652 | +0.07 | -0.08 | WEAK |
| midyear | 0.0711 | +0.07 | -0.08 | FAILED |
| march_early | 0.0643 | +0.06 | -0.08 | FAILED |
| sept_early | 0.0614 | +0.06 | -0.09 | FAILED |

## Reusable Script
- `analysis/x240_wf_ic_test.py` — walk-forward IC test, updated with S243 tests

## Key Discoveries (Honest)
- Monday+January = IC +0.11 — STRONG, closest to S1 best published
- Feb, March late, Oct = real signals (+0.08 to +0.09)
- Yearend, Midyear = weak/negative signals

## Next Steps
- Test more combos (triple_storm + jan)
- monday_jan is worth promoting as filter