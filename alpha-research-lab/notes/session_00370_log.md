# Session 370 - H580 C27 × Capacity Amplifier

**Date**: 2026-05-17

**Hypothesis**: C27 (blocked stocks) + tight_capacity = two hidden-demand mechanisms combining.

**Command**: `python analysis/h580_c27_capacity_amplifier.py`

**Saved artifact**: `artifacts/run_summaries/20260517_162721_c27_capacity_amplifier_research_branch.json`

## Results

| State | IC | Rows | Positive Years |
|-------|-----|------|----------------|
| blocked_tight | 0.1688 | 2,356 | 1/1 |
| liquid_tight | 0.1649 | 127,391 | 11/11 |
| tight_capacity | 0.1648 | 127,566 | 11/11 |
| blocked_either (C27) | 0.1477 | 15,848 | 10/10 |
| blocked_loose | 0.1328 | 13,492 | 9/9 |
| all_rows | 0.1302 | 826,404 | 11/11 |
| liquid | 0.1266 | 817,782 | 11/11 |
| liquid_loose | 0.1184 | 690,391 | 11/11 |

## Key Finding: MIXED (marginal, too sparse)

- C27 × tight: IC=0.1688 (+0.0211 vs raw C27, +0.0040 vs tight alone)
- blocked_tight: only 2,356 rows, 1/1 positive years (DEVELOPMENT SET ONLY)
- The IC boost is real but the positive years count is meaningless (1/1)
- **blocked_tight ≈ tight_capacity** — blocked adds almost nothing over tight alone
- The marginal +0.004 improvement over tight is below +0.01 threshold

**Interpretation**: Tight capacity is the dominant signal. The blocked component is redundant when combined with tight capacity. The ~2,356 row subset is too sparse for phase validation.

## Verdict: MIXED (marginal)

- Improvement over raw C27 is real (+0.0211) but sparse (only 1 dev year)
- Improvement over tight is marginal (+0.004 < +0.01 threshold)
- C27 is redundant when tight capacity is already present

**Next**: #81 C27 × Breadth Amplifier (blocked × low_breadth)