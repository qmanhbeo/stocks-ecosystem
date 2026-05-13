# Session 262 Log

Date: 2026-05-04
Focus: H384 news-flow confirmation consumer audit

## Summary

- Ran the fixed H383 consumer follow-through:
  `news_flow_confirmation_consumer`.
- Implemented reusable script:
  `analysis/h384_news_flow_confirmation_consumer.py`.
- Tested only two predeclared H383 states:
  `active_news_strong_flow` and `positive_news_strong_flow`.
- Used buyable rows from `data/features/entry_alpha/candidate_panel_daily.parquet`,
  cycle labels from `data/features/entry_alpha/entry_labels_cycle5.parquet`,
  C16 from `data/features/xs_order_pressure_daily.parquet`, and local-news
  state columns from `data/features/news/datasets/news_daily_features.parquet`.
- Used TRUE walk-forward years `2021-2025`; each fold chose only `K` from prior
  years for each fixed state. No `2026+` rows were used.

## Experiment Contract

Hypothesis:
- The H383 active/positive-news strong-flow IC edge can be consumed inside the
  buyable candidate pool by selecting the highest-C16 candidates from those
  fixed states.

Fixed states:
- `active_news_strong_flow`: active 1d PhoBERT news and
  `order_volume_ratio_rank >= 0.80`
- `positive_news_strong_flow`: positive 1d PhoBERT news and
  `order_volume_ratio_rank >= 0.80`

Consumer policy:
- On each date, filter to buyable candidate-pool rows with
  `candidate_pool_rank <= 20`.
- Inside each fixed state, select top `K` by `order_volume_ratio_rank`.
- Missing slots are cash.
- Train only the `K` choice from `top1/top2/top3/top5` using prior years.

Benchmarks:
- Primary: random same-`K` selection among active buyable rows from the same
  fixed state.
- Secondary: random same-`K` selection among all buyable candidate-pool rows.
- `5,000` random trials per walk-forward fold.

Pass rule:
- PASS if any fixed state beats both random same-support and random-all means
  on average, beats both in at least `60%` of WF years, has positive 2025 lift
  versus both, and has enough support.
- MIXED if only the same-support gate clears.
- FAIL otherwise.

## Commands

```bash
/home/manh/miniforge3/envs/stocks/bin/python -m py_compile analysis/h384_news_flow_confirmation_consumer.py
/home/manh/miniforge3/envs/stocks/bin/python analysis/h384_news_flow_confirmation_consumer.py
```

The first run produced a harmless pandas future warning. The script was cleaned
up and rerun; the second run is canonical.

## Saved Artifacts

- Summary:
  `artifacts/run_summaries/20260504_195935_h384_news_flow_confirmation_consumer_research_branch_news_flow_confirmation_consumer.json`
- Year table:
  `artifacts/entry_alpha/20260504_195935_h384_news_flow_confirmation_consumer_years.parquet`
- Daily table:
  `artifacts/entry_alpha/20260504_195935_h384_news_flow_confirmation_consumer_daily.parquet`

Earlier non-canonical first-run artifacts:
- `artifacts/run_summaries/20260504_195901_h384_news_flow_confirmation_consumer_research_branch_news_flow_confirmation_consumer.json`
- `artifacts/entry_alpha/20260504_195901_h384_news_flow_confirmation_consumer_years.parquet`
- `artifacts/entry_alpha/20260504_195901_h384_news_flow_confirmation_consumer_daily.parquet`

## Key Metrics

Panel:
- Candidate rows: `33,925`
- Daily rows: `1,737`
- Active-news strong-flow rows: `1,429`
- Positive-news strong-flow rows: `1,215`

State summaries:

| State | Mean policy abs return | Random-state mean | Lift vs random-state | Random-all mean | Lift vs random-all | Years > random-state | Years > random-all | 2025 lift vs random-all |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `active_news_strong_flow` | `+0.00038` | `+0.00064` | `-0.00026` | `+0.00375` | `-0.00337` | `2 / 5` | `2 / 5` | `+0.00300` |
| `positive_news_strong_flow` | `+0.00180` | `+0.00200` | `-0.00020` | `+0.00371` | `-0.00191` | `2 / 5` | `2 / 5` | `+0.00439` |

Both states selected `K=1` in every fold. 2025 was positive, but the mean and
year consistency gates failed.

## Verdict

H384 `FAILED`.

Interpretation:
- H383 remains valid offline IC evidence, but its active/positive-news
  strong-flow states do not currently form a candidate-pool allocation policy.
- Neither fixed state beat random same-support cleanly.
- Both fixed states failed the broader random-all allocation benchmark.

Durable-promotion status:
- branch kill or reframe for the current H383 consumer contract
- no live branch change
- no broad matrix or recommendation-contract promotion

Next action:
- Return to the ranked queue at `official_attention_delay`, using the H381-H384
  lesson: local-news/flow states need consumer proof before allocation use.

## Verification

- `py_compile` passed for the new script.
- The canonical H384 script completed and wrote saved artifacts.
- The saved JSON summary and year table were read before this verdict.
- `2026+` data was avoided; run window was `2019-2025`.
- The live branch stayed frozen and long-only.
- No heavy job was active after completion.
