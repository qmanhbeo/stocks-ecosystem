# Session 131 Log — Insider-Event Confirmation (2026-04-09)

## Objective

Take the next honest current-data branch after `H304`:
- `H305` insider-event confirmation

Question:
- does `C5` insider relative size become materially stronger when it confirms
  fresh company-event windows, or is broad event-conditioning still too weak to
  justify another sparse timing branch?

This session did not change the live branch.
It did not read `2026+`.

---

## What changed

Added one bounded research script:
- `analysis/h305_insider_event_confirmation.py`

### H305 - Insider-Event Confirmation
**Hypothesis:**
The lab may be underusing `C5`. The real sparse insider edge may not be
"insider relative size anywhere," but "insider relative size when a fresh
company event confirms the move."

**Command / code:**
`python analysis/h305_insider_event_confirmation.py`

**Inputs:**
- `data/features/xs_barrier_vol_1d_hose_full.parquet`
- `data/features/xs_insider_quality_features.parquet`
- `data/features/event_surface_daily.parquet`
- `artifacts/run_summaries/latest_research_branch_cafef_event_surface_v2_pilot.json`
- `artifacts/timing_data/20260408_192103_h301_cafef_event_surface_v2_pilot_pilot_surface.parquet`

**Saved artifact:**
`artifacts/run_summaries/20260409_101219_h305_insider_event_confirmation_research_branch_insider_event_confirmation.json`

| Metric | Value | Note |
|--------|-------|------|
| baseline C5 pooled IC | `+0.0131 / +0.0168 / +0.0164` | dev / validation / 2025 on standalone C5 fire rows |
| best broad candidate | `v1_recent_any_filing_5d` | strongest broad event-conditioned row |
| best broad pooled IC | `+0.0239 / +0.0124 / +0.0228` | improves dev and 2025, but validation slips below standalone |
| validation / 2025 uplift vs baseline | `-0.0044 / +0.0064` | broad v1 filing support is not stable enough |
| broad v2 candidate | `v2_recent_company_event_article_v2_5d` | broad event-v2 window remains unstable |
| broad v2 pooled IC | `-0.0104 / +0.0199 / -0.0124` | negative in dev and 2025 |
| narrow v2 pocket | `v2_rights_issuance_5d` | only family-local row with positive pooled IC in all phases |
| narrow v2 pooled IC | `+0.1060 / +0.0203 / +0.0215` | local support only |
| narrow v2 rows | `54 / 74 / 57` | too small for promotion |
| pass rows / mixed rows | `0 / 2` | broad branch does not pass |

**Result:**
Broad event confirmation does not rescue `C5` cleanly. The strongest broad row
(`v1_recent_any_filing_5d`) improves dev and 2025 but underperforms standalone
`C5` in validation. Broad event-v2 windows are worse: the generic recent-event
mask is negative in dev and 2025. The only durable local pocket is
`v2_rights_issuance_5d`, but it is too small to justify a broad reopened branch.

**Verdict: MIXED**

---

## Branch decision

`H305` does not reopen a generic insider-event timing branch:
- keep broad event-conditioning on `C5` as mixed local evidence only
- keep `v2_rights_issuance_5d` as the only narrow surviving pocket from this pass
- do **not** treat generic event-v2 confirmation as a real upgrade to `C5`

If the current-data queue continues, move to:
- `insider-follow-through-split`

---

## Validation

Completed during the pass:
- ran `python -m py_compile analysis/h305_insider_event_confirmation.py`
- ran `python analysis/h305_insider_event_confirmation.py`
- read the saved run summary and details artifact
