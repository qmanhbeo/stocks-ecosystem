# Dead Ends 001-030

## D001: Silent Order Pressure Fails Under Current PhoBERT Article-Count Proxy (2026-05-04, Session 258)

Dead end:
- Claim tested: C16 order pressure should be strongest before public narrative
  appears, proxied by `phobert_article_count_1d == 0` or
  `phobert_article_count_5d == 0`.
- Evidence: H381 used `analysis/h381_silent_order_pressure.py` with fixed
  no-news states, TRUE walk-forward test years `2018-2025`, `2016-2025` data
  only, no `2026+`, and direct C16 variation benchmarks.
- Result: `silent_5d` WF IC was `+0.0700`, below all-C16 `+0.0752` and active
  5d-news C16 `+0.0846`; `silent_1d` was also below all-C16 and active 1d-news
  C16. Down-market no-news controls failed the same way.

Do not reopen under current representation:
- Do not keep retesting "no own PhoBERT article count means cleaner C16" as a
  standalone split.
- The first-order effect is inverted: active-news C16 is stronger than no-news
  C16 in the current ticker-day count surface.

Reopening condition:
- Reopen only with a materially different "not public yet" representation, such
  as completed Ollama event-family states, peer/co-mention narrative-vacuum
  features, source-type timing, or another proxy that is not merely own-ticker
  PhoBERT article-count absence.

Source:
- [session_258_log.md](./session_258_log.md)
- `artifacts/run_summaries/20260504_130641_h381_silent_order_pressure_research_branch_silent_order_pressure.json`
