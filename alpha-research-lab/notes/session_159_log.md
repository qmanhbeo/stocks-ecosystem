# Session 159 Log - Skip-Aware Step-Value Hazard (2026-04-10)

## Objective

Test the next honest continuation implied by `H338`.

Question:
- if the one-step label still misses skip-over states, does replacing it with a
  skip-aware continuous target fix the smart-exit branch on the current daily
  state?

This session did not change the live branch.
It stayed long-only.
It did not use `2026` for predictive tuning.

---

## What changed

Added one bounded research script:
- `analysis/h339_skip_aware_step_value_hazard.py`

### H339 - Skip-Aware Step-Value Hazard
**Hypothesis:**
A skip-aware value target,
`max(later_legal_utility) - current_utility`,
will remove the `H337` skip-over ceiling and recover more `H334` oracle uplift
than the immediate-next-step classifier on the same current-day state.

**Command / code:**
`python analysis/h339_skip_aware_step_value_hazard.py`

**Inputs:**
- `artifacts/run_summaries/latest_research_branch_replacement_aware_step_hazard.json`
- `artifacts/portfolio_baselines/20260410_185752_h337_replacement_aware_step_hazard_step_rows.parquet`
- `artifacts/portfolio_baselines/20260410_185752_h337_replacement_aware_step_hazard_phase_results.parquet`

**Saved artifact:**
`artifacts/run_summaries/20260410_193438_h339_skip_aware_step_value_hazard_research_branch_skip_aware_step_value_hazard.json`

| Metric | Value | Note |
|--------|-------|------|
| verdict | `FAILED` | skip-aware label did not rescue the learned policy |
| step rows | `7,717` | same H337 legal-step panel |
| entries | `2,578` | same H334 executed-entry universe |
| features | `79` | unchanged H337 state contract |
| model | `Ridge(alpha=10.0)` | smallest honest target-only follow-up |
| selected margin | `0.0200` | most conservative margin in the tested grid |
| perfect skip-oracle recovered share, validation | `100.00%` | target ceiling is fully removed |
| perfect skip-oracle recovered share, confirmation | `100.00%` | target itself can exactly reproduce H334 |
| validation uplift vs fixed `3d` | `-0.00430` | worse than fixed baseline |
| confirmation uplift vs fixed `3d` | `-0.01109` | worse than fixed baseline |
| validation uplift delta vs H337 | `-0.00676` | worse than prior mixed branch |
| confirmation uplift delta vs H337 | `-0.01362` | worse than prior mixed branch |
| validation non-best-fixed rate | `95.60%` | long-hold bias returned |
| confirmation non-best-fixed rate | `96.04%` | long-hold bias returned |

### What the experiment proved

The skip-aware target itself is not the blocker anymore:
- a perfect skip-aware oracle matched the `H334` global oracle exactly
- recovered share vs `H334` oracle:
  - validation `100.00%`
  - confirmation `100.00%`

So `H338` was directionally right about the label ceiling:
- the skip-over problem was real
- the new target solves it by construction

### Why the learned policy still failed

The learned value model smoothed too aggressively toward positive continuation:
- selected margin:
  - `0.0200`
- predicted mean skip value vs true mean:
  - validation:
    - predicted `0.0273`
    - true `0.0147`
  - confirmation:
    - predicted `0.0270`
    - true `0.0105`

That pushed the policy back into an H336-style long-hold failure mode:
- validation horizon choices:
  - `3d 4.40%`
  - `5d 26.62%`
  - `10d 49.90%`
  - `15d 19.08%`
- confirmation horizon choices:
  - `3d 3.96%`
  - `5d 27.31%`
  - `10d 54.19%`
  - `15d 14.54%`

The per-horizon utility ranking stayed weak where the policy needed it most:
- validation Spearman:
  - overall `0.1644`
  - `3d 0.0462`
  - `5d 0.0379`
  - `10d -0.0068`
- confirmation Spearman:
  - overall `0.2024`
  - `3d 0.1916`
  - `5d -0.0100`
  - `10d 0.1372`

So the new label fixed the skip-over ceiling, but the current daily state plus
simple linear value learner still did not identify when *not* to keep holding.

**Result:**
`H339` rejects the idea that label repair alone is enough on the current daily
state. The exact skip-aware target can reproduce the oracle, but the learned
policy still overpredicts continuation, overrides fixed `3d` almost
everywhere, and underperforms both fixed `3d` and `H337` on holdout.

**Verdict: FAILED**

---

## Branch decision

`H339` closes the current narrow continuation:
- do **not** keep retuning skip-aware margins
- do **not** keep iterating simple target rewrites on the same daily state
- do **not** treat this as evidence that only threshold calibration is missing

If smart-exit ML is reopened later, the next distinct requirement is one of:
- richer post-entry state/data
- a materially different nonlinear / pairwise replacement model
- or a different sequence contract entirely

Until then, park current-state daily smart-exit ML as offline evidence only.

---

## Validation

Completed during the pass:
- ran `python -m py_compile analysis/h339_skip_aware_step_value_hazard.py`
- ran `python analysis/h339_skip_aware_step_value_hazard.py`
- read the saved run summary artifact
- inspected margin-grid, prediction-diagnostic, and skip-oracle artifacts

Additional repo checks were run after note promotion:
- ran `git diff --check`
- reran `python -m py_compile analysis/h337_replacement_aware_step_hazard.py analysis/h338_step_hazard_failure_audit.py analysis/h339_skip_aware_step_value_hazard.py`

The broader test suite was not run.
