# Session 153 Log — Foreign Room Residual Discontinuity (2026-04-10)

## Objective

Take the first non-LLM queue item after backup and the LLM-cache restart:
- `H333` foreign-room residual discontinuity

Question:
- after `H327/H328` killed raw and conditioned CafeF foreign-flow ranks, does
  the useful signal instead live in days where foreign room changes cannot be
  explained by net foreign trading?

This session did not change the live branch.
It stayed long-only.
It did not use `2026` for predictive tuning.

---

## What changed

Added one bounded research script:
- `analysis/h333_foreign_room_residual_discontinuity.py`

### H333 - Foreign Room Residual Discontinuity
**Hypothesis:**
The room mechanics residual
`delta(foreign_room_remaining) + foreign_net_volume` may mark ownership-regime,
corporate-action, or special-situation events that raw buy/sell ranks miss.

**Command / code:**
`python analysis/h333_foreign_room_residual_discontinuity.py`

**Inputs:**
- `data/foreign_flow/cafef/foreign_flow_daily.parquet`
- local daily stock volume panel
- `data/features/xs_barrier_vol_1d_hose_full.parquet`
- `artifacts/cache/future_rel_return_5d_hose.parquet`

**Saved artifact:**
`artifacts/run_summaries/20260410_132128_h333_foreign_room_residual_discontinuity_research_branch_foreign_room_residual_discontinuity.json`

| Metric | Value | Note |
|--------|-------|------|
| verdict | `FAILED` | residual discontinuity thresholding does not clear |
| merged rows | `817,074` | same 2015-2025 predictive universe as H327/H328 |
| merged tickers / dates | `391 / 2,741` | with `actual` and `fwd_rel_5d` targets |
| residual formula | `room_delta + foreign_net_volume` | ordinary net buy should reduce remaining room |
| residual exact-zero share | `65.64%` | room mechanics are still highly structured |
| systemic reset days | `288` | date-level top 5% residual reset score |
| best dense feature | `xs_ff_room_residual_loosen_rank` | sign flips in confirmation |
| best dense dev / validation / confirmation IC | `-0.0044 / -0.0109 / +0.0132` | dev too weak and 2025 flips |
| best dense corr vs S1 | `-0.0226` | orthogonal but not stable |
| best event state | `room_residual_systemic_abs_top5` | large systemic residual member |
| best event validation / confirmation actual lift | `-0.0724 / +0.0137` | sign breaks |
| best event validation / confirmation `fwd5` lift | `-0.0033 / +0.0090` | sign breaks |
| passing dense features | `0` | no rank clears H327-style gate |
| passing event states | `0` | no sparse state keeps T+1 and T+5 signs |

**Result:**
The residual series is not noise: about two thirds of rows are exactly explained
by ordinary room mechanics, while the failures cluster into identifiable
residual/reset states. But the predictive branch still fails. Dense residual
ranks are weak in dev and flip in 2025, and the sparse idiosyncratic/systemic
event states do not keep `T+1` and `T+5` lift signs aligned across validation
and confirmation.

**Verdict: FAILED**

---

## Branch decision

`H333` closes the first foreign-state continuation after raw-flow ranks:
- do **not** continue raw `room_delta + foreign_net_volume` thresholding
- do **not** promote idiosyncratic or systemic room-residual discontinuities
- if H95 continues, move to a different thesis:
  - `foreign-accumulation-change-point`
  - or a friction / insider interaction branch

Next honest H95 continuation:
- `foreign-accumulation-change-point`

---

## Validation

Completed during the pass:
- ran `python -m py_compile analysis/h333_foreign_room_residual_discontinuity.py`
- ran `python analysis/h333_foreign_room_residual_discontinuity.py`
- read the saved run summary artifact

The broader test suite was not run.
