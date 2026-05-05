# Session 290 Log

**Date**: 2026-05-05
**Focus**: H409 `volume_c16_cross_product`

## Summary

- Activated Bright-Mind B17 idea (Volume × C16 cross-product).
- Added `analysis/h409_volume_c16_cross_product.py`.
- Tested Volume × C16_lag1 cross-product vs forward IC.
- Verdict: **MIXED**. Cross adds +0.017 (8/8 pos years) but WORSE than Volume alone (+0.077).

## CRITICAL FINDING: Volume Alone is +0.077 IC!

The key finding is that Volume alone (order_volume_ratio) has **+0.077 IC with 8/8 positive years** - this is a NEW signal discovery!

## H409 - Volume × C16 Cross-Product

**Hypothesis:**
Volume × C16 cross-product predicts better than standalone Volume.

**Command / code:**
```bash
python alpha-research-lab/analysis/h409_volume_c16_cross_product.py
```

**Inputs:**
- `data/features/xs_barrier_vol_1d_hose_full.parquet` (S1 target)
- `data/features/xs_order_pressure_daily.parquet` (Volume, C16)

**Protocol:**
- No `2026+` rows, test years `2018-2025`
- Compare Volume alone vs C16 alone vs Vol×C16 cross-product

| State | Forward IC | Positive Years |
|-------|-----------|----------------|
| Volume alone | **+0.07762** | **8/8** |
| C16 alone | -0.04570 | 0/8 |
| **Vol×C16 cross** | +0.01651 | 8/8 |

**Saved artifact:**
`artifacts/run_summaries/volume_c16_cross_product_research_branch.json`

**Verdict: MIXED**

- Cross-product is positive but WORSE than Volume alone (0.017 vs 0.077).
- NOT a signal-library promotion.
- CRITICAL: Volume alone (order_volume_ratio) is a NEW strong signal with +0.077 IC, 8/8 positive years!

**Next**: Test Insider × C16 (B15) or add Volume to signal library (this is the real finding).

Source anchor: F373