# Session 93 Log

## Objective
Run the smallest honest follow-through after the global `H259` failure:
- `H262`: test whether reduced-shape intraday works as a thesis-family-specific contradiction / trust state rather than a global continuation model
- `H263`: only if `H262` passes, pool those family-local scores back into one family-aware continuation router

This session did not change the live branch.
It did not read `2026+`.

## Starting point

Coming in:
- `H258` had already passed the reduced-shape CafeF `1H` contract audit on `2023-2025`
- `H259` had already failed as a global continuation / exit predictor on the observed subset
- the new bright-mind boundary was that `H259` may have failed by aggregating incompatible `entry_thesis_family` mechanisms
- the live sticky branch remained frozen at `full_library + k5_r5_eq + h175__rel2_gt0 + sticky_bonus_0p015`

The honest question was no longer:
- "does reduced-shape intraday work globally?"

It was:
- does reduced-shape intraday only work inside one entry-thesis family?
- and if so, does that local win survive recombination into a pooled family-aware router?

## What changed

Added:
- `analysis/h262_intraday_family_contradiction_audit.py`
- `analysis/h263_pooled_family_aware_intraday_router.py`

Updated:
- `src/intraday_exit_research.py`
- `tests/test_intraday_exit_research.py`

Saved artifacts:
- `artifacts/run_summaries/latest_portfolio_exit_intraday_family_contradiction_audit.json`
- `artifacts/run_summaries/latest_portfolio_exit_intraday_family_aware_router.json`
- `artifacts/portfolio_baselines/20260403_110021_h262_intraday_family_contradiction_audit_results.parquet`
- `artifacts/portfolio_baselines/20260403_110021_h262_intraday_family_contradiction_audit_family_summary.parquet`
- `artifacts/portfolio_baselines/20260403_110021_h262_intraday_family_contradiction_audit_scored_panel.parquet`
- `artifacts/portfolio_baselines/20260403_110056_h263_pooled_family_aware_intraday_router_results.parquet`
- `artifacts/portfolio_baselines/20260403_110056_h263_pooled_family_aware_intraday_router_scored_panel.parquet`

### H262 - Family-Scoped Intraday Contradiction Audit
**Hypothesis:**
The `H259` failure is an aggregation failure, not a total mechanism kill: reduced-shape intraday only matters as a contradiction / trust modulator inside specific `entry_thesis_family` groups.

**Command / code:**
`conda run -n stocks python analysis/h262_intraday_family_contradiction_audit.py`

**Inputs:**
- `artifacts/portfolio_baselines/20260403_103104_h259_intraday_exit_predictive_screen_observed_panel.parquet`
- family splits:
  - `momentum_continuation`: dev `498`, validation `509`, confirmation `448`
  - `breakout_followthrough`: dev `143`, validation `97`, confirmation `103`
  - `crowding_pressure`: dev `93`, validation `127`, confirmation `84`
- family-local models:
  - `path_core`
  - `intraday_atoms`
  - `intraday_atoms_plus_path`

**Saved artifact:**
`artifacts/run_summaries/latest_portfolio_exit_intraday_family_contradiction_audit.json`

| Metric | Value | Note |
|--------|-------|------|
| observed rows | `2,102` | same observed subset as `H259` |
| passing family count | `1` | only one family clears the gate |
| passing family | `breakout_followthrough` | the only true survivor |
| breakout path-core validation AUC | `0.5273` | family-local baseline |
| breakout best candidate | `intraday_atoms` | family-local winner |
| breakout validation AUC delta vs path-core | `+0.1589` | clear local gain |
| breakout validation top-quintile delta vs path-core | `+0.0308` | clear local gain |
| breakout confirmation top-quintile hold advantage | `+0.0457` | survives strongly |
| crowding family decision | `FAILED` | validation top-quintile gets worse |
| momentum family decision | `FAILED` | validation AUC and top-quintile both worsen |

**Result:**
The reduced-shape contradiction thesis is real, but only inside `breakout_followthrough`. The other two families do not want the intraday follow-through on the current observed subset.

**Verdict: PASSED**

### H263 - Pooled Family-Aware Intraday Router
**Hypothesis:**
If one family-local contradiction win is real, a pooled family-aware router that uses intraday only where it helps should beat the global `H259` baselines.

**Command / code:**
`conda run -n stocks python analysis/h263_pooled_family_aware_intraday_router.py`

**Inputs:**
- `H262` family summary and scored panel
- pooled router map:
  - `breakout_followthrough` -> `intraday_atoms`
  - `crowding_pressure` -> `path_core`
  - `momentum_continuation` -> `path_core`
- global benchmarks rebuilt on the same observed subset:
  - `path_core_observed`
  - `intraday_shape_core`
  - `intraday_shape_atoms`
  - `intraday_shape_plus_path`

**Saved artifact:**
`artifacts/run_summaries/latest_portfolio_exit_intraday_family_aware_router.json`

| Metric | Value | Note |
|--------|-------|------|
| router intraday families | `1` | only `breakout_followthrough` uses intraday |
| router validation AUC | `0.4963` | beats `path_core_observed` |
| router validation top-quintile hold advantage | `-0.00024` | still weak in absolute terms, but better than baseline |
| router confirmation top-quintile hold advantage | `+0.00159` | materially above baseline |
| path-core observed validation AUC | `0.4895` | `H259` global baseline |
| path-core observed validation top-quintile hold advantage | `-0.00078` | `H259` global baseline |
| path-core observed confirmation top-quintile hold advantage | `-0.00848` | `H259` global baseline |
| best global intraday model | `intraday_shape_core` | still weaker on validation |
| router validation AUC delta vs path-core | `+0.0067` | pooled improvement |
| router validation top-quintile delta vs path-core | `+0.00054` | pooled improvement |
| router confirmation top-quintile delta vs path-core | `+0.01007` | strongest pooled evidence |

**Result:**
The family-aware router clears the branch rule against the global `H259` benchmark. The gain is narrow and still branch-local, but it is no longer true that reduced-shape intraday has no continuation value on the current observed subset.

**Verdict: PASSED**

## Branch decision

Do **not** change the live branch.

What Session 93 resolves:
- `H262` passes:
  - the `H259` failure was not a universal intraday-mechanism kill
  - reduced-shape contradiction is real inside `breakout_followthrough`
  - `momentum_continuation` and `crowding_pressure` still reject the intraday follow-through
- `H263` passes:
  - a pooled family-aware router beats the global `H259` path-only baseline on the observed subset
  - the usable contract is still narrow:
    - observed subset only
    - `2023-2025` only
    - no deterministic integration yet

Branch effect:
- keep `H260/H261` closed; Session 92's direct reduced-shape restart is still dead
- promote the family-aware intraday router as offline evidence only
- keep `H233` unresolved
- if this branch continues, the next honest follow-through is `H264`: deterministic family-aware continuation veto integration

## Validation

Completed before the runs:
- `python -m py_compile src/intraday_exit_research.py analysis/h262_intraday_family_contradiction_audit.py analysis/h263_pooled_family_aware_intraday_router.py tests/test_intraday_exit_research.py`
- `pytest -q tests/test_intraday_exit_research.py`

Completed for the experiments:
- `conda run -n stocks python analysis/h262_intraday_family_contradiction_audit.py`
- read `artifacts/run_summaries/latest_portfolio_exit_intraday_family_contradiction_audit.json`
- `conda run -n stocks python analysis/h263_pooled_family_aware_intraday_router.py`
- read `artifacts/run_summaries/latest_portfolio_exit_intraday_family_aware_router.json`

Verdict:
- `H262`: **PASSED**
- `H263`: **PASSED**
