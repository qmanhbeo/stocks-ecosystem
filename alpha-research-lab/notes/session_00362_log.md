# Session 362 - H563 Opposite-Day Breadth Entry

**Date**: 2026-05-17

**Hypothesis**: Test if the ONSET of low_breadth (first day it becomes low) is stronger than sustained low_breadth. H525 found low_breadth is better - now test if the transition captures extra alpha.

**Command**: `python analysis/h563_opposite_day_breadth_entry.py`

**Saved artifact**: `artifacts/run_summaries/20260517_155217_opposite_day_breadth_entry_research_branch.json`

## Results

| State | IC | Positive Years |
|-------|-----|----------------|
| sustained_low_breadth | 0.1442 | 3/3 |
| low_breadth | 0.1073 | 3/4 |
| first_day_low_breadth | 0.0977 | 1/2 |

## Key Finding: FAILED (OPPOSITE)

**Onset is WORSE than sustained**:
- First Day Low Breadth IC = 0.0977
- Sustained Low Breadth IC = 0.1442
- Onset vs Sustained = **-0.0464** (sustained wins by +4.6%!)

**The transition is NOT the alpha**:
- First day of low_breadth regime is weaker than steady state
- Sustained low_breadth is stronger (more stable, less noise)
- H525/H542 already confirmed: low breadth LEVEL is the signal, not the path to it

## Verdict: FAILED

- Onset (first day) is -0.0464 BELOW sustained
- The regime SHIFT is not captured - steady state is stronger
- Dead-end D069

**Next**: #62 Breadth Quintile Gate