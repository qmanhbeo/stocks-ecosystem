# Session 148 Log — Title-Sequence Novelty Distillation (2026-04-09)

## Objective

Take the first honest continuation from the cheap non-API news queue:
- `H329` title-sequence novelty distillation

Question:
- can deterministic title / summary / article-sequence rules recover enough of
  the saved LLM novelty labels to preserve the novelty half-life evidence on the
  current teacher window, without calling a paid API?

This session did not change the live branch.
It stayed long-only.
It did not read `2026+`.

---

## What changed

Added one bounded research script:
- `analysis/h329_title_sequence_novelty_distillation.py`

### H329 - Title-Sequence Novelty Distillation
**Hypothesis:**
The cheapest honest non-API continuation is to distill the saved LLM novelty
labels from deterministic article-sequence rules rather than to retry generic
keyword sentiment.

**Command / code:**
`python analysis/h329_title_sequence_novelty_distillation.py`

**Inputs:**
- `data/news/cafef/raw/*.jsonl`
- `data/llm_cache/*.jsonl`
- current teacher novelty labels from the cached LLM surface
- teacher-window market target built from local stock closes vs `VNINDEX`

**Saved artifact:**
`artifacts/run_summaries/20260409_225625_h329_title_sequence_novelty_distillation_details.json`

| Metric | Value | Note |
|--------|-------|------|
| verdict | `MIXED` | better teacher-label recovery, weak novelty-alpha preservation |
| teacher article rows | `12,295` | ticker-tagged teacher articles only |
| teacher cached days | `728` | available cache days used in the audit |
| teacher date range | `2015-09-21` to `2018-01-03` | current available teacher window, not a full active-book span |
| holdout year | `2017` | held-out teacher slice |
| holdout macro-F1 | `0.3965` | deterministic classifier |
| holdout macro-F1 baseline | `0.3107` | naive `always_new` |
| holdout macro-F1 delta | `+0.0858` | clear improvement over naive baseline |
| holdout balanced accuracy | `0.3971` | above naive `0.3333`, still weak overall |
| holdout `follow_up` precision | `0.1255` | hard class remains poorly captured |
| holdout `follow_up` recall | `0.0673` | hard class remains poorly captured |
| holdout `follow_up` F1 | `0.0876` | below pass bar |
| preserved key alpha contracts | `1 / 3` | only `30d new` kept the teacher sign |
| `1d follow_up` teacher / deterministic IC | `+0.0023 / -0.0142` | sign flipped negative |
| `5d follow_up_minus_new` teacher / deterministic IC | `-0.0025 / +0.0053` | sign flipped positive |
| `30d new` teacher / deterministic IC | `+0.0108 / +0.0092` | sign preserved |

**Result:**
The title-sequence rules did recover real structure. On held-out `2017`, they
beat the naive `always_new` novelty baseline by a material macro-F1 margin and
improved balanced accuracy as well. So the branch is not a clean dead end.

But the class that matters most for short-horizon novelty routing,
`follow_up`, stayed weak. Precision and recall are both low, and the
deterministic novelty surface preserved only `1 / 3` of the teacher novelty
contracts. The short-horizon `1d follow_up` line even flipped negative.

So this is not enough to justify a full deterministic novelty replacement on
the current heuristic. The result is mixed evidence that some cheap structure is
recoverable, not proof that the novelty branch can be taken fully off API.

**Verdict: MIXED**

---

## Branch decision

`H329` narrows the cheap-LLM surrogate branch:
- do **not** keep retuning pure novelty-only deterministic rules in isolation
- do **not** treat the old keyword sentiment path as revived
- keep the result as offline evidence that some teacher structure is recoverable

If the cheap branch continues, the next honest follow-up is:
- `hybrid-news-cascade`
  - use deterministic rules only as a confidence screen
  - route ambiguous / disagreement rows to the canonical LLM schema

Secondary follow-up if a pure deterministic branch is still desired:
- `deterministic-event-family-router`
  - test more lexical teacher fields such as `event_type`,
    `expectation_alignment`, `impact_scope`, and `source_authority`

---

## Validation

Completed during the pass:
- ran `python -m py_compile analysis/h329_title_sequence_novelty_distillation.py`
- ran `python analysis/h329_title_sequence_novelty_distillation.py`
- read `artifacts/run_summaries/latest_research_branch_title_sequence_novelty_distillation.json`
- inspected the saved article confusion table and decay-result parquet

The broader test suite was not run.
