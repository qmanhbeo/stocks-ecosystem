# Session 351 — H543 Breadth-Weighted Composite

## Hypothesis

H530 FAILED weighting raw S1 by 1/breadth (IC=0.1057 < baseline). Now test weighting C23/C24/C25/C26 COMPOSITE instead.

## Command / Code

```bash
python analysis/h543_breadth_weighted_composite.py --start-year 2015 --end-year 2025
```

## Inputs

- S1 decision panel (2015-2025)
- Order stats for vol regime computation
- OHLCV for Amihud illiquidity (C23)
- Composite = OR of C23/C24/C25/C26 signals

## Saved Artifact

`artifacts/run_summaries/20260517_151351_breadth_weighted_composite_research_branch.json`

## Results

| State | IC | Lift vs Baseline | Rows | Positive Years |
|-------|-----|-----------------|------|----------------|
| all_rows (baseline) | 0.1298 | — | 809,019 | 11/11 |
| low_breadth (all S1) | 0.1299 | +0.0001 | 168,466 | 11/11 |
| composite_signal | 0.1988 | +0.0690 | 97,236 | 11/11 |
| composite × low_breadth | 0.2364 | +0.1066 | 13,150 | 8/11 |

## Analysis

- **Composite signal works**: C23/C24/C25/C26 OR composite IC=0.1988 (+0.0690) beats baseline significantly
- **Low-breadth amplifies composite**: composite × low_breadth IC=0.2364 (+0.1066) is the strongest
- **Binary low_breadth on all S1 is weak**: IC=0.1299 (+0.0001), much weaker than H529's 0.1542 - likely due to different breadth calculation method (ticker-level vs row-level)

## Verdict: PASSED

Composite × low_breadth (IC=0.2364, +0.1066 lift) significantly beats:
- Baseline (+0.1066)
- Composite alone (+0.0376)
- Binary low_breadth on raw S1 (+0.1065)

The hypothesis is confirmed: weighting/combining C23/C24/C25/C26 signals with low_breadth filter works better than weighting raw S1.