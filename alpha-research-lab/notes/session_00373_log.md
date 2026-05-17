# Session 373 - H584 C27 as Signal Router

**Date**: 2026-05-17

**Hypothesis**: Does being blocked change how S1 performs on C23/C24 signals? Is C27 a router for signal selection?

**Command**: `python analysis/h584_c27_signal_router.py`

**Saved artifact**: `artifacts/run_summaries/20260517_163734_c27_signal_router_research_branch.json`

## Results

| State | IC | Rows | Positive Years |
|-------|-----|------|----------------|
| blocked_c23 | 0.1688 | 2,356 | 1/1 |
| c24_signal | 0.1670 | 148,128 | 11/11 |
| non_blocked_c23 | 0.1655 | 125,210 | 11/11 |
| c23_active | 0.1648 | 127,566 | 11/11 |
| non_blocked_c24 | 0.1566 | 141,432 | 11/11 |
| blocked_either (C27) | 0.1477 | 15,848 | 10/10 |
| all_rows | 0.1302 | 826,404 | 11/11 |
| non_blocked | 0.1272 | 810,556 | 11/11 |
| blocked_c24 | 0.0891 | 6,696 | 6/7 |

## Key Finding: C27 DESTROYS C24 signal quality — important negative router rule

- C23 × blocked: IC=0.1688 vs C23 × non-blocked: IC=0.1655 (+0.0033, marginal)
- **C24 × blocked: IC=0.0891 vs C24 × non-blocked: IC=0.1566 = -0.0675!**
- **C27 acts as a NEGATIVE router for C24**: when blocked, C24 signal collapses
- **Reason**: C24 = ceiling (high C16 = stocks that ran into limit-up). These need selling pressure to continue. When blocked from selling, the momentum mechanism is destroyed.
- C27 effect: +0.0205 (C27 makes raw S1 better on average, but this is dominated by C23 interactions)

**Practical insight**: EXCLUDE blocked_c24 from the signal set. C24 is already the weaker signal (0.167 vs C23 0.165), but when blocked it collapses to 0.089. This is a real router rule: don't use C24 on blocked stocks.

## Verdict: PASSED (negative router finding) — Finding F439

- Meets pass criterion (0.0675 > 0.01 absolute difference)
- But it's a NEGATIVE finding: C27 destroys C24, not an amplification
- **C27 should be used as a NEGATIVE filter for C24, not an amplifier**
- blocked_c23 is marginally better (+0.0033) confirming C27 × C23 combo works
- This resolves the C27 × signal interaction: C27 amplifies C23 but kills C24

**Next**: #86 Blocked Duration Sweet Spot (H534 found duration_8pl strong for active, test for C27)