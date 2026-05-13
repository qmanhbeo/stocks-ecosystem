# Session 280 Log

**Date**: 2026-05-05
**Focus**: H399 `crowd_count_ignition`

## Summary

- Activated the sixth S272/S273 eureka queue item.
- Added `analysis/h399_crowd_count_ignition.py`.
- Tested fixed high-buy-order-count intersections with average buy size,
  buy-volume pressure, C8 volume-z, and H394 predicted weather.
- Verdict: **MIXED**. High buy count is a modest C16 conditioner, but not a
  standalone signal; high volume-z explains the cleanest pocket, and the best
  size/weather crowd state is promising but not stable enough for promotion.

## H399 - Crowd Count Ignition

**Hypothesis:**
High buy-order count is modest alone because it mixes retail swarm and real
breadth; it may matter only with favorable predicted barrier weather or
supportive average-order-size structure.

**Command / code:**
```bash
python alpha-research-lab/analysis/h399_crowd_count_ignition.py
```

**Inputs:**
- `data/features/xs_barrier_vol_1d_hose_full.parquet`
- `data/features/xs_order_pressure_daily.parquet`
- `data/order_stats/cafef/order_stats_daily.parquet`
- `data/features/xs_rl_signal_matrix.parquet`
- `artifacts/h394_oracle_shadow_regime_distiller/20260505_170942_h394_oracle_shadow_regime_distiller_date_predictions.parquet`

**Protocol:**
- No `2026+` rows.
- Test years `2018-2025`, matching the H394 prediction artifact.
- Fixed states only: high buy count crossed with high/low average buy size,
  high buy-volume pressure, high C8 volume-z, and H394 low/high predicted
  weather.
- Primary gate judged C16 rank quality inside the state versus
  `high_buy_count` alone, not absolute IC versus random.
- Standalone score diagnostics were recorded for C16, buy-count rank,
  buy-volume-pressure rank, average-buy-size rank, and C8 volume-z.

**Saved artifact:**
`artifacts/run_summaries/20260505_174329_h399_crowd_count_ignition_research_branch_crowd_count_ignition.json`

| State / Score | Avg IC | Lift / Control | Positive Years | Note |
|---------------|--------|----------------|----------------|------|
| C16 all rows | `+0.07519` | baseline | `8 / 8` | raw C16 |
| `buy_count_rank` score | `-0.01075` | standalone diagnostic | `3 / 8` | anti-predictive as a rank |
| `high_buy_count` state | `+0.08463` | `+0.00944` vs all rows | `8 / 8` | modest conditioner |
| `volume_z_high80` state | `+0.10258` | `+0.02739` vs all rows | `8 / 8` | clean C8 volume-state pocket |
| `high_count_volume_z_high80` | `+0.10285` | `+0.01822` vs high count | `8 / 8` | no real lift over volume-z alone |
| `count_high_size_weather_low20` | `+0.10083` | `+0.01620` vs high count | `5 / 8` lift years | best primary crowd state |
| `count_weather_low20` | `+0.09062` | `+0.00599` vs high count | `6 / 8` lift years | weak weather context |
| `count_high_buy_pressure` | `+0.07732` | `-0.00731` vs high count | `3 / 8` lift years | buy-pressure raises hit rate, not rank IC |

**Result:**
The high-buy-count state is real only as a modest C16 conditioner:
`high_buy_count` avg IC `+0.08463` versus all-row C16 `+0.07519`, with
`+0.00944` average yearly lift and `6 / 8` positive lift years. But
`buy_count_rank` itself is anti-predictive (`-0.01075`, `3 / 8` positive
years), so buy count should not be promoted as a standalone rank signal.

The cleanest high-count-adjacent pocket is not actually count-specific:
`volume_z_high80` reached avg IC `+0.10258` with `8 / 8` positive years, and
`high_count_volume_z_high80` was only marginally higher (`+0.10285`). Treat
that as C8/volume-state evidence, not a new crowd-count primitive.

The best primary crowd state, `count_high_size_weather_low20`, cleared the
MIXED threshold with avg IC `+0.10083` and `+0.01620` average yearly lift
versus high count, but only `5 / 8` lift years. H394 low predicted weather is
the helpful direction; H394 high predicted weather degraded the count state.

Buy-volume-pressure intersections increased hit rates but degraded C16 rank
quality. This likely means pressure states select a high-hit-rate basket while
compressing within-state rank dispersion.

**Verdict: MIXED**

**Next action:**
Continue to `calendar_as_weak_prior_not_clock`. Carry forward H399 only as
context: use high buy count as a modest conditioner, high volume-z as the
cleaner volume state, and the high-size/H394-low-weather interaction as a
promising but unpromoted branch clue.

## Closeout

- Saved artifact was read before the verdict.
- Branch status changed to mixed/context only.
- No live branch changed.
- Memory write-back done in live state, compact notes, findings, dead ends,
  and signal library.
- `2026+` data was avoided.
- No heavy job remains active.
