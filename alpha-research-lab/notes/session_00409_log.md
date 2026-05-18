# Session 409 - H623 Anti-Coherence / Signal Conflict Edge

**Date**: 2026-05-18

## Hypothesis

Queue item 127: conflicting multi-signal states (up + down signals together)
may outperform coherent multi-signal states.

## Command

```bash
python analysis/h623_signal_conflict_edge.py
```

## Inputs

- Cached base panel from H621 (`artifacts/cache/h62x_base_panel_2015_2025.parquet`)

## Saved artifacts

- Summary: `artifacts/run_summaries/20260518_182544_h623_signal_conflict_edge_research_branch.json`
- Results: `artifacts/research_branches/20260518_182544_h623_signal_conflict_edge_results.parquet`
- Yearly: `artifacts/research_branches/20260518_182544_h623_signal_conflict_edge_yearly.parquet`

## Results

| State | IC | Rows | Positive Years |
|-------|-----|------|----------------|
| composite_2plus | 0.2456 | 29,542 | 11/11 |
| composite_conflict | 0.2019 | 15,693 | 11/11 |
| composite_coherent | 0.2000 | 13,849 | 11/11 |

Derived:
- conflict vs coherent lift = `+0.0020`

## Result

Conflict states are directionally higher than coherent states, but the gap is
small and below actionable threshold.

## Verdict: MIXED

## Next

- Advance to queue item 128 (Calendar × Breadth Interaction).
