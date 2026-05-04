# S268 Session Log

**Date**: 2026-05-04
**Focus**: H390 calendar-as-liquidity mechanism audit

## Summary

- Ran `calendar_as_liquidity_mechanism` as H390.
- Implemented reusable script:
  `analysis/h390_calendar_liquidity_mechanism.py`.
- Retested the old calendar C16 edges as daily C16 IC uplifts after
  walk-forward residualization on liquidity, breadth, news-volume, buyability,
  C16 availability, volume-pressure, and trailing down-market controls.
- Used `2016-2025` as the allowed window, but the candidate-control surface
  begins in 2019, so the saved daily panel spans `2019-01-02` through
  `2025-12-31` and TRUE walk-forward test years are `2021-2025`.
- No `2026+` rows were used.

## Experiment Contract

Hypothesis:
- Old calendar edges are proxies for settlement, attention, breadth, liquidity,
  and tradability regimes, not magic dates.

Fixed primary states:
- `monday_jan_combo`: Monday inside the first 10 calendar days of January,
  matching the old `c16_monday_jan_combo` definition.
- `quarter_start`: first five calendar days of January, April, July, and
  October.
- `late_quarter_month`: last five calendar days of March, June, September, and
  December.

Diagnostics:
- `january_monday`
- `monday`
- `january_first_10`

Mechanism controls:
- candidate count and candidate-pool size
- buyable breadth and liquid-open breadth
- top-10 buyable and liquid-open counts
- news-surge proxy
- market breadth and dispersion
- trailing VNI returns, realized volatility, drawdown, and 5d down-market flag
- top-book turnover/ADV proxies
- C16 row count, buyable share, and mean absolute order-volume-ratio pressure

Pass rule:
- PASS if one primary calendar state retains 1d residual daily-C16-IC lift
  above `+0.010`, has at least `60%` positive residual-lift years, non-negative
  2025 confirmation, and also has positive 5d residual lift.
- MIXED if only raw 1d IC lift remains.
- FAIL otherwise.

## Commands

```bash
python alpha-research-lab/analysis/h390_calendar_liquidity_mechanism.py
python -m py_compile alpha-research-lab/analysis/h390_calendar_liquidity_mechanism.py
```

Saved artifacts:
- Summary:
  `artifacts/run_summaries/20260504_204043_h390_calendar_liquidity_mechanism_research_branch_calendar_liquidity_mechanism.json`
- Daily table:
  `artifacts/timing_data/20260504_204043_h390_calendar_liquidity_mechanism_daily.parquet`
- Residualized daily table:
  `artifacts/timing_data/20260504_204043_h390_calendar_liquidity_mechanism_residuals.parquet`
- Fold table:
  `artifacts/timing_data/20260504_204043_h390_calendar_liquidity_mechanism_folds.parquet`
- State table:
  `artifacts/timing_data/20260504_204043_h390_calendar_liquidity_mechanism_states.parquet`

## Key Metrics

Panel:
- Daily rows: `1,749`
- Daily range: `2019-01-02` to `2025-12-31`
- Test years: `2021-2025`

Primary 1d residual IC results:

| State | WF years | Mean dates/year | Mean state IC | Raw IC lift | Positive raw years | Residual IC lift | Positive residual years | 2025 residual lift |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `monday_jan_combo` | `4` | `1.0` | `+0.105912` | `+0.015221` | `2 / 4` | `+0.027453` | `2 / 4` | `+0.083812` |
| `quarter_start` | `5` | `12.6` | `+0.096459` | `-0.003313` | `1 / 5` | `-0.001770` | `3 / 5` | `-0.003942` |
| `late_quarter_month` | `5` | `16.8` | `+0.088550` | `-0.011979` | `2 / 5` | `-0.006625` | `3 / 5` | `+0.003861` |

Primary 5d residual IC results:

| State | WF years | Mean dates/year | Mean state IC | Raw IC lift | Positive raw years | Residual IC lift | Positive residual years | 2025 residual lift |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `quarter_start` | `5` | `12.6` | `+0.084747` | `+0.008906` | `3 / 5` | `+0.008658` | `3 / 5` | `+0.026641` |
| `late_quarter_month` | `5` | `16.8` | `+0.061629` | `-0.016049` | `2 / 5` | `-0.014577` | `2 / 5` | `-0.052499` |
| `monday_jan_combo` | `4` | `1.0` | `+0.029053` | `-0.047698` | `2 / 4` | `-0.040549` | `2 / 4` | `+0.089055` |

Diagnostics:
- `january_first_10` is the cleaner residual calendar clue. On the 1d target
  it had mean raw IC lift `+0.024624`, residual IC lift `+0.030674`, and
  `5 / 5` positive residual-lift years. This was diagnostic only and was not
  a primary predeclared state.
- Broad `monday` also retained 1d residual lift (`+0.017387`, `4 / 5`
  positive residual years), but it was diagnostic only and not enough to revive
  the old exact Monday/January combo as a deployable 5d timing rule.

## Verdict

H390 `MIXED`.

Interpretation:
- The exact old `monday_jan_combo` still contains a sparse 1d C16-quality
  effect after mechanism controls, but it has only one active test date per
  evaluated year, only `2 / 4` positive 1d residual-lift years, and negative
  mean 5d residual lift.
- `quarter_start` and `late_quarter_month` do not retain independent 1d
  residual IC lift.
- Calendar remains useful as timing context and as a hypothesis generator, but
  this does not justify an independent live overlay, sparse-clock rule, matrix
  promotion, or recommendation policy under the current target.

Durable-promotion status:
- park or reframe `calendar_as_liquidity_mechanism`
- no live branch change
- no shared matrix or recommendation-contract promotion

Reopening condition:
- Reopen only with a predeclared broader January-window or weekday timing
  contract, a different 5d/execution target, or a downstream consumer that
  compares calendar context against mechanism-matched alternatives.

Next action:
- Continue the ranked queue at `tradability_release_pulse`.

## Verification

- `py_compile` passed.
- The script completed and wrote saved artifacts.
- The saved JSON summary, fold table, and state table were read before this
  verdict.
- `2026+` data was avoided; saved daily range ended `2025-12-31`.
- The live branch stayed frozen and long-only.
- No heavy job was active after completion.
