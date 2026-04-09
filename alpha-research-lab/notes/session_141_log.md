# Session 141 Log — Hawkes Disclosure Cascade (2026-04-09)

## Objective

Formalize and test the next current-data branch after `H320`:
- `H321` hawkes-disclosure-cascade

Question:
- do CafeF company-event disclosures behave like a self-exciting cascade,
  where decayed prior ticker / sector event intensity separates first-public
  shock, follow-up drift, and crowded states better than the H310 novelty
  windows?

This session did not change the live branch.
It stayed long-only.
It did not read `2026+`.

---

## What changed

Added one bounded research script:
- `analysis/h321_hawkes_disclosure_cascade.py`

### H321 - Hawkes Disclosure Cascade
**Hypothesis:**
The H310 event-v2 surface should be represented as a sparse self-exciting
disclosure process, not only as simple repeat-count windows. If the branch is
real, a same-day or recent-window cascade-intensity state should beat the
matched H310 novelty / follow-up / crowded control in both validation and
`2025`.

**Command / code:**
`python analysis/h321_hawkes_disclosure_cascade.py`

**Inputs:**
- `artifacts/run_summaries/latest_research_branch_event_v2_predictive_rescreen.json`
- `artifacts/timing_data/20260409_115740_h310_event_v2_predictive_rescreen_article_events.parquet`
- `artifacts/timing_data/20260409_115740_h310_event_v2_predictive_rescreen_first_public.parquet`
- `data/features/xs_barrier_vol_1d_hose_full.parquet`
- `data/features/sector_classification.parquet`
- `artifacts/cache/future_rel_return_5d_hose.parquet`

**Saved artifact:**
`artifacts/run_summaries/20260409_155621_hawkes_disclosure_cascade_research_branch_hawkes_disclosure_cascade.json`

| Metric | Value | Note |
|--------|-------|------|
| panel rows | `258,375` | `2023-2025` H310-compatible trading panel |
| panel tickers / dates | `394 / 748` | HOSE active-book panel |
| intensity model | decayed prior event counts | `tau=2/5/10`, ticker and sector-peer levels |
| best state | `today_self_accel_high` | same-day event with fast self-excitation acceleration |
| matched control | `event_today_follow20` | H310 same-day follow-up control |
| validation / confirmation daily IC rows | `30 / 31` | sparse but above same-day pass floor |
| validation / confirmation daily IC | `+0.2395 / +0.3215` | best cascade state |
| validation / confirmation IC uplift vs control | `+0.1831 / +0.2290` | both phases clear the bar |
| validation / confirmation actual uplift vs control | `+0.0369 / +0.0329` | same matched-control comparison |
| validation / confirmation `fwd5` uplift vs control | `+0.0014 / +0.0009` | positive both phases |

**Result:**
The cascade representation passed. The strongest result was not simple
low-intensity novelty. It was `today_self_accel_high`: same-day event rows
where short-horizon self-excitation exceeded longer-horizon intensity. That
state beat the H310 same-day follow-up control in validation and confirmation
on daily IC, actual response, and `5d` relative follow-through.

The result is still sparse, so the right consequence is not immediate library
promotion. It reopens the event-v2 timing branch as a narrow cascade-state
feature candidate.

**Verdict: PASSED**

---

## Branch decision

`H321` justifies a focused cascade follow-up:
- keep `today_self_accel_high` as a promoted offline timing candidate
- do **not** promote it directly into the live library yet
- run a narrow additive / orthogonality screen against the frozen
  `S1 / C4 / C13` core and the H310 `event_today_novel20` state

Next honest current-data queue item:
- `cascade-additive-screen`
  - test whether `today_self_accel_high` is merely a sharper cohort label or
    actually adds value over the frozen core / H310 event state

Next honest acquisition queue remains:
- `historical-foreign-flow-source`

---

## Validation

Completed during the pass:
- ran `python -m py_compile analysis/h321_hawkes_disclosure_cascade.py`
- ran `python analysis/h321_hawkes_disclosure_cascade.py`
- fixed one merge naming collision and reran the script
- read the saved run summary and detailed results artifacts

The broader test suite was not run.
