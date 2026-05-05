# Session 293 Log

**Date**: 2026-05-05
**Focus**: H412 `volume_c16_additive`

## Summary

- Activated Bright-Mind B29 idea (Volume + C16 additive).
- Added `analysis/h412_volume_c16_additive.py`.
- Tested Volume + C16 additive combinations vs forward IC.
- Verdict: **FAILED**. Additive doesn't beat Volume alone.

## H412 - Volume + C16 Additive

**Hypothesis:**
Volume additive with C16 (following H410 pattern) beats standalone Volume.

**Command / code:**
```bash
python alpha-research-lab/analysis/h412_volume_c16_additive.py
```

**Inputs:**
- `data/features/xs_barrier_vol_1d_hose_full.parquet` (S1 target)
- `data/features/xs_order_pressure_daily.parquet` (Volume, C16)

**Protocol:**
- Test years `2018-2025`
- Various additive weightings

| State | Forward IC | Positive Years |
|-------|-----------|----------------|
| Volume alone | +0.07492 | 8/8 |
| C16 alone | -0.00079 | 4/8 |
| 0.75V+0.25C16 | +0.07266 | - |
| 0.25V+0.75C16 | +0.05909 | 8/8 |

**Saved artifact:**
`artifacts/run_summaries/volume_c16_additive_research_branch.json`

**Verdict: FAILED**

- Additive cannot rescue C16 - C16 is too weak (essentially zero IC)
- H410 additive works only with S1 (+0.118 strong)
- C16 (+0.075) is weaker than S1 - not enough signal to add

**Next**: Test H413 (Triple Signal Additive: Vol+S1+C16) or stop additive experiments.

Source anchor: F376