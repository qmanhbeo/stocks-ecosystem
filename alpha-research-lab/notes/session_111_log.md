# Session 111 Log

## Objective
Run the next possible queued branch after H281 failed:
- `H282`: test the simple momentum-disagreement construction
- `xs_mom_disagree = xs_proba_rank - xs_reversal_1d_rank`
- check whether the disagreement is a new standalone signal or just a blend of the existing momentum and reversal axes

This session did not change the live branch.
It did not read `2026+`.

## What changed

Added:
- `analysis/h282_momentum_disagreement_audit.py`

Saved artifacts:
- `artifacts/run_summaries/20260405_210858_h282_momentum_disagreement_audit_signal_library_momentum_disagreement.json`
- `artifacts/run_summaries/20260405_210858_h282_momentum_disagreement_summary.json`
- `artifacts/portfolio_baselines/20260405_210858_h282_momentum_disagreement_results.parquet`

### H282 - Momentum Disagreement Audit
**Hypothesis:**
The rank difference between the primary momentum signal and the 1-day reversal signal adds a new orthogonal alpha axis.

**Command / code:**
`conda run -n stocks python analysis/h282_momentum_disagreement_audit.py`

**Inputs:**
- `data/features/xs_barrier_vol_1d_hose_full.parquet`
- `data/features/xs_shortterm_reversal.parquet`
- evaluation window:
  - `2015-2025`

**Saved artifact:**
`artifacts/run_summaries/20260405_210858_h282_momentum_disagreement_summary.json`

| Metric | Value | Note |
|--------|-------|------|
| candidate | `xs_mom_disagree` | `xs_proba_rank - xs_reversal_1d_rank` |
| avg IC | `+0.0854` | strong standalone predictive content |
| positive years | `11 / 11` | perfectly consistent |
| corr vs S1 | `+0.5333` | fails orthogonality gate |
| corr vs C9 | `-0.6260` | fails orthogonality gate |
| rows | `825,481` | full merged support |

**Result:**
The disagreement feature is real, but it is not new information. It is too correlated with both S1 and C9 to qualify as a standalone library signal.

**Verdict: MIXED**

## Branch decision

Do not promote `xs_mom_disagree` as a new signal.
If this idea is revisited, it should be as a residualized or interaction-only construct, not as the raw subtraction.

## Validation

Completed before the run:
- `conda run -n stocks python -m py_compile alpha-research-lab/analysis/h282_momentum_disagreement_audit.py`

Completed for the experiment:
- `conda run -n stocks python analysis/h282_momentum_disagreement_audit.py`
- read `artifacts/run_summaries/20260405_210858_h282_momentum_disagreement_summary.json`

Verdict:
- `H282`: **MIXED**
