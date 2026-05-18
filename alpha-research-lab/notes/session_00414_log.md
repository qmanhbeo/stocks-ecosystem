# Session 414 - H628 Signal Concentration During Low Breadth

**Date**: 2026-05-18

## Hypothesis

Queue item 132: in low-breadth regimes, concentrated signal mass may become
stronger than distributed signal mass.

## Command

```bash
python analysis/h628_signal_concentration_low_breadth.py
```

## Inputs

- Cached base panel from H621 (`artifacts/cache/h62x_base_panel_2015_2025.parquet`)

## Saved artifacts

- Summary: `artifacts/run_summaries/20260518_182550_h628_signal_concentration_low_breadth_research_branch.json`
- Results: `artifacts/research_branches/20260518_182550_h628_signal_concentration_low_breadth_results.parquet`
- Yearly: `artifacts/research_branches/20260518_182550_h628_signal_concentration_low_breadth_yearly.parquet`

## Results

| State | IC | Rows | Positive Years |
|-------|-----|------|----------------|
| conc_high | 0.2679 | 5,436 | 10/10 |
| conc_low | 0.2523 | 1,380 | 6/6 |
| composite_2plus | 0.2456 | 29,542 | 11/11 |
| dist_high | 0.2405 | 20,714 | 11/11 |
| dist_low | 0.2315 | 2,012 | 7/7 |

Derived:
- concentrated vs distributed inside low-breadth lift = `+0.0209`

## Result

Concentrated signal mass dominates distributed mass inside low-breadth states;
the hypothesized low-breadth concentration flip is confirmed.

## Verdict: PASSED

## Next

- Queue items 125-132 are fully addressed; no remaining active queue items.
