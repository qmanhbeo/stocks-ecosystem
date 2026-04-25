# Next Steps

This is the live small-brain file for current state, recent direction, and
next priorities.
Use [session_177_log.md](./session_177_log.md) for the latest full session
detail, and [findings.md](./findings.md) plus the active findings chunk for
durable conclusions.

---

## Current Live State

- The live alpha branch is unchanged. The current lab focus is on unblocking
  richer news surfaces, durable data acquisition, and low-resource local-ML
  infrastructure rather than promoting a new live branch.
- The active news path is now local-first:
  - PhoBERT owns sentiment
  - PhoBERT owns forward-looking
  - PhoBERT now has repo-native `article_scope` and `source_type` head paths
  - the Ollama residual lane owns only `event_family`, `impact_scope`,
    `source_authority`, `is_rumor`, and confidence / abstention diagnostics
  - combined per-ticker news exports now include the Ollama residual daily
    aggregates
- `llm-cache-fill` is no longer the default blocker for the local-news branch.
  The old hosted teacher cache is now legacy bootstrap material rather than the
  required next production dependency.
- The local Vietnamese encoder lane is now real:
  - PhoBERT sentiment datasets exist under `data/features/news/datasets/`
  - the forward-looking distillation lane uses durable checkpoints under
    `data/model_checkpoints/news/phobert_forward_looking/`
- Local-ML planning budget is now hard-capped at `3GB VRAM / 10GB RAM`.
- Long news/data scripts now expose canonical machine-readable status files
  under `alpha-research-lab/artifacts/job_status/`.
- Heavy PhoBERT train/publish commands now fail fast on this WSL workstation
  when the session hides CUDA even though the real WSL GPU runtime exists.
  Use `NEWS_FEATURES_ALLOW_CPU=1` only for an explicit CPU fallback.

## Immediate Follow-Up

1. `local-news-branch-followthrough`
   - Use the new local-first export contract as the default news surface.
   - First exact operator path:
     `python -m research_pipelines.news_features.core.aggregate_daily_features --sources phobert phobert_forward_looking ollama_guarded`

2. `phobert-binary-head-training`
   - Rerun `article_scope` before trusting its metrics from the first canary.
     That older run used the inherited forward-looking time split plus a hard
     `0.5` decision threshold, which made the head look dead even though the
     saved checkpoint had usable ranking signal.
   - The binary-head contract now supports:
     - head-specific split strategy
     - validation-calibrated positive threshold
     - optional positive class weighting
   - Train and score `article_scope`, then `source_type`, using the same
     sequential canary posture as `forward_looking`.
   - Their publish step now has forward-looking-style shard checkpoints too, so
     interrupted publish runs can resume instead of rescoring from scratch.
   - Exact entrypoints:
     - `python -m research_pipelines.news_features.core.train_phobert_article_scope --candidate-name phobert_base`
     - `python -m research_pipelines.news_features.core.train_phobert_source_type --candidate-name phobert_base`
   - Publish follow-through after each successful canary:
     - `python -m research_pipelines.news_features.core.build_phobert_article_scope_features`
     - `python -m research_pipelines.news_features.core.build_phobert_source_type_features`
   - Keep `forward_looking` sequential too; inspect the matching job-status and
     run-summary files before widening candidate search.

3. `ollama-residual-audit`
   - Audit whether the narrowed local residual taxonomy is useful enough for
     downstream alpha work before expanding local semantic scope again.
   - Do not reopen a broad hosted full-schema replacement branch.

4. `daily-order-pressure-and-proprietary-side-channels`
   - Use the new CafeF daily summary surfaces for order-pressure,
     implementation-pain, proprietary-flow, and cross-flow divergence audits.
   - Do not relabel these daily summaries as solved queue/open-fill or auction
     data.

5. `timing-vendor-source-decision`
   - Only reopen this if the branch still needs more than daily side channels
     and reduced-shape intraday before the LLM cache is ready.
   - The honest next action is still one exact vendor question about
     historical order-book depth, auction-state coverage, granularity, date
     range, and price.

## Recent State Digest

1. `Session 171`
   - The news pipeline now defaults to a local-first contract: PhoBERT for
     sentiment and forward-looking, minimal Ollama residual semantics, and no
     hosted API dependency in the default local-news path.
   - Full detail: [session_171_log.md](./session_171_log.md)

2. `Session 172`
   - Added repo-native PhoBERT `article_scope` and `source_type` head paths by
     reusing the forward-looking staged binary-head pattern.
   - Full detail: [session_172_log.md](./session_172_log.md)

3. `Session 173`
   - Tightened the binary-head trainer so it mirrors the forward-looking lane's
     local-first runtime posture and epoch-level observability.
   - Full detail: [session_173_log.md](./session_173_log.md)

4. `Session 174`
   - Moved the offline PhoBERT runtime guard into repo code so the main local
     PhoBERT commands no longer rely on shell-level offline prefixes.
   - Full detail: [session_174_log.md](./session_174_log.md)

5. `Session 168`
   - The targeted long-job scripts under `data_tools/` now expose canonical
     restart-safe job-status files and stricter durable resume boundaries.
   - Full detail: [session_168_log.md](./session_168_log.md)

6. `Session 175`
   - Confirmed the real WSL runtime sees the RTX 3050 GPU outside the
     restricted sandbox, then hardened heavy PhoBERT train/publish paths to
     fail fast when `/dev/dxg` is hidden instead of silently falling back to
     CPU.
   - Full detail: [session_175_log.md](./session_175_log.md)

7. `Session 176`
   - Upgraded binary-head publish to the same shard-checkpoint/finalize
     contract already used by forward-looking publish, with a focused resume
     test covering the article-scope lane.
   - Full detail: [session_176_log.md](./session_176_log.md)

8. `Session 178`
   - Completed the repaired local PhoBERT `article_scope` and `source_type`
     train/publish sequence on CUDA with mid-epoch train checkpoints,
     resume-safe publish checkpoints, and artifact sanity checks confirming the
     published parquets use the new trained model ids.
   - Full detail: [session_178_log.md](./session_178_log.md)

9. `Session 177`
   - Repaired the semantic binary-head contract so `article_scope` and
     `source_type` no longer inherit the forward-looking date split and hard
     `0.5` threshold blindly. Binary-head training now calibrates a per-head
     decision threshold on validation, publish uses that saved threshold, and
     `article_scope` defaults to a stratified article-level split with positive
     class weighting enabled.
   - Full detail: [session_177_log.md](./session_177_log.md)

10. `Session 167`
   - Repo-local planning assumptions are now explicitly constrained to
      `3GB VRAM / 10GB RAM` for safe local-ML work.
   - Full detail: [session_167_log.md](./session_167_log.md)

11. `Session 166`
   - The first real PhoBERT forward-looking canary forced two runtime repairs
     and established the current watchdog and stage-manifest flow.
   - Full detail: [session_166_log.md](./session_166_log.md)

12. `Local encoder branch`
   - Durable task split and branch reasoning now live in
     [local_bert_roadmap.md](./local_bert_roadmap.md).
   - Completed cheap local Ollama comparisons now live in
     [ollama_model_probe_log.md](./ollama_model_probe_log.md).

## Active / Parked Branch Pointers

- `local-vietnamese-encoder`
  - Active as the default local-news production surface.
  - Start with [local_bert_roadmap.md](./local_bert_roadmap.md).

- `cheap-local-ollama-generator`
  - Narrowed to the minimal local residual semantic lane rather than a direct
    full-schema replacement path.
  - Start with [ollama_model_probe_log.md](./ollama_model_probe_log.md).

- `cheap-llm-surrogate`
  - Parked on the current `2015-2017` teacher window unless new labels,
    more cache coverage, or a materially different contract appears.

- `timing-data-acquisition`
  - Still a source-acquisition-first branch.
  - Start with [timing_data_acquisition_plan.md](./timing_data_acquisition_plan.md)
    and [timing_data_source_scorecard.csv](./timing_data_source_scorecard.csv).

- `official-disclosure-and-daily-side-channels`
  - HNX disclosures plus CafeF order-stats / proprietary-trading now exist as
    raw surfaces, but the next work is bridge-first and audit-first rather than
    a broad alpha promotion claim.

- `foreign-flow`
  - Historical raw source exists, but raw-rank and simple conditioning paths
    failed. The next distinct continuation is a change-point or ownership-regime
    thesis, not more raw thresholds.

## Pointers

- Detailed session traces: `notes/session_NN_log.md`
- Durable conclusions: [findings.md](./findings.md)
- Active findings chunk: [findings-271-300.md](./findings-271-300.md)
- Signal registry: [signal_library.md](./signal_library.md)
- Data/source inventory: [data_sources.md](./data_sources.md)

## Working Rules

- `2026` data remains monitor-only until the user explicitly says otherwise.
- For any material experiment, save a compact result summary and update the
  note stack.
- Keep this file short. Put details in session logs, durable findings, or
  branch-specific notes instead of appending long narrative blocks here.
