# Session 287 Log

**Date**: 2026-05-05
**Focus**: H406 `noether_flow_break`

## Summary

- Activated 13th S272/S273 queue item.
- Added `analysis/h406_noether_flow_break.py`.
- Tested conservation law residual: expected price from flow vs forward actual.
- Verdict: **FAILED**. Residual inversely predicts forward returns.

## H406 - Noether Flow Break

**Hypothesis:**
Order flow should conserve: expected = f(flow). Residual predicts.

**Command / code:**
```bash
python alpha-research-lab/analysis/h406_noether_flow_break.py
```

**Inputs:**
- `data/features/xs_barrier_vol_1d_hose_full.parquet` (S1)
- `data/order_stats/cafef/order_stats_daily.parquet` (flow features)

**Protocol:**
- Train on 2018-2022, test on 2023-2025
- Train linear model: count/vol imbalance, avg size diff → same-day actual
- Test residual vs NEXT-DAY actual (proper forward target, not leak)

| State | Forward IC | Positive Years |
|-------|-----------|----------------|
| Expected (flow) | +0.00983 | 3/3 |
| Residual | -0.02861 | 0/3 |
| Count imbalance | +0.00461 | - |
| Vol imbalance | +0.00920 | - |
| Avg size diff | +0.00414 | - |

**Saved artifact:**
`artifacts/run_summaries/20260505_232007_noether_flow_break_research_branch.json`

**Verdict: FAILED**

The residual inversely predicts forward returns (-0.02861 IC, 0/3 positive).
The model captures flow in "expected", and residual is noise with negative
predictivity (mean-reversion after training fit). Conservation law breaks
do not hold as alpha.

**Next**: H407
Source anchor: D021