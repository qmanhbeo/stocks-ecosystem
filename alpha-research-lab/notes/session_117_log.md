# Session 117 Log

## Objective
Test whether lagged sector breadth / rotation can route the signal library between the fast reversal family and the slower continuation / reclaim family.

This session did not change the live branch.
It did not read `2026+`.

## What changed

Fixed a column-name mismatch in the quintile summary inside the new H287 audit script before rerunning the experiment.

Saved artifacts:
- `artifacts/run_summaries/20260405_225244_h287_breadth_to_horizon_router_audit_details.json`
- `artifacts/run_summaries/20260405_225244_h287_breadth_to_horizon_router_audit_standalone_signal.json`

### H287 - Breadth-to-Horizon Router Audit
**Hypothesis:**
Lagged sector breadth / rotation should tell us when the fast reversal family (`c13/c9/c12`) should dominate versus when the slower continuation / reclaim family (`c6/c4/W`) should dominate.

**Command / code:**
`conda run -n stocks python analysis/h287_breadth_to_horizon_router_audit.py`

**Inputs:**
- `data/features/xs_rl_signal_matrix.parquet`
- `data/features/xs_sector_rotation_daily.parquet`
- `data/stock/gia_lich_su_VNINDEX_1D.parquet`
- `data/stock/` OHLCV wide panel

**Saved artifact:**
`artifacts/run_summaries/20260405_225244_h287_breadth_to_horizon_router_audit_standalone_signal.json`

| Metric | Value | Note |
|--------|-------|------|
| verdict | `FAIL` | no regime split emerged |
| best state | `breadth_level_lag1` | strongest of the three state variables |
| best abs rho | `0.0353` | too small for a router |
| sign swap | `false` | fast family wins in every breadth quintile |
| q1 gap | `-0.0287` | slow family trails fast family |
| q5 gap | `-0.0126` | still slow family trailing |
| fast 1d mean IC | `+0.0321` | fast family stays strong on 1d |
| slow 5d mean IC | `+0.0166` | slower family is positive, but weaker |
| family gap mean | `-0.0154` | negative across the panel |
| panel rows | `2743` | matched daily state rows |
| panel dates | `2743` | one row per matched date |

**Result:**
The breadth state does not route the library into a fast-versus-slow horizon split. The fast family still dominates in every quintile, the state correlations are weak, and there is no sign swap to justify a router.

**Verdict: FAILED**

## Branch decision

Park the breadth-to-horizon router.
If this idea is revisited, it should use a materially different state variable than lagged sector breadth / rotation.
The next queue item is `replacement-pressure-breadth-throttle`.

## Validation

Completed before the run:
- `conda run -n stocks python analysis/h287_breadth_to_horizon_router_audit.py`

Completed for the experiment:
- read `artifacts/run_summaries/20260405_225244_h287_breadth_to_horizon_router_audit_standalone_signal.json`

Verdict:
- `H287`: **FAILED**
