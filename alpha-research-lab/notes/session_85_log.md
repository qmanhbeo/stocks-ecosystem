# Session 85 Log

## Objective
Run `H254` and test whether the `H252` report-window edge becomes useful only as a selector switchboard:
- incumbent sticky off-regime
- hard-gated `H201` on-regime

This session did not try to change the live branch.
It kept the synthesis branch narrow, offline, and locked to `2015-2025`, with no `2026+` read.

## Starting point

Coming in:
- `H253` had already shown that the hard report-window gate around `H201` is real offline evidence but not a frozen-compatibility winner
- the next branch-worthy synthesis idea was:
  - use `H201` only when the report-window regime is on
  - keep incumbent sticky behavior on all off-regime dates
- the live / incumbent branch was still:
  - `full_library + k5_r5_eq + h175__rel2_gt0 + sticky_bonus_0p015`

## What changed

Added:
- `analysis/h254_report_window_selector_switchboard.py`

Shared support updated:
- `simulate_strategy()` in `src/deterministic_portfolio.py` now accepts a date-varying `incumbent_score_bonus` schedule so hybrid switchboard audits can keep sticky bonus off-regime without polluting the on-regime selector leg

Regression coverage extended:
- `tests/test_deterministic_portfolio.py`

## H254 outcome

### Contract audited

`H254` stayed narrow and exact:
- date range used:
  - `2015-2022` dev
  - `2023-2024` validation
  - `2025` confirmation
- no `2026+` lockbox read

Carried selector:
- `state_blend__h199_sector_laggard_gap_absorb__30`

Carried regime:
- `top5_report_window_ge2`

Hybrid branch tested:
- on report-window dates:
  - use `H201`
  - activation scale `1.0`
  - sticky bonus `0.0`
- off report-window dates:
  - use `full_library`
  - keep frozen sticky activation
  - keep sticky bonus `0.015`

Variants audited:
- `switchboard_h201_on_regime`
- `winner_report_window_gate`
- `winner_always_on`
- `full_library_plus_sticky`

### What happened

The switchboard failed cleanly:
- `switchboard_h201_on_regime`
- regime share `49.34%`
- validation relative `+23.51%`
- validation delta vs incumbent sticky `-6.14%`
- validation IR delta `-0.08`
- confirmation relative `+5.72%`
- confirmation delta vs incumbent sticky `-13.08%`
- confirmation IR delta `-0.43`

Interpretation:
- the switchboard does improve confirmation versus the naked `H201` paths
- but it still underperforms the frozen sticky incumbent in both validation and confirmation
- the branch is therefore weaker than both the incumbent and the original `H252/H253` hope

Reference context:
- `winner_report_window_gate`
  - validation delta vs incumbent sticky `+29.91%`
  - confirmation delta vs incumbent sticky `-29.78%`
- `winner_always_on`
  - validation delta vs incumbent sticky `+16.51%`
  - confirmation delta vs incumbent sticky `-32.24%`
- `full_library_plus_sticky`
  - validation relative `+29.65%`
  - confirmation relative `+18.80%`

### Branch decision

Do **not** change the live branch.

What `H254` resolves:
- the report-window specialization story is not enough to rescue `H201` as a hybrid switchboard on the current stack
- the switchboard is better than the naked `H201` confirmation paths
- but not good enough to survive the honest incumbent benchmark

Branch effect:
- `H254` is **FAILED**
- close the current-data report-window selector-switchboard branch
- keep `H252/H253` as offline regime evidence only
- if the model-side queue is intentionally continued later, move to `H255`

Active workspace policy still does not change:
- acquisition-first timing-data work remains the main non-live branch
- live sticky branch remains frozen and monitor-only

## Validation

Completed:
- `python -m py_compile analysis/h254_report_window_selector_switchboard.py src/deterministic_portfolio.py tests/test_deterministic_portfolio.py`
- `pytest -q tests/test_deterministic_portfolio.py -q`
- full `conda run -n stocks python analysis/h254_report_window_selector_switchboard.py` run completed

Saved artifacts:
- `artifacts/run_summaries/latest_portfolio_report_window_selector_switchboard.json`
- `artifacts/portfolio_baselines/20260331_120602_h254_report_window_selector_switchboard_results.parquet`
- `artifacts/portfolio_baselines/20260331_120602_h254_report_window_selector_switchboard_candidate_daily.parquet`
- `artifacts/portfolio_baselines/20260331_120602_h254_report_window_selector_switchboard_gate_frame.parquet`
