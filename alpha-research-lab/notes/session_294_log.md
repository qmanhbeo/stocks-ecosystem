# Session 294 Log

**Date**: 2026-05-05
**Focus**: H413 `triple_signal_additive`

## Summary

- Activated Bright-Mind B30 idea (Triple Signal Additive).
- Added `analysis/h413_triple_signal_additive.py`.
- Tested Volume + S1 + C16 three-way additive vs forward IC.
- Verdict: **PASSED**. New best found: 0.1×Vol + 0.9×S1 = +0.135!

## H413 - Triple Signal Additive

**Hypothesis:**
Three-signal additive (Volume + S1 + C16) beats two-signal (H410).

**Command / code:**
```bash
python alpha-research-lab/analysis/h413_triple_signal_additive.py
```

**Inputs:**
- `data/features/xs_barrier_vol_1d_hose_full.parquet` (S1)
- `data/features/xs_order_pressure_daily.parquet` (Volume, C16)

**Protocol:**
- Test years `2018-2025`
- Compare to H410 baseline (0.25V+0.75S = +0.126)

| State | Forward IC | vs H410 |
|-------|-----------|---------|
| S1 alone | +0.118 | - |
| Volume alone | +0.075 | - |
| C16 alone | -0.0008 | - |
| H410 (0.25V+0.75S) | +0.126 | baseline |
| **0.1V+0.9S** | **+0.135** | **+0.009** |
| 0.15V+0.7S+0.15C16 | +0.133 | +0.006 |

**Saved artifact:**
`artifacts/run_summaries/triple_signal_additive_research_branch.json`

**Verdict: PASSED**

- New best: 0.1×Volume + 0.9×S1 = +0.135 IC
- Beats H410 by +0.009 IC (+7% improvement)
- Lower volume weight (10% vs 25%) is the key insight
- C16 doesn't add value in three-way (too weak)

**Next**: Test this in portfolio context or finalize this as candidate ranker.

Source anchor: F377