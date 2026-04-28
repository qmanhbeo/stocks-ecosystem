# Session 112 Log

## Objective
Trace the upstream source of `xs_news_sentiment_daily.parquet` and verify whether the LLM surface was genuinely empty or just stale.

This session did not change the live branch.
It did not read `2026+`.

## What changed

Updated notes only:
- `notes/findings-181-210.md`
- `notes/live_state.md`

Verified artifacts:
- `data/features/xs_news_sentiment_daily.parquet`
- `data/features/xs_llm_news_ticker_day.parquet`
- `data/llm_cache/`
- `data/news/cafef/raw/`

### H281 - LLM News Gate Audit Recheck
**Hypothesis:**
The rebuilt LLM ticker-day surface should be traced to its upstream cache and then judged on the same standalone sentiment gate against C1.

**Command / code:**
`conda run -n stocks python analysis/h281_llm_news_gate_audit.py`

**Inputs:**
- `data/features/xs_llm_news_ticker_day.parquet`
- `data/features/xs_news_sentiment_daily.parquet`
- `data/features/xs_barrier_vol_1d_hose_full.parquet`
- upstream source for the rebuilt LLM surface: `data/llm_cache/YYYY-MM-DD.jsonl` (current checkpoint reached `2017-06-04`; extraction is still in progress)

**Saved artifact:**
`artifacts/run_summaries/20260405_211650_h281_llm_news_gate_summary.json`

| Metric | Value | Note |
|--------|-------|------|
| best LLM candidate | `llm_sentiment_raw` | best sentiment-style candidate on the rebuilt LLM surface |
| best LLM avg IC | `+0.0061` | weak, below the current standalone gate |
| best LLM positive years | `2 / 2` | limited clean coverage |
| best LLM corr vs S1 | `+0.0014` | effectively orthogonal to S1 |
| best LLM corr vs C1 | `+0.0458` | still well below the C1 baseline edge |
| candidate rows | `826,404` | full LLM panel rows |
| nonzero LLM rows | `17,578` | rebuilt parquet is populated |
| raw cache horizon | `2015-09-21` to `2017-06-04` | current in-progress checkpoint |
| C1 `sentiment_score` avg IC | `+0.0473` | reference baseline |
| C1 `sentiment_score` positive years | `4 / 5` | baseline consistency on available years |
| C1 `sentiment_cs_z` avg IC | `+0.0688` | stronger but sparse annual coverage |

**Result:**
The LLM surface is not the legacy keyword-news table. It is built from `data/llm_cache`, which in turn is fed by `extract_llm_news_features.py` from raw CafeF news. The rebuilt surface contains real nonzero rows, and the upstream extraction is still in progress with the current checkpoint at `2017-06-04`; the raw sentiment-only contract still does not clear the standalone gate.

**Verdict: FAILED**

## Branch decision

Park `llm-news-gate` on raw sentiment alone.
If the branch is revisited, test a state-router, decay-contract, or interaction-style construct rather than another raw sentiment sweep, and resume the upstream cache build first.

## Validation

Completed during the verification pass:
- checked `data/features/xs_llm_news_ticker_day.parquet` row counts and nonzero coverage
- inspected `alpha-research-lab/data_tools/extract_llm_news_features.py`
- inspected `alpha-research-lab/data_tools/extract_news_sentiment.py`
- inspected `alpha-research-lab/data_tools/fetch_news_archive.py`

Verdict:
- `H281`: **FAILED**
