# Session 397 - H611 Implementation Pain as Position Sizing

**Date**: 2026-05-18

## Hypothesis

Queue item 114: blocked names may be better used as a position-size multiplier
instead of a hard filter.

Test:
- baseline score: `s1_xs_proba`
- sized score: `s1_xs_proba * 1.5` for `blocked_either`, else `*1.0`

## Command

```bash
python analysis/h611_implementation_pain_position_sizing.py
```

## Inputs

- S1 panel: `data/features/xs_barrier_vol_1d_hose_full.parquet`
- Tradability: `data/features/execution/tradability_daily.parquet`

## Saved artifacts

- Summary: `artifacts/run_summaries/20260518_163041_h611_implementation_pain_position_sizing_research_branch.json`
- Results: `artifacts/research_branches/20260518_163041_h611_implementation_pain_position_sizing_results.parquet`
- Yearly: `artifacts/research_branches/20260518_163041_h611_implementation_pain_position_sizing_yearly.parquet`

## Results

| Variant | IC | Rows |
|---------|-----|------|
| baseline_score | 0.1302 | 826,404 |
| blocked_multiplier_150 | 0.1292 | 826,404 |

## Result

Sizing blocked names up by `1.5x` degrades signal quality:

- lift(`blocked_1.5x` vs baseline) = `-0.0010`

## Verdict: FAILED

## Next

- Advance to queue item 115 (Market Regime Position Multiplier).
