# H596 - Zero-Cofire Edge Test

**Session**: 385

**Hypothesis**: F440 showed Q1 cofire (few competitors) is strong (IC=0.2064). But Q1 includes "1-2 other signals". Maybe "ZERO" (completely isolated, no other signals firing) is even stronger than Q1.

**Command**: `python analysis/h596_zero_cofire_edge.py`

**Inputs**: 
- S1 panel: xs_barrier_vol_1d_hose_full.parquet
- C16 panel: xs_order_pressure_daily.parquet (for order_volume_ratio_rank)

**Saved artifact**: `artifacts/run_summaries/20260517_174242_h596_zero_cofire_edge_research_branch.json`

| Metric | Value | Note |
|--------|-------|------|
| isolated_ic | NaN | Too sparse (32 rows) |
| few_ic | NaN | Too sparse (66 rows) |
| many_ic | 0.1648 | Crowded = 4+ others |
| any_active_ic | 0.1647 | Any active state |
| baseline_ic | 0.1302 | All rows |

**Result**: 
Attempted to use C16 active state (rank < 0.2) as proxy for signal firing, then count competitors per day. This approach is too narrow compared to the original F440 which used actual C23/C24/C25/C26 signal firing.

The original F440 computed cofire_count from C23 (high_illiq × vol_expansion), C24 (ceiling_count >= 2), C25 (vwap_below × vol_expansion), C26 (buy_heavy × illiq × vol_expansion). Using just C16 as proxy doesn't capture the same signal ecology.

**Verdict: FAILED - Data Constraint**

The experiment cannot be run with available data without computing C23/C24/C25/C26 signals from raw order_stats and OHLCV data. This requires:
- vol_change_pct from order_stats
- amihud_illiq computed inline from OHLCV
- ceiling_count parsed from price_change_raw
- vwap_deviation and buy_sell_imbalance

**Related findings**:
- F437 (H531): tight + low_breadth = 0.1979 (+0.0702 vs baseline)
- F440 (H82): cofire Q1 = 0.2064, Q4 = 0.1259 (+0.0805 lift)
- F445 (H95): composite_2+ = 0.2445 (multiple signals together strongest)

**Next**: 
- H97 (Order Arrival Micro-Structure) - test if arrival rate (orders per minute) × tight_capacity = stronger signal
- Or move to one of the multi-signal amplification ideas from H104-H112