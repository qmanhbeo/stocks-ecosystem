# Session 312 - 2026-05-08

## H433: state_transition_not_event

**Hypothesis:** Event timing matters as TRANSITION, not raw feature. Event-count delta (not level) vs same-day vs next-day predicts forward.

**Command / code:**
`python3 analysis/h433_state_transition_not_event.py`

**Inputs:**
- `data/features/xs_barrier_vol_1d_hose_full.parquet` - S1 scores and targets
- `data/features/xs_order_pressure_daily.parquet` - event count data

**Saved artifact:**
`artifacts/run_summaries/h433_state_transition_not_event_summary.json`

**Results:**

| Event-Count Delta Quintile | Mean IC | Lift vs Baseline |
|----------------------------|---------|------------------|
| D1_decr | +0.1109 | -0.0071 |
| D2 | +0.1269 | **+0.0088** |
| D3 | +0.1221 | +0.0040 |
| D4 | +0.1116 | -0.0064 |
| D5_incr | +0.1207 | +0.0027 |

Baseline (score_h413): mean IC +0.1181
Event count level: mean IC -0.0065 (negative!)

**Result:**
MIXED - D2 (moderate decreasing delta) has best lift (+0.0088), but pattern is inconsistent. Event-count level itself is negative IC (-0.0065), so delta provides some value but not a clean signal.

**Verdict: MIXED**

**Interpretation:**
- Event-count delta is marginally better than level
- D2 (moderate decrease) is the best bucket but effect is small
- Not a strong enough signal to promote

**Next step:** Stop - exhausted queue items that can be tested with available data