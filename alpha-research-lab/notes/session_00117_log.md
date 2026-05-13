# Session 117 Log — 2026-05-08

## H465: cross_signal_orthogonality_audit

**Decision: MIXED**

### Hypothesis
Test orthogonality of C20/C21/C22 — do combos add incremental IC beyond each alone?

### Results

**Individual signals:**
- C21a buy_heavy_accel_expansion: IC=0.2234
- C21b sell_heavy_decel_expansion: IC=0.2206
- C22 approaching_ceiling: IC=0.2166
- C20 buy_heavy_expansion: IC=0.2104

**Combos:**
- C21a×C22: IC=0.2119 (lift vs max: **-0.0115** — WORSE)
- C20×C22: IC=0.1997 (lift vs max: **-0.0169** — WORSE)
- C21a×C22×C20: IC=0.2119 (same as 2-way)
- C21a×C21b: 0 rows (mutually exclusive — can't be both)
- C21b×C22: 564 rows only (very sparse)

### Key insight
**Signals are NOT orthogonal — they share the vol_expansion regime driver.**
All combos are WORSE than the best individual signal. vol_expansion is the common factor making signals redundant when combined. Each signal captures the same vol-expansion amplification.

### What this means
- Do NOT combine C21/C22/C20 as a composite signal
- Each signal works as an independent standalone condition
- The signals are additive in the portfolio sense (different days they fire), not combinatorial
- C23 (illiquidity_expansion) should also NOT be combined with C21/C22 in the same entry

### Documenting memory

## H464: time_of_day_pattern

**Decision: PASSED (weak signal)**

### Hypothesis
VN market has T+2 settlement patterns, Monday effect, month-end, quarter-start.

### Results
- Monday: IC=0.1434 (+0.0132 lift) — real but modest
- Friday: IC=0.1119 (-0.0183 lift) — negative
- Month-end: IC=0.1367 (+0.0065 lift)
- January: IC=0.1343 (+0.0041 lift)
- Quarter-start: IC=0.1250 (-0.0052 lift)

### Key insight
Monday effect is the strongest calendar pattern (+0.0132 IC). Small but consistent. Not strong enough for standalone promotion but useful as weak RL context.

### Session summary
- H463 PASSED: C23 new signal — illiquidity_expansion IC=0.2616
- H464 PASSED (weak): Monday effect IC=0.1434 (+0.0132)
- H465 MIXED: signals NOT orthogonal — combos worse than individuals