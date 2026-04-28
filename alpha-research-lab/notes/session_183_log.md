# Session 183 Log - BERT-Only News Semantic Audit (2026-04-28)

## Objective

Continue the evergreen loop with data already available on disk:
- keep the live alpha branch unchanged
- avoid `2026` predictive use
- avoid GPU / Ollama / PhoBERT training jobs
- resolve the open question from Session 178: whether the completed PhoBERT
  `article_scope` and `source_type` heads add downstream alpha or routing value

This session stayed long-only.
It did not use `2026` for predictive tuning.

## Watchdog state

The previous Ollama residual runner was intentionally stopped before this pass.

Preflight checks:
- `ollama ps` returned no loaded model
- `nvidia-smi` showed no running GPU process
- no matching `build_ollama_guarded_features`, `train_phobert`, or Ollama
  runner process was active

Decision:
- do not resume the multi-day Ollama backfill in this session
- run only CPU/parquet audits on existing feature artifacts

## Experiments

### H343 - PhoBERT Semantic Condition Audit

**Hypothesis:**
The new local PhoBERT semantic heads may not be strong standalone intensity
signals, but they may make sentiment useful by routing it through stock-news,
forward-looking, or official-source states.

**Command / code:**
`python analysis/h343_phobert_semantic_condition_audit.py`

**Inputs:**
- `data/features/xs_barrier_vol_1d_hose_full.parquet`
- `data/features/news/datasets/phobert_ticker_day_sentiment.parquet`
- `data/features/news/datasets/phobert_forward_looking_ticker_day_features.parquet`
- `data/features/news/datasets/phobert_article_scope_ticker_day_features.parquet`
- `data/features/news/datasets/phobert_source_type_ticker_day_features.parquet`

**Saved artifact:**
`artifacts/run_summaries/20260428_065330_h343_phobert_semantic_condition_audit_research_branch_phobert_semantic_condition_audit.json`

| Metric | Value | Note |
|--------|-------|------|
| best feature | `h343_sentiment_x_official` | sentiment gated by source-type official/regulatory probability |
| avg IC | `+0.0125` | above the broad standalone IC bar |
| positive years | `9 / 10` | broad consistency passes |
| S1 corr | `-0.0498` | orthogonal to S1 |
| coverage | `22.48%` | same active-news support as PhoBERT sentiment |
| direct forward-looking IC | `+0.0062` | direct semantic intensity did not clear |
| direct article-scope IC | `+0.0082` | did not clear standalone gate |
| direct source-type IC | `+0.0071` | did not clear standalone gate |

**Result:**
Source-conditioned sentiment passed the broad H343 gate, while direct BERT head
intensity did not. This is useful evidence that `source_type` can improve the
local news surface, but the yearly details showed 2025 was negative, so a
fixed-winner confirmation audit was required before any promotion language.

**Verdict: PASSED, pending fixed-winner confirmation**

### H344 - PhoBERT Official-Sentiment Confirmation Audit

**Hypothesis:**
If H343 found a real standalone candidate, the fixed winner should survive the
lab's dev / validation / confirmation split without re-searching features.

**Command / code:**
`python analysis/h344_phobert_official_sentiment_confirmation.py`

**Inputs:**
- `artifacts/run_summaries/latest_research_branch_phobert_semantic_condition_audit.json`

**Saved artifact:**
`artifacts/run_summaries/20260428_065445_h344_phobert_official_sentiment_confirmation_research_branch_phobert_official_sentiment_confirmation.json`

| Metric | Value | Note |
|--------|-------|------|
| fixed feature | `h343_sentiment_x_official` | no new search |
| dev IC | `+0.0143` | 2016-2022 |
| validation IC | `+0.0146` | 2023-2024 |
| confirmation IC | `-0.0042` | 2025 |
| branch decision | offline evidence only | confirmation is non-positive |

**Result:**
The H343 winner is useful offline evidence but not a standalone promoted signal.
It worked in dev and validation, then failed the one-shot 2025 confirmation.
The correct next use is as a candidate transform inside the later combined
local-news audit, not another round of BERT-only sentiment tuning.

**Verdict: FAILED for standalone promotion**

## Memory changes

Updated:
- `notes/live_state.md`
- `notes/findings-271-300.md`
- `notes/signal_library.md`

Added:
- `analysis/h343_phobert_semantic_condition_audit.py`
- `analysis/h344_phobert_official_sentiment_confirmation.py`

Durable finding:
- `F284`

No durable dead-end file exists in the current repo note convention, so the
negative standalone-promotion result is recorded in the active findings chunk
and live tree instead.

## Verification

Completed:
- `python -m py_compile analysis/h343_phobert_semantic_condition_audit.py`
- `python analysis/h343_phobert_semantic_condition_audit.py`
- `python -m py_compile analysis/h344_phobert_official_sentiment_confirmation.py`
- `python analysis/h344_phobert_official_sentiment_confirmation.py`

## Next step

Do not promote BERT-only sentiment standalone.

The local-news branch should either:
- resume the guarded Ollama event-family residual backfill when multi-day local
  inference is acceptable, then run the combined local-news audit; or
- keep H343/H344 as offline context and move the evergreen loop to another
  CPU-light existing-data hypothesis.
