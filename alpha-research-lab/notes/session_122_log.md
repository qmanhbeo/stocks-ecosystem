# Session 122 Log — Breadth Activation Gate (2026-04-06)

## Objective
Test whether lagged sector breadth predicts day-to-day IC variation of S1 on the active book.

This session did not change the live branch.
It did not read `2026+`.

---

## What changed

Added and ran the H293 breadth activation gate audit script.

Saved artifact:
- `artifacts/run_summaries/20260406_122241_h293_breadth_activation_gate_standalone_signal.json`

### H293 - Breadth Activation Gate
**Hypothesis:**
Lagged sector breadth should explain day-to-day variation in the daily IC of S1 on the active book.

**Command / code:**
`conda run -n stocks python analysis/h293_breadth_activation_gate.py`

**Inputs:**
- `data/features/xs_barrier_vol_1d_hose_full.parquet`
- `data/features/xs_sector_rotation_daily.parquet`

**Saved artifact:**
`artifacts/run_summaries/20260406_122241_h293_breadth_activation_gate_standalone_signal.json`

| Metric | Value | Note |
|--------|-------|------|
| verdict | `FAIL` | breadth_lag1 is not a useful daily IC router |
| spearman rho | `+0.0032` | no meaningful relationship |
| p-value | `0.8664` | not significant |
| panel days | `2748` | 2015-01-05 to 2025-12-31 |
| daily IC mean | `+0.1491` | S1 remains strongly positive on average |
| q5 minus q1 IC mean | `-0.0042` | high breadth does not lift daily IC |

**Result:**
The breadth state does not explain day-to-day variation in S1 IC. The daily IC series stays strongly positive on average, but the lagged sector breadth proxy is effectively flat against it and the breadth quintiles do not form a useful activation gradient.

**Verdict: FAILED**

---

## Branch decision

Keep the live branch unchanged.
Park `breadth-activation-gate`.
Move the queue to `llm-news-gate`.

---

## Validation

Completed before the run:
- `conda run -n stocks python -m py_compile analysis/h293_breadth_activation_gate.py`

Completed for the experiment:
- read `artifacts/run_summaries/20260406_122241_h293_breadth_activation_gate_standalone_signal.json`

Verdict:
- `H293`: **FAILED**
