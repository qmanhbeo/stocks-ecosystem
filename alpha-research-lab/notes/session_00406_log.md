# Session 406 - H620 Implementation Pain × Multi-Signal Triple

**Date**: 2026-05-18

## Hypothesis

Queue item 124: implementation pain may amplify multi-signal pockets.

Tested:
- `composite_2plus × blocked_either`
- `composite_2plus × blocked_day_2_3` (H605-style control)

## Command

```bash
python analysis/h620_implementation_pain_multi_signal_triple.py
```

## Inputs

- S1 panel: `data/features/xs_barrier_vol_1d_hose_full.parquet`
- Tradability: `data/features/execution/tradability_daily.parquet`
- Order stats: `data/order_stats/cafef/order_stats_daily.parquet`
- OHLCV: `data/stock/gia_lich_su_*_1D.parquet`

## Saved artifacts

- Summary: `artifacts/run_summaries/20260518_181432_h620_implementation_pain_multi_signal_triple_research_branch.json`
- Results: `artifacts/research_branches/20260518_181432_h620_implementation_pain_multi_signal_triple_results.parquet`
- Yearly: `artifacts/research_branches/20260518_181432_h620_implementation_pain_multi_signal_triple_yearly.parquet`

## Results

| State | IC | Rows | Positive Years |
|-------|-----|------|----------------|
| composite_2plus | 0.2445 | 29,542 | 11/11 |
| composite_2plus_blocked_either | 0.1660 | 2,574 | 11/11 |
| composite_2plus_blocked_2_3 | NaN | 239 | 0/0 |

Derived:
- best combo lift vs `composite_2plus` = `-0.0785`

## Result

Implementation-pain combinations degrade the multi-signal baseline; the day-2-3
intersection remains too sparse.

## Verdict: FAILED

## Next

- Advance to queue item 125 (Cross-Signal Breadth Threshold Discovery).
