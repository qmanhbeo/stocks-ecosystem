# Session 380 — 2026-05-17

## H84 - Active-Set Persistence as Signal Quality Predictor

**Hypothesis:** Test active_persistence (active_days_last_10 / 10) - high persistence = consistently present = strong hidden demand. Compare Q4 (8-10 active/10d) vs Q1 (0-2 active/10d) vs raw active IC.

**Source:** H534 (duration_8pl strong), H522 (long duration anti-predictive for symbolic), H566 (current active best).

**Command / code:** Inline Python test

**Inputs:**
- S1 panel: xs_barrier_vol_1d_hose_full.parquet
- C16 panel: xs_order_pressure_daily.parquet
- Years: 2015-2025
- Persistence: count of active days in prior 9 days / 9

**Saved artifact:** None (inline test)

| Metric | Value | Note |
|--------|-------|------|
| all_rows baseline | IC=0.1277 (n=821,764) | |
| Active state (any) | IC=0.1598 (n=127,566) | |
| Active + Q1 (transient 0-2d) | IC=0.1346 (n=56,820) | -0.0252 vs active |
| Active + Q4 (sustained 7-9d) | IC=0.1825 (n=16,601) | +0.0227 vs active |
| Q4 vs Q1 lift | +0.0386 | Strong separation |

**Year-by-year:**
- Q4 (sustained): 11/11 positive, mean 0.1820
- Q1 (transient): 11/11 positive, mean 0.1434

**Result:**
PASSED. Active-set persistence is a strong signal conditioner:
- Stocks that have been consistently active (Q4) have significantly stronger signal
- Transient active stocks (Q1) are weaker than average active state
- The +0.0386 lift between Q4 vs Q1 is well above +0.01 threshold
- 11/11 positive years confirms robustness
- Mechanism: sustained presence in active state indicates persistent hidden demand, not one-off activation

**Verdict: PASSED (Finding F441)**

**Key insight:** This is consistent with H534's "duration_8pl = strong" finding - longer time in active state predicts stronger signal. The persistence ratio (rolling 9-day) gives a more granular view than binary duration threshold.

**Next action:** This is a promotion-worthy finding. Continue with H85 (State_quiet × C27 as Negative Router).