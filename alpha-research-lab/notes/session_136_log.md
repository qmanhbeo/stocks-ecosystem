# Session 136 Log — H309 Spark Wave (2026-04-09)

## Objective

Formalize and test the full post-`H309` spark queue under the richer
issuer-validated event-v2 surface:
- `H310` event-v2 predictive re-screen
- `H311` publication-time x family router
- `H312` v2-v1 disagreement router
- `H313` issuer-family spillover graph
- `H314` event-conditioned `C5` redux
- `H315` official disclosure timestamp source audit
- `H316` HNX event transfer pilot

This session did not change the live branch.
It stayed long-only.
It did not read `2026+`.

---

## What changed

Added one shared helper and seven bounded research scripts:
- `src/future_return_research.py`
- `analysis/h310_event_v2_predictive_rescreen.py`
- `analysis/h311_publication_time_x_family_router.py`
- `analysis/h312_v2_v1_disagreement_router.py`
- `analysis/h313_issuer_family_spillover_graph.py`
- `analysis/h314_event_conditioned_c5_redux.py`
- `analysis/h315_official_disclosure_timestamp_source_audit.py`
- `analysis/h316_hnx_event_transfer_pilot.py`

Also hardened `H313` after the first run proved the branch can legitimately
return an empty evaluation panel:
- preserve the panel schema on empty paths instead of crashing on `time`
  lookup during phase masking

### H310 - Event-V2 Predictive Re-Screen
**Hypothesis:**
The richer `H309` combined issuer-validated surface is finally broad enough to
rerun the old `H301/H307` predictive contract honestly. If event-v2 is real,
same-day first-public and recent low-repeat windows should now survive against
crowded follow-ups and the v1 company-event proxy.

**Command / code:**
`python analysis/h310_event_v2_predictive_rescreen.py`

**Inputs:**
- `data/news/cafef/raw/*.jsonl`
- `artifacts/run_summaries/latest_research_branch_issuer_lexicon_event_surface.json`
- `data/features/xs_barrier_vol_1d_hose_full.parquet`

**Saved artifact:**
`artifacts/run_summaries/20260409_115740_research_branch_event_v2_predictive_rescreen.json`

| Metric | Value | Note |
|--------|-------|------|
| unique mapped event articles | `6,043` | richer combined `H309` issuer surface |
| unique event tickers | `190` | `2023-2025` observed panel |
| pilot `5d` held-row coverage | `6.00%` | up from `3.84%` in `H309` |
| recent-window winner | `recent5_low_repeat20` | validation / confirmation pooled IC `+0.0811 / +0.1118` |
| recent uplift vs crowded | `+0.0139 / +0.0173` | validation / confirmation |
| same-day winner | `event_today_novel20` | validation / confirmation pooled IC `+0.1170 / +0.1829` |
| same-day uplift vs crowded | `+0.1023 / +0.1043` | validation / confirmation |

**Result:**
`H310` passed cleanly. The richer `H309` surface turns the old sparse pockets
into a real predictive branch. Both the same-day first-public state
(`event_today_novel20`) and the recent low-repeat state
(`recent5_low_repeat20`) now clear the predeclared bar. Event-v2 is honestly
reopened beyond acquisition work.

**Verdict: PASSED**

### H311 - Publication-Time X Family Router
**Hypothesis:**
If the surviving event-v2 edge is really a timing mechanism, then exact
publication-time buckets should separate by event family, with pre-open or
post-close windows beating intraday references.

**Command / code:**
`python analysis/h311_publication_time_x_family_router.py`

**Inputs:**
- `artifacts/run_summaries/latest_research_branch_event_v2_predictive_rescreen.json`
- `data/features/xs_barrier_vol_1d_hose_full.parquet`
- `artifacts/cache/future_rel_return_5d_hose.parquet`

**Saved artifact:**
`artifacts/run_summaries/20260409_120129_research_branch_publication_time_x_family_router.json`

| Metric | Value | Note |
|--------|-------|------|
| panel rows | `6,240` | same-day first-public rows across tested families |
| families tested | `4` | earnings, rights, board, meeting |
| best row | `board_management × post_close` | strongest mixed candidate |
| validation actual / fwd5 uplift vs intraday | `+0.0271 / +0.0030` | best row |
| confirmation actual / fwd5 uplift vs intraday | `-0.0056 / -0.0006` | same row flips weaker |

**Result:**
Publication time matters locally, but not cleanly enough for a broad router.
The best row improves in validation and then slips in confirmation, while other
families keep the same unstable pattern. The branch stays local timing evidence
only.

**Verdict: MIXED**

### H312 - V2-V1 Disagreement Router
**Hypothesis:**
If the richer event-v2 surface is adding genuinely new information, then the
`v2_only` cohort should beat both `v1_only` and `both` on the frozen
predictive contract.

**Command / code:**
`python analysis/h312_v2_v1_disagreement_router.py`

**Inputs:**
- `artifacts/run_summaries/latest_research_branch_event_v2_predictive_rescreen.json`
- `data/features/event_surface_daily.parquet`
- `data/features/xs_barrier_vol_1d_hose_full.parquet`
- `artifacts/cache/future_rel_return_5d_hose.parquet`

**Saved artifact:**
`artifacts/run_summaries/20260409_120129_research_branch_v2_v1_disagreement_router.json`

| Metric | Value | Note |
|--------|-------|------|
| panel rows | `258,371` | full `2023-2025` cohort panel |
| candidate cohort | `v2_only_5d` | intended disagreement state |
| validation / confirmation pooled IC | `+0.0939 / +0.0928` | positive both years |
| validation IC uplift vs `v1_only / both` | `+0.0044 / +0.0732` | only the `both` comparison is large |
| confirmation IC uplift vs `v1_only / both` | `-0.0015 / -0.0471` | not stable enough |
| validation fwd5 uplift vs `v1_only` | `-0.0007` | fails the drift side |

**Result:**
`v2_only` is directionally real, especially against crowded `both` states, but
it does not beat `v1_only` robustly enough to justify a broad disagreement
router. The branch stays mixed diagnostic evidence.

**Verdict: MIXED**

### H313 - Issuer-Family Spillover Graph
**Hypothesis:**
The remaining alias misses in `H309` may reflect genuine listed-group spillover
rather than mapping noise. If so, ambiguous family-name articles should often
reward a peer more than the named ticker.

**Command / code:**
`python analysis/h313_issuer_family_spillover_graph.py`

**Inputs:**
- `artifacts/run_summaries/latest_research_branch_issuer_lexicon_event_surface.json`
- `data/news/cafef/raw/*.jsonl`
- `data/features/xs_barrier_vol_1d_hose_full.parquet`
- `artifacts/cache/future_rel_return_5d_hose.parquet`

**Saved artifact:**
`artifacts/run_summaries/20260409_120743_research_branch_issuer_family_spillover_graph.json`

| Metric | Value | Note |
|--------|-------|------|
| ambiguous family aliases | `9` | derived from HOSE issuer names |
| matched article rows | `0` | no evaluation cases survived |
| validation rows | `0` | no spillover panel |
| confirmation rows | `0` | no spillover panel |

**Result:**
The branch failed cleanly. There is no surviving ambiguity panel broad enough
to support a family-recipient thesis, so the observed `H309` misses are better
treated as narrow mapping noise, not a new recipient branch.

**Verdict: FAILED**

### H314 - Event-Conditioned C5 Redux
**Hypothesis:**
The richer `H309/H310` surface may rescue the old insider-event idea if `C5`
is conditioned only on the sharper same-day or family-specific event windows.

**Command / code:**
`python analysis/h314_event_conditioned_c5_redux.py`

**Inputs:**
- `artifacts/run_summaries/latest_research_branch_event_v2_predictive_rescreen.json`
- `data/features/xs_insider_quality_features.parquet`
- `data/features/xs_barrier_vol_1d_hose_full.parquet`

**Saved artifact:**
`artifacts/run_summaries/20260409_120129_research_branch_event_conditioned_c5_redux.json`

| Metric | Value | Note |
|--------|-------|------|
| baseline `C5` validation / confirmation IC | `+0.0168 / +0.0164` | standalone benchmark |
| best broad local row | `v2_same_day_any` | richest mixed candidate |
| `v2_same_day_any` validation / confirmation IC | `+0.0988 / +0.0157` | strong locally, not stable enough |
| `v2_same_day_any` uplift vs baseline | `+0.0820 / -0.0007` | confirmation misses the bar |
| best narrow row | `v2_same_day_earnings` | validation-only pop on `35` rows |

**Result:**
The richer event surface sharpens a few local insider pockets, but it still
does not produce a broad conditioned `C5` branch. The surviving states remain
too small or too unstable to promote.

**Verdict: MIXED**

### H315 - Official Disclosure Timestamp Source Audit
**Hypothesis:**
If an official timestamped disclosure history already exists locally, the next
event ceiling may be source authority rather than more CafeF engineering.

**Command / code:**
`python analysis/h315_official_disclosure_timestamp_source_audit.py`

**Inputs:**
- local `data/` tree only

**Saved artifact:**
`artifacts/run_summaries/20260409_115757_research_branch_official_disclosure_timestamp_source_audit.json`

| Metric | Value | Note |
|--------|-------|------|
| local hit count | `0` | no official-disclosure files found |
| blocker | `missing_local_official_disclosure_history` | branch remains source-blocked |
| result | `SKIP` | data audit only |

**Result:**
The official-source branch is still blocked by missing local data, not by an
unrun experiment. Nothing in the workspace currently supports an honest
official-timestamp branch.

**Verdict: NEUTRAL**

### H316 - HNX Event Transfer Pilot
**Hypothesis:**
The richer event-v2 mapping contract may transfer to HNX cheaply enough to
justify a later HNX price-model pilot.

**Command / code:**
`python analysis/h316_hnx_event_transfer_pilot.py`

**Inputs:**
- `artifacts/run_summaries/latest_research_branch_issuer_lexicon_event_surface.json`
- `data/news/cafef/raw/*.jsonl`

**Saved artifact:**
`artifacts/run_summaries/20260409_120129_research_branch_hnx_event_transfer_pilot.json`

| Metric | Value | Note |
|--------|-------|------|
| HNX tickers in pilot | `402` | listing-metadata universe |
| training title rows | `94` | too thin already |
| holdout rows | `17` | insufficient for a real transfer judgment |
| strict / combined assigned share | `17.65% / 17.65%` | no effective lift |
| combined assigned precision | `100.00%` | but on only `3` assignments |
| validated metadata aliases | `0` | no HNX metadata lift survived |

**Result:**
The HNX event-transfer idea is still too sparse to judge honestly. The mapping
does not fail on precision; it fails on title volume. This is a data-coverage
block, not a green light for HNX expansion.

**Verdict: NEUTRAL**

---

## Branch decision

Session 136 result:
- `H310`: event-v2 is now a real predictive branch under the richer `H309`
  surface
- `H311`: keep publication-time × family only as local offline timing evidence
- `H312`: keep `v2_only` disagreement only as mixed cohort evidence; do **not**
  open a broad disagreement router
- `H313`: kill the family-recipient spillover branch on the current contract
- `H314`: keep insider-event confirmation closed as a broad branch
- `H315`: keep official disclosure timing data marked as source-blocked
- `H316`: keep HNX event transfer marked as too sparse / data-blocked

Next honest current-data queue item:
- `event-v2-additive-screen`
  - turn the passed `H310` same-day and recent-window states into a bounded
    additive screen against the existing v1 proxy and frozen `S1 / C4 / C13`
  - do **not** spend more cycles on finer routing branches until that broader
    promotion question is answered

---

## Validation

Completed during the pass:
- ran `python -m py_compile` on `src/future_return_research.py` and all
  `H310-H316` scripts
- ran `python analysis/h310_event_v2_predictive_rescreen.py`
- built `artifacts/cache/future_rel_return_5d_hose.parquet`
- ran `python analysis/h311_publication_time_x_family_router.py`
- ran `python analysis/h312_v2_v1_disagreement_router.py`
- ran `python analysis/h314_event_conditioned_c5_redux.py`
- ran `python analysis/h315_official_disclosure_timestamp_source_audit.py`
- ran `python analysis/h316_hnx_event_transfer_pilot.py`
- reran `python analysis/h313_issuer_family_spillover_graph.py` after fixing
  the empty-panel schema path
- read every saved run summary before promoting the results
