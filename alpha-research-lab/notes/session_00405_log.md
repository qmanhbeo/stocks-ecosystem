# Session 405 - H619 Post-Breadth-Spike Recovery Timing

**Date**: 2026-05-18

## Hypothesis

Queue item 123: post-spike low-breadth recovery windows may amplify
`composite_2plus` beyond the base low-breadth combo.

## Command

```bash
python analysis/h619_post_breadth_spike_recovery_timing.py
```

## Inputs

- S1 panel: `data/features/xs_barrier_vol_1d_hose_full.parquet`
- Order stats: `data/order_stats/cafef/order_stats_daily.parquet`
- OHLCV: `data/stock/gia_lich_su_*_1D.parquet`

## Saved artifacts

- Summary: `artifacts/run_summaries/20260518_181213_h619_post_breadth_spike_recovery_timing_research_branch.json`
- Results: `artifacts/research_branches/20260518_181213_h619_post_breadth_spike_recovery_timing_results.parquet`
- Yearly: `artifacts/research_branches/20260518_181213_h619_post_breadth_spike_recovery_timing_yearly.parquet`

## Results

| State | IC | Rows | Positive Years |
|-------|-----|------|----------------|
| composite_2plus_low_breadth | 0.2694 | 5,038 | 11/11 |
| composite_2plus_low_breadth_post_spike | 0.2581 | 2,392 | 8/8 |

Derived:
- lift(`post_spike` vs low_breadth baseline) = `-0.0113`

## Result

Post-spike recovery timing degrades the low-breadth multi-signal baseline.

## Verdict: FAILED

## Next

- Advance to queue item 124 (Implementation Pain × Multi-Signal Triple).
