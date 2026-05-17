# Session 381 Log — H592 Signal Accumulation Intensity

**Date:** 2026-05-17
**Hypothesis:** H592 - Signal Accumulation Intensity
**Status:** PASSED

## Hypothesis

F441 (Session 380) showed sustained presence in active state = stronger signal.
Now test: cumulative signal intensity - total days in active state in last 30 days.

**Pass criterion:** Q4 (highest accumulation 75-100%) > Q1 (lowest) by > +0.01 IC lift

## Results

| State | IC | Rows | Positive Years |
|-------|-----|------|----------------|
| accumulation_q4 (high 20+ days) | 0.2006 | 8,001 | 11/11 |
| accumulation_q3 | 0.1915 | 37,950 | 11/11 |
| accumulation_8pl (8+ days) | 0.1819 | 187,472 | 11/11 |
| accumulation_q2 | 0.1775 | 141,521 | 11/11 |
| active_only | 0.1648 | 127,566 | 11/11 |
| all_rows (baseline) | 0.1302 | 826,404 | 11/11 |
| accumulation_q1 (low 0-7 days) | 0.1137 | 638,538 | 11/11 |

**Key lifts:**
- Q4 vs baseline: **+0.0704** (> +0.01 threshold) ✓
- Q4 vs Q1: **+0.0869** (> +0.01 threshold) ✓
- accumulation_8pl vs baseline: **+0.0517** (> +0.01 threshold) ✓

## Verdict: PASSED

Signal accumulation intensity is a REAL effect. Stocks with sustained presence in active state (20+ days in last 30) have much stronger alpha than transient activation.

This confirms and extends F441:
- F441: duration in current active state (consecutive days)
- H592: cumulative days in last 30 days (non-consecutive)

Both mechanisms work - persistence in active state predicts stronger signal.

## Next Steps

- Update findings with F442
- Consider H93 (cofire-persistence interaction) next