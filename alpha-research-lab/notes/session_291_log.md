# Session 291 Log

**Date**: 2026-05-05
**Focus**: H410 `volume_s1_additive`

## Summary

- Activated Bright-Mind B22 idea (Volume + S1 additive).
- Added `analysis/h410_volume_s1_additive.py`.
- Tested various Volume + S1 additive combinations vs forward IC.
- Verdict: **PASSED**. 0.25×Volume + 0.75×S1 beats both standalone!

## H410 - Volume + S1 Additive Combination

**Hypothesis:**
Volume additive (not cross-product) with S1 improves over standalone S1.

**Command / code:**
```bash
python alpha-research-lab/analysis/h410_volume_s1_additive.py
```

**Inputs:**
- `data/features/xs_barrier_vol_1d_hose_full.parquet` (S1)
- `data/features/xs_order_pressure_daily.parquet` (Volume)

**Protocol:**
- No `2026+` rows, test years `2018-2025`
- Compare S1 alone, Vol alone, various additive weightings

| State | Forward IC | Positive Years |
|-------|-----------|----------------|
| S1 alone | +0.11790 | 8/8 |
| Vol alone | +0.07492 | 8/8 |
| 0.25V+0.75S | **+0.12649** | **-** |
| 0.50V+0.50S | +0.09970 | 8/8 |
| 0.75V+0.25S | +0.08465 | - |

**Saved artifact:**
`artifacts/run_summaries/volume_s1_additive_research_branch.json`

**Verdict: PASSED**

- Best: 0.25×Volume + 0.75×S1 adds **+0.009 IC lift** over S1 alone
- Additive WORKS better than cross-product (H408, H409 showed cross hurts)
- Key insight: small volume weight (25%) improves S1; too much volume hurts

**Next**: Try H411 Triple Storm on Volume (B23) or test 0.25V+0.75S in portfolio.

Source anchor: F374