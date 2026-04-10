# Session 156 Log - Action-Value Horizon Router (2026-04-10)

## Objective

Take the next smart-exit distillation step after:
- `H334` showed a constrained legal-exit oracle has material upper-bound uplift
- `H335` failed to distill that oracle with a simple scheduled hold/sell policy

Question:
- can an entry-time action-value model predict each legal exit horizon's utility
  and choose a non-`3d` horizon only when the predicted utility margin is large
  enough?

This session did not change the live branch.
It stayed long-only.
It did not use `2026` for predictive tuning.

---

## What changed

Added one bounded research script:
- `analysis/h336_action_value_horizon_router.py`

### H336 - Action-Value Horizon Router
**Hypothesis:**
Predict per-horizon exit utility from entry-time daily state, then override the
best fixed `3d` exit only when the predicted best legal horizon has a
dev-selected utility margin.

**Command / code:**
`python analysis/h336_action_value_horizon_router.py`

**Inputs:**
- `artifacts/run_summaries/latest_research_branch_exit_oracle_upper_bound.json`
- `artifacts/portfolio_baselines/20260410_134038_h334_exit_oracle_upper_bound_entry_outcomes.parquet`
- `data/features/xs_rl_signal_matrix.parquet`
- `data/features/activation_state_daily.parquet`
- `data/features/execution/tradability_daily.parquet`

**Saved artifact:**
`artifacts/run_summaries/20260410_140352_h336_action_value_horizon_router_research_branch_action_value_horizon_router.json`

| Metric | Value | Note |
|--------|-------|------|
| verdict | `FAILED` | do not continue entry-time value routing on current daily features |
| entries | `2,578` | same H334 executed-entry universe |
| horizons | `3d / 5d / 10d / 15d` | legal scheduled exit horizons |
| feature count | `32` | entry-time daily state features |
| model type | `GradientBoostingRegressor(max_depth=2, n_estimators=80, min_samples_leaf=30)` | one regressor per horizon |
| selected margin | `0.0000` | selected on dev only |
| dev model uplift vs fixed `3d` | `+0.02075` | `34.81%` of oracle uplift recovered |
| validation model uplift vs fixed `3d` | `-0.00406` | negative out of sample |
| confirmation model uplift vs fixed `3d` | `-0.00960` | materially negative out of sample |
| validation oracle uplift recovered | `-10.16%` | negative recovery |
| confirmation oracle uplift recovered | `-21.84%` | negative recovery |
| validation override rate | `86.37%` | too aggressive away from fixed `3d` |
| confirmation override rate | `82.82%` | too aggressive away from fixed `3d` |
| validation model / oracle horizon match | `22.85%` | weak imitation |
| confirmation model / oracle horizon match | `25.11%` | weak imitation |

Per-horizon rank quality was weak out of sample:
- validation Spearman:
  - `h3 0.1048`
  - `h5 0.0686`
  - `h10 0.0303`
  - `h15 0.0641`
- confirmation Spearman:
  - `h3 0.0777`
  - `h5 -0.0739`
  - `h10 0.0932`
  - `h15 0.0543`

The learned router overrode the fixed `3d` exit too often:
- validation choices:
  - `3d 13.63%`
  - `5d 20.13%`
  - `10d 11.95%`
  - `15d 54.30%`
- confirmation choices:
  - `3d 17.18%`
  - `5d 36.12%`
  - `10d 8.37%`
  - `15d 38.33%`

**Result:**
The action-value router fit the dev oracle gap but failed on validation and
confirmation. It overrode fixed `3d` on most entries and pushed too many
positions into longer horizons without recovering oracle utility.

**Verdict: FAILED**

---

## Branch decision

`H336` closes the entry-time action-value horizon-router path for the current
daily feature state:
- do **not** integrate this policy
- do **not** rescue it with validation / confirmation margin retuning
- do **not** continue more entry-time value-routing variants on the same state
- if smart-exit work continues, move to a materially different target:
  - `discrete-exit-hazard`
- otherwise park smart-exit ML until new post-entry state/data exists

---

## Validation

Completed during the pass:
- ran `python -m py_compile analysis/h336_action_value_horizon_router.py`
- ran `python analysis/h336_action_value_horizon_router.py`
- read the saved run summary artifact
- inspected the saved scored-entry and margin-grid artifacts
- ran `git diff --check`
- reran `python -m py_compile analysis/h334_exit_oracle_upper_bound.py analysis/h335_exit_mdp_lite_distillation.py analysis/h336_action_value_horizon_router.py`

The broader test suite was not run.
