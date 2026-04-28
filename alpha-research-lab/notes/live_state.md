# Live State

What this file is for: current working state, active constraints or blockers,
and immediate next actions. Keep it operational and short. Put session detail
in session logs, durable conclusions in findings chunks, failed or parked paths
in dead-end chunks, and cheap recovery context in the compact files.

Latest full session detail: [session_207_log.md](./session_207_log.md)
Last verified: [Session 207](./session_207_log.md), 2026-04-29.

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
- Event-v2, dividend-clock, foreign/proprietary/sector-flow, old OHLCV queue,
  smart-exit linear tweaks, and BERT-only sentiment are parked or failed under
  the current target/consumer contracts. Use the compact dead-end view before
  reopening any of them.

## Active Jobs / Constraints

- No heavy local-model job is currently active.
- The guarded Ollama residual backfill was stopped by request in Session 207.
  The last status-file heartbeat before shutdown was
  `2026-04-28T23:09:46.984098+00:00`, with `755 / 7344` checkpoint batches
  and `15,100` processed input rows.
- Stale status file:
  `alpha-research-lab/artifacts/job_status/ollama_guarded_publish.json`
- Session 207 verified that `tmux` no longer has `ollama_guarded_backfill`,
  `ollama ps` is empty, and no backfill Python process remains. The Ollama
  service itself is still available.
- Local-ML planning budget remains hard-capped at `3GB VRAM / 10GB RAM`.
- `2026` data remains monitor-only until the user explicitly says otherwise.
- Heavy PhoBERT train/publish commands should fail fast when CUDA is hidden;
  use `NEWS_FEATURES_ALLOW_CPU=1` only for an explicit CPU fallback.

## Immediate Next Actions

- If the local-news branch continues, decide whether to resume the guarded
  Ollama residual backfill from checkpoint before doing any downstream
  aggregation.
- Resume command if reopened:
  `python -m research_pipelines.news_features.core.build_ollama_guarded_features`
- After the guarded Ollama residual surface finishes, aggregate the default
  local-first news features:
  `python -m research_pipelines.news_features.core.aggregate_daily_features --sources phobert phobert_forward_looking ollama_guarded`
- Then run one bounded downstream audit of the combined local-news surface
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
