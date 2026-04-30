# Live State

What this file is for: current working state, active constraints or blockers,
and immediate next actions. Keep it operational and short. Put session detail
in session logs, durable conclusions in findings chunks, failed or parked paths
in dead-end chunks, and cheap recovery context in the compact files.

Latest full session detail: [session_211_log.md](./session_211_log.md)
Last verified: [Session 211](./session_211_log.md), 2026-04-30.

Compact recovery:
- [sessions_compact.md](./sessions_compact.md)
- [findings_compact.md](./findings_compact.md)
- [deadends_compact.md](./deadends_compact.md)

Source durable memory:
- [findings.md](./findings.md)
- [findings-301-330.md](./findings-301-330.md)

---

## Current State

- The active lab focus is still local-first news infrastructure and bounded
  follow-through, not a new live alpha promotion.
- The local news stack is real: PhoBERT owns sentiment, forward-looking,
  `article_scope`, and `source_type`; Ollama is only the guarded residual
  event-family lane.
- The hosted `llm-cache-fill` path is legacy bootstrap material, not the
  default blocker for the local-news branch.
- C16 order pressure is now a published shared feature contract at
  `data/features/xs_order_pressure_daily.parquet`, but downstream use is
  opt-in only. Do not run more C16 sizing/search unless a consumer asks for a
  matrix/export integration.
- Event-v2, dividend-clock, legal-holiday timing, foreign/proprietary/sector-flow,
  old OHLCV queue, smart-exit linear tweaks, and BERT-only sentiment are parked
  or failed under the current target/consumer contracts. Use the compact
  dead-end view before reopening any of them.

## Active Jobs / Constraints

- No heavy local-model job is active. The guarded Ollama residual backfill was
  stopped for the day at the user's request in Session 211.
- The stopped run used the lockbox cutoff:
  `python -m research_pipelines.news_features.core.build_ollama_guarded_features --max-published-at 2025-12-31T23:59:59+07:00`
- The cutoff-aware input cache was rebuilt to `142,296` rows with max
  published timestamp `2025-12-31T20:40:05+07:00`; `4,576` gated articles were
  filtered out by date, so the current backfill is not scoring `2026+` rows.
- Stop status: `stopped_by_user`, phase `score`, `3,638 / 7,115` checkpoint
  batches, `72,760 / 142,296` processed input rows, `45,620` reused from the
  existing row-level score cache and `27,140` newly scored after the cache
  boundary. The tmux session is gone, `ollama ps` is empty, and the GPU is idle.
- Local-ML planning budget remains hard-capped at `3GB VRAM / 10GB RAM`.
- `2026` data remains monitor-only until the user explicitly says otherwise.
- Heavy PhoBERT train/publish commands should fail fast when CUDA is hidden;
  use `NEWS_FEATURES_ALLOW_CPU=1` only for an explicit CPU fallback.

## Immediate Next Actions

- Keep the guarded Ollama residual backfill stopped unless the user asks to
  resume it. When it is restarted, use the same checkpoint-safe lockbox command:
  `python -m research_pipelines.news_features.core.build_ollama_guarded_features --max-published-at 2025-12-31T23:59:59+07:00`
- After the guarded Ollama residual surface finishes, aggregate the default
  local-first news features:
  `python -m research_pipelines.news_features.core.aggregate_daily_features --sources phobert phobert_forward_looking phobert_article_scope phobert_source_type ollama_guarded`
- Then run the prepared bounded downstream audit:
  `python analysis/h364_combined_local_news_audit.py`
  before promoting any news feature into the signal library.
- Only if a downstream consumer explicitly asks for C16, merge
  `data/features/xs_order_pressure_daily.parquet` into the consolidated lab
  matrix or an export path and run a focused consumer/portfolio audit.

## Do Not Reopen Unless

- Do not reopen binary-head training unless label quality or downstream alpha
  evidence specifically demands it.
- Do not continue standalone foreign-flow windows, foreign-support-on-C5
  variants, proprietary-flow rank/conflict variants, or sector-pressure
  variants unless a materially different data source, target, or market
  contract exists.
- Do not tune more event-v2 overlays, entry-label variants, payoff-shape
  filters, or sparse-clock variants unless new event data, a materially
  different target, or a different downstream consumer contract exists.
- Do not tune more dividend windows, bonuses, or sparse-clock overlays under
  the current target. Keep the pre-ex clock as offline calendar evidence only.
- Do not tune more legal-holiday pre/post offsets, closure-length gates, bonus
  sizes, or veto variants under the current top-5 executable selector. H363's
  `all_holidays__post_5` payoff hint did not transfer to the fixed portfolio
  sparse-clock contract.
- Do not continue linear smart-exit feature-set tweaks unless richer
  post-entry state/data or a materially different model contract appears.
- Do not rerun stale H135/H136/H137 old-OHLCV variants under the current
  contract.
- Do not tune more BERT-only sentiment variants or promote PhoBERT sentiment
  standalone; keep official-conditioned sentiment as a candidate transform for
  the combined local-news audit.

## Pointers

- Detailed session traces: `notes/session_NN_log.md`
- Signal registry: [signal_library.md](./signal_library.md)
- Data/source inventory: [data_sources.md](./data_sources.md)
- Local BERT roadmap: [local_bert_roadmap.md](./local_bert_roadmap.md)
- Ollama probe log: [ollama_model_probe_log.md](./ollama_model_probe_log.md)
- Timing acquisition plan:
  [timing_data_acquisition_plan.md](./timing_data_acquisition_plan.md)
- Timing source scorecard:
  [timing_data_source_scorecard.csv](./timing_data_source_scorecard.csv)

## Working Rules

- For any material experiment, save a compact result summary and update the
  note stack.
- Use compact files for cheap context recovery before opening long session
  logs or findings chunks.
- Close out every material pass with this checklist:
  - session log updated
  - `sessions_compact.md` prepended with a source-linked entry
  - `live_state.md` updated only if current state, constraints, or immediate
    actions changed, with `Last verified` refreshed when checked
  - durable findings or dead ends promoted when warranted
  - `findings_compact.md` or `deadends_compact.md` updated only when durable
    memory changed, with source anchors included
- Keep this file focused on current state and immediate action. If a detail is
  not needed to decide the next pass, move it to a source note or compact view.
