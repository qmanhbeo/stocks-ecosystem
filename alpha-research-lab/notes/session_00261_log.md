# Session 261 Log

Date: 2026-05-04
Focus: H383 news-flow disagreement / confirmation audit

## Summary

- Continued the evergreen queue after H382 by activating
  `news_flow_disagreement`.
- Implemented reusable script:
  `analysis/h383_news_flow_disagreement.py`.
- Used fixed C16/news state definitions only: no threshold tuning, no live
  branch retuning, and no `2026+` rows.
- Primary target was next-day close-to-close relative return versus VNINDEX.
  Secondary diagnostic target was the existing S1 `actual` label.
- Used TRUE walk-forward folds: test years `2018-2025`, with train years
  strictly before each test year.

## Experiment Contract

Hypothesis:
- Public text and posted-order pressure interact: disagreement states may flag
  traps, while active-news plus strong C16 may confirm tradable demand.

Fixed score:
- `order_volume_ratio_rank`

Fixed state gates:
- high flow: `order_volume_ratio_rank >= 0.80`
- weak flow: `order_volume_ratio_rank <= 0.40`
- active news: `phobert_article_count_1d > 0`
- no news: `phobert_article_count_5d == 0`
- positive / negative news: fixed PhoBERT sentiment/probability orientation
- source/scope heads: fixed `>= 0.50` probability where used

Primary states:
- `bullish_flow_negative_news`
- `bullish_flow_no_news`
- `positive_news_weak_flow`
- `active_news_strong_flow`

Pass rule:
- PASS if a predeclared primary state has positive WF mean 1d relative-return
  IC, beats its fixed baseline by more than `0.005`, has at least `60%`
  positive WF years, has positive 2025 confirmation IC, and has average test
  support at or above `500` rows.
- MIXED if only a secondary stronger-news confirmation state clears the same
  gate.
- FAIL otherwise.

## Commands

```bash
/home/manh/miniforge3/envs/stocks/bin/python -m py_compile analysis/h383_news_flow_disagreement.py
/home/manh/miniforge3/envs/stocks/bin/python analysis/h383_news_flow_disagreement.py
```

The first run exposed a secondary-diagnostic bug: the helper required three
unique target values, which incorrectly blanked the binary S1 `actual` ICs.
The script was fixed to allow binary targets and rerun. The second run is the
canonical artifact below.

## Saved Artifacts

- Summary:
  `artifacts/run_summaries/20260504_195247_h383_news_flow_disagreement_research_branch_news_flow_disagreement.json`
- Fold table:
  `artifacts/order_pressure/20260504_195247_h383_news_flow_disagreement_folds.parquet`
- State table:
  `artifacts/order_pressure/20260504_195247_h383_news_flow_disagreement_states.parquet`

Earlier non-canonical first-run artifacts:
- `artifacts/run_summaries/20260504_195200_h383_news_flow_disagreement_research_branch_news_flow_disagreement.json`
- `artifacts/order_pressure/20260504_195200_h383_news_flow_disagreement_folds.parquet`
- `artifacts/order_pressure/20260504_195200_h383_news_flow_disagreement_states.parquet`

## Key Metrics

Panel:
- Rows: `757,454`
- Dates: `2,500`
- Tickers: `394`
- Active-news share: `22.50%`
- Strong-flow share: `18.27%`

Main rows:

| State | WF mean rel IC | WF mean S1 IC | Positive years | 2025 rel IC | Lift vs baseline | Mean 1d rel return |
|---|---:|---:|---:|---:|---:|---:|
| `active_news` | `+0.11070` | `+0.08897` | `8 / 8` | `+0.11635` | `+0.01666` vs all-C16 | `+0.00065` |
| `positive_news_strong_flow` | `+0.10854` | `+0.06904` | `8 / 8` | `+0.12854` | `+0.04566` vs strong-flow | `+0.00685` |
| `active_news_strong_flow` | `+0.10293` | `+0.06972` | `8 / 8` | `+0.12163` | `+0.04005` vs strong-flow | `+0.00653` |
| `c16_all` | `+0.09404` | `+0.07519` | `8 / 8` | `+0.08855` | baseline | `+0.00037` |
| `no_news_5d` | `+0.08852` | `+0.06995` | `8 / 8` | `+0.07746` | `-0.00552` vs all-C16 | `+0.00045` |
| `bullish_flow_no_news` | `+0.05433` | `+0.03865` | `8 / 8` | `+0.05632` | `-0.00855` vs strong-flow | `+0.00430` |
| `positive_news_weak_flow` | `+0.02327` | `+0.01058` | `8 / 8` | `+0.03580` | `-0.00063` vs weak-flow | `-0.00198` |

## Verdict

H383 `PASSED`, but the durable mechanism is confirmation rather than the
original disagreement story.

Interpretation:
- H381's inversion was confirmed on a stronger target: active-news rows make
  C16 more predictive than no-news rows.
- `active_news_strong_flow` cleared the primary pass rule versus the
  strong-flow baseline.
- `positive_news_strong_flow` was even stronger as a secondary confirmation
  state.
- No-news and weak-flow disagreement states did not beat their baselines.

Durable-promotion status:
- offline evidence only
- no live branch change
- no shared matrix or portfolio-contract promotion yet

Next action:
- Run one fixed H383 consumer integration audit: select buyable candidate-pool
  rows inside `active_news_strong_flow` / `positive_news_strong_flow`, choose
  only `K` from prior years, and compare against random same-support and
  random-all candidate policies. If that does not promote or narrow cleanly,
  return to the queued `official_attention_delay` branch.

## Verification

- `py_compile` passed for the new script.
- The canonical H383 script completed and wrote saved artifacts.
- The saved JSON summary and state/fold tables were read before this verdict.
- `2026+` data was avoided; run window was `2016-2025`.
- The live branch stayed frozen and long-only.
- No heavy job was active after completion.
