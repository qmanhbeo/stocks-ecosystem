# Session 391 - H605 Multi-Signal × Blocked Triple

**Date**: 2026-05-17

## Hypothesis

F445 (`composite_2plus`) and F444 (`blocked_day_2_3`) are both strong separately.
If they encode orthogonal hidden-demand mechanisms, the intersection
`composite_2plus × blocked_day_2_3` should add material lift over
`composite_2plus` alone.

## Command

```bash
python analysis/h605_multi_signal_blocked_triple.py
```

## Inputs

- S1 panel: `data/features/xs_barrier_vol_1d_hose_full.parquet`
- Tradability: `data/features/execution/tradability_daily.parquet`
- Order stats: `data/order_stats/cafef/order_stats_daily.parquet`
- OHLCV: `data/stock/gia_lich_su_*_1D.parquet`

## Saved artifacts

- Summary: `artifacts/run_summaries/20260517_192349_h605_multi_signal_blocked_triple_research_branch.json`
- Results: `artifacts/research_branches/20260517_192349_h605_multi_signal_blocked_triple_results.parquet`
- Yearly: `artifacts/research_branches/20260517_192349_h605_multi_signal_blocked_triple_yearly.parquet`

## Results

| State | IC | Rows | Positive Years |
|-------|-----|------|----------------|
| composite_2plus | 0.2445 | 29,542 | 11/11 |
| blocked_day_2_3 | 0.1743 | 1,562 | 5/5 |
| composite_2plus_blocked_2_3 | NaN | 207 | 0/0 (below yearly minimum rows) |
| all_rows | 0.1298 | 809,019 | 11/11 |

## Result

Intersection state is too sparse for valid yearly IC evaluation under the
current minimum-row contract, so no promotable lift can be estimated.

Interpretation:
- This does **not** invalidate F445 or F444 individually.
- It does invalidate the current triple intersection contract as a practical
  branch on this data surface.

## Verdict: FAILED (data-gated sparsity)

## Next

- Advance to H111-style branch: breadth-adjusted multi-signal weighting vs
  binary low-breadth gate on the same `composite_2plus` base.
