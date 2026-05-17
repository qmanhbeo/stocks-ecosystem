# Session 376 - H586 Blocked Duration Sweet Spot

**Date**: 2026-05-17

**Hypothesis**: Persistence of being blocked (like active state duration) modulates C27 quality.

**Command**: `python analysis/h586_blocked_duration_sweet_spot.py`

**Saved artifact**: `artifacts/run_summaries/20260517_165545_blocked_duration_sweet_spot_research_branch.json`

## Results

| State | IC | Rows | Positive Years |
|-------|-----|------|----------------|
| duration_2_3d | 0.1635 | 1,930 | 1/1 |
| duration_1d | 0.1516 | 13,778 | 9/9 |
| blocked_either (C27) | 0.1477 | 15,848 | 10/10 |
| all_rows | 0.1302 | 826,404 | 11/11 |
| duration_4_7d | NaN | 140 | 0/0 |
| duration_8pl | NaN | 0 | 0/0 |

## Key Finding: FAILED (sparse) — but new insight from 2-3d

- blocked_either = 15,848 rows: 87% are newly blocked (1d), 12% are 2-3d
- duration_8pl = 0 rows (no stocks stay blocked for 8+ consecutive days)
- **duration_2_3d IC=0.1635 vs duration_1d IC=0.1516 = +0.0119 diff (> +0.01!)**
- But duration_2_3d is sparse: only 1,930 rows, 1/1 positive years (dev-only)
- The pattern mirrors H534: sustained > fresh, but C27 durations are much shorter

**Key contrast**: C27 blocked stocks resolve quickly (most 1d). Active state stocks can stay active for weeks (H534: 8d+ = strongest). Blocked is more transient — stocks are rarely blocked for long because trading halts resolve.

**Sparsity insight**: Blocked state is episodic but short. The 2-3d sub-state shows potential but lacks enough data for validation.

## Verdict: FAILED (sparse) — Dead-end D079

- 8d+ duration doesn't exist for blocked stocks (too transient)
- 2-3d shows promising pattern (+0.0119 vs 1d) but sparse (1/1 positive years)
- C27 queue exhausted. All remaining items (#68-87) are either dead-ends, blocked, or not applicable.

**C27 Queue Summary:**
- F438: Implementation pain = positive signal (standalone)
- F439: C27 destroys C24 signal (negative router)
- D074-D079: 6 dead-ends from 8 tested C27 amplifier/router/combination experiments

**Next**: Move to fresh bright-mind queue. C27 discovery is complete.