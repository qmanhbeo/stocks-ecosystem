# Session 371 - H581 C27 × Breadth Amplifier

**Date**: 2026-05-17

**Hypothesis**: C27 (blocked stocks) × low_breadth amplifies the signal (like H565 found for tight+low_breadth).

**Command**: `python analysis/h581_c27_breadth_amplifier.py`

**Saved artifact**: `artifacts/run_summaries/20260517_162913_c27_breadth_amplifier_research_branch.json`

## Results

| State | IC | Rows | Positive Years |
|-------|-----|------|----------------|
| low_breadth | 0.1550 | 121,504 | 3/3 |
| liquid_low_breadth | 0.1540 | 120,852 | 3/3 |
| blocked_high_breadth | 0.1500 | 14,825 | 9/9 |
| blocked_either (C27) | 0.1477 | 15,848 | 10/10 |
| all_rows | 0.1302 | 826,404 | 11/11 |
| liquid | 0.1266 | 817,782 | 11/11 |
| liquid_high_breadth | 0.1189 | 696,930 | 9/9 |
| blocked_low_breadth | 0.0960 | 1,023 | 1/1 |

## Key Finding: OPPOSITE + SPARSE - C27 × low_breadth DEGRADES and is too sparse

- C27 × low_breadth: IC=0.0960 (-0.0517 vs raw C27!)
- blocked_low_breadth: only 1,023 rows, 1/1 positive years (sparse)
- C27 × high_breadth: IC=0.1500 (+0.0023 vs raw C27) — slightly better, not worse
- **Breadth filter WORKS OPPOSITE for C27**: low_breadth HURTS, high_breadth helps slightly
- C27 lift in low_breadth: -0.0580, C27 lift in high_breadth: +0.0311

**Mechanism**: When breadth is low, there are few active signals. Blocked stocks in this regime may represent isolated, illiquid names with no crowd interest — different from the "hidden demand" mechanism of C27. The blocked signal works best when there IS some signal activity (high breadth), suggesting the blocked signal captures a relative effect within an active crowd, not absolute illiquidity.

## Verdict: FAILED (opposite + sparse) — Dead-end D075

- Intersection is too sparse (1,023 rows) for meaningful IC
- Direction is opposite: low_breadth HURTS C27
- C27 is a different mechanism from tight_capacity/breadth amplifiers

**Next**: #82 C27 × Signal Composite (blocked with C23/C24/C25/C26)