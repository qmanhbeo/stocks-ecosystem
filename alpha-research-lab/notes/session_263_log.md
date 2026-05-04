# Session 263 Log

Date: 2026-05-04
Focus: H385 official attention delay

## Summary

- Ran `official_attention_delay` as the next ranked local-news branch.
- Implemented reusable script:
  `analysis/h385_official_attention_delay.py`.
- Tested fixed official/regulatory and forward-looking local-news states with
  support from high C16 or positive insider conviction.
- Used close-to-close 1d and 5d excess returns versus VNINDEX, not a
  candidate-pool allocation policy.
- Used `2016-2025` rows only. No `2026+` rows were used.

## Experiment Contract

Hypothesis:
- Official/regulatory or forward-looking own-ticker articles need flow or
  insider support and may pay after a delay, rather than on the headline day.

Fixed support:
- C16 support: `order_volume_ratio_rank >= 0.80`
- Insider support: positive `c5_signal_present` and positive
  `c5_ins_relative_size_5d`
- Supported state: official/forward local-news row plus either support source.

Controls:
- Unsupported official/forward rows with the same broad local-news source or
  forward-looking state, but without C16 or insider support.
- Secondary support-only substates split C16 and insider support.

Pass rule:
- PASS if `official_supported` or `official_forward_supported` has 5d payoff
  lift above `+0.002` versus its unsupported baseline, at least `60%` positive
  5d-lift years, positive 2025 5d lift, enough rows, and 5d lift at least as
  large as 1d lift.
- MIXED if only narrower support substates clear.
- FAIL otherwise.

## Commands

```bash
/home/manh/miniforge3/envs/stocks/bin/python -m py_compile analysis/h385_official_attention_delay.py
/home/manh/miniforge3/envs/stocks/bin/python analysis/h385_official_attention_delay.py
```

## Saved Artifacts

- Summary:
  `artifacts/run_summaries/20260504_200524_h385_official_attention_delay_research_branch_official_attention_delay.json`
- Fold table:
  `artifacts/news_flow/20260504_200524_h385_official_attention_delay_folds.parquet`
- State table:
  `artifacts/news_flow/20260504_200524_h385_official_attention_delay_states.parquet`

## Key Metrics

Panel:
- Rows: `756,382`
- Dates: `2,500`
- Tickers: `394`
- Official/regulatory share: `4.999%`
- Forward-looking share: `5.366%`
- Support share: `19.320%`

Primary pass states:

| State | Mean rows | Mean 1d payoff | Mean 5d payoff | 1d lift | 5d lift | Positive 5d-lift years | 2025 5d lift | Mean C16 IC 5d |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `official_supported` | `734.625` | `+0.005059` | `+0.006671` | `+0.005358` | `+0.007408` | `8 / 8` | `+0.005566` | `+0.05245` |
| `official_forward_supported` | `1191.500` | `+0.004914` | `+0.007290` | `+0.005242` | `+0.007657` | `8 / 8` | `+0.006799` | `+0.04607` |

Secondary states:
- `official_c16`: 5d lift `+0.008112`, `8 / 8` positive 5d-lift years,
  2025 5d lift `+0.006269`.
- `forward_supported`: passed as a secondary state.
- `forward_c16`: 5d lift `+0.007984`, `8 / 8` positive 5d-lift years, 2025
  5d lift `+0.005486`.

Unsupported baselines were weak or negative:
- `official_no_support`: mean 1d `-0.000299`, mean 5d `-0.000737`, 2025 5d
  `-0.005205`.
- `official_forward_no_support`: mean 1d `-0.000328`, mean 5d `-0.000367`,
  2025 5d `-0.004933`.

## Verdict

H385 `PASSED`.

Interpretation:
- Official/regulatory and forward-looking local-news states become useful when
  confirmed by high C16 or positive insider conviction.
- The effect is delay-shaped: the 5d payoff lift is larger than the 1d lift for
  both primary pass states.
- The branch supports an official-attention-delay mechanism, but it is not yet
  a candidate-pool allocator or live portfolio rule.
- Within-state C16 IC is positive on average but mixed by year, so the durable
  state is support-confirmed official/forward attention, not necessarily
  ranking by C16 inside the state.

Durable-promotion status:
- offline evidence
- no live branch change
- no shared matrix or recommendation-contract promotion

Next action:
- Run one fixed consumer audit for the H385 states before any allocation use:
  `official_supported` and `official_forward_supported` inside the buyable
  candidate panel, with random same-support and random-all benchmarks.

## Verification

- `py_compile` passed for the new script.
- The H385 script completed and wrote saved artifacts.
- The saved JSON summary, state table, and fold table were read before this
  verdict.
- `2026+` data was avoided; run window was `2016-2025`.
- The live branch stayed frozen and long-only.
- No heavy job was active after completion.
