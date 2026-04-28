# Session 42 Log (2026-03-28)

## Summary

Session 42 closed the two queued OHLCV-only tests from Session 41 and cleaned up the signal registry.

**Net result:** H123 passed as a 60d continuation signal and was promoted to C11. H124 passed standalone
in its low-beta orientation, but it failed the independence rule because it overlaps heavily with C10
illiquidity, so it was rejected for RL promotion.

## Quick Log Inventory

- H121 and H122 remain documented in `notes/session_40_log.md` and `notes/session_41_log.md`
- H123 and H124 were created and run in this session; they are no longer pending
- H124 was checked against C10 and failed the orthogonality rule, so it is not part of the RL matrix
- `notes/findings.md` is now an index; new findings continue in the padded chunk file `notes/findings-061-090.md`

## Experiments

### H123 — 3-Month Reversal Test -> C11 PASS

**Script:** `analysis/h123_3m_reversal_standalone.py`
**Artifact:** `artifacts/run_summaries/20260328_121637_h123_3m_reversal_standalone_signal.json`

The reversal hypothesis did not hold. The signal that passed was the raw 60d excess-return rank,
which is a medium-term continuation signal.

| Feature | IC | Pos Years | Corr S1 | Gate |
|---------|-----|-----------|---------|------|
| xs_ret_60d_lag_rank | +0.0101 | 9/11 | +0.008 | **PASS** |
| xs_reversal_60d | -0.0101 | 2/11 | -0.008 | fail |

**Interpretation:** 60d relative strength persists after the short-term reversal window has faded.
This is an orthogonal continuation axis, not a reversal pocket.

**Promoted:** `xs_ret_60d_lag_rank` -> **C11**

---

### H124 — Beta Regime Test -> REJECTED

**Script:** `analysis/h124_beta_regime_standalone.py`
**Artifact:** `artifacts/run_summaries/20260328_121804_h124_beta_regime_standalone_signal.json`

The low-beta orientation passed standalone, but it did not meet the independence requirement.

| Feature | IC | Pos Years | Corr S1 | Gate |
|---------|-----|-----------|---------|------|
| xs_beta_60d_rank | -0.0131 | 4/11 | +0.005 | fail |
| xs_low_beta_60d | +0.0131 | 7/11 | -0.005 | PASS (standalone) |

**Pairwise check:** `corr(xs_low_beta_60d, C10) = +0.5524`

**Interpretation:** beta is mostly a liquidity/size proxy here. Once C10 is in the library,
H124 does not add a distinct RL axis, so it stays rejected.

---

## RL Matrix Update

`data_tools/build_rl_signal_matrix.py` now exports:

- `c10_illiq_level_rank`
- `c11_ret_60d_lag_rank`

**Output:** `data/features/xs_rl_signal_matrix.parquet`

**Shape:** `826,404 x 13`

Coverage:

- `c10_illiq_level_rank`: 823,048 / 826,404 rows
- `c11_ret_60d_lag_rank`: 823,990 / 826,404 rows

The H124 low-beta signal was not kept in the matrix because it overlaps too strongly with `C10`.

## Pairwise Check

`C11` remains orthogonal to the existing candidate set.

| Pair | Spearman rho |
|------|--------------|
| C11 vs C4 | -0.0742 |
| C11 vs C5 | -0.0346 |
| C11 vs C6 | -0.1180 |
| C11 vs C7 | +0.0431 |
| C11 vs C8 | +0.1684 |
| C11 vs C9 | -0.1179 |
| C11 vs C10 | -0.0686 |

## Handoff Notes

- Keep `C11` in the RL matrix and signal library
- Keep `H124` in the rejected table
- Future OHLCV searches should start from the orthogonalized beta / longer-horizon continuation ideas in `notes/live_state.md`
- `notes/findings-061-090.md` now holds F85 and F86 for this session
