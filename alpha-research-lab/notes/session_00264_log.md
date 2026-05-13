# Session 264 Log

Date: 2026-05-04
Focus: H386 official delay consumer router

## Summary

- Ran the fixed H385 consumer follow-through:
  `official_delay_consumer_router`.
- Implemented reusable script:
  `analysis/h386_official_delay_consumer_router.py`.
- Tested only two predeclared H385 pass states:
  `official_supported` and `official_forward_supported`.
- Used buyable rows from `data/features/entry_alpha/candidate_panel_daily.parquet`,
  cycle labels from `data/features/entry_alpha/entry_labels_cycle5.parquet`,
  C16 from `data/features/xs_order_pressure_daily.parquet`, local-news state
  columns from `data/features/news/datasets/news_daily_features.parquet`, and
  C5 insider fields from `data/features/xs_rl_signal_matrix.parquet`.
- Used TRUE walk-forward years `2021-2025`; each fold chose only `K` from prior
  years for each fixed state. No `2026+` rows were used.

## Experiment Contract

Hypothesis:
- The H385 support-confirmed official/forward delayed-payoff states can be
  consumed inside the buyable candidate pool.

Fixed states:
- `official_supported`: official/regulatory source row plus high C16 or
  positive C5 insider support.
- `official_forward_supported`: official/regulatory or forward-looking row plus
  high C16 or positive C5 insider support.

Consumer policy:
- On each date, filter to buyable candidate-pool rows with
  `candidate_pool_rank <= 20`.
- Inside each fixed state, select top `K` by lowest `candidate_pool_rank`, with
  highest `order_volume_ratio_rank` only as a tie-breaker.
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
- MIXED if only one random-policy gate clears.
- FAIL otherwise.

## Commands

```bash
/home/manh/miniforge3/envs/stocks/bin/python -m py_compile analysis/h386_official_delay_consumer_router.py
/home/manh/miniforge3/envs/stocks/bin/python analysis/h386_official_delay_consumer_router.py
```

## Saved Artifacts

- Summary:
  `artifacts/run_summaries/20260504_201315_h386_official_delay_consumer_router_research_branch_official_delay_consumer_router.json`
- Year table:
  `artifacts/entry_alpha/20260504_201315_h386_official_delay_consumer_router_years.parquet`
- Daily table:
  `artifacts/entry_alpha/20260504_201315_h386_official_delay_consumer_router_daily.parquet`

## Key Metrics

Panel:
- Candidate rows: `33,925`
- Daily rows: `1,737`
- Official-supported rows: `344`
- Official/forward-supported rows: `558`

State summaries:

| State | Mean policy abs return | Random-state mean | Lift vs random-state | Random-all mean | Lift vs random-all | Years > random-state | Years > random-all | 2025 lift vs random-all |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `official_supported` | `-0.00171` | `-0.00136` | `-0.00035` | `+0.00368` | `-0.00540` | `2 / 5` | `1 / 5` | `-0.00227` |
| `official_forward_supported` | `-0.00187` | `-0.00130` | `-0.00057` | `+0.00368` | `-0.00555` | `2 / 5` | `1 / 5` | `-0.00244` |

Support:
- `official_supported`: minimum active dates per WF year `23`.
- `official_forward_supported`: minimum active dates per WF year `41`.
- Both states had enough support, so the failure is return quality, not an
  empty-sample artifact.

## Verdict

H386 `FAILED`.

Interpretation:
- H385 remains valid offline delayed-payoff evidence.
- The two fixed H385 states do not currently form a buyable candidate-pool
  allocator when consumed by candidate rank and compared with random
  same-support plus random-all policies.
- Do not promote H385 states into the live branch, matrix contract, or shared
  recommendation candidate policy from H385/H386 alone.

Durable-promotion status:
- branch kill or reframe for this consumer contract
- H385 remains offline evidence only
- no live branch change
- no broad matrix or recommendation-contract promotion

Next action:
- Return to the broader ranked queue at `insider_down_rescue`.

## Verification

- `py_compile` passed for the new script.
- The H386 script completed and wrote saved artifacts.
- The saved JSON summary, year table, and daily table were read before this
  verdict.
- `2026+` data was avoided; run window was `2019-2025`.
- The live branch stayed frozen and long-only.
- No heavy job was active after completion.
