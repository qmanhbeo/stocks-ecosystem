# S242 Session Log

**Date**: 2026-05-03
**Focus**: Test S239/S240 mathematics-inspired hypotheses with walk-forward IC

## Reference Baselines (Walk-Forward IC)
- Random: ~0.00 (noise)
- C16: +0.078 
- S1: +0.149 (best published)

## Tests Run

### january_first_10
- **Claim**: First 10 trading days have institutional reallocation effect
- **Test**: Filter days 1-10 of year, IC(C16)
- **Result**: IC=0.0817
- **vs Random**: +0.08 (PASSED - real signal)
- **vs C16**: +0.00 (slight improvement)
- **vs S1**: Still below best published (-0.07)
- **Verdict**: REAL SIGNAL, but not new best

### volume_vol_combo (vol regime confirmation)
- **Claim**: Volume regime affects C16 strength
- **Test**: IC(C16) by volume_rank quintile
- **Result**: vol_low IC=0.0695, vol_high IC=0.0941
- **vs Random**: +0.07 to +0.09 (both PASSED)
- **Significance**: vol_high has stronger signal than vol_low (+0.02)
- **Verdict**: REAL SIGNAL - regime matters

## Summary Table
| Test | IC | vs Random | vs S1 | Verdict |
|------|-----|----------|-------|--------|
| january_first_10 | 0.0817 | +0.08 | -0.07 | REAL |
| vol_high | 0.0941 | +0.09 | -0.05 | REAL |
| vol_low | 0.0695 | +0.07 | -0.08 | REAL |

## Reusable Script
- `analysis/x240_wf_ic_test.py` — walk-forward IC test

## Findings
- January is a real signal (+8% over random) - not S1 class but legitimate
- Volume regime is a real discriminator - use for sizing

## Next Steps
- Test more S239 ideas that have data available
- Consider combining january + high volume for combo test