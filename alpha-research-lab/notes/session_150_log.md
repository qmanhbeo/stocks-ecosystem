# Session 150 Log — Deterministic Event-Family Router Audit (2026-04-10)

## Objective

Take the next honest cheap non-API continuation after `H330`:
- `H331` deterministic event-family router audit

Question:
- can lexical rules recover enough of the non-novelty LLM teacher fields to
  preserve the strongest `5d` routed news buckets better than the dead
  keyword-news baseline?

This session did not change the live branch.
It stayed long-only.
It did not read `2026+`.

---

## What changed

Added one bounded research script:
- `analysis/h331_deterministic_event_family_router_audit.py`

### H331 - Deterministic Event-Family Router Audit
**Hypothesis:**
If the cheap branch is going to work without more API spend, the next honest
 candidate is not more novelty tuning but more lexical teacher fields:
`source_authority`, `expectation_alignment`, `impact_scope`, and the densest
event-type families.

**Command / code:**
`python analysis/h331_deterministic_event_family_router_audit.py`

**Inputs:**
- `data/news/cafef/raw/*.jsonl`
- `data/llm_cache/*.jsonl`
- `data/features/xs_news_sentiment_daily.parquet`
- teacher-window market target built from local stock closes vs `VNINDEX`

**Saved artifact:**
`artifacts/run_summaries/20260410_112153_h331_deterministic_event_family_router_audit_details.json`

| Metric | Value | Note |
|--------|-------|------|
| verdict | `FAILED` | structure recovered, but broad lexical router does not clear the branch bar |
| teacher article rows | `12,378` | ticker-tagged rows with at least one tested teacher field |
| teacher date range | `2015-09-21` to `2018-01-03` | current available teacher window |
| preserved field champions | `3 / 4` | `expectation_alignment`, `impact_scope`, `event_type` kept teacher sign |
| failed field champion | `source_authority__rumor_source` | teacher / deterministic IC `+0.0678 / -0.0848` |
| dense macro-F1 improvements | `2` | `source_authority` and `impact_scope` |
| `source_authority` macro-F1 delta | `+0.1514` | vs train-majority baseline on held-out `2017` |
| `impact_scope` macro-F1 delta | `+0.4364` | strongest dense-field recovery |
| `expectation_alignment` macro-F1 delta | `+0.0244` | too weak to count as a real lexical recovery |
| `event_type` macro-F1 delta | `+0.4458` | sparse family subset only |
| best deterministic feature | `source_authority__rumor_source` | abs IC `0.0848` |
| best keyword baseline | `sentiment_score` | abs IC `0.1303` on `609` matched rows |

**Result:**
The lexical router is not empty. It recovered a lot of held-out structure in
`source_authority`, `impact_scope`, and the focused `event_type` subset, and
it preserved `3 / 4` of the teacher field champions on the `5d` routed target.

But the failure matters more than the partial recovery. The best teacher
authority state was `rumor_source`, and the deterministic version flipped sign
hard negative. `expectation_alignment` also stayed too weak. Most importantly,
the best deterministic feature still did not beat the old keyword-news
baseline, so the branch did not honestly reopen a broad lexical replacement
path.

**Verdict: FAILED**

---

## Branch decision

`H331` closes the direct lexical router as the next cheap continuation:
- keep the partial structure recovery as offline evidence only
- do **not** continue broad direct field tuning on the current contract
- do **not** treat sparse `event_type` success as enough to reopen the branch

If the cheap branch continues, the next honest follow-up is:
- `surrogate-disagreement-residual`
  - treat the remaining student-teacher disagreement or teacher-fallback tail
    itself as the candidate signal source

---

## Validation

Completed during the pass:
- ran `python -m py_compile analysis/h331_deterministic_event_family_router_audit.py`
- ran `python analysis/h331_deterministic_event_family_router_audit.py`
- reran after a small artifact-hygiene fix to strip `inf` target means
- read `artifacts/run_summaries/latest_research_branch_deterministic_event_family_router_audit.json`
- inspected the saved field-metrics, feature-results, and keyword-baseline
  parquet artifacts

The broader test suite was not run.
