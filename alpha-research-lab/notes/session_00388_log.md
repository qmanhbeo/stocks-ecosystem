# Session 388 — H106 Signal Pair Synergy Matrix

**Date**: 2026-05-17

## Hypothesis

F445 found "2+ signals" works (IC 0.2445), but which SPECIFIC pairs have strongest synergy? C23+C24 vs C23+C25 vs C24+C25 etc. Some pairs redundant, others complementary.

**Pass criterion**: Best pair IC > composite_2+ baseline (0.2445) by > +0.01

## Command

`python analysis/h106_signal_pair_synergy.py`

## Results

| State | IC | Rows | Positive Years |
|-------|-----|------|----------------|
| composite_2plus (F445) | 0.2445 | 29,542 | 11/11 |
| c23_c26 | 0.2396 | 13,281 | 11/11 |
| c24_c26 | 0.2281 | 5,310 | 11/11 |
| c23_c24 | 0.2280 | 8,736 | 11/11 |
| c23_c25 | 0.1954 | 15,693 | 11/11 |
| c25_c26 | 0.1636 | 2,858 | 11/11 |
| c24_c25 | NaN | 0 | 0/11 |

## Key Finding: FAILED

**No specific pair beats composite_2+**:
- Best pair (c23_c26): IC = 0.2396 (-0.0049 vs composite_2+)
- All pairs are WORSE than the generic "any 2+ signals" (0.2445)

**Mechanism insight**: The synergy is in having multiple signals, NOT in which specific signals combine. The specific pair doesn't matter - any 2+ signals together creates the alpha. The "AND" logic of multiple signals is the key, not the composition.

This is a dead-end - specific pair synergy is not the mechanism.

## Verdict: FAILED (Dead-end D083)

## Next Steps

- H107 (Signal Order as Hidden State) - which signal fires first? May still be worth testing
- H108 (Multi-Signal × Blocked Triple) - F445 + F438/F444
- Or move to orthogonal amplifier combos (H109 triple-factor)

---

**Finding**: F449 (FAILED) - No specific pair beats composite_2+. Best pair c23_c26 = 0.2396 (-0.0049). Synergy is in "2+ signals" logic, not specific composition. Dead-end D083.