# Session 133 Log — Event Novelty Half-Life Without LLM (2026-04-09)

## Objective

Take the next honest current-data branch after `H306`:
- `H307` event novelty half-life without LLM

Question:
- do the `H301` first-public company-event rows support a usable novelty versus
  crowding split on the observed `2023-2025` panel, or is the branch still too
  sparse to reopen without the blocked LLM cache?

This session did not change the live branch.
It did not read `2026+`.

---

## What changed

Added one bounded research script:
- `analysis/h307_event_novelty_half_life_without_llm.py`

### H307 - Event Novelty Half-Life Without LLM
**Hypothesis:**
`H301` first-public company events may already contain a useful novelty /
crowding state without needing article-level LLM coverage. If so, low-repeat
recent windows or same-day first-public rows should sharpen the frozen `S1`
cross-sectional prior relative to crowded follow-up states.

**Command / code:**
`python analysis/h307_event_novelty_half_life_without_llm.py`

**Inputs:**
- `artifacts/timing_data/20260408_192103_h301_cafef_event_surface_v2_pilot_first_public.parquet`
- `data/features/xs_barrier_vol_1d_hose_full.parquet`
- `data/features/event_surface_daily.parquet`

**Saved artifact:**
`artifacts/run_summaries/20260409_104621_h307_event_novelty_half_life_without_llm_research_branch_event_novelty_half_life_without_llm.json`

| Metric | Value | Note |
|--------|-------|------|
| first-public rows | `5,177` | saved `H301` event rows used to rebuild repeat-density states |
| broad recent-window target | `recent5_low_repeat20` | intended honest promotion contract |
| recent-window validation / 2025 avg IC | `+0.0669 / +0.1567` | positive but unstable |
| recent-window uplift vs crowded | `-0.0392 / +0.0661` | loses in validation, wins only in 2025 |
| recent-window uplift vs v1 proxy | `-0.0109 / +0.0523` | fails the broad validation bar |
| same-day sparse pocket | `event_today_novel20` | first-public over trailing `20d` |
| same-day validation / 2025 avg IC | `+0.0008 / +0.1215` | directionally positive but tiny |
| same-day uplift vs crowded | `+0.0703 / +0.1107` | beats crowded same-day follow-ups |
| same-day validation / 2025 daily IC rows | `16 / 17` | too sparse for a broad branch |

**Result:**
The broad recent-window novelty split failed the honest contract. Low-repeat
recent windows did not beat crowded follow-up windows in validation, and they
also stayed below the broad v1 company-proxy control in validation. The only
surviving evidence is a sparse same-day first-public pocket:
`event_today_novel20` beat `event_today_crowded20` in both validation and
confirmation, but on only `16 / 17` daily IC rows.

**Verdict: MIXED**

---

## Branch decision

`H307` keeps event novelty alive only as local sparse-state evidence:
- do **not** open a broad event-novelty branch from the current `H301` contract
- do keep the same-day first-public versus crowded split as offline evidence
- if the current-data queue continues, move to:
  - `stock-local-predictability-atlas`
- if the event family is intentionally reopened, prefer the data-wiring follow-up:
  - `issuer-lexicon-event-surface`

---

## Validation

Completed during the pass:
- ran `python -m py_compile analysis/h307_event_novelty_half_life_without_llm.py`
- ran `python analysis/h307_event_novelty_half_life_without_llm.py`
- read the saved run summary and details artifact
