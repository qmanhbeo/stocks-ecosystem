# Session 113 Log

## Objective
Test the high-priority gap-failure exhaustion branch while the LLM extractor continues in the background, using the smallest honest combined H130/H133-style audit.

This session did not change the live branch.
It did not read `2026+`.

## What changed

Added:
- `analysis/h283_gap_failure_exhaustion_standalone.py`

Saved artifacts:
- `artifacts/run_summaries/20260405_222642_h283_gap_failure_exhaustion_standalone_signal.json`

### H283 - Gap-Failure Exhaustion Audit
**Hypothesis:**
A failed gap-acceptance state becomes stronger when gated by the compression/blow-off regime from H133.

**Command / code:**
`conda run -n stocks python analysis/h283_gap_failure_exhaustion_standalone.py`

**Inputs:**
- `data/features/xs_barrier_vol_1d_hose_full.parquet`
- `data/stock/gia_lich_su_<TICKER>_1D.parquet`
- `data/features/sector_classification.parquet` via redundancy checks against the candidate matrix

**Saved artifact:**
`artifacts/run_summaries/20260405_222642_h283_gap_failure_exhaustion_standalone_signal.json`

| Metric | Value | Note |
|--------|-------|------|
| best variant | `xs_gap_failure_exhaustion_3` | strongest gap-failure combo |
| best IC | `+0.0371` | strong standalone content |
| best positive years | `10 / 11` | consistent |
| best corr vs S1 | `+0.233` | still within gate |
| best max candidate corr | `+0.796` | fails redundancy gate badly |
| merged rows | `824,689` | full support on the 2015-2025 window |
| tickers | `394` | full HOSE universe |
| dates | `2,748` | full support on the 2015-2025 window |
| overlap verdict | `dup` | all three variants collapse onto `C13` |

**Result:**
The gap-failure construction is real and predictive, but it is not a new independent signal. All three variants overlap the existing compression blow-off axis too strongly, with the best variant still mapping to `c13_compress_blowoff_2`.

**Verdict: MIXED**

## Branch decision

Do not promote the generic gap-failure exhaustion blend.
The next materially different branch while LLM extraction continues is `H136` sector-conditioned blow-off reversal.

## Validation

Completed before the run:
- `conda run -n stocks python -m py_compile analysis/h283_gap_failure_exhaustion_standalone.py`

Completed for the experiment:
- `conda run -n stocks python analysis/h283_gap_failure_exhaustion_standalone.py`
- read `artifacts/run_summaries/20260405_222642_h283_gap_failure_exhaustion_standalone_signal.json`

Verdict:
- `H283`: **MIXED**
