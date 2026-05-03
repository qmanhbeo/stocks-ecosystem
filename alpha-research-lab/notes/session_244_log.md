# S244 Session Log

**Date**: 2026-05-03
**Focus**: Test S244 new eureka hypotheses - untested data + mechanisms

## Reference Baselines (Walk-Forward IC)
- Random: ~0.00 (noise benchmark)
- Independent signal threshold: IC > 0.05 = REAL
- C16: +0.078 (used only for enhancement tests)
- S1: +0.149 (best published - PRIMARY for RL)

## Results (2026-05-03)

### rank_time_acceleration
- **Claim**: Rank velocity > rank level
- **Result**: IC = 0.0576
- **vs Random**: +0.06 (**REAL SIGNAL**)
- **vs C16**: -26% (NOT an enhancement - this is independent)
- **Verdict**: REAL - use as standalone state feature

### consecutive_down_days  
- **Claim**: Market down streak amplifies C16
- **Result**: IC = 0.1030
- **vs Random**: +0.10 (**REAL SIGNAL**)
- **Verdict**: REAL - confirms X226, use as filter

## Next Test (in progress)

### dividend_signal_momentum (2026-05-03)
- **Claim**: Dividend announcements drive pre-event accumulation
- **Result**: IC = 0.0934
- **vs Random**: +0.09 (**REAL**) - but year-to-year noisy
- **Verdict**: REAL but inconsistent (some years negative)