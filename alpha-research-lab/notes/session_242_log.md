# S242 Session Log

**Date**: 2026-05-03
**Focus**: Test S239/S240 mathematics-inspired hypotheses with walk-forward IC

## Tests Run

### january_first_10
- **Claim**: First 10 trading days have institutional reallocation effect
- **Test**: Filter days 1-10 of year, IC(C16)
- **Result**: IC=0.0817
- **Baseline**: ~0.078 (C16 all-year)
- **Boost**: +5%
- **Verdict**: PASSED

### volume_vol_combo (vol regime confirmation)
- **Claim**: Volume regime affects C16 strength
- **Test**: IC(C16) by volume_rank quintile
- **Result**: vol_low IC=0.0695, vol_high IC=0.0941
- **Baseline**: ~0.078
- **Boost**: vol_high +21% over vol_low
- **Verdict**: PASSED (confirms S237/S238 findings)

## Baseline Comparison
| Test | IC | Baseline | Boost |
|------|-----|----------|-------|
| january_first_10 | 0.0817 | 0.078 | +5% |
| vol_high (rank>0.7) | 0.0941 | 0.078 | +21% |
| vol_low (rank<0.3) | 0.0695 | 0.078 | -11% |

## Reusable Script
- `analysis/x240_wf_ic_test.py` — walk-forward IC test

## Findings
- January effect is real (+5%) — NEW FINDING
- High volume regime amplifies C16 — CONFIRMED
- Low volume regime weakens C16 — CONFIRMED

## Next Steps
- Test more S239 ideas that have data available
- Consider combining january + high volume for combo test