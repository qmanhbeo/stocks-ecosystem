# S271 Session Log

**Date**: 2026-05-04
**Focus**: H393 nihilist reversal audit

## Summary

- Ran `nihilist_reversal` as H393.
- Implemented reusable script:
  `analysis/h393_nihilist_reversal.py`.
- Tested whether high C16 after stock and market weakness works better when
  local news is weak or not bullish.
- Used `2016-2025` rows only. No `2026+` rows were used.

## Experiment Contract

Primary state:
- `nihilist_reversal`: high C16, stock down on trailing 1d and 3d returns,
  VNI down on trailing 1d and 3d returns, and no bullish 5d local-news support.

Diagnostics:
- `nihilist_no_news`
- `nihilist_weak_active_news`

Controls:
- `stock_market_down_high_c16`
- `stock_down_high_c16`
- `market_down_high_c16`
- raw `high_c16`
- `active_news_high_c16`
- `stock_market_down_high_c16_bullish_news`

Pass rule:
- PASS if `nihilist_reversal` has positive mean 5d relative payoff and beats
  all controls by more than `+0.002` on average, with at least `60%`
  positive-lift years and positive 2025 lifts.
- MIXED if it is positive but control-incomplete.
- FAIL otherwise.

## Commands

```bash
python -m py_compile alpha-research-lab/analysis/h393_nihilist_reversal.py
python alpha-research-lab/analysis/h393_nihilist_reversal.py
```

Saved artifacts:
- Summary:
  `artifacts/run_summaries/20260504_210147_h393_nihilist_reversal_research_branch_nihilist_reversal.json`
- Fold table:
  `artifacts/order_pressure/20260504_210147_h393_nihilist_reversal_folds.parquet`
- State table:
  `artifacts/order_pressure/20260504_210147_h393_nihilist_reversal_states.parquet`

## Key Metrics

Primary state:
- `nihilist_reversal`: mean 5d relative payoff `+0.010170`, 5d hit rate
  `0.5435`, mean C16 5d IC `+0.07738`, mean rows/year `995.0`, but 2025 5d
  payoff `-0.000982`.

Controls:
- `stock_down_high_c16`: mean 5d payoff `+0.012197`, 5d hit rate `0.5616`,
  mean C16 5d IC `+0.09182`, and 2025 payoff `+0.002174`.
- `stock_market_down_high_c16`: mean 5d payoff `+0.010001`, 2025 payoff
  `-0.000772`.
- raw `high_c16`: mean 5d payoff `+0.008645`, 2025 payoff `+0.000733`.
- `active_news_high_c16`: mean 5d payoff `+0.008698`, 2025 payoff
  `+0.001773`.

Primary lift diagnostics:
- Versus `stock_market_down_high_c16`: mean 5d lift `+0.000169`, only `2 / 8`
  positive years, 2025 lift `-0.000210`.
- Versus `stock_down_high_c16`: mean 5d lift `-0.002027`, only `1 / 8`
  positive years, 2025 lift `-0.003156`.
- Versus `market_down_high_c16`: mean 5d lift `+0.003238`, `8 / 8` positive
  years, 2025 lift `+0.000937`.
- Versus raw `high_c16`: mean 5d lift `+0.001525`, `5 / 8` positive years,
  2025 lift `-0.001716`.
- Versus `active_news_high_c16`: mean 5d lift `+0.001472`, `5 / 8` positive
  years, 2025 lift `-0.002755`.
- Versus bullish-news capitulation: mean 5d lift `+0.000518`, only `2 / 8`
  positive years, 2025 lift `-0.000749`.

Narrow clue:
- `nihilist_weak_active_news` had mean 5d payoff `+0.009845` and 2025 payoff
  `+0.008064`, but only `183` rows/year and it was not the primary state. It
  needs a separate fixed contract if reopened.

## Verdict

H393 `MIXED`.

Interpretation:
- The capitulation/no-bullish-news state is positive, but it is not stronger
  than the simpler `stock_down_high_c16` control and it fails 2025.
- The useful piece remains high C16 after stock weakness. Adding market
  weakness and no-bullish-news does not improve that control.
- Do not promote a nihilist-reversal overlay or matrix column under this
  representation.

Durable-promotion status:
- park or narrow nihilist reversal
- no live branch change
- no shared matrix or recommendation-contract promotion

Reopening condition:
- Reopen only with a predeclared weak-active-news subset, intraday absorption
  after capitulation, or a consumer rule that explicitly tests re-entry after
  the no-bullish-news washout rather than same-day entry.

Next action:
- Continue the refreshed queue at `anti_signal_annihilation_veto`.

## Verification

- `py_compile` passed.
- The script completed and wrote saved artifacts.
- The saved JSON summary, fold table, and state table were read before this
  verdict.
- `2026+` data was avoided; run window was `2016-2025`.
- The live branch stayed frozen and long-only.
- No heavy job was active after completion.
