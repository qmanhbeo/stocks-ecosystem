# Session 120 Log

## Objective
Test whether the rebuilt LLM news surface contains a real state-gated edge in the early nonzero window, and whether that edge survives bucketed audits better than raw pooled sentiment.

This session did not change the live branch.
It did not read `2026+`.

## What changed

Added the H290 LLM news state-router audit script.

Saved artifacts:
- `artifacts/run_summaries/20260405_231037_h290_llm_news_state_router_audit_details.json`
- `artifacts/run_summaries/20260405_231037_h290_llm_news_state_router_audit_standalone_signal.json`

### H290 - LLM News State Router Audit
**Hypothesis:**
The rebuilt CafeF LLM news surface should separate follow-up / miss-state news from the weak pooled sentiment surface, with the edge showing up in the right news-state buckets rather than in raw sentiment alone.

**Command / code:**
`conda run -n stocks python analysis/h290_llm_news_state_router_audit.py`

**Inputs:**
- `data/features/xs_llm_news_ticker_day.parquet`

**Saved artifact:**
`artifacts/run_summaries/20260405_231037_h290_llm_news_state_router_audit_standalone_signal.json`

| Metric | Value | Note |
|--------|-------|------|
| verdict | `PASS` | state-gated edge exists, but only offline |
| best feature | `llm_sentiment_5d` | strongest bucketed surface |
| best state kind | `novelty` | best gate family |
| best bucket | `follow` | strongest bucket |
| mean daily IC | `+0.4796` | very strong in-window edge |
| daily hit rate | `0.8667` | 13/15 positive days in the bucket |
| positive years | `1 / 1` | only one nonzero year in this bucket |
| best nonzero rows | `75` | bucket-level nonzero rows |
| window years | `2015-2017` | only nonzero news window |
| nonzero window rows | `4308` | raw active rows in the nonzero window |
| pooled `llm_sentiment_30d` IC | `-0.0121` | weak / negative overall surface |

**Result:**
The rebuilt LLM news surface does contain real signal, but it is state-gated rather than generic. Follow-up news and miss-state news carry the useful edge, while pooled sentiment and beat/new states are weak or negative. The active-book years remain effectively zero-valued in this cache surface, so this is offline evidence only for now.

**Verdict: PASS**

## Branch decision

Keep `C15` as offline evidence only.
Keep `news-marginal-slot` blocked until active-book years have nonzero news coverage.
The next queue item is `news-decay-contract`.

## Validation

Completed before the run:
- `conda run -n stocks python analysis/h290_llm_news_state_router_audit.py`

Completed for the experiment:
- read `artifacts/run_summaries/20260405_231037_h290_llm_news_state_router_audit_standalone_signal.json`

Verdict:
- `H290`: **PASS**
