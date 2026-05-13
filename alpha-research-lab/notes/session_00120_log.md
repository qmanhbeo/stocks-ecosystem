# Session 120 Log — 2026-05-08

## H449: order_flow_momentum

**Decision: PASSED** (but ACCELERATION does NOT add value)

### Results
- c16_level_high: IC=0.1614 (+0.0326 lift, 11/11 pos years) — BEST
- c16_accel_expanding: IC=0.1219 (-0.0069)
- c16_accel_neutral: IC=0.1287 (-0.0001)
- c16_accel_contracting: IC=0.1303 (+0.0015)
- c16_level_low: IC=0.1192 (-0.0096)
- all_rows: IC=0.1288 (baseline)

### Key insight
**C16 ACCELERATION (second derivative) is NOT predictive** - the acceleration/deceleration 
states perform WORSE than the baseline. However, C16 LEVEL (high) is the strongest state 
at IC=0.1614 (+0.0326 lift), confirming that order pressure MAGNITUDE matters, not its 
change rate.

This confirms H443's "order flow momentum doesn't help" pattern:
- H443: Foreign flow momentum - marginal at best
- H449: C16 acceleration - NEGATIVE (accelerating flows underperform)

The edge comes from LEVELS (high pressure, high volume), not MOMENTUM (changes in pressure).
Use current order pressure as a regime conditioner, not its derivative.

### Connection to queue
- AJ in queue was "order_flow_momentum" - tested and CONFIRMED NEGATIVE
- H447 showed vol LEVEL + return works (contrarian), not vol CHANGE
- H446 showed vol EXPANSION works (REGIME), not momentum

This is a dead-end for acceleration-based signals.

---

## Session 120 Summary

**H449 PASSED but with OPPOSITE insight: acceleration is NOT signal, level IS.**

The queue item "order_flow_momentum" (AJ) is now DEAD-END. C16 level works, not acceleration.

### Next session: session 121
Queue items remaining:
- AK: replacement_quality_revival
- AL: volume_adjusted_return (H447 already tested)
- AM: liquidity_adjusted_return
- AN: news_velocity_as_signal