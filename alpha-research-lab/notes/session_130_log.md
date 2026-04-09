# Session 130 Log — Execution Spillover Substitutes (2026-04-08)

## Objective

Take the next honest blocked-LLM side-branch continuation after `H303`:
- `H304` execution spillover substitutes

Question:
- when the raw top-ranked name is blocked or falls into the same thin bucket
  that broke `H296`, does the tradable edge spill into the nearest eligible
  same-family or same-sector substitute, or does it simply disappear?

This session did not change the live branch.
It did not read `2026+`.

---

## What changed

Added one bounded research script:
- `analysis/h304_execution_spillover_substitutes.py`

### H304 - Execution Spillover Substitutes
**Hypothesis:**
The execution mismatch in `H296` may not destroy the edge completely. On dates
when the raw top pick is blocked or obviously thin, the nearest eligible
same-family or same-sector substitute may still inherit the alpha.

**Command / code:**
`python analysis/h304_execution_spillover_substitutes.py`

**Inputs:**
- `data/features/entry_alpha/candidate_panel_daily.parquet`
- `data/features/entry_alpha/entry_labels_cycle5.parquet`
- `data/features/sector_classification.parquet`

**Saved artifact:**
`artifacts/run_summaries/20260408_231957_h304_execution_spillover_substitutes_research_branch_execution_spillover_substitutes.json`

| Metric | Value | Note |
|--------|-------|------|
| blocked top1 dates | `137` | raw rank-1 name cannot be bought next open |
| thin top1 dates | `1192` | rank-1 name lands in the same H296 thin bucket |
| blocked-or-thin dates | `1238` | total stressed execution dates considered |
| best local row | `blocked_or_thin_top1 × same_family_or_sector` | best recorded candidate |
| validation top-edge vs other top | `-0.0070` | negative in the main validation window |
| 2025 top-edge vs other top | `+0.0036` | only local confirmation rebound |
| validation hit rate | `46.91%` | below even a weak promotion bar |
| 2025 hit rate | `54.95%` | positive but not enough to offset validation failure |
| validation / 2025 dates | `194 / 91` | enough coverage for an honest read |
| pass rows | `0` | no candidate met the predeclared bar |
| mixed rows | `4` | only weak local evidence remained |

**Result:**
The nearest eligible substitutes do not preserve the edge cleanly on stressed
execution dates. The best local row only rebounds in `2025`; it is still
negative through the main `2023-2024` validation window, and all candidate rows
miss the pass contract.

**Verdict: MIXED**

---

## Branch decision

`H304` does not reopen execution routing as a predictive branch:
- keep the `H296` execution mismatch diagnosis
- keep `H304` only as weak local substitute evidence
- do **not** treat same-family or same-sector substitute picking as a real fix

If another non-LLM side branch is intentionally reopened, move to:
- `insider-event-confirmation`

---

## Validation

Completed during the pass:
- ran `python -m py_compile analysis/h304_execution_spillover_substitutes.py`
- ran `python analysis/h304_execution_spillover_substitutes.py`
- read the saved run summary and details artifact
