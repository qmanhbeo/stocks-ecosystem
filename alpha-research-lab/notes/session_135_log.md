# Session 135 Log — Issuer-Lexicon Event Surface (2026-04-09)

## Objective

Take the next honest current-data follow-up after `H308`:
- `H309` issuer-lexicon event surface

Question:
- is the `H301` event-v2 coverage ceiling mostly a mapping problem, and can
  issuer metadata widen the CafeF company-event surface materially without
  sacrificing masked-title holdout precision?

This session did not change the live branch.
It did not read `2026+`.

---

## What changed

Added one bounded research script:
- `analysis/h309_issuer_lexicon_event_surface.py`

### H309 - Issuer-Lexicon Event Surface
**Hypothesis:**
The `H301` alias-expanded event-v2 pilot stayed too sparse mostly because the
title-prefix alias map was too narrow. If issuer metadata is used only to
propose aliases, and those aliases are validated on `2023-2024` known-ticker
titles before a `2025` masked-title holdout, the combined lexicon should widen
coverage materially while preserving high holdout precision.

**Command / code:**
`python analysis/h309_issuer_lexicon_event_surface.py`

**Inputs:**
- `data/news/cafef/raw/*.jsonl`
- `artifacts/run_summaries/latest_research_branch_cafef_event_surface_v2_pilot.json`
- `data/features/xs_rl_signal_matrix.parquet`
- `data/features/execution/tradability_daily.parquet`
- vnstock `Listing().symbols_by_exchange()` issuer metadata fetch

**Saved artifact:**
`artifacts/run_summaries/20260409_112918_h309_issuer_lexicon_event_surface_research_branch_issuer_lexicon_event_surface.json`

| Metric | Value | Note |
|--------|-------|------|
| training title rows | `871` | `2023-2024` single-ticker known-title event articles |
| metadata candidate aliases | `1,191` | unique-to-ticker aliases proposed from issuer metadata |
| validated metadata aliases | `120` | survived training support `>=2` and dominance `>=0.9` |
| strict holdout assigned share / precision | `43.81% / 98.82%` | `H301` baseline |
| metadata-only holdout assigned share / precision | `48.45% / 100.00%` | metadata layer alone stays very clean |
| combined holdout assigned share / precision | `62.37% / 99.17%` | strong lift with no real precision loss |
| new correct holdout assignments | `36` | examples: `BVH`, `PDR`, `MSN`, `DBC`, `DPG`, `SRF`, `VHM` |
| strict / combined pilot 5d held-row coverage | `2.30% / 3.84%` | `+1.55pp` absolute lift |
| strict / combined unique pilot articles | `3,933 / 6,043` | `+2,110` articles |

**Result:**
`H309` passed cleanly. The metadata-backed validated aliases materially widened
the event-v2 surface while keeping holdout precision effectively unchanged.
Combined assignment share rose from `43.81%` to `62.37%`, holdout precision
stayed at `99.17%`, and pilot held-row coverage improved from `2.30%` to
`3.84%`. The mapping ceiling in `H301` was real. The remaining observed error
in the holdout was narrow (`HHS` vs `TCH` around the Hoàng Huy naming family),
not a broad collapse in precision.

**Verdict: PASSED**

---

## Branch decision

`H309` reopens the event-v2 branch as a predictive follow-up:
- keep the issuer-validated lexicon as the new event-v2 acquisition baseline
- do **not** treat this as a live signal promotion yet; it is still a mapping
  pass, not an alpha pass
- the next honest queue item is:
  - `event-v2-predictive-re-screen`
- the right contract is now to retest the richer combined surface against the
  old v1 company-proxy and `H307` same-day/recent-window states

---

## Validation

Completed during the pass:
- ran `python -m py_compile analysis/h309_issuer_lexicon_event_surface.py`
- ran `python analysis/h309_issuer_lexicon_event_surface.py`
- read the saved run summary and details artifact
