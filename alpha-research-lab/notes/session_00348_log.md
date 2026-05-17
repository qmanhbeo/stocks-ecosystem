# Session 348 - H538 Capacity Expansion Regime

## Hypothesis
Test if contracting capacity (fewer orders over time) + S1 beats static tight_capacity. Hidden demand growing = stronger signal.

## Command
```bash
cd alpha-research-lab && conda run -n stocks python analysis/h538_capacity_expansion_regime.py
```

## Inputs
- S1 panel: xs_barrier_vol_1d_hose_full.parquet (2015-2025)
- C16: xs_order_pressure_daily.parquet
- Tight capacity: bottom 20% by order_volume_ratio within each date
- Capacity change: 5-day delta of order_volume_ratio

## Saved Artifact
`artifacts/run_summaries/20260517_150424_capacity_expansion_regime_research_branch.json`

## Results

| State | Avg IC | Lift vs Baseline | Rows |
|-------|--------|------------------|------|
| tight_expanding | 0.1697 | +0.0395 | 31,829 |
| tight_capacity | 0.1588 | +0.0285 | 163,147 |
| tight_contracting | 0.1553 | +0.0251 | 127,938 |
| strongly_contracting | 0.1463 | +0.0161 | 158,715 |
| tight_stable | 0.1421 | +0.0119 | 3,380 |
| all_rows | 0.1302 | — | 826,404 |

## Result
**MIXED** - tight_contracting beats baseline (+0.0251) but is WORSE than static tight_capacity (-0.0034).

## Key Finding - OPPOSITE OF HYPOTHESIS
**tight_expanding** (more orders over time) beats **tight_contracting** (fewer orders over time) by +0.0144 IC!

The hypothesis was that contracting capacity indicates "hidden demand growing" (fewer orders = less competition), but empirically:
- Expanding capacity (more orders flowing into tight names) = IC=0.1697, STRONGEST
- Static tight capacity = IC=0.1588
- Contracting capacity = IC=0.1553, WEAKEST of the three

This suggests that tight capacity works because it's a regime marker, not because of "hidden demand" - the expansion within that regime (more orders arriving) indicates sustained interest, not competition.

## Verdict: MIXED