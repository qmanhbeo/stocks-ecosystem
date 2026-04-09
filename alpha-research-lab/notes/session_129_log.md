# Session 129 Log — Event-Conditioned Intraday Disagreement (2026-04-08)

## Objective

Take the first honest continuation from the post-128 side-branch queue:
- `H303` event-conditioned intraday disagreement

Question:
- do the surviving `H299` disagreement atoms become materially stronger inside
  the fresh company-event windows recovered by the `H301` event-v2 pilot?

This session did not change the live branch.
It did not read `2026+`.

---

## What changed

Added one bounded research script:
- `analysis/h303_event_conditioned_intraday_disagreement.py`

### H303 - Event-Conditioned Intraday Disagreement
**Hypothesis:**
The real surviving value in `H299` may be a state-transition detector that
sharpens only when a fresh `H301` company-event window is present, rather than
as a generic observed-subset atom.

**Command / code:**
`python analysis/h303_event_conditioned_intraday_disagreement.py`

**Inputs:**
- `artifacts/run_summaries/latest_research_branch_intraday_library_atoms.json`
- `artifacts/portfolio_baselines/20260408_192203_h299_intraday_library_atoms_scored_panel.parquet`
- `artifacts/run_summaries/latest_research_branch_cafef_event_surface_v2_pilot.json`
- `artifacts/timing_data/20260408_192103_h301_cafef_event_surface_v2_pilot_pilot_surface.parquet`
- `data/features/event_surface_daily.parquet`

**Saved artifact:**
`artifacts/run_summaries/20260408_211247_h303_event_conditioned_intraday_disagreement_research_branch_event_conditioned_intraday_disagreement.json`

| Metric | Value | Note |
|--------|-------|------|
| observed rows | `243,763` | same `H299` observed subset, `2023-2025` only |
| best event candidate | `fade_tension_disagreement × event_v2_5d` | best local interaction row |
| validation IC | `+0.0430` | stronger than the unconditional `H299` row |
| 2025 IC | `+0.0455` | also stronger than the unconditional row |
| validation uplift vs full | `+0.0065` | local improvement over unconditional `H299` |
| 2025 uplift vs full | `+0.0247` | clear local uplift |
| validation uplift vs no-event | `+0.0069` | recent event-v2 window beats the no-event complement |
| 2025 uplift vs no-event | `+0.0251` | recent event-v2 window also beats no-event in confirmation |
| validation uplift vs v1 | `-0.0083` | still weaker than the broad v1 proxy in validation |
| 2025 uplift vs v1 | `+0.0116` | only beats v1 in confirmation |
| validation / 2025 IC days | `240 / 211` | enough coverage for an honest `5d` comparison |

**Result:**
Fresh `H301` event-v2 windows do help the best `H299` disagreement atom relative
to the unconditional and no-event versions. But they do **not** beat the broader
v1 company-proxy control consistently, and the second disagreement atom does not
improve at all on the same contract. That is not enough to reopen a predictive
combined timing branch.

**Verdict: FAILED**

---

## Branch decision

`H303` closes the generic combination of these two lines on the current
contract:
- keep `H299` disagreement atoms as separate observed-subset offline evidence
- keep `H301` event-v2 as acquisition evidence only
- do **not** reopen a combined recent-event overlay on generic event-v2 windows

If another blocked-LLM side branch is intentionally reopened, move to:
- `execution-spillover-substitutes`

---

## Validation

Completed during the pass:
- ran `python -m py_compile analysis/h303_event_conditioned_intraday_disagreement.py`
- ran `python analysis/h303_event_conditioned_intraday_disagreement.py`
- read the saved run summary and comparison table
