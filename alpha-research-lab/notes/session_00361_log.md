# Session 361 - H562 Breadth Velocity (Change Rate)

**Date**: 2026-05-17

**Hypothesis**: Test if breadth CHANGE RATE (velocity) is a hidden regime. Not how LOW breadth is, but how FAST it's contracting. Rapid collapse = regime shift = stronger alpha.

**Command**: `python analysis/h562_breadth_velocity.py`

**Saved artifact**: `artifacts/run_summaries/20260517_154848_breadth_velocity_research_branch.json`

## Results

| State | IC | Positive Years |
|-------|-----|----------------|
| contracting (breadth decreasing) | 0.1310 | 11/11 |
| steady (breadth stable) | 0.1303 | 11/11 |
| expanding (breadth increasing) | 0.1297 | 11/11 |
| low_breadth | 0.1073 | 3/4 |

## Key Finding: FAILED

**Velocity effect is negligible**:
- Contracting IC = 0.1310
- Expanding IC = 0.1297
- Velocity lift = **+0.0013** (far below +0.01 threshold)

All three velocity states (contracting, steady, expanding) are nearly identical to baseline (0.1246). The rate of breadth change does NOT capture hidden regime structure.

## Verdict: FAILED

- Velocity lift is only +0.0013 - essentially noise
- H525 was about absolute breadth level, not change rate
- This is a dead-end - velocity is not a hidden regime detector

**Next**: The current queue from handoff is exhausted (#60, #66, #67 all tested). Return to bright-mind queue for next ideas.