# Session 413 - H627 Breadth-Expansion Exit Rule

**Date**: 2026-05-18

## Hypothesis

Queue item 131: adaptive exit on breadth expansion (`>1.5x` entry breadth) may
beat fixed-hold exits for low-breadth composite entries.

## Command

```bash
python analysis/h627_breadth_expansion_exit_rule.py
```

## Inputs

- Cached base panel from H621 (`artifacts/cache/h62x_base_panel_2015_2025.parquet`)
- Event-study mode using close-to-close returns on entry events

## Saved artifacts

- Summary: `artifacts/run_summaries/20260518_182548_h627_breadth_expansion_exit_rule_research_branch.json`
- Events: `artifacts/research_branches/20260518_182548_h627_breadth_expansion_exit_rule_events.parquet`
- Yearly: `artifacts/research_branches/20260518_182548_h627_breadth_expansion_exit_rule_yearly.parquet`
- Aggregate: `artifacts/research_branches/20260518_182548_h627_breadth_expansion_exit_rule_aggregate.parquet`

## Results

| Metric | Value |
|--------|-------|
| event_rows | 3,245 |
| fixed_mean_return (5d) | 0.0119 |
| adaptive_mean_return (breadth-expansion exit) | 0.0084 |
| lift (adaptive - fixed) | -0.0035 |
| fixed_win_rate | 0.5196 |
| adaptive_win_rate | 0.5146 |
| mean_fixed_hold_days | 4.99 |
| mean_adaptive_hold_days | 2.32 |

## Result

Breadth-expansion exits shorten holding duration but reduce mean return and win
rate versus fixed 5-day exits.

## Verdict: FAILED

## Next

- Advance to queue item 132 (Signal Concentration During Low Breadth).
