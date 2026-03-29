# Session 68 Log

## Objective
Advance the next sequential selector ladder for the promoted H199 atom without touching the frozen live sticky branch.

Hard rules unchanged:
- long-only only
- no synthetic hedges
- no shorting assumptions
- ADV / capacity parked for the current-account branch
- no tuning on `2026+`

## Starting point

Session 67 ended with a clear branch state:
- live branch frozen at:
  - `full_library + k5_r5_eq + h175__rel2_gt0 + sticky_bonus_0p015`
- first additive H152 family closed
- one second-wave atom promoted out of H199:
  - `h199_sector_laggard_gap_absorb`

That made the next ladder deterministic:
1. `H200`: add the H199 atom to `full_library`
2. if it passes, `H201`: test state-scoped additive blending
3. if that passes, `H202`: test frozen sticky-activation compatibility

## Implementation

New code:
- `analysis/h200_additive_h199_atom_bakeoff.py`
- `analysis/h201_state_scoped_h199_atom_bakeoff.py`
- `analysis/h202_h199_selector_activation_compatibility.py`

Small helper extension:
- `src/additive_selector_research.py`
  - added summary payload / skip helpers

Minor test extension:
- `tests/test_additive_selector_research.py`

## H200 — additive H199 atom bakeoff

Goal:
- test whether the promoted second-wave atom helps when simply added to the `full_library` backbone

Candidate:
- `full_library + h199_sector_laggard_gap_absorb`

Result:
- **PASS**
- validation:
  - relative return `+68.21%`
  - baseline `+43.45%`
  - delta `+24.76%`
  - IR `1.16`
  - baseline IR `0.82`
  - delta `+0.34`
- confirmation:
  - relative return `-5.95%`
  - baseline `-20.02%`
  - delta `+14.07%`

Interpretation:
- this atom is materially additive at the selector level
- unlike the H152 atoms, it survives the locked promotion rule cleanly

## H201 — state-scoped H199 additive bakeoff

Goal:
- test whether the atom helps more when only blended into the selector inside `liq_open_basic`

Variants:
- `state_blend__h199_sector_laggard_gap_absorb__10`
- `state_blend__h199_sector_laggard_gap_absorb__20`
- `state_blend__h199_sector_laggard_gap_absorb__30`

Result:
- **PASS**
- winner:
  - `state_blend__h199_sector_laggard_gap_absorb__30`
  - validation relative `+46.17%`
  - validation delta vs baseline `+2.72%`
  - validation IR `0.90`
  - validation IR delta `+0.08`
  - confirmation relative `-13.43%`
  - confirmation delta vs baseline `+6.58%`

Interpretation:
- the `30%` state-scoped blend is now the strongest selector candidate in the H199 family
- it improves on the baseline cleanly enough to be worth carrying into activation compatibility

## H202 — sticky-activation compatibility

Goal:
- test whether the H201 winner also works under the frozen sticky activation rule
- activation remained fixed:
  - `h175__rel2_gt0 + sticky_bonus_0p015`

Compared variants:
- `winner_always_on`
- `winner_plus_sticky`
- incumbent:
  - `full_library_plus_sticky`

Result:
- **FAIL**
- always-on winner selector:
  - validation relative `+46.17%`
  - validation IR `0.90`
- incumbent sticky branch:
  - validation relative `+29.65%`
  - validation IR `0.61`
  - confirmation relative `+18.80%`
- winner + sticky:
  - validation relative `+16.64%`
  - validation delta vs incumbent `-13.01%`
  - validation IR `0.40`
  - validation IR delta `-0.21`
  - confirmation relative `+24.70%`
  - confirmation delta `+5.90%`

Interpretation:
- the new selector is genuinely stronger in always-on form
- but it does **not** survive the current frozen sticky activation overlay
- that means it is not a live-branch replacement yet

## Branch decision

Live track:
- unchanged
- keep the sticky branch frozen
- continue `H179/H183` monitoring only

Research track:
- promoted offline selector candidate:
  - `state_blend__h199_sector_laggard_gap_absorb__30`
- current status:
  - offline-only lead candidate
  - not live-compatible under the frozen sticky overlay

Next branch if selector-side research continues:
1. `H203`: pairwise additive bakeoff built around the H201 winner, always-on first
2. if that fails, `H204`: resume second-wave signal search with a genuinely new family

Anti-leakage note:
- do not keep retuning the exact single-atom H199 family against `2025`
- the current H199 branch has now been resolved through:
  - additive test
  - state-scoped test
  - activation compatibility test

## Artifacts

New summaries:
- `artifacts/run_summaries/latest_portfolio_additive_h199_atom_bakeoff.json`
- `artifacts/run_summaries/latest_portfolio_state_scoped_h199_atom_bakeoff.json`
- `artifacts/run_summaries/latest_portfolio_h199_selector_activation_compatibility.json`

Detailed outputs:
- `artifacts/portfolio_baselines/*h200_additive_h199_atom_bakeoff*`
- `artifacts/portfolio_baselines/*h201_state_scoped_h199_atom_bakeoff*`
- `artifacts/portfolio_baselines/*h202_h199_selector_activation_compatibility*`

## Validation

Session 68 hygiene completed:
- `python -m py_compile` passed on new code
- focused tests passed:
  - `tests/test_additive_selector_research.py`
  - `tests/test_research_protocol.py`
  - `tests/test_tradability_conditioned_research.py`
- `git diff --check` passed
