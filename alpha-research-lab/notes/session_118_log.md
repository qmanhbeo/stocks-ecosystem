# Session 118 Log

## Objective
Test whether the entry book's own breadth / score-gap state can act as a horizon allocator between the fast reversal family and the slower continuation / reclaim family.

This session did not change the live branch.
It did not read `2026+`.

## What changed

Added the H288 replacement-pressure breadth-throttle audit script.

Saved artifacts:
- `artifacts/run_summaries/20260405_225738_h288_replacement_pressure_breadth_throttle_audit_details.json`
- `artifacts/run_summaries/20260405_225738_h288_replacement_pressure_breadth_throttle_audit_standalone_signal.json`

### H288 - Replacement-Pressure Breadth Throttle Audit
**Hypothesis:**
Lagged candidate-pool breadth and incumbent displacement pressure should tell us when the slower continuation family should dominate versus when the fast reversal family should dominate.

**Command / code:**
`conda run -n stocks python analysis/h288_replacement_pressure_breadth_throttle_audit.py`

**Inputs:**
- `data/features/xs_rl_signal_matrix.parquet`
- `data/features/activation_state_daily.parquet`
- `data/stock/gia_lich_su_VNINDEX_1D.parquet`
- `data/stock/` OHLCV wide panel

**Saved artifact:**
`artifacts/run_summaries/20260405_225738_h288_replacement_pressure_breadth_throttle_audit_standalone_signal.json`

| Metric | Value | Note |
|--------|-------|------|
| verdict | `MIXED` | positive but not a router |
| best state | `candidate_count_lag1` | strongest state variable |
| best abs rho | `0.0679` | positive, but below router bar |
| sign swap | `false` | fast family still wins in every quintile |
| q1 gap | `-0.0270` | slow family trails fast family |
| q5 gap | `-0.0052` | slow family still trails |
| pressure combo rho | `+0.0528` | directionally positive |
| family gap mean | `-0.0154` | negative across the panel |
| panel rows | `2742` | matched daily state rows |
| panel dates | `2742` | one row per matched date |

**Result:**
Book breadth and pressure do matter a little, but they do not flip the fast-vs-slow horizon split. The fast family still wins in every quintile, so this is evidence for a weak allocator, not a router.

**Verdict: MIXED**

## Branch decision

Park the breadth-to-horizon router.
Keep the breadth-pressure state as weak evidence only.
The next queue item is `marginal-slot-label`.

## Validation

Completed before the run:
- `conda run -n stocks python analysis/h288_replacement_pressure_breadth_throttle_audit.py`

Completed for the experiment:
- read `artifacts/run_summaries/20260405_225738_h288_replacement_pressure_breadth_throttle_audit_standalone_signal.json`

Verdict:
- `H288`: **MIXED**
