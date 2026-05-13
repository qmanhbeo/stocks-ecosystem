# Session 296 Log

**Date**: 2026-05-05
**Focus**: H415 `weight_optimization`

## Summary

- Activated Bright-Mind B45 idea (Weight Optimization).
- Added `analysis/h415_weight_optimization.py`.
- Grid search Vol/S1 weight ratios.
- Verdict: **MIXED**. Marginal improvement found but within noise.

## H415 - Weight Optimization

**Hypothesis:**
Optimum Vol/S1 weight ratio beyond 0.1/0.9.

**Command / code:**
```bash
python alpha-research-lab/analysis/h415_weight_optimization.py
```

**Inputs:**
- `data/features/xs_barrier_vol_1d_hose_full.parquet` (S1)
- `data/features/xs_order_pressure_daily.parquet` (Volume)

**Protocol:**
- Grid search 0.05-0.50 volume weights

| Weight | IC | Pos Years |
|--------|-----|--------|
| S1 only | +0.118 | 8/8 |
| 10V+90S | +0.135 | 8/8 |
| **15V+85S** | **+0.136** | **8/8** |
| 20V+80S | +0.132 | 8/8 |
| 25V+75S | +0.126 | 8/8 |

**Verdict: MIXED**

- Best: 15V+85S = +0.136
- Delta vs H413 (10V+90S): +0.001 - within noise
- The optimum is in 10-15% Volume range
- H413 (10V+90S) remains the practical standard

**Next**: Test B46 (rank-based weights) or portfolio test of best ranker.

Source anchor: F379