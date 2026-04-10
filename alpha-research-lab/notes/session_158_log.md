# Session 158 Log - Step-Hazard Failure Audit (2026-04-10)

## Objective

Diagnose why `H337` stayed mixed instead of clearing the smart-exit bar.

Question:
- is the blocker mainly:
  - the one-step label itself
  - the fixed `0.50` threshold
  - a simple missing feature family
  - or weak out-of-sample utility localization on the current daily state?

This session did not change the live branch.
It stayed long-only.
It did not use `2026` for predictive tuning.

---

## What changed

Added one bounded research script:
- `analysis/h338_step_hazard_failure_audit.py`

### H338 - Step-Hazard Failure Audit
**Hypothesis:**
The exact `H337` blocker can be identified by separating four competing causes:
label ceiling, threshold choice, utility-target mismatch, and missing feature
family.

**Command / code:**
`python analysis/h338_step_hazard_failure_audit.py`

**Inputs:**
- `artifacts/run_summaries/latest_research_branch_replacement_aware_step_hazard.json`
- `artifacts/portfolio_baselines/20260410_185752_h337_replacement_aware_step_hazard_step_rows.parquet`
- `artifacts/portfolio_baselines/20260410_185752_h337_replacement_aware_step_hazard_policy_entries.parquet`
- `artifacts/portfolio_baselines/20260410_185752_h337_replacement_aware_step_hazard_h211_policy_entries.parquet`

**Saved artifact:**
`artifacts/run_summaries/20260410_191016_h338_step_hazard_failure_audit_research_branch_step_hazard_failure_audit.json`

| Metric | Value | Note |
|--------|-------|------|
| verdict | `MIXED` | blocker narrowed sharply, but not to one single cause only |
| root cause | `partial_identification` | primary blocker identified with a secondary ceiling still present |
| step rows | `7,717` | same H337 legal-step decision panel |
| entries | `2,578` | same H334 executed-entry universe |
| perfect step-oracle recovered share, validation | `72.56%` | one-step hazard label is not the main ceiling |
| perfect step-oracle recovered share, confirmation | `68.48%` | one-step hazard label is usable |
| dev-selected threshold | `0.50` | already the best dev operating point in the tested grid |
| threshold issue | `false` | threshold tuning did not rescue the branch |
| feature family issue | `false` | no simple ablation family fixed the branch |
| validation utility Spearman | `0.0296` | very weak utility ranking |
| confirmation utility Spearman | `0.1174` | still only modest utility ranking |
| validation skip-over entry rate | `24.32%` | secondary label ceiling |
| confirmation skip-over entry rate | `21.15%` | secondary label ceiling |

### What the audit ruled out

Threshold choice is not the main blocker:
- tested thresholds:
  - `0.35`
  - `0.40`
  - `0.45`
  - `0.50`
  - `0.55`
  - `0.60`
  - `0.65`
- dev-selected threshold:
  - `0.50`
- at `0.50`, validation / confirmation uplift vs fixed `3d`:
  - `+0.00245`
  - `+0.00253`
- lower thresholds turned sharply negative out of sample
- higher thresholds collapsed back toward fixed `3d`

The one-step label is not the main hard cap:
- perfect step-oracle recovered share:
  - validation `72.56%`
  - confirmation `68.48%`

So a strong learner on the same label family could still recover much more than
`H337` did.

No simple feature-family omission rescued the branch:
- `core_only`:
  - validation / confirmation uplift `+0.00020 / -0.00337`
- `core_plus_replacement`:
  - `+0.00230 / +0.00253`
- `full_no_event`:
  - `-0.00109 / +0.00283`
- `full_no_replacement`:
  - `+0.00282 / +0.00248`
- `full`:
  - `+0.00208 / +0.00154`

No simple family change produced a real breakout.

### What the audit found

The main blocker is weak out-of-sample utility localization on the current
daily state:
- overall utility Spearman:
  - validation `0.0296`
  - confirmation `0.1174`
- mean step delta utility remained negative in every out-of-sample horizon:
  - validation:
    - `3d -> 5d: -0.0010`
    - `5d -> 10d: -0.0043`
    - `10d -> 15d: -0.0014`
  - confirmation:
    - `3d -> 5d: -0.0063`
    - `5d -> 10d: -0.0095`
    - `10d -> 15d: -0.0092`

That means profitable continuation pockets do exist, but the current daily
state does not rank them strongly enough on holdout.

There is also a secondary skip-over ceiling:
- entries with skip-over conflicts:
  - validation `24.32%`
  - confirmation `21.15%`
- these are cases where the immediate next legal step is worse, but a later
  legal horizon is still better than exiting now

**Result:**
`H337` is not mainly failing because the branch picked the wrong threshold, or
because one missing simple feature family was omitted, or because the one-step
hazard label is impossible. It is mainly failing because the current daily
state does not localize continuation utility well enough out of sample. A
secondary but real limitation is that one-step labels still miss skip-over
states on about one-fifth to one-quarter of entries.

**Verdict: MIXED**

---

## Branch decision

`H338` narrows the branch materially:
- do **not** keep retuning the `H337` threshold
- do **not** reopen `H335` or `H336`
- do **not** claim that a larger model will fix this by itself
- if continuing, keep the current-state hazard setup but change the target:
  - make it skip-aware
  - make it utility-weighted
  - make it more explicitly replacement-relative

---

## Validation

Completed during the pass:
- ran `python -m py_compile analysis/h338_step_hazard_failure_audit.py`
- ran `python analysis/h338_step_hazard_failure_audit.py`
- read the saved run summary artifact
- inspected threshold sweep, skip-over, utility-alignment, and ablation artifacts
- ran `git diff --check`
- reran `python -m py_compile analysis/h337_replacement_aware_step_hazard.py analysis/h338_step_hazard_failure_audit.py`

The broader test suite was not run.
