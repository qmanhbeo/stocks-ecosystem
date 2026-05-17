# Session 392 - H606 Breadth-Adjusted Multi-Signal

**Date**: 2026-05-17

## Hypothesis

Continuous inverse-breadth weighting may work on the stronger multi-signal
subset (`composite_2plus`), even though H530 failed on raw S1.

Test:
- binary gate: `composite_2plus_low_breadth`
- continuous weight: `weighted_score = s1_xs_proba * inv_breadth_weight` on `composite_2plus`

## Command

```bash
python analysis/h606_breadth_adjusted_multi_signal.py
```

## Inputs

- S1 panel: `data/features/xs_barrier_vol_1d_hose_full.parquet`
- Order stats: `data/order_stats/cafef/order_stats_daily.parquet`
- OHLCV: `data/stock/gia_lich_su_*_1D.parquet`

## Saved artifacts

- Summary: `artifacts/run_summaries/20260517_192638_h606_breadth_adjusted_multi_signal_research_branch.json`
- Results: `artifacts/research_branches/20260517_192638_h606_breadth_adjusted_multi_signal_results.parquet`

## Results

| State | IC | Rows | Positive Years |
|-------|-----|------|----------------|
| composite_2plus_low_breadth (binary gate) | 0.2823 | 4,811 | 10/10 |
| composite_2plus | 0.2456 | 29,542 | 11/11 |
| composite_2plus_weighted_inv_breadth | 0.1615 | 29,542 | 11/11 |

## Result

Binary low-breadth gating remains decisively better than continuous weighting
on the multi-signal subset.

- Binary vs base composite: `+0.0367`
- Weighted vs binary: `-0.1208`

## Verdict: FAILED

## Next

- Advance to H109 or H110 branch from queue.
