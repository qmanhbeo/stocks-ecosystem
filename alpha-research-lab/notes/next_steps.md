# Next Steps

This is a lightweight research backlog. The operational source of truth remains
`notes/live_state.md`.

## Local-News Queue

Context:
- The guarded Ollama residual backfill is stopped for the day at
  `3,638 / 7,115` checkpoint batches with a 2025 cutoff.
- H342/H343/H344 show BERT-only sentiment/context is not enough for standalone
  promotion, but official-conditioned sentiment is useful offline evidence.
- H364 is prepared as the fixed combined local-news audit and should only run
  after Ollama completes and all local sources are aggregated.

Queue:
- Resume and finish `ollama_guarded_backfill` only when requested:
  `python -m research_pipelines.news_features.core.build_ollama_guarded_features --max-published-at 2025-12-31T23:59:59+07:00`
- Aggregate all local news surfaces:
  `python -m research_pipelines.news_features.core.aggregate_daily_features --sources phobert phobert_forward_looking phobert_article_scope phobert_source_type ollama_guarded`
- Run:
  `python analysis/h364_combined_local_news_audit.py`

## Bright-Mind Queue: Holiday Timing

Context:
- Session 5 tested Tet and generic seasonality as broad FPT-era model features;
  that path failed and should not be repeated as dense calendar inputs.
- Session 209 ran H363 as the current legal-major public-holiday timing audit.
  The holiday calendar builder produced `436` 2015-2025 sparse pre/post trading
  states across `53` VNINDEX-inferred closure clusters with no `2026+` leakage.
- H363 found one payoff-passing state, `all_holidays__post_5`, but the required
  fixed `+0.015` sparse portfolio bonus had `0.00% / 0.00%`
  validation/confirmation relative-return deltas and failed the portfolio gate.

Queue:
- `holiday_closure_dislocation`: completed by H363 as generic holiday/closure
  payoff evidence. Keep only as offline evidence; do not tune closure-length
  gates under the current selector.
- `civil_holiday_sparse_clock`: closed by H363 under the current fixed sparse
  portfolio contract. Civil holiday states had hints, but no portfolio-level
  rule is promotable without changing the target or downstream consumer.
- `holiday_news_silence_break`: claim that holiday windows matter most when
  company-specific news or official disclosures break through a low-attention
  period. First test: after the local-news aggregate finishes, compare
  holiday-window news/disclosure tagged names against matched non-holiday names.

Guardrail:
- Do not reopen generic calendar/seasonality features. Treat holidays as sparse
  state-transition or execution/attention tests, exclude `2026+`, and require
  validation plus confirmation before any portfolio experiment is promoted.
- After H363, do not tune more legal-holiday pre/post offsets, bonus sizes, or
  veto variants under the current top-5 executable selector.
