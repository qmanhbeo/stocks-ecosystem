# Session 401 - H615 Signal Concentration × Breadth Interaction

**Date**: 2026-05-18

## Hypothesis

Queue item 118: interaction between concentration and breadth may create a
stronger `composite_2plus` regime.

Tested 4-way states:
- low breadth × high concentration
- low breadth × low concentration
- high breadth × high concentration
- high breadth × low concentration

## Command

```bash
python analysis/h615_signal_concentration_breadth_interaction.py
```

## Inputs

- S1 panel: `data/features/xs_barrier_vol_1d_hose_full.parquet`
- Order stats: `data/order_stats/cafef/order_stats_daily.parquet`
- OHLCV: `data/stock/gia_lich_su_*_1D.parquet`

## Saved artifacts

- Summary: `artifacts/run_summaries/20260518_164406_h615_signal_concentration_breadth_interaction_research_branch.json`
- Results: `artifacts/research_branches/20260518_164406_h615_signal_concentration_breadth_interaction_results.parquet`
- Yearly: `artifacts/research_branches/20260518_164406_h615_signal_concentration_breadth_interaction_yearly.parquet`

## Results

| State | IC | Rows | Positive Years |
|-------|-----|------|----------------|
| c2_low_breadth_low_conc | 0.2745 | 1,415 | 4/4 |
| c2_high_breadth_high_conc | 0.2485 | 926 | 2/2 |
| c2_high_breadth_low_conc | 0.2401 | 1,683 | 5/5 |
| c2_low_breadth_high_conc | 0.2614 | 495 | 2/2 |
| composite_2plus | 0.2445 | 29,542 | 11/11 |

Derived:
- best low-breadth IC (low_conc): `0.2745`
- best high-breadth IC (high_conc): `0.2485`
- lift: `+0.0260`

## Result

Directional interaction exists, but robustness is insufficient:

- best-low years: 4
- best-high years: 2
- best-high confirmation rows: 3

## Verdict: MIXED

## Next

- Advance to queue item 119 (Multi-Signal Temporal Coherence).
