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

## F152: The Continuation / Hold-vs-Exit Hazard Family Fails At The First Predictive Gate; Changing The Exit Target Alone Does Not Yet Create Useful Exit Alpha On Current Data (2026-03-29, Session 72)

Session 72 tested a genuinely different high-level hypothesis family:
- not a new sell rule
- not a new threshold stack
- but a new target:
  - “should this legally sellable held position be kept for one more cycle?”

The branch built continuation labels from the frozen `full_library` selector:
- forward `5`-day stock return minus forward `5`-day benchmark return
- label = `1` when that hold advantage is positive

Three dev-trained continuation models were tested:
- `continuation_core`
- `continuation_plus_thesis`
- `continuation_plus_rank`

Best result:
- `continuation_core`
- validation AUC `0.5060`
- validation top-quintile hold advantage `-0.0058`
- confirmation AUC `0.5106`
- confirmation top-quintile hold advantage `-0.0081`

Other models were not better:
- `continuation_plus_rank`
  - validation AUC `0.5031`
  - confirmation AUC `0.5230`
  - top-quintile hold advantage still negative
- `continuation_plus_thesis`
  - validation AUC `0.4996`
  - confirmation AUC `0.5225`
  - top-quintile hold advantage still negative

Because `H218` failed, the next two rungs were skipped:
- `H219`: continuation exit bands
- `H220`: sticky compatibility

**Key finding:** a materially different exit target is not enough by itself. On current daily data, the hold-vs-exit continuation family does not contain useful predictive edge.

**Implication:** close `H218-H220` and do not retune it on the same locked window. The next honest exit branch must now depend on a genuinely new data family, not just a new formulation over the same daily inputs.
