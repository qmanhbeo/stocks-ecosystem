# Session 157 Log - Replacement-Aware Step-Hazard (2026-04-10)

## Objective

Take the next smart-exit step after:
- `H334` showed a constrained legal-exit oracle has material upper-bound uplift
- `H335` failed to distill that oracle with a generic legal-horizon hold/sell model
- `H336` failed to recover it with entry-time action-value horizon routing

Question:
- can a one-step, current-hold-state hazard model fix the `H336` failure mode
  by deciding only whether to wait one more legal step versus exit now?

This session did not change the live branch.
It stayed long-only.
It did not use `2026` for predictive tuning.

---

## What changed

Added one bounded research script:
- `analysis/h337_replacement_aware_step_hazard.py`

### H337 - Replacement-Aware Step-Hazard
**Hypothesis:**
A one-step hazard that uses current hold-day state and a replacement-pressure
proxy can recover useful H334 oracle uplift better than entry-time routing or a
generic hold-label classifier.

**Command / code:**
`python analysis/h337_replacement_aware_step_hazard.py`

**Inputs:**
- `artifacts/run_summaries/latest_research_branch_exit_oracle_upper_bound.json`
- `artifacts/portfolio_baselines/20260410_134038_h334_exit_oracle_upper_bound_entry_outcomes.parquet`
- `artifacts/portfolio_baselines/20260410_134038_h334_exit_oracle_upper_bound_horizon_outcomes.parquet`
- `artifacts/run_summaries/latest_portfolio_exit_strength_exhaustion.json`
- `data/features/xs_rl_signal_matrix.parquet`
- `data/features/activation_state_daily.parquet`
- `data/features/execution/tradability_daily.parquet`
- `data/features/event_surface_daily.parquet`
- `data/stock/`

**Saved artifact:**
`artifacts/run_summaries/20260410_185752_h337_replacement_aware_step_hazard_research_branch_replacement_aware_step_hazard.json`

| Metric | Value | Note |
|--------|-------|------|
| verdict | `MIXED` | improved the branch, but not enough to integrate |
| step rows | `7,717` | legal step decisions at `3d / 5d / 10d` |
| policy entries | `2,578` | same H334 executed-entry universe |
| feature count | `79` | current state, entry state, activation, event, and replacement features |
| current event features | `15` | event surface v1 features included in the first pass |
| local H211 params | `0.15 / 0.05` | return-since-entry / score-drop thresholds |
| dev decision AUC | `0.5771` | real but modest step signal |
| validation decision AUC | `0.5107` | barely above random |
| confirmation decision AUC | `0.5587` | modest confirmation signal |
| validation uplift vs fixed `3d` | `+0.00245` | positive out of sample |
| confirmation uplift vs fixed `3d` | `+0.00253` | positive out of sample |
| validation delta vs local H211 | `+0.00742` | beats the local H211 rule on the same entry universe |
| confirmation delta vs local H211 | `+0.03246` | materially better than the local H211 rule |
| validation oracle uplift recovered | `6.14%` | still small |
| confirmation oracle uplift recovered | `5.75%` | still small |
| validation model / oracle horizon match | `32.49%` | better than `H335/H336` but still limited |
| confirmation model / oracle horizon match | `45.37%` | meaningfully improved versus `H336` |

The policy no longer hallucinates long holds:
- validation model horizon choices:
  - `3d 63.31%`
  - `5d 14.88%`
  - `10d 4.82%`
  - `15d 16.98%`
- confirmation model horizon choices:
  - `3d 73.13%`
  - `5d 10.13%`
  - `10d 5.73%`
  - `15d 11.01%`

This is the opposite shape of `H336`, which over-pushed entries into `15d`.
But the new hazard is still too conservative relative to the oracle:
- oracle horizon choices on validation:
  - `3d 35.22%`
  - `5d 22.22%`
  - `10d 18.24%`
  - `15d 24.32%`
- oracle horizon choices on confirmation:
  - `3d 46.26%`
  - `5d 18.06%`
  - `10d 17.62%`
  - `15d 18.06%`

Top standardized signals in the dev hazard model:
- `current_event_density_20d`
- `entry_score__full_library`
- `full_score_drop_since_entry`
- `current_recent_any_filing_20d`
- `current_buyable_top5_cutoff_score`

**Result:**
`H337` materially improved the smart-exit branch. Unlike `H336`, it no longer
learns a bad long-horizon preference, and unlike the local H211 rule it keeps
some value on the H334 entry universe. But the out-of-sample uplift remains too
small relative to the oracle gap to justify integration.

**Verdict: MIXED**

---

## Branch decision

`H337` is the best current daily-data smart-exit formulation so far, but it is
still only mixed offline evidence:
- do **not** integrate this policy
- do **not** reopen `H335` or `H336`
- if continuing the branch, stay inside the one-step current-state hazard family
- the next honest step is either:
  - a stronger replacement-relative step label
  - a smaller state family derived from the `H337` evidence
- otherwise park smart-exit ML until better post-entry data exists

---

## Validation

Completed during the pass:
- ran `python -m py_compile analysis/h337_replacement_aware_step_hazard.py`
- ran `python analysis/h337_replacement_aware_step_hazard.py`
- read the saved run summary artifact
- inspected the saved policy, local H211 benchmark, and step-row artifacts
- ran `git diff --check`
- reran `python -m py_compile analysis/h334_exit_oracle_upper_bound.py analysis/h335_exit_mdp_lite_distillation.py analysis/h336_action_value_horizon_router.py analysis/h337_replacement_aware_step_hazard.py`

The broader test suite was not run.
