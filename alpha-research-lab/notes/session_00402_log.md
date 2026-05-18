# Session 402 - H616 Multi-Signal Temporal Coherence

**Date**: 2026-05-18

## Hypothesis

Queue item 119: within `composite_2plus`, directionally coherent mixes should
beat mixed-direction combinations.

Definitions:
- coherent: `composite_2plus` with no `C25` conflict
- mixed: `composite_2plus` with `C25` plus at least one positive-direction signal

## Command

```bash
python analysis/h616_multi_signal_temporal_coherence.py
```

## Inputs

- S1 panel: `data/features/xs_barrier_vol_1d_hose_full.parquet`
- Order stats: `data/order_stats/cafef/order_stats_daily.parquet`
- OHLCV: `data/stock/gia_lich_su_*_1D.parquet`

## Saved artifacts

- Summary: `artifacts/run_summaries/20260518_180504_h616_multi_signal_temporal_coherence_research_branch.json`
- Results: `artifacts/research_branches/20260518_180504_h616_multi_signal_temporal_coherence_results.parquet`
- Yearly: `artifacts/research_branches/20260518_180504_h616_multi_signal_temporal_coherence_yearly.parquet`

## Results

| State | IC | Rows | Positive Years |
|-------|-----|------|----------------|
| coherent_2plus | 0.1957 | 13,849 | 11/11 |
| mixed_2plus | 0.1955 | 15,693 | 11/11 |
| composite_2plus | 0.2445 | 29,542 | 11/11 |

Derived:
- lift(`coherent` vs `mixed`) = `+0.0002`

## Result

Coherence direction effect is non-actionable under current definitions.

## Verdict: MIXED

## Next

- Advance to queue item 120 (Breadth-Scale Signal Strength Regression).
