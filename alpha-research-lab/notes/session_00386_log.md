# H604 - Multi-Signal × Low-Breadth Amplification

**Session**: 386

**Hypothesis**: F445 (composite_2+ = 0.2445) + H529 (low_breadth filter = +0.0266) might AMPLIFY further. Each independently amplifies - now combine.

**Command**: `python analysis/h604_multi_signal_breadth.py`

**Inputs**: 
- S1 panel: xs_barrier_vol_1d_hose_full.parquet
- Order stats: data/order_stats/cafef/order_stats_daily.parquet
- OHLCV: data/stock/gia_lich_su_*_1D.parquet (for Amihud illiquidity)

**Saved artifact**: `artifacts/run_summaries/20260517_174457_h604_multi_signal_breadth_amplification_research_branch.json`

| Metric | Value | Note |
|--------|-------|------|
| composite_2plus_ic | 0.2445 | F445 baseline |
| composite_2plus_low_breadth_ic | 0.2651 | **COMBO** |
| low_breadth_ic | 0.1290 | Alone is weak |
| lift_vs_composite | +0.0206 | **Above +0.01 threshold!** |
| positive_years | 10/11 | Consistent |

**Result**: 
**PASSED**! The multi-signal finding (F445) is amplified further by adding the low_breadth filter. The combination beats each component:
- composite_2+ × low_breadth (0.2651) > composite_2+ alone (0.2445) by +0.0206
- composite_2+ × low_breadth (0.2651) > low_breadth alone (0.1290) by +0.1361
- The combination is stronger than either amplifier alone

This confirms that orthogonal amplifiers stack: F437 (tight+low_breadth), F440 (cofire isolation), F441 (persistence), F442 (accumulation), F445 (multi-signal), and now F447 (multi-signal+low_breadth).

**Verdict: PASSED - Finding F447**

**Next**: 
- H105 (Multi-Signal × Persistence Stacking) - combine F445 with F441/F442 persistence
- Or test specific signal pairs (H106)