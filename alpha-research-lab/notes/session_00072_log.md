# Session 72 Log

## Objective
Test a materially different exit branch based on a new target:
- not “does this name match a sell heuristic?”
- but “should this held position be kept for one more cycle?”

This is the continuation-alpha / hold-vs-exit hazard branch.

Hard rules unchanged:
- long-only only
- no synthetic hedges
- no shorting assumptions
- ADV / capacity parked for the current-account branch
- no tuning on `2026+`
- sequential hypothesis ladders remain mandatory

## Starting point

Session 71 closed the second exit-family branch:
- H211 remains the best always-on exit winner:
  - `strength_exhaustion__return_since_entry_threshold_0p15__score_drop_threshold_0p05`
- the newer H214-H216 families did not beat it
- live branch remained unchanged:
  - `full_library + k5_r5_eq + h175__rel2_gt0 + sticky_bonus_0p015`

The next honest way to continue exit research was to change the target itself.

## Implementation

New helper:
- `src/continuation_exit_research.py`
  - builds a held-position continuation dataset from the frozen `full_library` selector
  - labels each legal held position by forward `5`-day hold-vs-benchmark advantage
  - fits simple logistic continuation models on dev only

Extended engine support:
- `src/deterministic_portfolio.py`
  - feature-matrix support in `MarketInputs`
  - continuation-hazard exit family
  - thesis-family and post-entry path tracking already added in Session 71 now reused here

New analyses:
- `analysis/h218_continuation_alpha_model.py`
- `analysis/h219_continuation_exit_bands.py`
- `analysis/h220_continuation_exit_activation_compatibility.py`

Tests:
- `tests/test_continuation_exit_research.py`

## H218 — Continuation Alpha Model

Goal:
- predict whether a currently held, legally sellable position should be kept for one more cycle

Target:
- `future_hold_advantage_5d > 0`
- where hold advantage is the stock’s forward open-to-open return minus the benchmark’s forward open-to-open return over the next `5` trading days

Model families tested:
- `continuation_core`
  - holding age
  - score change since entry
  - return since entry
  - peak return since entry
  - underwater days
  - blocked-sell streak
- `continuation_plus_thesis`
  - core + thesis score change
- `continuation_plus_rank`
  - core + thesis score change + score rank + entry rank

Result:
- **FAIL**
- no model cleared the promotion gate

Best model:
- `continuation_core`
  - validation AUC `0.5060`
  - validation top-quintile hold advantage `-0.0058`
  - confirmation AUC `0.5106`
  - confirmation top-quintile hold advantage `-0.0081`

Other models:
- `continuation_plus_rank`
  - validation AUC `0.5031`
  - confirmation AUC `0.5230`
  - top-quintile hold advantage still negative
- `continuation_plus_thesis`
  - validation AUC `0.4996`
  - confirmation AUC `0.5225`
  - top-quintile hold advantage still negative

Interpretation:
- the continuation target is genuinely new
- on current data it does not produce useful predictive signal
- the branch dies at the first gate

## H219 — Continuation Exit Bands

Rule:
- only run if H218 produces a promoted continuation model

Result:
- **SKIP**
- reason:
  - H218 produced no promoted continuation model

## H220 — Sticky Compatibility

Rule:
- only run if H219 produces a promoted continuation-band winner

Result:
- **SKIP**
- reason:
  - H219 produced no promoted continuation-band winner

## Branch decision

The continuation / hold-vs-exit hazard family is now closed on the current data.

Implications:
- do not reopen H218-H220 on the same locked protocol window
- keep H211 as the best offline exit-alpha evidence
- keep the live sticky branch unchanged

Next honest requirement for exit research:
- a genuinely new data family
  - corporate event surface
  - intraday / auction structure
  - order-book / queue data if obtainable

## Artifacts

New summaries:
- `artifacts/run_summaries/latest_portfolio_exit_continuation_alpha_model.json`
- `artifacts/run_summaries/latest_portfolio_exit_continuation_bands.json`
- `artifacts/run_summaries/latest_portfolio_exit_continuation_activation_compatibility.json`

Detailed outputs:
- `artifacts/portfolio_baselines/*h218_continuation_alpha_model*`

## Validation

Session 72 hygiene completed:
- `python -m py_compile` passed
- focused tests passed:
  - `tests/test_exit_alpha.py`
  - `tests/test_continuation_exit_research.py`
  - `tests/test_additive_selector_research.py`
- `git diff --check` passed
