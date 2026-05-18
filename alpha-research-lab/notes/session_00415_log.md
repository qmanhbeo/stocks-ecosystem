# Session 415 - H629 Remaining Numbered Queue Batch (85-91, 96-103)

**Date**: 2026-05-18

## Hypothesis

Resolve all remaining open numbered queue items with the smallest valid proxy
tests where exact legacy state contracts were unavailable.

Covered items:
- 85-91
- 96-103

## Command

```bash
python analysis/h629_remaining_queue_85_103_batch.py
```

## Inputs

- Cached base panel: `artifacts/cache/h62x_base_panel_2015_2025.parquet`
- Tradability: `data/features/execution/tradability_daily.parquet`
- Order stats: `data/order_stats/cafef/order_stats_daily.parquet`

## Saved artifacts

- Summary: `artifacts/run_summaries/20260518_212651_h629_remaining_queue_85_103_batch_research_branch.json`
- Decisions: `artifacts/research_branches/20260518_212651_h629_remaining_queue_85_103_batch_decisions.parquet`
- Results: `artifacts/research_branches/20260518_212651_h629_remaining_queue_85_103_batch_results.parquet`
- Yearly: `artifacts/research_branches/20260518_212651_h629_remaining_queue_85_103_batch_yearly.parquet`

## Results

| Item | Verdict | Key comparison | Lift |
|------|---------|----------------|------|
| 85 | PASSED | quiet_blocked vs quiet_liquid | +0.0743 |
| 86 | PASSED | low_breadth×vol_exp vs high_breadth×vol_contr | +0.0360 |
| 87 | FAILED | first_active_after_quiet vs sustained_active_2+ | -0.0354 |
| 88 | FAILED | tight_blocked vs tight_liquid | -0.0601 |
| 89 | FAILED | spread_concentration_q4 vs q1 (amihud proxy) | -0.0346 |
| 90 | PASSED | enter_tight_exit_expanding vs enter_tight_exit_tight | +0.0279 |
| 91 | DATA_GATED | deep vol-exp vs mild vol-exp | NaN (mild empty) |
| 96 | FAILED | cofire_zero vs cofire_few | -0.0725 |
| 97 | PASSED | tight+high_arrival vs tight_capacity | +0.0130 |
| 98 | FAILED | per-signal low-breadth mean vs high-breadth mean | -0.0081 |
| 99 | PASSED | triple_amp vs tight+low pair | +0.0833 |
| 100 | DATA_GATED | high_accum×low_breadth vs high_accum | NaN |
| 101 | PASSED | was_active_now_inactive vs never_active | +0.0630 |
| 102 | FAILED | persistent_low_breadth vs transient_low_breadth | -0.0110 |
| 103 | DATA_GATED | tight×high_accum vs tight×low_accum | NaN |

Batch totals:
- PASSED: 6
- FAILED: 6
- DATA_GATED: 3

## Result

All open numbered queue items are now addressed with explicit outcomes. Several
items pass under current proxy definitions (notably 85, 86, 90, 97, 99, 101),
while zero-cofire and breadth-persistence variants fail, and three items remain
data-gated by support/coverage.

## Verdict: BATCH_COMPLETED

## Next

- Write queue status back into `live_state.md` and compact notes.
- Continue with Bright-Mind backlog first-pass closure.
