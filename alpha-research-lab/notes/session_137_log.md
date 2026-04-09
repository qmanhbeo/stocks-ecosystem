# Session 137 Log — Event-V2 Additive Screen (2026-04-09)

## Objective

Take the next honest follow-up after `H310-H316`:
- `H317` event-v2 additive screen

Question:
- do the passed `H310` event-v2 states add enough value on top of a frozen
  `S1 / C4 / C13` core score to justify a broader additive-promotion branch, or
  do they stay as predictive cohort evidence only?

This session did not change the live branch.
It stayed long-only.
It did not read `2026+`.

---

## What changed

Added one bounded research script:
- `analysis/h317_event_v2_additive_screen.py`

### H317 - Event-V2 Additive Screen
**Hypothesis:**
The strongest passed `H310` states, especially same-day first-public
`event_today_novel20`, may be strong enough to improve a frozen `S1 / C4 / C13`
core score beyond both the plain core baseline and a same-form broad v1 event
control.

**Command / code:**
`python analysis/h317_event_v2_additive_screen.py`

**Inputs:**
- `data/features/xs_rl_signal_matrix.parquet`
- `artifacts/run_summaries/latest_research_branch_event_v2_predictive_rescreen.json`
- `data/features/event_surface_daily.parquet`

**Saved artifact:**
`artifacts/run_summaries/20260409_124456_research_branch_event_v2_additive_screen.json`

| Metric | Value | Note |
|--------|-------|------|
| panel rows / dates / tickers | `258,375 / 748 / 394` | observed `2023-2025` additive panel |
| best standalone state | `event_today_novel20` | same-day first-public remains the only positive sparse state |
| validation / confirmation standalone IC | `+0.0055 / +0.0026` | still below standalone promotion scale |
| validation / confirmation active lift | `+0.0314 / +0.0307` | active rows beat daily average |
| best additive candidate | `core_mul__event_today_novel20__30` | 30% state-scoped core upweight |
| validation IC delta vs core / v1 control | `+0.0002 / +0.0019` | positive but tiny |
| confirmation IC delta vs core / v1 control | `-0.00003 / +0.0007` | effectively flat |
| recent low-repeat status | `failed` | negative standalone and additive on this contract |

**Result:**
`H317` came back mixed, but the promotion question is effectively answered for
now. The same-day first-public state is still real as sparse cohort evidence,
with positive validation and confirmation active-row lift and near-zero overlap
with the frozen anchors. But once forced into an additive overlay on top of the
core `S1 / C4 / C13` score, the uplift is far too small to justify promotion.
The recent low-repeat state does not survive the additive screen at all.

**Verdict: MIXED**

---

## Branch decision

`H317` does not invalidate `H310`, but it does stop the current additive
promotion path:
- keep `H310` event-v2 as predictive cohort evidence
- keep `event_today_novel20` as the surviving narrow state
- do **not** promote event-v2 into the additive/library queue yet
- do **not** spend more current-data budget on event-v2 integration until the
  data stack changes materially or a broader contract becomes available

Next honest non-LLM queue item:
- `historical-foreign-flow-source`
  - current-data event promotion is now exhausted
  - the next highest-upside honest continuation is a blocked new-data branch,
    not another local event retune

---

## Validation

Completed during the pass:
- ran `python -m py_compile analysis/h317_event_v2_additive_screen.py`
- ran `python analysis/h317_event_v2_additive_screen.py`
- fixed one reporting bug where standalone state coverage was being computed on
  active rows only instead of the full phase panel
- reran `python analysis/h317_event_v2_additive_screen.py`
- read the saved run summary and detailed results artifacts
