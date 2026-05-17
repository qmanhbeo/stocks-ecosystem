# Session 387 — H105 Multi-Signal × Persistence Stacking

**Date**: 2026-05-17

## Hypothesis

F445 (composite_2+ = IC 0.2445) + F441/F442 (persistence/accumulation) - are sustained multi-signal stocks even stronger?

**Pass criterion**: composite_2+ × persistence/accumulation beats composite_2+ alone by > +0.01 IC

## Command

`python analysis/h105_multi_signal_persistence.py`

## Results

| State | IC | Rows | Positive Years |
|-------|-----|------|----------------|
| composite_2plus_accum_q4 | **0.2506** | 2,498 | 11/11 |
| composite_2plus (F445) | 0.2445 | 29,542 | 11/11 |
| composite_2plus_persist_q4 | 0.2424 | 16,570 | 11/11 |
| accumulation_q4 | 0.1921 | 19,751 | 11/11 |
| persist_q4 | 0.1760 | 197,217 | 11/11 |
| duration_8pl | 0.1724 | 5,902 | 11/11 |
| all_rows (baseline) | 0.1298 | 809,019 | 11/11 |
| composite_2plus_duration_8pl | NaN | 598 | 0/11 |

## Lifts vs composite_2+ alone (0.2445)

- composite_2plus_accum_q4: **+0.0061** (marginal, below +0.01 threshold)
- composite_2plus_persist_q4: **-0.0021** (WORSE - hurts multi-signal!)
- composite_2plus_duration_8pl: sparse, NaN

## Key Finding: MIXED (marginal)

1. **Accumulation Q4** provides marginal improvement: IC 0.2506 vs 0.2445 = +0.0061 lift. Below the +0.01 threshold but positive.
2. **Persistence Q4** actually HURTS the multi-signal: -0.0021. Opposite of expectation.
3. The two persistence mechanisms (accumulation vs persistence ratio) have OPPOSITE effects when combined with multi-signal.

**Mechanism insight**: Multi-signal already captures strong alpha; adding persistence filter introduces noise that degrades the signal. Accumulation (cumulative 30d) works slightly better than persistence ratio (rolling 9d).

## Verdict: MIXED (marginal)

- Not a promotion-worthy signal (lift below +0.01)
- Persistence filter HURTS multi-signal (negative lift)
- Accumulation provides marginal improvement
- Duration 8+ too sparse with multi-signal

## Next Steps

- Document as dead-end for H105
- Consider H106 (Signal Pair Synergy Matrix) - which specific signal pairs have strongest synergy
- Continue with orthogonal amplifier combinations from F437/F440/F441/F442

---

**Finding**: F448 (MIXED) - composite_2+ × accumulation_q4 = 0.2506 (+0.0061 vs composite_2+), below +0.01 threshold. Persistence ratio hurts multi-signal.