# Session 393 - H607 Inverse Multi-Signal Edge

**Date**: 2026-05-17

## Hypothesis

Even though `composite_2plus` is strongest (F445), perhaps blocked
single-signal names (`signal_1 AND blocked`) are a pre-convergence hidden-demand
pocket and can beat plain `signal_1`.

## Command

```bash
python analysis/h607_inverse_multi_signal_edge.py
```

## Inputs

- S1 panel: `data/features/xs_barrier_vol_1d_hose_full.parquet`
- Tradability: `data/features/execution/tradability_daily.parquet`
- Order stats: `data/order_stats/cafef/order_stats_daily.parquet`
- OHLCV: `data/stock/gia_lich_su_*_1D.parquet`

## Saved artifacts

- Summary: `artifacts/run_summaries/20260517_192829_h607_inverse_multi_signal_edge_research_branch.json`
- Results: `artifacts/research_branches/20260517_192829_h607_inverse_multi_signal_edge_results.parquet`
- Yearly: `artifacts/research_branches/20260517_192829_h607_inverse_multi_signal_edge_yearly.parquet`

## Results

| State | IC | Rows | Positive Years |
|-------|-----|------|----------------|
| signal_1 | 0.1724 | 67,694 | 11/11 |
| signal_1_blocked | 0.1237 | 6,948 | 10/11 |
| signal_1_liquid | 0.1673 | 60,746 | 11/11 |
| all_rows | 0.1298 | 809,019 | 11/11 |

## Result

Blocked state degrades the single-signal pocket rather than improving it.

- lift(`signal_1_blocked` vs `signal_1`) = `-0.0487`

## Verdict: FAILED

## Next

- Advance to H109 triple-factor intersection branch.
