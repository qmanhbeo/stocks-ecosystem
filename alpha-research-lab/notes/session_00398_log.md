# Session 398 - H612 Market Regime Position Multiplier

**Date**: 2026-05-18

## Hypothesis

Queue item 115: apply breadth regime as exposure multiplier instead of binary
filter:

- low breadth: `1.5x`
- high breadth: `0.5x`
- middle: `1.0x`

## Command

```bash
python analysis/h612_market_regime_position_multiplier.py
```

## Inputs

- S1 panel: `data/features/xs_barrier_vol_1d_hose_full.parquet`
- Order stats: `data/order_stats/cafef/order_stats_daily.parquet`
- OHLCV: `data/stock/gia_lich_su_*_1D.parquet`

## Saved artifacts

- Summary: `artifacts/run_summaries/20260518_163315_h612_market_regime_position_multiplier_research_branch.json`
- Results: `artifacts/research_branches/20260518_163315_h612_market_regime_position_multiplier_results.parquet`
- Yearly: `artifacts/research_branches/20260518_163315_h612_market_regime_position_multiplier_yearly.parquet`

## Results

| Variant | IC | Rows |
|---------|-----|------|
| baseline_score | 0.1298 | 809,019 |
| breadth_scaled_score | 0.0769 | 809,019 |

## Result

Breadth-based global score scaling is strongly harmful:

- lift(`breadth_scaled` vs baseline) = `-0.0529`

## Verdict: FAILED

## Next

- Advance to queue item 116 (Cross-Sectional Dispersion as Regime).
