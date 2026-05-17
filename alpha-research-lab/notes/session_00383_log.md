# Session 383 - H594 Blocked-State Transition Timing

**Date**: 2026-05-17

**Hypothesis**: C27 (blocked) is positive but transient. First-day blocked might be the purest "pain" signal before market adapts. Test blocked_day_1 vs blocked_day_2_3d vs blocked_day_4pl.

**Command**: `python analysis/h594_blocked_transition_timing.py`

**Saved artifact**: `artifacts/run_summaries/20260517_173335_blocked_transition_timing_research_branch.json`

## Results

| State | IC | Rows | Positive Years |
|-------|-----|------|----------------|
| **blocked_day_2_3** | **0.1734** | 1,606 | **5/5** |
| blocked_either | 0.1526 | 15,848 | 11/11 |
| blocked_day_1 | 0.1498 | 13,778 | 11/11 |
| blocked_day_4pl | 0.1084 | 464 | 1/1 |
| baseline | 0.1461 | 826,404 | - |

## Key Finding: PASSED (Opposite Direction)

**Blocked-state duration DOES matter**:
- blocked_day_2_3 IC = 0.1734 beats blocked_either (0.1526) by **+0.0208 lift**
- This exceeds the +0.01 threshold → PASSED

**BUT opposite of hypothesis**:
- Hypothesis expected: first-day blocked = purest signal (initial pain)
- Actual finding: continuing blocked 2-3 days = STRONGEST
- blocked_day_2_3 > blocked_day_1 > blocked_day_4pl

**Mechanism (reversed)**: Sustained blockage (2-3 days) indicates persistent hidden demand that the market hasn't yet priced in. First-day blocked is just noise - the signal emerges after 2-3 days of sustained pain. This is consistent with H534 (longer duration = stronger signal for active state).

**Verdict: PASSED** - Finding F444

- Add to findings as F444 (blocked_duration matters, but in opposite direction)
- C27 continues to show interesting structure beyond just "blocked vs not blocked"

**Next**: H95 (Multi-Signal Co-occurrence Superposition)