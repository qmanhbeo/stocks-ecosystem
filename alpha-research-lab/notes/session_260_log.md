# Session 260 Log

Date: 2026-05-04
Focus: H382 fixed H364 local-news consumer integration audit

## Summary

- Used the `experimentor` protocol on the next activated branch from
  `notes/live_state.md`: one fixed portfolio/consumer audit for
  `h364_official_sentiment_x_earnings_guidance`.
- Implemented reusable script:
  `analysis/h382_h364_local_news_consumer_integration.py`.
- Used TRUE walk-forward years: for each test year, the script used only prior
  years to choose the consumer `K` from `top1/top2/top3/top5`, then tested the
  chosen policy on the next year.
- No `2026+` rows were used. The run window was `2019-2025`, producing test
  years `2021-2025`.
- Because this is not a direct S1 or C16 variation, the benchmark was random
  candidate policy, not S1/C16.

## Experiment Contract

Hypothesis:
- The fixed H364 local-news feature can be consumed inside the candidate pool
  by selecting the highest-H364 buyable active-news candidate(s) better than
  random same-support candidate selection.

Fixed feature:
- `h364_official_sentiment_x_earnings_guidance`
- Formula:
  `phobert_sentiment_score_sum * phobert_source_type_official_or_regulatory_prob_mean * clip(ollama_guarded_event_family_earnings_share + ollama_guarded_event_family_guidance_share, 0, 1)`

Data:
- `data/features/entry_alpha/candidate_panel_daily.parquet`
- `data/features/entry_alpha/entry_labels_cycle5.parquet`
- `data/features/news/datasets/news_daily_features.parquet`

Consumer policy:
- On each date, filter to buyable candidate-pool rows.
- Use H364-active rows only for the H364 policy.
- Select top `K` by the fixed H364 score; missing slots are cash.
- Train only the `K` choice on prior years.

Benchmarks:
- Primary: random same-`K` selection among active buyable H364 candidates.
- Secondary: random same-`K` selection among all buyable candidate-pool rows.
- `5,000` random trials per walk-forward fold.

Pass rule:
- PASS if support is sufficient, mean lift versus random-active is positive,
  at least `60%` of walk-forward years beat random-active mean, and 2025
  confirmation lift is positive.
- MIXED if only partial consistency.
- FAIL otherwise.

## Commands

```bash
/home/manh/miniforge3/envs/stocks/bin/python -m py_compile analysis/h382_h364_local_news_consumer_integration.py
/home/manh/miniforge3/envs/stocks/bin/python analysis/h382_h364_local_news_consumer_integration.py
```

The script was run twice; the second run was after removing a harmless pandas
future-warning and is the canonical artifact below. Both runs produced the same
metrics.

## Saved Artifacts

- Summary:
  `artifacts/run_summaries/20260504_194152_h382_h364_local_news_consumer_integration_research_branch_h364_local_news_consumer_integration.json`
- Year table:
  `artifacts/entry_alpha/20260504_194152_h382_h364_local_news_consumer_integration_years.parquet`
- Daily table:
  `artifacts/entry_alpha/20260504_194152_h382_h364_local_news_consumer_integration_daily.parquet`

## Key Metrics

Aggregate:
- verdict: `PASSED`
- durable status: `offline_evidence`
- mean policy absolute cycle return: `-0.00026`
- mean random-active absolute cycle return: `-0.00117`
- mean lift versus random-active: `+0.00092`
- years beating random-active mean: `4 / 5`
- years beating random-active p95: `0 / 5`
- 2025 confirmation lift versus random-active: `+0.00296`
- 2025 random-active percentile: `0.855`
- mean random-all absolute cycle return: `+0.00342`
- mean lift versus random-all: `-0.00367`
- years beating random-all mean: `1 / 5`
- minimum active dates in a test year: `192`

Year table:

| Test year | K | Active dates | Policy abs return | Random-active mean | Lift vs random-active | Random-active pctile | Random-all mean | Lift vs random-all |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2021 | 1 | 232 | `+0.01231` | `+0.01204` | `+0.00027` | `0.5388` | `+0.01594` | `-0.00363` |
| 2022 | 1 | 213 | `-0.01302` | `-0.01140` | `-0.00163` | `0.3296` | `-0.00647` | `-0.00655` |
| 2023 | 1 | 192 | `-0.00094` | `-0.00150` | `+0.00056` | `0.6016` | `+0.00384` | `-0.00478` |
| 2024 | 1 | 217 | `-0.00362` | `-0.00603` | `+0.00241` | `0.8800` | `+0.00128` | `-0.00490` |
| 2025 | 1 | 224 | `+0.00399` | `+0.00102` | `+0.00296` | `0.8550` | `+0.00249` | `+0.00150` |

## Verdict

H382 passed only as a narrow same-support event-candidate ranker. H364 adds
ranking value within its own active news subset, but the active subset is not a
better broad allocation universe than the full buyable candidate pool.

Durable-promotion status:
- offline evidence only
- no live branch change
- no broad portfolio-consumer promotion

Next action:
- Use H364 as a local-news anchor inside broader `news_flow_disagreement`,
  official-delay, or source-triangle interaction tests.
- Do not add H364 as a broad candidate-pool allocator without a stronger
  consumer contract.

## Verification

- `py_compile` passed for the new script.
- H382 completed from the reusable script.
- The saved JSON summary was read before this judgment.

