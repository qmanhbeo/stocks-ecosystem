# Session 374 - H583 Liquid in Bad Breadth as Contrarian

**Date**: 2026-05-17

**Hypothesis**: Liquid stocks (tradable, ignored by crowd) are contrarian in high-breadth regime.

**Command**: `python analysis/h583_liquid_contrarian_high_breadth.py`

**Saved artifact**: `artifacts/run_summaries/20260517_164307_liquid_contrarian_high_breadth_research_branch.json`

## Results

| State | IC | Rows | Positive Years |
|-------|-----|------|----------------|
| blocked_high_breadth | 0.2029 | 5,836 | 4/4 |
| low_breadth | 0.1550 | 121,504 | 3/3 |
| liquid_low_breadth | 0.1540 | 120,852 | 3/3 |
| blocked_either (C27) | 0.1477 | 15,848 | 10/10 |
| all_rows | 0.1302 | 826,404 | 11/11 |
| liquid | 0.1266 | 817,782 | 11/11 |
| high_breadth | 0.1095 | 213,193 | 5/5 |
| liquid_high_breadth | 0.1029 | 210,142 | 5/5 |
| blocked_low_breadth | 0.0960 | 1,023 | 1/1 |

## Key Finding: OPPOSITE - Liquid is WORSE in high breadth, Blocked is BETTER

- Liquid × high_breadth: IC=0.1029 (-0.0236 vs liquid alone, -0.0511 vs liquid × low_breadth)
- Blocked × high_breadth: IC=0.2029 (+0.0552 vs blocked alone, +0.0934 vs high_breadth baseline)
- Liquid lift in high_breadth: -0.0066 (NEGATIVE — liquid is ignored by the market in crowded times, not contrarian)
- Blocked lift in high_breadth: +0.0934 (VERY STRONG — blocked stocks are MOST valuable in crowded times!)
- Contrarian hypothesis FAILS: liquid is NOT a contrarian play in high-breadth

**Critical insight**: blocked_high_breadth = 0.2029 is the STRONGEST single state seen this session. C27 works best when the market is crowded (many signals firing). The "pain" of implementation is most valuable when everyone's chasing the same names.

## Verdict: FAILED (opposite) — Dead-end D077

- Contrarian hypothesis fails completely
- Liquid is WORSE in high_breadth, confirming the crowd ignores tradable stocks in crowded markets
- Blocked stocks fill the void even more when crowd is active — opposite of contrarian intuition

**Next**: #85 C27 × Vol Interaction (blocked × vol_expansion vs vol_contraction)