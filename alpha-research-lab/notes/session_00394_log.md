# Session 394 - H608 Capacity-Modulated Multi-Signal

**Date**: 2026-05-17

## Hypothesis

Tight capacity (F437) may amplify the multi-signal pocket (F445). Test whether
`composite_2plus AND tight_capacity` beats `composite_2plus` alone.

## Command

```bash
python analysis/h608_capacity_modulated_multi_signal.py
```

## Inputs

- S1 panel: `data/features/xs_barrier_vol_1d_hose_full.parquet`
- Order stats: `data/order_stats/cafef/order_stats_daily.parquet`
- OHLCV: `data/stock/gia_lich_su_*_1D.parquet`

## Saved artifacts

- Summary: `artifacts/run_summaries/20260517_193032_h608_capacity_modulated_multi_signal_research_branch.json`
- Results: `artifacts/research_branches/20260517_193032_h608_capacity_modulated_multi_signal_results.parquet`
- Yearly: `artifacts/research_branches/20260517_193032_h608_capacity_modulated_multi_signal_yearly.parquet`

## Results

| State | IC | Rows | Positive Years |
|-------|-----|------|----------------|
| composite_2plus | 0.2445 | 29,542 | 11/11 |
| composite_2plus_tight | 0.2404 | 22,156 | 11/11 |
| tight_capacity | 0.1900 | 160,573 | 11/11 |
| all_rows | 0.1298 | 809,019 | 11/11 |

## Result

Tight capacity does not amplify multi-signal; it slightly degrades the
multi-signal IC.

- lift(`composite_2plus_tight` vs `composite_2plus`) = `-0.0041`

## Verdict: FAILED

## Next

- Advance to H109 triple-factor intersection branch.
