# Session 396 - H610 Regime Transition Timing Alpha

**Date**: 2026-05-18

## Hypothesis

Queue item 113: the transition moment into low breadth may beat already
sustained low breadth for `composite_2plus` entries.

## Command

```bash
python analysis/h610_regime_transition_timing_alpha.py
```

## Inputs

- S1 panel: `data/features/xs_barrier_vol_1d_hose_full.parquet`
- Order stats: `data/order_stats/cafef/order_stats_daily.parquet`
- OHLCV: `data/stock/gia_lich_su_*_1D.parquet`

## Saved artifacts

- Summary: `artifacts/run_summaries/20260518_162807_h610_regime_transition_timing_alpha_research_branch.json`
- Results: `artifacts/research_branches/20260518_162807_h610_regime_transition_timing_alpha_results.parquet`
- Yearly: `artifacts/research_branches/20260518_162807_h610_regime_transition_timing_alpha_yearly.parquet`

## Results

| State | IC | Rows | Positive Years |
|-------|-----|------|----------------|
| composite_2plus_sustained_low | 0.2797 | 2,138 | 4/4 |
| composite_2plus_transition_low | 0.2793 | 2,928 | 10/10 |
| composite_2plus_low_breadth | 0.2699 | 5,066 | 11/11 |
| composite_2plus | 0.2445 | 29,542 | 11/11 |
| all_rows | 0.1298 | 809,019 | 11/11 |

## Result

Transition timing does not beat sustained low breadth:

- lift(`transition` vs `sustained`) = `-0.0004`
- both transition and sustained are strong, but effectively tied

## Verdict: FAILED

## Next

- Advance to queue item 114 (Implementation Pain as Position Sizing).
