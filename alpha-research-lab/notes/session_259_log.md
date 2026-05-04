# Session 259 Log

Date: 2026-05-04
Focus: Finish Ollama unblock follow-through and run H364 combined local-news audit

## Summary

- Confirmed the guarded Ollama residual backfill is complete:
  `7344 / 7344` checkpoint batches, `146,872` gated input articles, and
  `1,406,206` ticker-day rows.
- Patched `analysis/h364_combined_local_news_audit.py` so its readiness check
  accepts the current authorized full Ollama backfill with blank
  `max_published_at`. The audit still filters all feature frames and S1 rows to
  `2016-2025`, so `2026+` is not used for the H364 decision.
- Refreshed the default local-news aggregate overlay with PhoBERT sentiment,
  forward-looking, article-scope, source-type, and Ollama guarded residual
  features.
- Ran H364 from the saved script and judged from the saved JSON summary.

## Commands

```bash
/home/manh/miniforge3/envs/stocks/bin/python -m py_compile analysis/h364_combined_local_news_audit.py

/home/manh/miniforge3/envs/stocks/bin/python -m research_pipelines.news_features.core.aggregate_daily_features --sources phobert phobert_forward_looking phobert_article_scope phobert_source_type ollama_guarded

/home/manh/miniforge3/envs/stocks/bin/python analysis/h364_combined_local_news_audit.py
```

## Aggregate Output

- Loaded source rows:
  - PhoBERT sentiment: `1,436,996`
  - PhoBERT forward-looking: `1,436,996`
  - PhoBERT article-scope: `1,436,996`
  - PhoBERT source-type: `1,436,996`
  - Ollama guarded: `1,406,206`
- Wrote `1,436,996` combined rows across `406` tickers to:
  `data/features/news/datasets/news_daily_features.parquet`
- Per-ticker exports under `data/features/news/predictions/` were refreshed by
  the aggregate command.

## H364 Result

Saved summary:
- `artifacts/run_summaries/20260504_183132_h364_combined_local_news_audit_research_branch_combined_local_news_audit.json`

Verdict: `PASSED`.

Best fixed feature:
- `h364_official_sentiment_x_earnings_guidance`

Metrics:
- active rows: `103,248`
- coverage: `13.329%` of S1 rows
- average IC: `+0.01766`
- positive years: `10 / 10`
- S1 correlation: `-0.0104`
- dev IC: `+0.0173`
- validation IC: `+0.0200`
- confirmation 2025 IC: `+0.0156`
- validation rows: `23,130`
- confirmation rows: `12,370`

## Verdict

The completed Ollama event-family residual surface unlocked the first
standalone local-news pass. The useful state is not broad pooled news sentiment;
it is official/regulatory source probability, sentiment, and Ollama
earnings/guidance event-family agreement.

This is a candidate local-news signal and offline evidence, not a live-branch
change. Per the H364 ladder, the next honest step is one fixed
portfolio/consumer integration audit for
`h364_official_sentiment_x_earnings_guidance`, with no `2026+` fitting.

## Files Changed

- `analysis/h364_combined_local_news_audit.py`
- `data/features/news/datasets/news_daily_features.parquet`
- `data/features/news/predictions/*_news_features.parquet`
- `artifacts/run_summaries/20260504_183132_h364_combined_local_news_audit_research_branch_combined_local_news_audit.json`
- note stack: `notes/session_259_log.md`, `notes/live_state.md`,
  `notes/sessions_compact.md`,
  `notes/findings-331-360.md`, `notes/findings_compact.md`,
  `notes/signal_library.md`

## Verification

- `py_compile` passed for the edited H364 script.
- Aggregate command completed and wrote the combined news dataset.
- H364 completed and wrote a saved run summary.
