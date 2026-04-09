# Session 140 Log — Criticality Order Parameter (2026-04-09)

## Objective

Formalize and test the next current-data branch after `H319`:
- `H320` criticality-order-parameter

Question:
- does a raw market-criticality field explain next-cycle selector efficacy
  beyond the incumbent short-memory activation state?

This session did not change the live branch.
It stayed long-only.
It did not read `2026+`.

---

## What changed

Added one bounded research script:
- `analysis/h320_criticality_order_parameter.py`

### H320 - Criticality Order Parameter
**Hypothesis:**
Daily market-criticality proxies derived from raw OHLCV, limit clustering,
gap/intraday alignment, synchrony, and dispersion should explain selector
efficacy beyond the existing `full_recent_cycle_relative_return_ewm3`
activation-memory baseline. If the branch is real, at least one criticality
order parameter should show stable validation and `2025` residual lift or
condition the incumbent high-efficacy state.

**Command / code:**
`python analysis/h320_criticality_order_parameter.py`

**Inputs:**
- `data/features/activation_meta_daily.parquet`
- raw daily stock OHLCV under `data/stock/`

**Saved artifact:**
`artifacts/run_summaries/20260409_153718_criticality_order_parameter_research_branch_criticality_order_parameter.json`

| Metric | Value | Note |
|--------|-------|------|
| rows | `2,748` | daily activation rows after trailing-z warmup / label filtering |
| baseline | `full_recent_cycle_relative_return_ewm3` | incumbent short-memory activation state |
| baseline validation / confirmation rho vs target | `+0.6126 / +0.6557` | still very strong |
| best feature | `gap_alignment_pressure` | high gap/intraday same-direction pressure |
| best feature decision | `MIXED` | weak residual trace only |
| best validation / confirmation residual rho | `-0.0431 / -0.1246` | high state is adverse, not positive |
| best validation / confirmation residual lift | `-0.0077 / -0.0083` | high minus not-high residual |
| best validation / confirmation baseline-conditioned residual lift | `-0.0054 / -0.0410` | high baseline plus high gap-alignment vs high baseline only |

**Result:**
The criticality branch did not produce a promotable activation overlay. The
incumbent recent-efficacy memory already explains most of the selector-efficacy
variation. The only stable-looking trace was adverse: high gap-alignment
pressure tends to subtract residual efficacy, including inside the incumbent
high-baseline state. That is directionally interesting as offline meta-state
evidence, but it is not strong or broad enough to replace, augment, or reopen
the activation gate family.

**Verdict: MIXED**

---

## Branch decision

`H320` does not justify a new criticality activation branch on the current data:
- keep the adverse `gap_alignment_pressure` trace as offline evidence only
- keep the live activation memory baseline unchanged
- do **not** open a raw OHLCV criticality router or additive overlay

Next honest current-data queue item:
- `hawkes-disclosure-cascade`
  - the current-data complex-systems activation idea is now narrowed
  - the next wild-frontier branch should return to event/news timing with a
    self-exciting cascade representation

Next honest acquisition queue remains:
- `historical-foreign-flow-source`

---

## Validation

Completed during the pass:
- ran `python -m py_compile analysis/h320_criticality_order_parameter.py`
- ran `python analysis/h320_criticality_order_parameter.py`
- patched warning-prone pandas calls and reran the script
- read the saved run summary and detailed results artifacts

The broader test suite was not run.
