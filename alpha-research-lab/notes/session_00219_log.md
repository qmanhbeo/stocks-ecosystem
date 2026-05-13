# Session 219 Log

Date: 2026-05-03

## Completed Experiments (H365-H378 + X1-X5)

### H372 - Volume Leads Price
- **Result**: FAILED
- **IC**: +0.008 (not significant)
- **Conclusion**: Volume does not lead price

### H373 - Sector Relative
- **Result**: FAILED (circular)
- **Conclusion**: Uses actual return as signal

### H374 - Early Session Capture
- **Result**: FAILED (negative IC)
- **IC**: -0.015
- **Conclusion**: First-hour indicators negatively correlated

### H375 - C16 Rate of Change
- **Result**: FAILED
- **IC**: +0.061 vs +0.084 baseline
- **Conclusion**: RoC weaker than level

### H377 - Curvature Weighting
- **Result**: FAILED
- **IC**: +0.013 vs +0.084 baseline
- **Conclusion**: Confidence weighting reduces signal

### X1 - Auction Sequence
- **Result**: FAILED
- **IC**: -0.015
- **Conclusion**: Morning/afternoon volume ratio negative

### X2 - Day Exhaustion Timing
- **Result**: MIXED (validation only)
- **IC**: +0.054 REVERSAL
- **Conclusion**: Late session gain predicts next-day REVERSAL - useful for exit, not entry

### X3 - Pre-Open Gap
- **Result**: NO DATA
- **Conclusion**: No pre-open data available

### X4 - VNINDEX Weight
- **Result**: NO DATA
- **Conclusion**: No weight change data available

### X5 - Lunar Calendar
- **Result**: FAILED
- **IC**: +0.006
- **Conclusion**: No significant lunar effect

---

## Summary

| Test | Result | IC |
|------|--------|-----|
| C16 baseline | PASSED | +0.077 to +0.084 |
| All C16 combinations | FAILED | < baseline |
| Early session (H374) | FAILED | -0.015 |
| Sector relative (H373) | FAILED | - |
| Volume ROC (H375) | FAILED | +0.061 |
| Curvature (H377) | FAILED | +0.013 |
| Auction seq (X1) | FAILED | -0.015 |
| Day exhaustion (X2) | MIXED | +0.054 |
| Lunar (X5) | FAILED | +0.006 |

---

## C16 Champion
**All attempts to improve or combine with C16 have failed.**

---

## Next Actions
1. Return to previous branch work (H93 champion, H340 confirmed)
2. New hypothesis needed
3. Or close this experimental branch