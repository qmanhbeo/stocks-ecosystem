# Session 412 - H626 Signal Decay Acceleration / Exit Zone

**Date**: 2026-05-18

## Hypothesis

Queue item 130: post-persistence zones (especially `31+`) may reveal decay or
flip behavior versus earlier persistence buckets.

## Command

```bash
python analysis/h626_signal_decay_exit_zone.py
```

## Inputs

- Cached base panel from H621 (`artifacts/cache/h62x_base_panel_2015_2025.parquet`)

## Saved artifacts

- Summary: `artifacts/run_summaries/20260518_182643_h626_signal_decay_exit_zone_research_branch.json`
- Results: `artifacts/research_branches/20260518_182643_h626_signal_decay_exit_zone_results.parquet`
- Yearly: `artifacts/research_branches/20260518_182643_h626_signal_decay_exit_zone_yearly.parquet`

## Results

| State | IC | Rows | Positive Years |
|-------|-----|------|----------------|
| age_1_7 | 0.2800 | 7,720 | 11/11 |
| age_8_20 | 0.2375 | 21,072 | 11/11 |
| age_21_30 | 0.1455 | 750 | 2/2 |
| age_31_plus | NaN | 0 | 0/0 |

## Result

The `31+` zone has no support under current construction; the tested decay
boundary cannot be validated. Observed pattern is front-loaded strength
(`1-7` strongest) rather than a measured `31+` flip regime.

## Verdict: FAILED

## Next

- Advance to queue item 131 (Breadth-Expansion Exit Rule).
