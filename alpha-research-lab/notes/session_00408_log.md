# Session 408 - H622 Signal Magnitude as Hidden State

**Date**: 2026-05-18

## Hypothesis

Queue item 126: rank-weighted signal magnitude may outperform binary
`composite_2plus` count.

## Command

```bash
python analysis/h622_signal_magnitude_hidden_state.py
```

## Inputs

- Cached base panel from H621 (`artifacts/cache/h62x_base_panel_2015_2025.parquet`)

## Saved artifacts

- Summary: `artifacts/run_summaries/20260518_182530_h622_signal_magnitude_hidden_state_research_branch.json`
- Results: `artifacts/research_branches/20260518_182530_h622_signal_magnitude_hidden_state_results.parquet`
- Yearly: `artifacts/research_branches/20260518_182530_h622_signal_magnitude_hidden_state_yearly.parquet`

## Results

| State | IC | Rows | Positive Years |
|-------|-----|------|----------------|
| composite_2plus | 0.2456 | 29,542 | 11/11 |
| composite_mag_q50 | 0.2456 | 29,542 | 11/11 |
| composite_mag_q75 | 0.2451 | 25,660 | 11/11 |
| composite_mag_q90 | 0.2004 | 13,658 | 11/11 |

Derived:
- best magnitude state lift vs baseline = `0.0000`

## Result

Magnitude ranking does not improve binary multi-signal logic; tighter magnitude
cuts only reduce coverage and eventually degrade IC.

## Verdict: FAILED

## Next

- Advance to queue item 127 (Anti-Coherence / Signal Conflict Edge).
