# Session 400 - H614 Persistence Decay Boundary

**Date**: 2026-05-18

## Hypothesis

Queue item 117: persistence has a decay boundary; very long accumulation may be
weaker than the `20-30` accumulation window for `composite_2plus`.

## Command

```bash
python analysis/h614_persistence_decay_boundary.py
```

## Inputs

- S1 panel: `data/features/xs_barrier_vol_1d_hose_full.parquet`
- Order stats: `data/order_stats/cafef/order_stats_daily.parquet`
- Order pressure: `data/features/xs_order_pressure_daily.parquet`
- OHLCV: `data/stock/gia_lich_su_*_1D.parquet`

## Saved artifacts

- Summary: `artifacts/run_summaries/20260518_163916_h614_persistence_decay_boundary_research_branch.json`
- Results: `artifacts/research_branches/20260518_163916_h614_persistence_decay_boundary_results.parquet`
- Yearly: `artifacts/research_branches/20260518_163916_h614_persistence_decay_boundary_yearly.parquet`

## Results

| State | IC | Rows | Positive Years |
|-------|-----|------|----------------|
| composite_2plus_accum_20_30 | 0.2542 | 8,969 | 11/11 |
| composite_2plus_accum_31plus | 0.2407 | 4,934 | 11/11 |
| composite_2plus | 0.2445 | 29,542 | 11/11 |
| composite_2plus_accum_0_7 | 0.2252 | 3,149 | 11/11 |

## Result

Bounded persistence effect confirmed:

- lift(`20-30` vs `31+`) = `+0.0135`
- very long accumulation remains positive, but weaker than the `20-30` pocket

## Verdict: PASSED

## Next

- Advance to queue item 118 (Signal Concentration × Breadth Interaction).
