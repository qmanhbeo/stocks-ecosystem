# Session 390 - H107 Signal Order as Hidden State

**Date:** 2026-05-17

## Hypothesis

Signal Order as Hidden State: Does WHICH signal fires FIRST matter? C23→C24 
transition might indicate different demand than C24→C23. Test signal_sequence 
(first signal detected) vs signal_count (just count).

## Command

```bash
python analysis/h107_signal_order_hidden_state.py
```

## Inputs

- S1 panel: xs_barrier_vol_1d_hose_full.parquet (2015-2025)
- Order stats: order_stats_daily.parquet
- OHLCV for Amihud calculation

## Saved Artifacts

- Results: `artifacts/research_branches/20260517_175713_h107_signal_order_hidden_state_results.parquet`
- Summary: `artifacts/run_summaries/20260517_175713_h107_signal_order_hidden_state_research_branch.json`

## Results

| State | IC | Rows | Positive Years |
|-------|-----|------|-----------------|
| composite_2plus (F445 baseline) | 0.2445 | 29,542 | 11/11 |
| first_c23 | 0.2361 | 21,001 | 11/11 |
| first_any | 0.2360 | 21,227 | 11/11 |
| any_signal | 0.1988 | 97,236 | 11/11 |
| all_rows | 0.1298 | 809,019 | 11/11 |
| first_c24 | NaN | 54 | 0 |
| first_c25 | NaN | 172 | 0 |
| first_c26 | 0 | 0 | 0 |

**Lift vs F445:** -0.0085 (NEGATIVE - signal order HURTS)

## Verdict: FAILED

Signal order does NOT add value:
- first_any (0.2360) is WORSE than composite_2+ (0.2445) by -0.0085
- The specific first signals (C24/C25/C26) are too sparse to be meaningful
- C24 first = 54 rows, C25 first = 172 rows, C26 first = 0 rows
- Only C23 first has enough data (21,001 rows) but it's still weaker than composite

**Conclusion:** The synergy in composite_2+ is in the "2+ signals" logic (multiple signals 
firing together), NOT in which specific signal fires first. Signal sequence/order is NOT a 
hidden state. Dead-end D084.