# Session 407 - H621 Cross-Signal Breadth Threshold Discovery

**Date**: 2026-05-18

## Hypothesis

Queue item 125: each signal family (C23/C24/C25/C26) may have a different
optimal breadth gate (`<10%`, `<20%`, `<30%`) instead of one market-wide rule.

## Command

```bash
python analysis/h621_cross_signal_breadth_threshold_discovery.py
```

## Inputs

- S1 panel: `data/features/xs_barrier_vol_1d_hose_full.parquet`
- Order stats: `data/order_stats/cafef/order_stats_daily.parquet`
- OHLCV: `data/stock/gia_lich_su_*_1D.parquet`

## Saved artifacts

- Summary: `artifacts/run_summaries/20260518_182525_h621_cross_signal_breadth_threshold_discovery_research_branch.json`
- Results: `artifacts/research_branches/20260518_182525_h621_cross_signal_breadth_threshold_discovery_results.parquet`
- Yearly: `artifacts/research_branches/20260518_182525_h621_cross_signal_breadth_threshold_discovery_yearly.parquet`
- Optimal thresholds: `artifacts/research_branches/20260518_182525_h621_cross_signal_breadth_threshold_discovery_optimal_thresholds.parquet`

## Results

| State | IC | Rows | Positive Years |
|-------|-----|------|----------------|
| c23_low_20 | 0.2673 | 5,336 | 11/11 |
| c24_low_20 | 0.2072 | 5,784 | 11/11 |
| c25_low_30 | 0.1320 | 16,872 | 11/11 |
| c26_low_20 | 0.2373 | 1,559 | 5/5 |
| composite_2plus | 0.2456 | 29,542 | 11/11 |

Derived:
- unique optimal thresholds across signals = `2`
- mean lift of best-threshold vs `20%` baseline = `+0.0061`

## Result

Signal-specific threshold differences exist (notably `C25` preferring `<30%`),
but mean incremental lift over the common `<20%` baseline is below promotion
threshold.

## Verdict: MIXED

## Next

- Advance to queue item 126 (Signal Magnitude as Hidden State).
