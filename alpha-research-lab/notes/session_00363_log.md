# Session 363 - H564 Breadth Quintile Gate

**Date**: 2026-05-17

**Hypothesis**: Test if breadth QUINTILES (Q1-Q5) capture different alpha regimes vs binary bottom 20%. H525 found low_breadth is better - test if finer granularity helps.

**Command**: `python analysis/h564_breadth_quintile_gate.py`

**Saved artifact**: `artifacts/run_summaries/20260517_155334_breadth_quintile_gate_research_branch.json`

## Results

| State | IC | Positive Years |
|-------|-----|----------------|
| Q2 (2nd lowest) | 0.1435 | 4/4 |
| Q3 (middle) | 0.1171 | 7/8 |
| Q4 | 0.1140 | 6/6 |
| binary low_breadth | 0.1073 | 3/4 |
| Q5 (highest) | 0.1066 | 5/5 |
| Q1 (lowest) | 0.1053 | 3/4 |

## Key Finding: FAILED

**Quintiles do NOT beat binary**:
- Q1 (lowest breadth) = 0.1053
- Binary low_breadth = 0.1073
- Q1 vs Binary = **-0.0020** (binary wins!)

**Non-monotonic pattern**:
- Q2 is STRONGEST (0.1435), NOT Q1
- Pattern: Q2 > Q3 > Q4 > Q5 > Q1
- The lowest breadth (Q1) is NOT the best regime
- This contradicts H525's binary finding

**H525/H529 were about C23/C24 on low_breadth**, not raw S1 on breadth:
- The finding was: C23/C24/C25/C26 composite works better on low_breadth dates
- Raw S1 on low_breadth is weak (0.107)
- Breadth as pure regime filter on raw S1 doesn't work

## Verdict: FAILED

- Quintiles don't improve over binary
- Q1 (lowest) is not the sweet spot - Q2 is stronger
- This tests raw S1 on breadth, not signal × breadth combo
- Dead-end D070

**Next**: #63 Capacity-Breadth Direction Combo