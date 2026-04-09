# Session 142 Log — Cascade Additive Screen (2026-04-09)

## Objective

Formalize and test the next follow-up after the `H321` pass:
- `H322` cascade-additive-screen

Question:
- does the H321 `today_self_accel_high` cascade state add enough value on top
  of the frozen `S1 / C4 / C13` core to justify promotion beyond sparse cohort
  evidence?

This session did not change the live branch.
It stayed long-only.
It did not read `2026+`.

---

## What changed

Added one bounded research script:
- `analysis/h322_cascade_additive_screen.py`

### H322 - Cascade Additive Screen
**Hypothesis:**
The H321 winner should not only beat the matched H310 follow-up cohort; it
should improve a frozen core ranker built from `S1 / C4 / C13`. If real enough
for promotion, `today_self_accel_high` should lift validation IC/spread versus
the core and matched controls without breaking `2025`.

**Command / code:**
`python analysis/h322_cascade_additive_screen.py`

**Inputs:**
- `artifacts/run_summaries/latest_research_branch_hawkes_disclosure_cascade.json`
- `data/features/xs_rl_signal_matrix.parquet`

**Saved artifact:**
`artifacts/run_summaries/20260409_160230_h322_cascade_additive_screen_research_branch_cascade_additive_screen.json`

| Metric | Value | Note |
|--------|-------|------|
| panel rows | `258,375` | `2023-2025` matrix-compatible panel |
| panel tickers / dates | `394 / 748` | HOSE active-book panel |
| standalone state | `today_self_accel_high` | H321 winner |
| standalone validation / confirmation IC | `+0.0046 / +0.0072` | binary state vs `actual` across full daily universe |
| standalone validation / confirmation active lift | `+0.0288 / +0.0570` | strong sparse cohort response |
| best additive variant | `core_mul__today_self_accel_high__50` | `50%` multiplicative boost on active state |
| best additive decision | `MIXED` | below promotion bar |
| best validation / confirmation IC delta vs core | `+0.00015 / +0.00005` | too small for promotion |
| best validation / confirmation spread delta vs core | `+0.00018 / -0.00021` | confirmation spread slips |
| best validation / confirmation IC delta vs matched follow-up control | `+0.00076 / +0.00044` | positive but tiny |
| best validation / confirmation IC delta vs H310 novelty control | `-0.00012 / +0.00017` | does not beat novelty cleanly |

**Result:**
The cascade state remains real as a sparse cohort and is cleaner than the H310
follow-up state, but it is not additive enough over the frozen core to promote.
The best overlay barely moves full-universe IC and does not improve spread
consistently. This mirrors the broad H317 lesson, with a sharper event state
but the same additive ceiling.

**Verdict: MIXED**

---

## Branch decision

`H322` narrows the H321 pass:
- keep `today_self_accel_high` as offline event-timing evidence
- do **not** promote it into the live/library additive queue
- do **not** keep tuning event-v2 overlays on the current frozen core

Next honest current-data creative queue item:
- `policy-beneficiary-graph`
  - the current event-v2 additive path is now narrowed again
  - the next wild branch should test a materially different information
    channel, not another event-v2 rank overlay

Next honest acquisition queue remains:
- `historical-foreign-flow-source`

---

## Validation

Completed during the pass:
- ran `python -m py_compile analysis/h322_cascade_additive_screen.py`
- ran `python analysis/h322_cascade_additive_screen.py`
- read the saved run summary and detailed results artifacts

The broader test suite was not run.
