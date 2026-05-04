# Session 258 Log

Date: 2026-05-04
Focus: H381 silent order pressure walk-forward test

## Summary

- Continued the evergreen queue after H380 by activating
  `silent_order_pressure`.
- Implemented reusable script:
  `analysis/h381_silent_order_pressure.py`.
- Tested fixed no-news C16 states using published C16, H93 labels, and dense
  PhoBERT/news ticker-day article counts.
- Used TRUE walk-forward yearly folds: for each test year, train years are
  strictly earlier years. State definitions are fixed and no thresholds were
  tuned on future years.
- Used data from `2016-2025`; no `2026+` rows were used.

## Experiment Contract

- Hypothesis: C16 order pressure is strongest when it appears before a public
  news narrative, proxied by `phobert_article_count_1d == 0` or
  `phobert_article_count_5d == 0`.
- Direct variation benchmark: all published C16 rows.
- Peer benchmark: active-news C16 rows.
- Down-market control: no-news C16 on down-market days versus all down-market
  C16 and active-news down-market C16.
- Primary pass rule: `silent_5d` must have positive WF mean IC, beat all-C16 by
  more than `0.005`, beat `active_5d`, have at least `60%` positive WF years,
  and have positive 2025 IC.

## Command

```bash
/home/manh/miniforge3/envs/stocks/bin/python analysis/h381_silent_order_pressure.py
```

## Saved Artifacts

- Summary:
  `artifacts/run_summaries/20260504_130641_h381_silent_order_pressure_research_branch_silent_order_pressure.json`
- Fold table:
  `artifacts/order_pressure/20260504_130641_h381_silent_order_pressure_folds.parquet`
- State table:
  `artifacts/order_pressure/20260504_130641_h381_silent_order_pressure_states.parquet`

## Key Metrics

Panel:
- Rows: `758,414`.
- Dates: `2,500`.
- Tickers: `394`.
- 1d active-news share: `22.48%`.
- 5d active-news share: `44.26%`.

Primary states:

| State | WF mean IC | Positive years | 2025 IC | Lift vs baseline | Lift vs peer |
|---|---:|---:|---:|---:|---:|
| `c16_all` | `+0.0752` | `8 / 8` | `+0.0713` | `0.0000` | NA |
| `silent_5d` | `+0.0700` | `8 / 8` | `+0.0617` | `-0.0051` | `-0.0145` |
| `active_5d` | `+0.0846` | `8 / 8` | `+0.0858` | `+0.0094` | `+0.0145` |
| `silent_1d` | `+0.0720` | `8 / 8` | `+0.0657` | `-0.0032` | `-0.0170` |
| `active_1d` | `+0.0890` | `8 / 8` | `+0.0907` | `+0.0138` | `+0.0170` |
| `silent_5d_down_market` | `+0.0845` | `8 / 8` | `+0.0734` | `-0.0075` | `-0.0138` |
| `active_5d_down_market` | `+0.0983` | `8 / 8` | `+0.0987` | `+0.0063` | `+0.0138` |

## Verdict

Verdict: `FAILED`.

Durable status: branch kill or reframe.

Reasoning:
- The primary no-news state failed the direct C16 variation benchmark:
  `silent_5d` IC was `+0.0700`, below all-C16 `+0.0752` and below active-news
  C16 `+0.0846`.
- The 1d no-news variant also failed.
- The down-market no-news control also failed; active-news down-market C16 was
  stronger.
- The useful inversion is that active-news rows made C16 stronger, not weaker.

## Next Action

- Remove `silent_order_pressure` from the active queue under current PhoBERT
  article-count representation.
- Record dead end `D001` and finding `F341`.
- Reopen only if the representation changes materially, for example with
  completed Ollama event-family data, peer/co-mention narrative-vacuum features,
  or a different "not public yet" proxy.
- Continue next with `news_flow_disagreement`, using H381's inversion as the
  starting clue: active narrative plus C16 may be confirmation rather than
  crowding.
