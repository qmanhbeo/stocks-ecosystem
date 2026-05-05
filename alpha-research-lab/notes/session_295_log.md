# Session 295 Log

**Date**: 2026-05-05
**Focus**: H414 `alternative_target_additive`

## Summary

- Activated Bright-Mind B42 idea (Alternative Target Additive).
- Added `analysis/h414_alternative_target_additive.py`.
- Tested Vol+S1 additive (0.1V+0.9S) on different barrier targets.
- Verdict: **PASSED**. Works on ALL horizons (1d, 10d, 20d).

## H414 - Alternative Target Additive

**Hypothesis:**
Vol+S1 additive works on different barrier targets (generalization test).

**Command / code:**
```bash
python alpha-research-lab/analysis/h414_alternative_target_additive.py
```

**Inputs:**
- `data/features/xs_barrier_vol_1d_hose_full.parquet` (1d)
- `data/features/xs_barrier_10d_label_hose_full.parquet` (10d)
- `data/features/xs_barrier_20d_label_hose_full.parquet` (20d)
- `data/features/xs_order_pressure_daily.parquet` (Volume)

**Protocol:**
- Test years `2018-2025`
- Compare S1 alone vs 0.1V+0.9S on each target

| Target | S1 Alone | 0.1V+0.9S | Lift | Pos Years |
|--------|----------|-------------|------|--------|
| 1d | +0.118 | +0.135 | +0.017 | 8/8 |
| 10d | +0.119 | +0.138 | +0.019 | 8/8 |
| 20d | +0.119 | +0.138 | +0.019 | 8/8 |

**Saved artifact:**
`artifacts/run_summaries/alternative_target_additive_research_branch.json`

**Verdict: PASSED**

- Additive WORKS on ALL horizons
- 10d and 20d show same pattern as 1d
- +0.019 IC lift on longer horizons
- This confirms the additive is a generalizable pattern, not target-specific

**Next**: Test in portfolio context or add foreign/insider signals.

Source anchor: F378