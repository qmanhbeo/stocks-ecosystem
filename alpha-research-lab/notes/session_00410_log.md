# Session 410 - H624 Calendar-Breadth Interaction

**Date**: 2026-05-18

## Hypothesis

Queue item 128: low-breadth regime quality may vary by weekday (Monday vs
Friday vs other).

## Command

```bash
python analysis/h624_calendar_breadth_interaction.py
```

## Inputs

- Cached base panel from H621 (`artifacts/cache/h62x_base_panel_2015_2025.parquet`)

## Saved artifacts

- Summary: `artifacts/run_summaries/20260518_182545_h624_calendar_breadth_interaction_research_branch.json`
- Results: `artifacts/research_branches/20260518_182545_h624_calendar_breadth_interaction_results.parquet`
- Yearly: `artifacts/research_branches/20260518_182545_h624_calendar_breadth_interaction_yearly.parquet`

## Results

| State | IC | Rows | Positive Years |
|-------|-----|------|----------------|
| low_breadth_other | 0.2484 | 2,116 | 9/9 |
| low_breadth_monday | 0.2477 | 592 | 2/2 |
| low_breadth_composite | 0.2406 | 3,392 | 11/11 |
| low_breadth_friday | 0.2012 | 684 | 1/1 |

Derived:
- best day-state lift vs generic low-breadth state = `+0.0077`

## Result

Weekday conditioning adds only marginal lift and is partially sparse; not
strong enough for promotion.

## Verdict: MIXED

## Next

- Advance to queue item 129 (Ticker-Specific Breadth).
