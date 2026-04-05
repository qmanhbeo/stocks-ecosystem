# Session 114 Log

## Objective
Test whether the H133 compression blow-off reversal gets stronger inside hot sectors or recent ceiling clusters.

This session did not change the live branch.
It did not read `2026+`.

## What changed

Added:
- `analysis/h284_sector_conditioned_blowoff_reversal_standalone.py`

Saved artifacts:
- `artifacts/run_summaries/20260405_222947_h284_sector_conditioned_blowoff_reversal_standalone_signal.json`

### H284 - Sector-Conditioned Blow-Off Reversal Audit
**Hypothesis:**
The H133 compression blow-off reversal state should strengthen when gated by hot sectors or recent ceiling clusters.

**Command / code:**
`conda run -n stocks python analysis/h284_sector_conditioned_blowoff_reversal_standalone.py`

**Inputs:**
- `data/features/xs_barrier_vol_1d_hose_full.parquet`
- `data/features/xs_rl_signal_matrix.parquet`
- `data/features/xs_sector_rotation_daily.parquet`

**Saved artifact:**
`artifacts/run_summaries/20260405_222947_h284_sector_conditioned_blowoff_reversal_standalone_signal.json`

| Metric | Value | Note |
|--------|-------|------|
| base local feature | `h284_c13_compress_blowoff_2` | local copy of the H133 reversal state |
| base IC | `+0.0350` | strong, but identical to existing `C13` |
| hot-sector interaction IC | `-0.0010` | hot-sector gating weakens the state |
| ceiling-cluster interaction IC | `+0.0137` | standalone-positive but redundant with `c7_ceiling_count_5d` |
| hot-and-cluster interaction IC | `+0.0095` | below the standalone gate |
| hot-sector subset c13 IC | `+0.0198` | weaker than the unconditional state |
| ceiling-cluster subset c13 IC | `-0.0512` | outright negative |
| hot-and-cluster subset c13 IC | `-0.0542` | outright negative |
| merged rows | `823,666` | full 2015-2025 support |
| tickers | `393` | one ticker filtered out by intersection coverage |

**Result:**
The sector-conditioning idea does not create a new axis. Hot-sector gating makes the state worse, and the ceiling-cluster version is still just a repackaged version of the existing ceiling-count signal.

**Verdict: REJECTED_AS_REDUNDANT**

## Branch decision

Park `sector-conditioned blow-off`.
The next materially different queue item is `5d-label-contract`.

## Validation

Completed before the run:
- `conda run -n stocks python -m py_compile analysis/h284_sector_conditioned_blowoff_reversal_standalone.py`

Completed for the experiment:
- `conda run -n stocks python analysis/h284_sector_conditioned_blowoff_reversal_standalone.py`
- read `artifacts/run_summaries/20260405_222947_h284_sector_conditioned_blowoff_reversal_standalone_signal.json`

Verdict:
- `H284`: **REJECTED_AS_REDUNDANT**
