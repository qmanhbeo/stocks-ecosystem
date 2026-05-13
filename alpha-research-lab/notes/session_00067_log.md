# Session 67 Log

## Objective
Implement the next sequential selector-discovery ladder without touching the frozen live sticky branch.

Hard rules unchanged:
- long-only only
- no synthetic hedges
- no shorting assumptions
- ADV / capacity parked for the current-account branch
- no tuning on `2026+`

## Starting point

Session 66 left the branch in the correct state:
- live branch frozen at:
  - `full_library + k5_r5_eq + h175__rel2_gt0 + sticky_bonus_0p015`
- offline selection discovery reopened under the locked protocol:
  - dev `2015-2022`
  - validation `2023-2024`
  - one-shot confirmation `2025`
  - forward lockbox `2026+`
- `H151` failed cleanly
- `H152` produced four candidate atoms but no selector replacement

That made the next ladder straightforward:
1. `H196`: additive bakeoff for the `H152` atoms on top of `full_library`
2. if no promoted atoms, skip `H197/H198`
3. then run `H199`: second-wave tradability-conditioned signal search

## Implementation

New code:
- `src/additive_selector_research.py`
- `analysis/h196_additive_atom_bakeoff.py`
- `analysis/h197_state_scoped_additive_bakeoff.py`
- `analysis/h198_selector_activation_compatibility.py`
- `analysis/h199_second_wave_tradability_conditioned_search.py`
- `tests/test_additive_selector_research.py`

Extended helper:
- `src/tradability_conditioned_research.py`

Added second-wave candidate signal support in `build_candidate_signal_frame()`:
- `h199_floor_release_rebound`
- `h199_ceiling_release_followthrough`
- `h199_sector_laggard_gap_absorb`
- `h199_breakout_after_compression`
- `h199_buyable_reversal_after_1d_weakness`

## H196 — one-atom additive bakeoff

Goal:
- test whether the `H152` atoms help only when added to the `full_library` selector backbone

Candidates:
- `full_library_baseline`
- `full_library + h152_sector_laggard_tradable`
- `full_library + h152_limit_release_pressure`
- `full_library + h152_liq_open_continue_3`
- `full_library + h152_breakout_volume_quality`

Acceptance rule:
- validation:
  - relative delta `>= +5 percentage points`, or
  - IR delta `>= +0.05`
- confirmation:
  - relative delta `>= -5 percentage points`
  - IR delta `>= -0.05`

Result:
- **FAIL**
- nearest miss:
  - `full_library + h152_sector_laggard_tradable`
  - validation relative:
    - `+47.01%`
    - baseline `+43.45%`
    - delta `+3.56%`
  - validation IR:
    - `0.8863`
    - baseline `0.8211`
    - delta `+0.0653`
  - confirmation relative:
    - `-21.21%`
    - delta `-1.19%`
  - it still failed because the confirmation IR deterioration breached the locked gate

Interpretation:
- the `H152` atoms are not additive enough one at a time under the locked selector-level rule
- the first additive family is now closed

## H197 — state-scoped additive bakeoff

Branch rule:
- only run if `H196` produces promoted atoms

Result:
- **SKIPPED**
- reason:
  - `H196` produced no promoted atoms

This skip was written deliberately as a run summary, not left implicit.

## H198 — sticky-activation compatibility

Branch rule:
- only run if `H197` produces a promoted winner

Result:
- **SKIPPED**
- reason:
  - `H197` produced no promoted winner

Small implementation note:
- the first skip attempt exposed a control-flow bug because the script expected a results artifact even for a skipped upstream summary
- that was patched in the same session

## H199 — second-wave tradability-conditioned signal search

Goal:
- search for more specific tradability-transition atoms after the `H152` additive family failed

State:
- `liq_open_basic = can_buy_next_open & tv_to_adv20 >= 1.10 & clv >= 0.45`

Candidate families:
- `h199_floor_release_rebound`
- `h199_ceiling_release_followthrough`
- `h199_sector_laggard_gap_absorb`
- `h199_breakout_after_compression`
- `h199_buyable_reversal_after_1d_weakness`

Dev-pass survivors:
- `h199_sector_laggard_gap_absorb`
  - dev IC `+0.0117`
  - corr with S1 `+0.0629`
  - validation IC `+0.0015`
  - confirmation IC `+0.0135`
  - naive validation selector relevance `+3.70%`
  - **promoted**
- `h199_breakout_after_compression`
  - dev IC `+0.0190`
  - corr with S1 `+0.0706`
  - but selector relevance was poor
- `h199_ceiling_release_followthrough`
  - dev IC `+0.0116`
  - corr with S1 `+0.0742`
  - validation IC was negative

Interpretation:
- the second-wave branch found one credible new atom:
  - `h199_sector_laggard_gap_absorb`
- that atom still is not a selector replacement
- it is the only atom worth carrying into the next additive test

## Branch decision

Live track:
- unchanged
- keep the sticky live branch frozen
- continue `H179/H183` forward monitoring only

Research track:
- `H152` additive family is now closed
- next branch is:
  1. `H200`: additive bakeoff for `h199_sector_laggard_gap_absorb` on top of `full_library`
  2. if `H200` passes, `H201`: state-scoped additive blend for that atom
  3. if `H201` passes, `H202`: sticky-activation compatibility test

Anti-leakage note:
- do not keep retuning the failed `H152` additive family against `2025`
- use the new `H199` atom family once through the same ladder, then stop or promote

## Artifacts

New summaries:
- `artifacts/run_summaries/latest_portfolio_additive_atom_bakeoff.json`
- `artifacts/run_summaries/latest_portfolio_state_scoped_additive_bakeoff.json`
- `artifacts/run_summaries/latest_portfolio_selector_activation_compatibility.json`
- `artifacts/run_summaries/latest_tradability_conditioned_signal_search_v2.json`

Detailed outputs:
- `artifacts/portfolio_baselines/*h196_additive_atom_bakeoff*`
- `artifacts/portfolio_baselines/*h197_state_scoped_additive_bakeoff*`
- `artifacts/portfolio_baselines/*h198_selector_activation_compatibility*`
- `artifacts/portfolio_baselines/*h199_second_wave_tradability_conditioned_search*`

## Validation

Session 67 hygiene completed:
- `python -m py_compile` passed on all new code
- focused tests passed:
  - `tests/test_research_protocol.py`
  - `tests/test_tradability_conditioned_research.py`
  - `tests/test_additive_selector_research.py`
- `git diff --check` passed
