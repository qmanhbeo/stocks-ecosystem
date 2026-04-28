# Session 185 Log - Residual Long-Horizon Reversal Queue Cleanup (2026-04-28)

## Objective

Continue the evergreen loop with data already available on disk:
- keep the live alpha branch unchanged
- avoid `2026` predictive use
- avoid GPU / Ollama / PhoBERT training jobs
- resolve the stale `H137` queue idea: sign-flipped 90d/120d residual after
  removing the promoted C11 60d continuation axis

This session stayed long-only.
It did not use `2026` for predictive tuning.

## Queue audit

While selecting the next ready hypothesis, the signal library still listed:
- `H135: Gap-failure exhaustion`
- `H136: Sector-conditioned blow-off reversal`
- `H137: Residual long-horizon reversal`

The first two were already solved in later sessions:
- `H283` tested gap-failure exhaustion and found it predictive but redundant
  with the existing C13 compression blow-off axis
- `H284` tested sector-conditioned blow-off and parked it because the sector /
  ceiling gates did not improve H133

This pass only needed to run the still-unresolved residual long-horizon item.

## Experiment

### H346 - Residual Long-Horizon Reversal

**Hypothesis:**
H126 showed raw 90d/120d continuation is redundant with C11. After removing
C11 cross-sectionally, the leftover 90d/120d residual may work in the opposite
direction as a distinct reversal axis.

**Command / code:**
`python analysis/h346_residual_long_horizon_reversal.py`

**Inputs:**
- local OHLCV panels under `data/stock/`
- VNINDEX close series
- `data/features/xs_barrier_vol_1d_hose_full.parquet`
- `data/features/xs_rl_signal_matrix.parquet` for redundancy annotation

**Saved artifact:**
`artifacts/run_summaries/20260428_071334_h346_residual_long_horizon_reversal_research_branch_residual_long_horizon_reversal.json`

| Metric | Value | Note |
|--------|-------|------|
| verdict | `FAILED` | no residual reversal or continuation control clears the standalone gate |
| merged rows | `821,308` | 2015-2025 S1 universe |
| merged tickers / dates | `394 / 2,748` | excludes `2026` through S1 loader |
| best feature | `xs_ret_120d_resid_c11_continuation_rank` | continuation control, not the hypothesized reversal |
| best avg IC | `+0.0072` | below `0.01` gate |
| best positive years | `10 / 11` | directionally consistent but too weak |
| best S1 corr | `-0.0061` | orthogonal but not strong enough |
| 120d residual reversal IC | `-0.0072` | hypothesized sign is wrong |
| 90d residual reversal IC | `-0.0063` | hypothesized sign is wrong |

**Result:**
The sign-flipped residual long-horizon thesis fails. The residual continuation
controls are weakly positive and orthogonal, but below the standalone IC gate.
This closes the stale H137 queue item rather than creating a new C-signal.

**Verdict: FAILED**

## Branch decision

Close the old OHLCV queue entries:
- H135 was already closed by H283
- H136 was already closed by H284
- H137 is now closed by H346

Do not tune more 90d/120d residual variants unless a materially different
target or portfolio contract is introduced.

## Memory changes

Updated:
- `notes/live_state.md`
- `notes/findings-271-300.md`
- `notes/signal_library.md`

Added:
- `analysis/h346_residual_long_horizon_reversal.py`

Durable finding:
- `F286`

## Verification

Completed:
- `python -m py_compile analysis/h346_residual_long_horizon_reversal.py`
- `python analysis/h346_residual_long_horizon_reversal.py`

## Next step

Continue the evergreen loop with a genuinely unresolved existing-data branch.
Do not rerun H135/H136/H137 from the stale signal-library queue.
