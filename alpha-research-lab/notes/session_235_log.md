# Session 235: Bright Mind eureka tests

**Date:** 2026-05-03
**Focus:** Test S235 bright-mind ideas

## Results

| Test | IC | Result |
|------|-----|-------|
| sentiment_only | 0.010 | WEAK |
| c16_only | 0.078 | baseline |
| c16+sent_combo | 0.071 | FAILED - worse |
| c16+sent+triple | 0.080 | NEUTRAL |
| entry_window_T+0 | 0.078 | baseline |
| entry_window_T+1 | 0.020 | T+0 optimal |
| entry_window_T+2 | 0.004 | decays fast |
| vnindex_momentum_bot20 | 0.090 | PASSED |
| vnindex_momentum_top20 | 0.064 | worse |

## Findings

- **news_c16_divergence**: FAILED - sentiment too weak, combos worse
- **entry_window**: C16 decays fast - T+0 is optimal entry
- **vnindex_momentum**: C16 works better when index momentum is negative (+15% in bottom 20%)
  - Confirms contrarian nature of C16

## Next

- Queue: c13_cross_microstructure, alternative_label_c16
- OR need new bright ideas