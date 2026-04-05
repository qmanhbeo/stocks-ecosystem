# Session 110 Log

## Objective
Run the next possible queued branch after the H280 confirmation failure:
- `H281`: test the built LLM news sentiment surface as a standalone gate
- compare the best LLM sentiment candidate against the legacy keyword-news baseline C1
- keep the live branch frozen

This session did not change the live branch.
It did not read `2026+`.

## What changed

Added:
- `analysis/h281_llm_news_gate_audit.py`

Saved artifacts:
- `artifacts/run_summaries/20260405_210827_h281_llm_news_gate_audit_signal_library_llm_news_gate.json`
- `artifacts/run_summaries/20260405_210827_h281_llm_news_gate_summary.json`
- `artifacts/portfolio_baselines/20260405_210827_h281_llm_news_gate_results.parquet`

### H281 - LLM News Gate Audit
**Hypothesis:**
The built LLM ticker-day news surface should produce a standalone sentiment signal with cleaner consistency than the legacy keyword-news baseline C1.

**Command / code:**
`conda run -n stocks python analysis/h281_llm_news_gate_audit.py`

**Inputs:**
- `data/features/xs_llm_news_ticker_day.parquet`
- `data/features/xs_news_sentiment_daily.parquet`
- `data/features/xs_barrier_vol_1d_hose_full.parquet`
- evaluation window:
  - LLM surface: `2015-2025`
  - C1 baseline: `2016-2025`

**Saved artifact:**
`artifacts/run_summaries/20260405_210827_h281_llm_news_gate_summary.json`

| Metric | Value | Note |
|--------|-------|------|
| best LLM candidate | `llm_sentiment_raw` | all LLM sentiment variants tied on the same constant surface |
| best LLM avg IC | `NaN` | constant-input surface, so IC is undefined |
| best LLM positive years | `0 / 11` | no yearly variation to score |
| best LLM corr vs S1 | `NaN` | undefined from constant input |
| best LLM corr vs C1 | `NaN` | undefined from constant input |
| candidate rows | `826,404` | full LLM panel rows |
| C1 `sentiment_score` avg IC | `+0.0473` | reference baseline |
| C1 `sentiment_score` positive years | `4 / 5` | baseline consistency on available years |
| C1 `sentiment_cs_z` avg IC | `+0.0688` | stronger but sparse annual coverage |

**Result:**
The built LLM sentiment surface does not currently function as a standalone signal on this artifact. Every tested sentiment-style LLM column was constant-zero / undefined, so there is no usable IC to promote.

**Verdict: FAILED**

## Branch decision

Park `llm-news-gate` on the current artifact.
If the branch is ever reopened, it needs a non-constant sentiment surface or a different extracted contract.

## Validation

Completed before the run:
- `conda run -n stocks python -m py_compile alpha-research-lab/analysis/h281_llm_news_gate_audit.py`

Completed for the experiment:
- `conda run -n stocks python analysis/h281_llm_news_gate_audit.py`
- read `artifacts/run_summaries/20260405_210827_h281_llm_news_gate_summary.json`

Verdict:
- `H281`: **FAILED**
