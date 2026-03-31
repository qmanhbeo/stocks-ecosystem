# Session 81 Log

## Objective
Run `H250` and test whether sparse contradiction states between continuation and reversal signals contain a new selector edge that can challenge the current `H201` offline lead.

This session did not try to change the live branch.
It kept the branch offline, long-only, and locked to `2015-2025`, with no `2026+` read.

## Starting point

Coming in:
- `H201` was still the current offline lead:
  - `state_blend__h199_sector_laggard_gap_absorb__30`
- `H249` had already shown that selector-relative activation does not rescue the `H201` winner
- the next materially different queued question was whether disagreement states between `S1`, `C9`, `C12`, `C13`, `C14`, and the `H199` atom contain a new routed selector edge

## What changed

Added:
- `analysis/h250_contradiction_state_router.py`

Shared support added:
- `src/contradiction_state_router.py`

Regression coverage added:
- `tests/test_contradiction_state_router.py`

## H250 outcome

### Contract audited

`H250` stayed on the locked selector protocol:
- date range used:
  - `2015-2022` dev
  - `2023-2024` validation
  - `2025` confirmation
- no `2026+` lockbox read

Signal families used:
- continuation:
  - `S1`
  - `C12`
  - `C14`
  - `H199`
- reversal / veto:
  - `C9`
  - `C13`

Sparse router candidates tested:
- `h250_momentum_pullback_acceptance`
- `h250_sector_laggard_pullback_acceptance`
- `h250_gap_trend_without_blowoff`
- `h250_disagreement_balance`
- `h250_blowoff_reset_router`

### Screen stage

Promoted router:
- `h250_disagreement_balance`
- active share `13.35%`
- dev IC `+0.0184`
- corr with `S1` `+0.0905`
- validation IC `+0.0159`
- confirmation IC `+0.0184`
- validation relative `+33.27%`
- confirmation relative `-23.86%`

Interpretation:
- this is the only contradiction-state candidate strong enough to earn a selector audit
- the other continuation-style routers had positive standalone IC but negative selector relevance
- the pure reversal reset router failed the standalone gate cleanly

### Direct selector audit

Compared strategies:
- `full_library_baseline`
- `full_library_plus__h250_disagreement_balance`
- `state_blend__h199_sector_laggard_gap_absorb__30`

Baseline:
- validation relative `+43.45%`
- confirmation relative `-20.02%`

`H250` additive winner:
- validation relative `+78.16%`
- validation delta vs baseline `+34.71%`
- validation IR delta vs baseline `+0.53`
- confirmation relative `-20.80%`
- confirmation delta vs baseline `-0.78%`
- confirmation IR delta vs baseline `+0.01`

`H201` offline lead:
- validation relative `+46.17%`
- confirmation relative `-13.43%`

`H250` winner vs `H201`:
- validation delta `+31.99%`
- validation IR delta `+0.45`
- confirmation delta `-7.36%`
- confirmation IR delta `-0.18`

Interpretation:
- `h250_disagreement_balance` is real enough to improve the selector backbone materially on validation
- it even clears the baseline additive gate
- but it does **not** beat the current `H201` offline lead on confirmation

## Branch decision

Do **not** replace `H201` as the current offline lead.

What `H250` resolves:
- contradiction-state routing is a real family on the current stack
- the best current router is:
  - `h250_disagreement_balance`
- that router is good enough to keep as offline-only evidence
- it is **not** good enough to dislodge `state_blend__h199_sector_laggard_gap_absorb__30`

Branch effect:
- `H250` is **MIXED**
- keep `h250_disagreement_balance` as a secondary offline / RL-state candidate
- if the model-side queue is intentionally continued later, move to `H251`

Active workspace policy still does not change:
- acquisition-first timing-data work remains the main non-live branch
- live sticky branch remains frozen and monitor-only

## Validation

Completed:
- `python -m py_compile analysis/h250_contradiction_state_router.py src/contradiction_state_router.py tests/test_contradiction_state_router.py`
- `pytest -q tests/test_contradiction_state_router.py tests/test_activation_meta.py`
- full `python analysis/h250_contradiction_state_router.py` run completed

Saved artifacts:
- `artifacts/run_summaries/latest_portfolio_contradiction_state_router.json`
- `artifacts/portfolio_baselines/20260331_105001_h250_contradiction_state_router_screen_results.parquet`
- `artifacts/portfolio_baselines/20260331_105001_h250_contradiction_state_router_audit_results.parquet`
- `artifacts/portfolio_baselines/20260331_105001_h250_contradiction_state_router_best_daily.parquet`
- `artifacts/portfolio_baselines/20260331_105001_h250_contradiction_state_router_audit_scored.parquet`
