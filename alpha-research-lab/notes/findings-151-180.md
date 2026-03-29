# Findings 151-180

## F151: Genuinely New Exit Families Still Do Not Beat The Existing H211 Strength-Exhaustion Winner; The Current Exit Branch Is More Clearly Closed On Existing Data (2026-03-29, Session 71)

Session 71 reopened exit research the right way:
- not by retuning `H207-H213`
- not by changing thresholds on the existing exhaustion winner
- but by testing genuinely different post-entry hypothesis families against the current H211 anchor

New families tested:
- `H214`: thesis inconsistency
- `H215`: failed follow-through
- `H216`: time under water

Current anchor coming in:
- `strength_exhaustion__return_since_entry_threshold_0p15__score_drop_threshold_0p05`
- validation relative `+54.45%`
- validation IR `1.17`
- confirmation relative `-4.70%`

### H214 — Thesis inconsistency
Best new variant:
- `thesis_inconsistency__score_drop_threshold_0p05__thesis_drop_threshold_0p1`
- validation relative `+28.44%`
- validation delta vs H211 `-26.01%`
- confirmation relative `-13.78%`

This was a clear fail.

### H215 — Failed follow-through
Best new variant:
- `failed_followthrough__current_return_threshold_0p0__grace_days_2__peak_return_threshold_0p03__score_drop_threshold_0p0`
- validation relative `+56.39%`
- validation delta vs H211 `+1.95%`
- validation IR delta `+0.0448`
- confirmation relative `-5.22%`
- confirmation delta vs H211 `-0.52%`

This was a real near-miss, but it still failed the locked promotion gate.

### H216 — Time under water
Best new variant:
- `time_under_water__grace_days_5__peak_return_threshold_0p03__underwater_days_threshold_3`
- validation relative `+55.30%`
- validation delta vs H211 `+0.85%`
- validation IR delta `+0.2334`
- confirmation relative `-39.36%`
- confirmation delta vs H211 `-34.66%`

This was a hard confirmation fail.

### H217 — Sticky compatibility
Skipped by rule:
- no genuinely new family displaced the H211 anchor
- so there was no new exit-family winner worth testing under the frozen sticky branch

**Key finding:** the current best exit-alpha evidence remains the original H211 strength-exhaustion family. The newer, genuinely different post-entry families do not beat it under the locked protocol.

**Implication:** close the current exit branch more firmly. Do not reopen it with more threshold tuning on the same data. The next honest exit branch now requires either:
- a genuinely new data family, or
- a materially different exit hypothesis family that is not a variant of H211/H214-H216.
