# S269 Session Log

**Date**: 2026-05-04
**Focus**: H391 tradability-release pulse audit

## Summary

- Ran `tradability_release_pulse` as H391.
- Implemented reusable script:
  `analysis/h391_tradability_release_pulse.py`.
- Tested whether high-ranked candidate rows that become buyable after a prior
  blocked-buy state beat same-rank stable-buyable and non-release-buyable
  controls.
- Used `2019-2025` candidate-panel and cycle-label rows only. No `2026+` rows
  were used.

## Experiment Contract

Hypothesis:
- A high-ranked name that was good but unbuyable may have a short executable
  continuation edge when it becomes buyable.

Fixed primary states:
- `top5_release`: `candidate_pool_rank <= 5`, `prev_can_buy_next_open == false`,
  `can_buy_next_open == true`, and `release_flag == true`.
- `top10_release`: same release definition with `candidate_pool_rank <= 10`.

Diagnostics:
- `top20_release`
- stable-buyable and non-release-buyable controls for top-5/top-10/top-20
- still-blocked controls for blocked-buy health context

Pass rule:
- PASS if `top5_release` or `top10_release` has positive mean cycle relative
  return, can-sell rate above `0.90`, mean lift above `+0.002` versus both
  same-year same-rank stable-buyable and non-release-buyable controls, at
  least `60%` positive-lift years, and positive 2025 matched-control lifts.
- MIXED if a primary release state is only directionally positive.
- FAIL otherwise.

## Commands

```bash
python -m py_compile alpha-research-lab/analysis/h391_tradability_release_pulse.py
python alpha-research-lab/analysis/h391_tradability_release_pulse.py
```

Saved artifacts:
- Summary:
  `artifacts/run_summaries/20260504_204826_h391_tradability_release_pulse_research_branch_tradability_release_pulse.json`
- Fold table:
  `artifacts/entry_alpha/20260504_204826_h391_tradability_release_pulse_folds.parquet`
- State table:
  `artifacts/entry_alpha/20260504_204826_h391_tradability_release_pulse_states.parquet`

## Key Metrics

Panel:
- Rows: `34,980`
- Dates: `1,749`
- Release rows: `513`
- Release-flag mismatches against
  `prev_can_buy_next_open == false and can_buy_next_open == true`: `0`
- Test years: `2021-2025`

Primary release states:

| State | WF years | Mean rows | Mean relative return | Hit rate | Can-sell rate | Mean rank | Lift vs matched stable | Positive stable-lift years | 2025 stable lift |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `top5_release` | `5` | `15.0` | `-0.032254` | `0.3048` | `0.8675` | `2.69` | `-0.033668` | `1 / 5` | `-0.080106` |
| `top10_release` | `5` | `29.8` | `-0.027022` | `0.3461` | `0.8896` | `5.15` | `-0.028365` | `1 / 5` | `-0.066302` |

Diagnostic:
- `top20_release` also failed: mean relative return `-0.020405`, lift versus
  matched stable/non-release controls `-0.021859`, only `1 / 5` positive
  matched-control years, and 2025 lift `-0.031930`.
- Current release rows have high limit-release pressure diagnostics, but that
  did not translate into executable continuation.
- Still-blocked controls were not a rescue path: top-20 still-blocked rows were
  less negative than release rows on average, while top-5/top-10 still-blocked
  support was sparse.

## Verdict

H391 `FAILED`.

Interpretation:
- The current entry-panel `release_flag` marks a real tradability transition,
  but high-ranked release rows are weak subsequent buys under the cycle-label
  target.
- This looks more like delayed exhaustion after limit/blocked-buy pressure than
  a door-open continuation edge.
- Do not add a `wait_release` inclusion boost, live overlay, matrix column, or
  recommendation policy from this representation.

Durable-promotion status:
- branch kill or reframe for tradability-release pulse under the current
  entry-panel release contract
- no live branch change
- no shared matrix or recommendation-contract promotion

Reopening condition:
- Reopen only with a materially different release contract, such as order-book
  queue/open-fill data, intraday post-release absorption, or a rule that waits
  for re-block risk and next-day sellability to normalize before entry.

Next action:
- Continue the ranked queue at `source_triangle_sparse`.

## Verification

- `py_compile` passed.
- The script completed and wrote saved artifacts.
- The saved JSON summary, fold table, and state table were read before this
  verdict.
- `2026+` data was avoided; run window was `2019-2025`.
- The live branch stayed frozen and long-only.
- No heavy job was active after completion.
