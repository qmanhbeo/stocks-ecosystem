# Session 71 Log

## Objective
Reopen exit research only with **genuinely new post-entry hypothesis families**, not with threshold retuning of `H207-H213`.

Hard rules unchanged:
- long-only only
- no synthetic hedges
- no shorting assumptions
- ADV / capacity parked for the current-account branch
- no tuning on `2026+`
- sequential hypothesis ladders remain mandatory

## Starting point

Session 70 closed the first exit ladder with:
- best always-on exit winner:
  - `strength_exhaustion__return_since_entry_threshold_0p15__score_drop_threshold_0p05`
- live branch unchanged:
  - `full_library + k5_r5_eq + h175__rel2_gt0 + sticky_bonus_0p015`
- branch rule:
  - do not retune `H207-H213` on the same locked window

That left one honest follow-up:
- test genuinely different exit families against the H211 winner

## Implementation

Engine extension:
- `src/deterministic_portfolio.py`
  - added optional ranked feature matrices into `MarketInputs`
  - added thesis-family support tracking
  - added post-entry path trackers:
    - `peak_return_since_entry`
    - `underwater_days_since_entry`
  - added new exit families:
    - `thesis_inconsistency`
    - `failed_followthrough`
    - `time_under_water`
  - extended blotter diagnostics for the new exit states

Helper changes:
- `src/exit_experiment_utils.py`
  - now loads the feature columns needed for thesis-family exits
- `src/exit_alpha.py`
  - extended exit-state panel columns

New scripts:
- `analysis/h214_thesis_inconsistency_exit.py`
- `analysis/h215_failed_followthrough_exit.py`
- `analysis/h216_time_under_water_exit.py`
- `analysis/h217_new_exit_activation_compatibility.py`

Tests:
- `tests/test_exit_alpha.py`
  - added targeted checks for:
    - thesis-family matrix construction
    - thesis inconsistency exit
    - failed follow-through exit
    - time-under-water exit

Cleanup fix:
- thesis-family averaging originally emitted noisy all-NaN warnings
- replaced `np.nanmean` with explicit finite-count division

## H214 — Thesis-Inconsistency Exit

Goal:
- exit when the specific entry-thesis family that supported the trade has decayed enough

Entry thesis families used:
- `momentum_continuation`
- `breakout_followthrough`
- `crowding_pressure`

Result:
- **FAIL**
- best new variant:
  - `thesis_inconsistency__score_drop_threshold_0p05__thesis_drop_threshold_0p1`
  - validation relative `+28.44%`
  - validation delta vs H211 `-26.01%`
  - confirmation relative `-13.78%`

Interpretation:
- thesis tracking is conceptually different
- on current data it is materially worse than the existing H211 exit winner

## H215 — Failed-Follow-Through Exit

Goal:
- exit trades that never begin working after a short grace window

Result:
- **FAIL, BUT NEAR-MISS**
- best variant:
  - `failed_followthrough__current_return_threshold_0p0__grace_days_2__peak_return_threshold_0p03__score_drop_threshold_0p0`
  - validation relative `+56.39%`
  - validation delta vs H211 `+1.95%`
  - validation IR delta `+0.0448`
  - confirmation relative `-5.22%`
  - confirmation delta vs H211 `-0.52%`

Interpretation:
- there is real information in failed follow-through
- it still did not clear the locked promotion gate over H211

## H216 — Time-Under-Water Exit

Goal:
- exit dead-capital positions that stay underwater too long without enough prior progress

Result:
- **FAIL**
- best variant:
  - `time_under_water__grace_days_5__peak_return_threshold_0p03__underwater_days_threshold_3`
  - validation relative `+55.30%`
  - validation delta vs H211 `+0.85%`
  - validation IR delta `+0.2334`
  - confirmation relative `-39.36%`
  - confirmation delta vs H211 `-34.66%`

Interpretation:
- the family can look attractive on validation
- it fails badly on confirmation
- dead-capital exits are not stable enough here

## H217 — New-Family Sticky Compatibility

Rule:
- only run if a genuinely new exit family displaces the old H211 winner

Result:
- **SKIP**
- reason:
  - no new family beat the H211 anchor

Interpretation:
- there is no new exit-family winner worth compatibility-testing under the frozen sticky branch

## Branch decision

Best exit winner remains:
- `strength_exhaustion__return_since_entry_threshold_0p15__score_drop_threshold_0p05`

Branch effect:
- the exit-alpha result from Session 70 still stands
- the genuinely new follow-up families did not beat it
- do not reopen the current exit branch on the same data with more threshold tuning

Live branch:
- unchanged
- keep:
  - `full_library + k5_r5_eq + h175__rel2_gt0 + sticky_bonus_0p015`

Next honest requirement if exit research is reopened:
- a genuinely new data family, or
- a materially different exit hypothesis family

## Artifacts

New summaries:
- `artifacts/run_summaries/latest_portfolio_exit_thesis_inconsistency.json`
- `artifacts/run_summaries/latest_portfolio_exit_failed_followthrough.json`
- `artifacts/run_summaries/latest_portfolio_exit_time_under_water.json`
- `artifacts/run_summaries/latest_portfolio_exit_new_family_activation_compatibility.json`

Detailed outputs:
- `artifacts/portfolio_baselines/*h214_thesis_inconsistency_exit*`
- `artifacts/portfolio_baselines/*h215_failed_followthrough_exit*`
- `artifacts/portfolio_baselines/*h216_time_under_water_exit*`
- `artifacts/portfolio_baselines/*h217_new_exit_activation_compatibility*`

## Validation

Session 71 hygiene completed:
- `python -m py_compile` passed on new code
- focused tests passed:
  - `tests/test_exit_alpha.py`
  - `tests/test_additive_selector_research.py`
- `git diff --check` passed
