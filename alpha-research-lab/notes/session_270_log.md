# S270 Session Log

**Date**: 2026-05-04
**Focus**: H392 source-triangle sparse audit

## Summary

- Ran `source_triangle_sparse` as H392.
- Implemented reusable script:
  `analysis/h392_source_triangle_sparse.py`.
- Tested whether agreement among high C16, positive prior insider signal, and
  local-news source/type heads forms a sparse high-conviction state beyond
  two-way controls.
- Used `2016-2025` rows only. No `2026+` rows were used.

## Experiment Contract

Sensors:
- `c16_high`: `order_volume_ratio_rank >= 0.80` from the published C16 surface.
- `insider_buy`: positive `c5_ins_relative_size_5d` with C5 signal present.
- `source_news`: official/regulatory source-type or stock-scope PhoBERT news
  probability at least `0.50`.
- `forward_text`: forward-looking PhoBERT probability at least `0.50`.

Primary states:
- `c16_insider_any_news`: high C16 plus positive insider plus either
  source-news or forward-looking text.
- `c16_insider_source`: high C16 plus positive insider plus source-news.

Controls:
- `c16_insider_no_news`
- `c16_any_news_no_insider`
- `insider_any_news_no_c16`
- `exactly_two_sensors`

Pass rule:
- PASS if a primary state has positive mean 5d relative payoff and beats all
  controls by more than `+0.002` on average, with at least `60%` positive-lift
  years and positive 2025 lifts.
- MIXED if only a broader three-sensor or news-triangle pocket is positive.
- FAIL otherwise.

## Commands

```bash
python -m py_compile alpha-research-lab/analysis/h392_source_triangle_sparse.py
python alpha-research-lab/analysis/h392_source_triangle_sparse.py
```

Saved artifacts:
- Summary:
  `artifacts/run_summaries/20260504_205532_h392_source_triangle_sparse_research_branch_source_triangle_sparse.json`
- Fold table:
  `artifacts/news_flow/20260504_205532_h392_source_triangle_sparse_folds.parquet`
- State table:
  `artifacts/news_flow/20260504_205532_h392_source_triangle_sparse_states.parquet`

## Key Metrics

Panel:
- Rows: `769,977`
- Dates: `2,500`
- Tickers: `398`
- Sensor shares: C16 `18.21%`, insider `1.31%`, source-news `8.88%`,
  forward-text `5.38%`, two-plus `4.77%`, three-plus `0.58%`.

Primary states:

| State | WF years | Mean rows | Mean 1d rel | Mean 5d rel | 5d hit rate | Mean C16 IC 1d | Mean C16 IC 5d | 2025 5d rel |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `c16_insider_any_news` | `8` | `35.625` | `+0.005611` | `+0.003177` | `0.4760` | `-0.10006` | `-0.02621` | `-0.005394` |
| `c16_insider_source` | `8` | `31.625` | `+0.005139` | `+0.004065` | `0.4858` | `-0.12440` | `-0.00988` | `-0.000207` |

Primary lift diagnostics:
- `c16_insider_any_news` versus `c16_insider_no_news`: mean 5d lift
  `-0.007315`, `1 / 8` positive years, 2025 lift `-0.007749`.
- `c16_insider_any_news` versus `c16_any_news_no_insider`: mean 5d lift
  `-0.005205`, `2 / 8` positive years, 2025 lift `-0.008313`.
- `c16_insider_any_news` versus `insider_any_news_no_c16`: mean 5d lift
  `+0.002099`, `4 / 8` positive years, 2025 lift `+0.001072`.
- `c16_insider_any_news` versus `exactly_two_sensors`: mean 5d lift
  `+0.000271`, `4 / 8` positive years, 2025 lift `-0.003072`.
- `c16_insider_source` had the same failure shape: it beat
  `insider_any_news_no_c16` and barely beat `exactly_two_sensors`, but lost to
  `c16_insider_no_news` and `c16_any_news_no_insider`.

Broader mixed clue:
- `three_plus_sensors` had mean 5d payoff `+0.008062`, 5d hit rate `0.5091`,
  and mean 5d lift `+0.005156` versus `exactly_two_sensors`, with `8 / 8`
  positive lift years. 2025 lift was only `+0.001170`, below the `+0.002` gate.
- `c16_source_forward` was the strongest broad news triangle: mean 5d payoff
  `+0.008828`, but 2025 payoff was slightly negative (`-0.001165`).

## Verdict

H392 `MIXED`.

Interpretation:
- Adding news to the C16+insider core did not improve the core. The stronger
  control was actually `c16_insider_no_news`, with mean 5d payoff `+0.010492`.
- The broad three-sensor pocket is real as offline context, mostly from C16
  plus source and forward-looking news, but it does not satisfy the
  insider+C16 source-triangle thesis.
- Do not promote a C16+insider+news triangle overlay or matrix column under the
  current representation.

Durable-promotion status:
- park or narrow source-triangle sparse
- no live branch change
- no shared matrix or recommendation-contract promotion

Reopening condition:
- Reopen only with a narrower predeclared non-insider news triangle, such as
  `c16_source_forward`, or with a different insider-quality representation.

Next action:
- The explicit queue is exhausted. Continue by creating the next branch from
  the hidden-flow memo; the highest-value next candidate is
  `nihilist_reversal`.

## Verification

- `py_compile` passed.
- The script completed and wrote saved artifacts.
- The saved JSON summary, fold table, and state table were read before this
  verdict.
- `2026+` data was avoided; run window was `2016-2025`.
- The live branch stayed frozen and long-only.
- No heavy job was active after completion.
