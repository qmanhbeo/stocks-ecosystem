# Session 94 Log

## Objective
Run the first deterministic follow-through after Session 93's observed-subset router result:
- `H264`: test whether the family-aware intraday contradiction router survives honest deterministic integration once it must compete against explicit path-only controls and a usable cutoff requirement
- `H265`: only if `H264` passes, test sticky compatibility against the frozen live branch contract

This session did not change the live branch.
It did not read `2026+`.

## Starting point

Coming in:
- `H258` had already passed the reduced-shape CafeF `1H` contract audit on `2023-2025`
- `H259` had already failed as a global continuation / exit predictor on the observed subset
- `H262` had already passed narrowly:
  - reduced-shape intraday contradiction survived only inside `breakout_followthrough`
- `H263` had already passed narrowly:
  - the pooled family-aware router beat the global `H259` path-only observed baseline on the same observed subset
- the skeptical follow-up constraint was explicit:
  - `H264` must include family-aware `path_core` parity
  - `H264` must require a usable deterministic cutoff rather than a better probability rank alone
- the live sticky branch remained frozen at `full_library + k5_r5_eq + h175__rel2_gt0 + sticky_bonus_0p015`

The honest question was no longer:
- "does the family-aware router rank continuation rows a bit better?"

It was:
- does that router survive deterministic integration once missing intraday must be handled honestly?
- and does it still beat explicit global and family-aware path-only controls when cutoffs are forced?

## What changed

Added:
- `analysis/h264_family_aware_continuation_veto_integration.py`
- `analysis/h265_family_aware_continuation_activation_compatibility.py`

Updated:
- `src/deterministic_portfolio.py`
- `src/intraday_exit_research.py`
- `tests/test_exit_alpha.py`
- `tests/test_intraday_exit_research.py`

Saved artifacts:
- `artifacts/run_summaries/latest_portfolio_exit_family_aware_continuation_veto_integration.json`
- `artifacts/portfolio_baselines/20260403_112830_h264_family_aware_continuation_veto_integration_results.parquet`
- `artifacts/portfolio_baselines/20260403_112830_h264_family_aware_continuation_veto_integration_best_daily.parquet`
- `artifacts/portfolio_baselines/20260403_112830_h264_family_aware_continuation_veto_integration_best_exit_panel.parquet`
- `artifacts/portfolio_baselines/20260403_112830_h264_family_aware_continuation_veto_integration_router_daily.parquet`
- `artifacts/portfolio_baselines/20260403_112830_h264_family_aware_continuation_veto_integration_router_exit_panel.parquet`

### H264 - Family-Aware Continuation Veto Integration
**Hypothesis:**
The `H263` observed-subset router is strong enough to justify one deterministic continuation-veto follow-through:
- keep `momentum_continuation` and `crowding_pressure` on family-local path-core treatment
- use reduced-shape intraday contradiction only for `breakout_followthrough`
- and still beat explicit path-only controls once a real cutoff must be chosen

**Command / code:**
`conda run -n stocks python analysis/h264_family_aware_continuation_veto_integration.py`

**Inputs:**
- `H258` reduced-shape panel
- `H262` family summary and family-local model rows
- continuation panel rebuilt on `2023-2025` only
- deterministic cutoff grid:
  - `0.40`
  - `0.45`
  - `0.50`
  - `0.55`
  - `0.60`
- three ladders:
  - `global_path_core`
  - `family_path_core`
  - `family_router`
- usable-cutoff rule:
  - positive exit events required
  - validation and confirmation cash weight must stay within `+0.15` of the always-on baseline

**Saved artifact:**
`artifacts/run_summaries/latest_portfolio_exit_family_aware_continuation_veto_integration.json`

| Metric | Value | Note |
|--------|-------|------|
| overall winner | `global_path_core__thr_0p5` | path-only control wins the deterministic ladder |
| overall winner validation relative delta | `+0.2465` | vs always-on baseline |
| overall winner validation IR delta | `+0.3562` | vs always-on baseline |
| overall winner confirmation relative delta | `+0.0247` | still positive |
| family path-core leader | `family_path_core__thr_0p55` | second-best control |
| family path-core confirmation relative delta | `+0.0478` | stronger than the global winner on confirmation |
| best family-router cutoff | `family_router__thr_0p4` | strongest router variant |
| family-router validation relative delta | `+0.2006` | validation is not the problem |
| family-router validation IR delta | `+0.6731` | strong local validation lift |
| family-router confirmation relative delta | `-0.0760` | breaks the branch gate |
| family-router confirmation IR delta | `-0.9032` | breaks badly |
| family-router exit events | `21` | too sparse to be a convincing liveable cutoff |
| family-router confirmation cash weight | effectively `0.00%` | the rule almost never fires into usable confirmation behavior |

**Result:**
The family-aware intraday contradiction router does **not** survive deterministic integration.

The failure mode is specific and useful:
- the best family-router cutoff (`0.40`) looks strong on validation
- but it collapses on confirmation
- and it triggers only `21` exits across the full `2023-2025` window

The controls beat it cleanly:
- `global_path_core__thr_0p5` is the overall deterministic winner
- `family_path_core__thr_0p55` is also promotable and survives confirmation better than the router

That means the surviving `H262/H263` intraday result remains:
- real as observed-subset offline evidence
- not strong enough as a deterministic continuation veto

**Verdict: FAILED**

### H265 - Family-Aware Activation Compatibility
**Branch rule:**
Run only if `H264` passes.

**Result:**
Not run.

Reason:
- `H264` failed the deterministic gate
- the family-aware router is not the winner once path-only controls are forced into the same ladder

## Branch decision

Do **not** change the live branch.

What Session 94 resolves:
- `H264` fails:
  - the observed-subset family-aware router is not strong enough to justify deterministic continuation-veto integration
  - explicit path-only controls dominate the deterministic ladder
  - the best router cutoff is too sparse and breaks on confirmation
- `H265` stays closed:
  - no sticky compatibility follow-through is honest after the `H264` failure

Branch effect:
- keep the Session 93 router as offline evidence only
- close the family-aware continuation-veto integration branch on the current contract
- do **not** reopen `H260/H261`
- do **not** promote the local `2023-2025` path-core control winners to the live branch:
  - this session was testing incremental intraday value on a narrow restarted window
  - it was not a full historical continuation-branch relaunch
- if intraday work continues, the next honest follow-through is:
  - `breakout-entry trust relocation`
- secondary fallback if that stalls:
  - selector-state / top-k intraday stress routing
  - or library-grade intraday state atoms

## Validation

Completed before the run:
- `python -m py_compile src/intraday_exit_research.py src/deterministic_portfolio.py analysis/h264_family_aware_continuation_veto_integration.py analysis/h265_family_aware_continuation_activation_compatibility.py tests/test_intraday_exit_research.py tests/test_exit_alpha.py`
- `pytest -q tests/test_intraday_exit_research.py tests/test_exit_alpha.py`

Completed for the experiment:
- `conda run -n stocks python analysis/h264_family_aware_continuation_veto_integration.py`
- read `artifacts/run_summaries/latest_portfolio_exit_family_aware_continuation_veto_integration.json`

Intentionally not run:
- `conda run -n stocks python analysis/h265_family_aware_continuation_activation_compatibility.py`
  - blocked by the `H264` fail rule

Verdict:
- `H264`: **FAILED**
- `H265`: **NOT RUN**
