# Session 149 Log — Hybrid News Cascade Audit (2026-04-10)

## Objective

Take the next honest cheap non-API continuation after `H329`:
- `H330` hybrid news cascade audit

Question:
- can a deterministic-first novelty router preserve the saved teacher novelty
  contracts while sending only the ambiguous article tail to the paid API?

This session did not change the live branch.
It stayed long-only.
It did not read `2026+`.

---

## What changed

Added one bounded research script:
- `analysis/h330_hybrid_news_cascade_audit.py`

### H330 - Hybrid News Cascade Audit
**Hypothesis:**
The best cheap-LLM continuation after `H329` is not a full deterministic
replacement, but a hybrid cascade: auto-label only the high-confidence novelty
rows and route the ambiguous remainder to the canonical LLM schema.

**Command / code:**
`python analysis/h330_hybrid_news_cascade_audit.py`

**Inputs:**
- `data/news/cafef/raw/*.jsonl`
- `data/llm_cache/*.jsonl`
- `H329` deterministic novelty heuristics
- teacher-window market target built from local stock closes vs `VNINDEX`

**Saved artifact:**
`artifacts/run_summaries/20260410_110333_h330_hybrid_news_cascade_audit_details.json`

| Metric | Value | Note |
|--------|-------|------|
| verdict | `MIXED` | substantial cost reduction, but still short-horizon contract failure |
| teacher article rows | `12,295` | ticker-tagged teacher articles only |
| teacher date range | `2015-09-21` to `2018-01-03` | current available teacher window |
| policy ladder | `5` | strict to aggressive predeclared routing policies |
| best hybrid policy | `aggressive_triple` | best cost / contract trade-off |
| best policy preserved contracts | `2 / 3` | `5d follow_up_minus_new` and `30d new` only |
| best policy API article share | `0.2028` | deterministic handled `79.7%` of articles |
| best policy API text share | `0.2035` | deterministic handled `79.6%` of text length |
| best policy holdout macro-F1 | `0.5654` | well above pure deterministic `0.3965` |
| best policy holdout `follow_up` F1 | `0.4139` | well above pure deterministic `0.0876` |
| strongest label-fidelity policy | `new_only_strict` | holdout macro-F1 `0.8840`, follow_up F1 `0.8235` |
| strongest label-fidelity API article share | `0.5885` | still preserved only `2 / 3` contracts |
| failed contract across all policies | `1d follow_up` | sign stayed negative in every hybrid policy |

**Result:**
The hybrid cascade is real as a cost-reduction lens. Even the aggressive policy
kept only about `20%` of articles and text on the teacher side while improving
held-out novelty reconstruction materially over the pure deterministic
baseline. More conservative policies pushed label fidelity much higher.

But the branch still fails the contract that matters most. Every tested policy,
including the strict new-only cascade that sent almost `59%` of articles back
to the teacher, left the `1d follow_up` IC negative. So the hybrid novelty
cascade is not enough to preserve the short-horizon novelty-alpha mechanism.

**Verdict: MIXED**

---

## Branch decision

`H330` narrows the cheap-LLM surrogate branch again:
- keep the hybrid cascade as offline evidence that substantial API savings are
  possible without collapsing novelty labels
- do **not** continue novelty-only cascade tuning in isolation
- do **not** treat the novelty branch as production-ready under a hybrid
  contract

If the cheap branch continues, the next honest follow-up is:
- `deterministic-event-family-router`
  - move to more lexical teacher fields such as `event_type`,
    `expectation_alignment`, `impact_scope`, and `source_authority`

Secondary follow-up:
- `surrogate-disagreement-residual`
  - test whether teacher-fallback rows or student-teacher disagreement carry
    the remaining short-horizon information

---

## Validation

Completed during the pass:
- ran `python -m py_compile analysis/h330_hybrid_news_cascade_audit.py`
- ran `python analysis/h330_hybrid_news_cascade_audit.py`
- read `artifacts/run_summaries/latest_research_branch_hybrid_news_cascade_audit.json`
- inspected the saved policy-summary and alpha-contract parquet artifacts

The broader test suite was not run.
