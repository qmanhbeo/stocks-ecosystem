# Session 389 - H121 Tight Capacity × Multi-Signal Amplifier

**Date:** 2026-05-17

## Hypothesis

Tight Capacity × Multi-Signal:
- F437 found tight+low_breadth = 0.2062
- F447 found composite_2+ × low_breadth = 0.2651
- Test triple: tight + composite_2+ + low_breadth vs F447 baseline (0.2651)

## Command

```bash
python analysis/h121_tight_capacity_multi_signal.py
```

## Inputs

- S1 panel: xs_barrier_vol_1d_hose_full.parquet (2015-2025)
- Order stats: order_stats_daily.parquet
- OHLCV for Amihud calculation

## Saved Artifacts

- Results: `artifacts/research_branches/20260517_175521_h121_tight_capacity_multi_signal_results.parquet`
- Yearly: `artifacts/research_branches/20260517_175521_h121_tight_capacity_multi_signal_yearly.parquet`
- Summary: `artifacts/run_summaries/20260517_175521_h121_tight_capacity_multi_signal_research_branch.json`

## Results

| State | IC | Rows | Positive Years |
|-------|-----|------|-----------------|
| triple_tight_composite_low | 0.2702 | 3,604 | 9/11 |
| composite_2plus_low_breadth (F447) | 0.2651 | 4,811 | 10/11 |
| composite_2plus | 0.2445 | 29,542 | 11/11 |
| tight_low_breadth (F437) | 0.1905 | 32,126 | 11/11 |
| tight_capacity | 0.1900 | 160,573 | 11/11 |
| all_rows | 0.1298 | 809,019 | 11/11 |

**Lift vs F447:** +0.0051 (below +0.01 threshold)

## Verdict: MIXED

The triple (tight + composite_2+ + low_breadth = 0.2702) provides marginal improvement over F447 (0.2651), but the lift (+0.0051) is below the +0.01 promotion threshold. Adding tight_capacity to composite_2+ × low_breadth does not add significant incremental value.

Key observations:
- tight_capacity alone (0.190) is much weaker than composite_2+ × low_breadth (0.265)
- The triple intersection is sparse (3,604 rows vs 4,811 for F447)
- F447 (composite_2+ × low_breadth) already captures most of the signal value
- Adding tight_capacity provides only +0.005 lift, not enough for promotion

**Conclusion:** F447 remains the stronger signal combination. The triple does not merit promotion but provides useful negative evidence about incremental value of tight_capacity on top of multi-signal + breadth.