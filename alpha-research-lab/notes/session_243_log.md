# S243 Session Log

**Date**: 2026-05-03
**Focus**: Test S243 calendar + combo hypotheses with walk-forward IC

## Reference Baselines (Walk-Forward IC)
- Random: ~0.00 (noise)
- C16: +0.078 
- S1: +0.149 (best published - PRIMARY for RL)

## Tests Run

### February Mid (Feb 15-28)
- **Claim**: Post-Tet recovery effect
- **Result**: IC=0.0858
- **vs Random**: +0.09 (real signal)
- **Verdict**: TIER 2 - calendar filter for RL

### March Quadrant
- **Claim**: March week position matters
- **Result**: early=0.0643, late=0.0833
- **vs Random**: +0.06 to +0.08
- **Verdict**: March late = TIER 2, early = TIER 3

### May Effect
- **Claim**: Historical May pattern
- **Result**: IC=0.0805
- **vs Random**: +0.08
- **Verdict**: TIER 2 (weaker)

### September Call
- **Claim**: Back-to-school effect
- **Result**: early=0.0614, late=0.0791
- **vs Random**: +0.06 to +0.08
- **Verdict**: TIER 2/3

### October Uncertainty
- **Claim**: October volatility effect
- **Result**: IC=0.0817
- **vs Random**: +0.08
- **Verdict**: TIER 2 - calendar filter for RL

### Yearend Window (Dec 20+)
- **Claim**: Last 10 days effect
- **Result**: IC=0.0652
- **vs Random**: +0.07
- **Verdict**: TIER 3 (weak)

### Monday + January Combo
- **Claim**: Monday × January combo
- **Result**: IC=0.1109
- **vs Random**: +0.11 (STRONG signal)
- **Verdict**: TIER 1 - strong calendar combo for RL

### Midyear Rebalancing (Jun-Jul)
- **Claim**: June/July rebalancing
- **Result**: IC=0.0711
- **vs Random**: +0.07
- **Verdict**: TIER 3 (weak) - FAILED

## RL Signal Inventory
| Test | IC | vs Random | Tier | Use |
|------|-----|----------|------|-----|
| monday_jan | 0.1109 | +0.11 | T1 | calendar combo |
| february_mid | 0.0858 | +0.09 | T2 | calendar filter |
| march_late | 0.0833 | +0.08 | T2 | calendar filter |
| monday | 0.0836 | +0.08 | T2 | calendar filter |
| october | 0.0817 | +0.08 | T2 | calendar filter |
| may | 0.0805 | +0.08 | T2 | calendar filter |
| sept_late | 0.0791 | +0.08 | T2 | calendar filter |
| yearend | 0.0652 | +0.07 | T3 | weak |
| midyear | 0.0711 | +0.07 | T3 | weak/failed |
| march_early | 0.0643 | +0.06 | T3 | weak |
| sept_early | 0.0614 | +0.06 | T3 | weak |

## Reusable Script
- `analysis/x240_wf_ic_test.py` — walk-forward IC test

## Key Discoveries
- **monday_jan = TIER 1** - strongest calendar combo (IC 0.11)
- **Feb/Mar/Oct/Mon = TIER 2** - real calendar filters (IC 0.08-0.09)
- These are VALID RL FEATURES for state encoding

## Next Steps
- Test more combos (triple_storm + jan)
- monday_jan is worth promoting as RL filter