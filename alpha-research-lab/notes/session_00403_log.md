# Session 403 - H617 Breadth-Scale Signal Strength Regression

**Date**: 2026-05-18

## Hypothesis

Queue item 120: breadth effect on `composite_2plus` may be continuous, not just
binary low-breadth gating.

## Command

```bash
python analysis/h617_breadth_scale_signal_strength.py
```

## Inputs

- S1 panel: `data/features/xs_barrier_vol_1d_hose_full.parquet`
- Order stats: `data/order_stats/cafef/order_stats_daily.parquet`
- OHLCV: `data/stock/gia_lich_su_*_1D.parquet`

## Saved artifacts

- Summary: `artifacts/run_summaries/20260518_180725_h617_breadth_scale_signal_strength_research_branch.json`
- Results: `artifacts/research_branches/20260518_180725_h617_breadth_scale_signal_strength_results.parquet`
- Yearly: `artifacts/research_branches/20260518_180725_h617_breadth_scale_signal_strength_yearly.parquet`
- Continuous score results: `artifacts/research_branches/20260518_180725_h617_breadth_scale_signal_strength_continuous_results.parquet`

## Results

Binary/quintile states:
- `composite_2plus_low_breadth IC=0.2694`
- Quintiles (Q1->Q5): `0.2694, 0.2608, 0.2261, 0.2336, 0.2230`

Continuous scaling:
- `composite_2plus` with `score * (1 - breadth_pct_rank)`:
  `IC=0.0878`

## Result

- Continuous breadth scaling is strongly harmful vs binary gate:
  - lift(`continuous` vs binary) = `-0.1816`
- Quintile profile shows a directional decay tendency from low to high breadth,
  but non-monotonic in middle quintiles.

## Verdict: MIXED

## Next

- Advance to queue item 122 (Signal-Day Distribution as Hidden Regime).
