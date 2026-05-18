# Session 399 - H613 Cross-Sectional Dispersion as Regime

**Date**: 2026-05-18

## Hypothesis

Queue item 116: lower cross-sectional S1 score dispersion (date-level) may
indicate stronger agreement and improve `composite_2plus` quality.

## Command

```bash
python analysis/h613_cross_sectional_dispersion_regime.py
```

## Inputs

- S1 panel: `data/features/xs_barrier_vol_1d_hose_full.parquet`
- Order stats: `data/order_stats/cafef/order_stats_daily.parquet`
- OHLCV: `data/stock/gia_lich_su_*_1D.parquet`

## Saved artifacts

- Summary: `artifacts/run_summaries/20260518_163631_h613_cross_sectional_dispersion_regime_research_branch.json`
- Results: `artifacts/research_branches/20260518_163631_h613_cross_sectional_dispersion_regime_results.parquet`
- Yearly: `artifacts/research_branches/20260518_163631_h613_cross_sectional_dispersion_regime_yearly.parquet`

## Results

| State | IC | Rows | Positive Years |
|-------|-----|------|----------------|
| composite_2plus_low_disp | 0.2539 | 5,709 | 5/5 |
| composite_2plus | 0.2445 | 29,542 | 11/11 |
| composite_2plus_high_disp | 0.2372 | 5,419 | 7/7 |

Derived lifts:
- low vs high: `+0.0167`
- low vs composite baseline: `+0.0094`

## Result

Direction is favorable (low-dispersion > high-dispersion), but support is not
robust:

- low-dispersion has only 5 yearly points
- high-dispersion has sparse out-of-sample support (confirmation rows 29)

## Verdict: MIXED

## Next

- Advance to queue item 117 (Persistence Decay Boundary).
