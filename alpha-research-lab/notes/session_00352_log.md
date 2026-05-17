# Session 352 — H544 Duration-Weighted Signal Strength

## Hypothesis

H534 found longer active-state duration predicts STRONGER signal. Now test using duration as continuous weight modifier for S1 instead of binary filter.

## Command / Code

```bash
python analysis/h544_duration_weighted_signal.py --start-year 2015 --end-year 2025
```

## Inputs

- S1 decision panel (2015-2025)
- Order stats for C16 (order_volume_ratio_rank) computation
- Duration computed as consecutive days in active state (C16 <= 0.2)

## Saved Artifact

`artifacts/run_summaries/20260517_151544_duration_weighted_signal_strength_research_branch.json`

## Results

| State | IC | Lift vs Baseline | Rows | Positive Years |
|-------|-----|-----------------|------|----------------|
| all_rows (baseline) | 0.1302 | — | 826,404 | 11/11 |
| duration_any | 0.1648 | +0.0346 | 127,566 | 11/11 |
| duration_2_3d | 0.1722 | +0.0420 | 36,356 | 11/11 |
| duration_4_7d | 0.1812 | +0.0510 | 14,640 | 11/11 |
| duration_8pl | 0.1832 | +0.0530 | 5,292 | 4/11 |
| weighted (S1 × log(1+days)) | 0.0959 | — | active only | — |
| weighted_rank | 0.0972 | — | active only | — |

## Analysis

- **Binary filters confirm H534**: duration_8pl IC=0.1832 (+0.0530) - longer duration = stronger signal
- **Weighted versions FAIL**: weighting S1 by duration actually HURTS the signal
  - Best weighted IC = 0.0972 vs binary best = 0.1832 (difference: -0.086)
  - The multiplication by duration weight dilutes the S1 signal rather than enhancing it
- **Key insight**: Duration works as a FILTER (selecting stocks that have been active longer), but NOT as a continuous weight (multiplying S1 by duration adds noise)

## Verdict: FAILED

The hypothesis that duration could be used as a continuous weight modifier is falsified. Binary filtering works (duration as selector), but continuous weighting fails (duration as multiplier). H534's finding that "longer active state predicts stronger signal" applies to selection, not weighting.