# Session 279 Log

**Date**: 2026-05-05
**Focus**: H398 `insider_pre_reaction_clock`

## Summary

- Activated the fifth S272/S273 eureka queue item.
- Added `analysis/h398_insider_pre_reaction_clock.py`.
- Reproduced the S272 positive-insider next-trading-day lead and compared
  T-1/T0/T+1 event-time states against same-ticker non-event dates.
- Crossed T+1 insider events with news activity, high buy-order count, C16
  support, and order-count reaction proxies.
- Verdict: **MIXED**. The insider T+1 lead survives strongly, but the
  pre-reaction thesis is wrong under the current news/order-count proxies.

## H398 - Insider Pre-Reaction Clock

**Hypothesis:**
S272 says next-trading-day positive insider events are real; the edge might be
strongest before news or order-count sensors visibly react.

**Command / code:**
```bash
python alpha-research-lab/analysis/h398_insider_pre_reaction_clock.py
```

**Inputs:**
- `data/features/xs_barrier_vol_1d_hose_full.parquet`
- `data/features/xs_order_pressure_daily.parquet`
- `data/order_stats/cafef/order_stats_daily.parquet`
- `data/features/news/datasets/news_daily_features.parquet`
- `data/insider_cache/*.parquet`

**Protocol:**
- No `2026+` rows.
- Test years `2015-2025`.
- Positive insider events use `RealBuyVolume - RealSellVolume > 0`.
- T+1 mapping follows S272: first trading day strictly after the publication
  date for trading-day disclosures, or the next available trading day for
  non-trading publication dates.
- Baseline is same-ticker non-event dates in ticker-years that had an insider
  event.
- Score is decision-time C16 order-pressure rank; target is the S1 future
  1d barrier-hit label used only as target.

**Saved artifact:**
`artifacts/run_summaries/20260505_173706_h398_insider_pre_reaction_clock_research_branch_insider_pre_reaction_clock.json`

| State | Avg IC | Lift / Control | Positive Years | Note |
|-------|--------|----------------|----------------|------|
| `insider_tplus1` | `+0.10498` | `+0.03000` vs same-ticker non-event | `11 / 11` | S272 lead reproduced |
| `insider_t0` | `+0.10816` | `+0.03317` vs same-ticker non-event | `11 / 11` | same-day event state also strong |
| `insider_tminus1` | `+0.08763` | `+0.01265` vs same-ticker non-event | `11 / 11` | positive but weaker |
| `insider_tplus1_pre_reaction` | `+0.09247` | `-0.01811` vs reacted | `11 / 11` | pre-reaction gate failed |
| `insider_tplus1_reacted` | `+0.11058` | `+0.01811` vs pre-reaction | `11 / 11` | news/order-count reaction confirms |
| `insider_tplus1_order_count_high` | `+0.13776` | `+0.04487` vs not-high | `11 / 11` | strongest IC conditioner |

**Result:**
The S272 insider T+1 event-state signal is real and durable. H398 reproduced
avg C16 IC `+0.10498`, `11 / 11` positive years, and IC lift `+0.03000`
versus same-ticker non-event dates. T0 is similarly strong.

The specific pre-reaction clock hypothesis failed. T+1 rows without active
news and without high buy-order count still have signal (`+0.09247` avg IC),
but reacted rows are stronger (`+0.11058`) and beat pre-reaction by
`+0.01811` avg IC. High buy-order-count T+1 insider rows are the strongest
rank-quality pocket (`+0.13776` avg IC), though the hit-rate lift is flat.

The C16-support subset should not be interpreted as a C16 ranker because
truncating the score inside high-C16 rows creates a negative within-subset IC;
its high hit-rate is a support-state diagnostic, not a rank-quality result.

**Verdict: MIXED**

**Next action:**
Continue to `crowd_count_ignition`, using H398's reaction-confirmation result:
high buy-order count should be tested as a structured conditioner, not as
generic retail swarm or quiet pre-reaction evidence.

## Closeout

- Saved artifact was read before the verdict.
- Branch status changed to mixed: insider lead reproduced, pre-reaction form
  parked.
- No live branch changed.
- Memory write-back done in live state, compact notes, findings, dead ends,
  and signal library.
- `2026+` data was avoided.
- No heavy job remains active.
