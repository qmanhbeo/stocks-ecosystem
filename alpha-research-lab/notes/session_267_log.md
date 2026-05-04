# Session 267 Log

Date: 2026-05-04
Focus: H389 post-Ollama event cascade

## Summary

- Ran `post_ollama_event_cascade` after the guarded Ollama event-family
  backfill and daily aggregate were complete.
- Implemented reusable script:
  `analysis/h389_post_ollama_event_cascade.py`.
- First run exposed non-finite future-return rows; patched the target loader to
  drop `inf`/`-inf` returns and reran. The second run is canonical.
- Tested fixed guarded-Ollama event states: first event after 20 quiet trading
  days, repeat event within 5 days, same-family repeat, family transition, and
  broad event-family pockets.
- Used `2016-2025` rows only. No `2026+` rows were used.

## Experiment Contract

Hypothesis:
- The guarded Ollama event-family residual can revive event timing if it
  changes the event representation relative to old CafeF event-v2.

Fixed states:
- `event_first20`: known event after at least 20 trading days without a prior
  known guarded-Ollama event for the ticker.
- `event_repeat5`: known event within 5 trading days of a prior known event.
- `event_same_family_repeat5`: repeat event with the same dominant event
  family.
- `event_family_transition5`: repeat event with a changed dominant event
  family.
- Family pockets: earnings/guidance, M&A or asset, capital raise/debt, and
  regulatory/legal.

Pass rule:
- PASS if `event_family_transition5`, `event_first20`, or `event_repeat5` has
  positive mean 5d payoff and beats generic event, relevant cascade control,
  and no-event rows by more than `+0.002` on average, with at least `60%`
  positive-lift years and positive 2025 lifts.
- MIXED if only an event-family pocket beats generic event rows.
- FAIL otherwise.

## Commands

```bash
/home/manh/miniforge3/envs/stocks/bin/python -m py_compile analysis/h389_post_ollama_event_cascade.py
/home/manh/miniforge3/envs/stocks/bin/python analysis/h389_post_ollama_event_cascade.py
```

Canonical saved artifacts:
- Summary:
  `artifacts/run_summaries/20260504_203158_h389_post_ollama_event_cascade_research_branch_post_ollama_event_cascade.json`
- Fold table:
  `artifacts/news_flow/20260504_203158_h389_post_ollama_event_cascade_folds.parquet`
- State table:
  `artifacts/news_flow/20260504_203158_h389_post_ollama_event_cascade_states.parquet`

Non-canonical first-run artifacts with non-finite target means:
- `artifacts/run_summaries/20260504_202950_h389_post_ollama_event_cascade_research_branch_post_ollama_event_cascade.json`
- `artifacts/news_flow/20260504_202950_h389_post_ollama_event_cascade_folds.parquet`
- `artifacts/news_flow/20260504_202950_h389_post_ollama_event_cascade_states.parquet`

## Key Metrics

Panel:
- Rows: `889,849`
- Dates: `2,500`
- Tickers: `398`
- Event-today share: `12.107%`

State summaries:

| State | WF years | Mean rows | Mean 5d rel payoff | 2025 5d payoff |
|---|---:|---:|---:|---:|
| `event_first20` | `8` | `1156.000` | `+0.002375` | `-0.002423` |
| `event_family_transition5` | `8` | `3927.875` | `+0.001618` | `-0.002199` |
| `event_any` | `8` | `11392.375` | `+0.001388` | `-0.003037` |
| `event_mna_asset` | `8` | `7426.250` | `+0.001346` | `-0.003134` |
| `no_event_today` | `8` | `81895.875` | `+0.001346` | `-0.004634` |
| `event_earnings_guidance` | `8` | `3059.000` | `+0.001312` | `-0.001275` |
| `event_repeat5` | `8` | `8015.000` | `+0.001232` | `-0.003175` |
| `event_same_family_repeat5` | `8` | `4087.125` | `+0.000856` | `-0.004272` |

Lift diagnostics:
- `event_first20` was the best cascade state, but its mean 5d lifts were only
  `+0.00099` versus generic event, `+0.00114` versus repeat event, and
  `+0.00103` versus no-event rows. These are below the `+0.002` gate; 2025
  lift versus event controls was also below `+0.001`.
- `event_family_transition5` had mean lifts `+0.00023` versus generic event,
  `+0.00076` versus same-family repeat, and `+0.00027` versus no-event rows.
- No broad event-family pocket beat generic event rows by enough to qualify as
  MIXED.
- Old reference: H321's best event-v2 cascade state had validation and
  confirmation 5d uplift versus control of `+0.00142` and `+0.00088`; H361's
  fixed sparse-clock portfolio follow-through failed. H389 does not improve
  enough on that evidence to reopen event timing.

## Verdict

H389 `FAILED`.

Interpretation:
- Guarded Ollama event-family states are broad and clean enough to inspect, but
  the first/repeat/transition representation does not revive event timing.
- `event_first20` is a small offline hint, not a new event representation.
- Keep event timing parked under the current target and consumer contracts.

Durable-promotion status:
- branch kill or reframe for post-Ollama event cascade
- no live branch change
- no shared matrix or recommendation-contract promotion

Next action:
- Continue the broader ranked queue at `calendar_as_liquidity_mechanism`.

## Verification

- `py_compile` passed after patching non-finite target handling.
- The canonical H389 script completed and wrote saved artifacts.
- The saved JSON summary, state table, and fold table were read before this
  verdict.
- `2026+` data was avoided; run window was `2016-2025`.
- The live branch stayed frozen and long-only.
- No heavy job was active after completion.
