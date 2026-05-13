# Session 289 Log

**Date**: 2026-05-05
**Focus**: H408 `s1_c16_cross_product`

## Summary

- Activated Bright-Mind B21 idea (S1×C16 cross-product).
- Added `analysis/h408_s1_c16_cross_product.py`.
- Tested S1 × C16_lag1 cross-product vs forward IC.
- Verdict: **MIXED**. Cross adds +0.108 (8/8 pos years) but WORSE than S1 alone (+0.118).

## H408 - S1 × C16 Cross-Product

**Hypothesis:**
S1 score × C16 cross-product predicts better than standalone S1.

**Command / code:**
```bash
python alpha-research-lab/analysis/h408_s1_c16_cross_product.py
```

**Inputs:**
- `data/features/xs_barrier_vol_1d_hose_full.parquet` (S1)
- `data/features/xs_order_pressure_daily.parquet` (C16)

**Protocol:**
- No `2026+` rows, test years `2018-2025`
- Compare S1 alone vs C16 alone vs S1×C16 cross-product

| State | Forward IC | Positive Years |
|-------|-----------|----------------|
| S1 alone | **+0.11838** | **8/8** |
| C16 alone | -0.02966 | 0/8 |
| **S1×C16 cross** | +0.10821 | 8/8 |

**Saved artifact:**
`artifacts/run_summaries/s1_c16_cross_product_research_branch.json`

**Verdict: MIXED**

Cross-product is positive (+0.108) but WORSE than S1 alone (+0.118). The cross subtracts ~0.010 IC from S1.
- NOT a signal-library promotion (doesn't beat S1)
- C16 acts as a filter but doesn't add alpha

**Next**: Try B15 (Insider × C16) or B17 (Volume × C16) from B-queue.

Source anchor: F372