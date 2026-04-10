# Session 155 Log — Exit MDP-Lite Distillation (2026-04-10)

## Objective

Take the next smart-exit step after `H334` passed the legal-oracle upper-bound
audit:
- `H335` exit-MDP-lite distillation

Question:
- can a simple ex-ante hold-vs-sell classifier recover a material share of the
  H334 oracle uplift without using future path outcomes at inference?

This session did not change the live branch.
It stayed long-only.
It did not use `2026` for predictive tuning.

---

## What changed

Added one bounded research script:
- `analysis/h335_exit_mdp_lite_distillation.py`

### H335 - Exit MDP-Lite Distillation
**Hypothesis:**
At legal scheduled exit horizons, a simple dev-trained classifier can decide
whether to sell now or hold to a later legal horizon and recover useful H334
oracle uplift walk-forward.

**Command / code:**
`python analysis/h335_exit_mdp_lite_distillation.py`

**Inputs:**
- `artifacts/run_summaries/latest_research_branch_exit_oracle_upper_bound.json`
- `artifacts/portfolio_baselines/20260410_134038_h334_exit_oracle_upper_bound_entry_outcomes.parquet`
- `artifacts/portfolio_baselines/20260410_134038_h334_exit_oracle_upper_bound_horizon_outcomes.parquet`
- `data/features/xs_rl_signal_matrix.parquet`
- `data/features/activation_state_daily.parquet`
- `data/features/execution/tradability_daily.parquet`
- `data/stock/`

**Saved artifact:**
`artifacts/run_summaries/20260410_135144_h335_exit_mdp_lite_distillation_research_branch_exit_mdp_lite_distillation.json`

| Metric | Value | Note |
|--------|-------|------|
| verdict | `FAILED` | do not integrate this policy |
| decision rows | `7,717` | legal `3d / 5d / 10d` hold/sell decisions |
| policy entries | `2,578` | same H334 executed-entry universe |
| feature count | `57` | path, score, signal, activation, tradability features |
| hold threshold | `0.50` | fixed threshold, no retuning |
| dev decision AUC | `0.6299` | classifier sees some in-sample structure |
| validation decision AUC | `0.5897` | still above random |
| confirmation decision AUC | `0.5746` | still above random |
| dev model uplift vs fixed `3d` | `+0.00472` | only `7.92%` of oracle uplift recovered |
| validation model uplift vs fixed `3d` | `-0.00037` | underperforms fixed `3d` |
| confirmation model uplift vs fixed `3d` | `-0.00918` | materially worse than fixed `3d` |
| validation oracle uplift recovered | `-0.93%` | negative recovery |
| confirmation oracle uplift recovered | `-20.88%` | negative recovery |
| validation model / oracle horizon match | `23.27%` | weak imitation |
| confirmation model / oracle horizon match | `19.82%` | weak imitation |

**Result:**
The classifier sees some ex-ante signal in AUC space, but the induced sequential
policy is not economically useful. It tends to hold too long relative to fixed
`3d`, choosing `5d/10d/15d` on most validation and confirmation entries, and
that loses utility out of sample. This closes the first simple MDP-lite
distillation contract.

**Verdict: FAILED**

---

## Branch decision

`H335` closes the simple `exit-mdp-lite` integration path:
- do **not** integrate this learned policy
- do **not** retune the `0.50` threshold against validation / confirmation
- do **not** jump from this to neural/offline RL
- if the smart-exit branch continues, move to a materially different label:
  - `discrete-exit-hazard`

---

## Validation

Completed during the pass:
- ran `python -m py_compile analysis/h335_exit_mdp_lite_distillation.py`
- ran `python analysis/h335_exit_mdp_lite_distillation.py`
- read the saved run summary artifact
- inspected the saved policy artifact after fixing relative-return carry-through

The broader test suite was not run.
