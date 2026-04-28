# Next Steps

This is the live small-brain file for current state, recent direction, and
next priorities.
Use [session_187_log.md](./session_187_log.md) for the latest full session
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
  - the Ollama residual lane now defaults to the minimal event-family task;
    wider generator fields remain optional diagnostics, while `article_scope`
    and `source_type` are the preferred local scope/source proxies
  - combined per-ticker news exports should include the Ollama residual daily
    aggregates after the guarded backfill and aggregation pass finish
- `llm-cache-fill` is no longer the default blocker for the local-news branch.
  The old hosted teacher cache is now legacy bootstrap material rather than the
  required next production dependency.
- The local Vietnamese encoder lane is now real:
  - PhoBERT sentiment datasets exist under `data/features/news/datasets/`
  - the forward-looking distillation lane uses durable checkpoints under
    `data/model_checkpoints/news/phobert_forward_looking/`
- The repaired `article_scope` and `source_type` PhoBERT heads are already
  trained and published; do not reopen binary-head training as the next queue
  item unless label quality or downstream alpha evidence specifically demands
  it.
- There is no active heavy local-model job at the moment. The BERT-gated
  Ollama residual backfill was stopped after `12 / 7344` checkpoint batches,
  leaving reusable partial score/checkpoint state for `240` completed article
  rows.
- Local-ML planning budget is now hard-capped at `3GB VRAM / 10GB RAM`.
- Long news/data scripts now expose canonical machine-readable status files
  under `alpha-research-lab/artifacts/job_status/`.
- Heavy PhoBERT train/publish commands now fail fast on this WSL workstation
  when the session hides CUDA even though the real WSL GPU runtime exists.
  Use `NEWS_FEATURES_ALLOW_CPU=1` only for an explicit CPU fallback.

## Immediate Follow-Up

1. `ollama-residual-backfill-resume`
   - Current state: stopped / partial, not actively running.
   - Status file:
     `artifacts/job_status/ollama_guarded_publish.json`
   - The no-flag default remains the intended resume command:
     `python -m research_pipelines.news_features.core.build_ollama_guarded_features`
   - Expected scope: BERT-gated priority universe only,
     `phobert_article_scope_prob_positive >= 0.28`, about `146872` article
     rows, `20`-row checkpoint shards, and reusable row-level score cache under
     `data/features/news/datasets/ollama_guarded_score_cache/`.
   - The stopped partial state currently has `12 / 7344` checkpoint batches and
     `240` scored article rows. Resume only when the machine is intended to
     spend multi-day local Ollama time again.

2. `local-news-branch-followthrough-after-ollama`
   - After the guarded Ollama residual surface finishes, aggregate the default
     local-first news features:
     `python -m research_pipelines.news_features.core.aggregate_daily_features --sources phobert phobert_forward_looking ollama_guarded`
   - Then run a bounded downstream audit of the combined local-news surface
     before promoting any news feature into the signal library.

3. `phobert-news-signal-audit`
   - Existing H342 evidence says pooled PhoBERT sentiment is not a promoted
     standalone alpha signal: best PhoBERT sentiment avg IC was only `+0.0082`
     and failed the gate, while sparse keyword sentiment stayed stronger but
     narrow.
   - H343 found a useful BERT-only conditioned feature:
     `h343_sentiment_x_official` had avg IC `+0.0125`, `9 / 10` positive years,
     and S1 corr `-0.0498`.
   - H344 then fixed that winner and applied the dev / validation /
     confirmation split. It failed standalone promotion because 2025
     confirmation was `-0.0042` despite dev `+0.0143` and validation `+0.0146`.
   - Keep official-conditioned PhoBERT sentiment as offline evidence and a
     candidate transform for the later combined local-news audit. Do not tune
     more BERT-only sentiment variants or promote it standalone.

4. `foreign-flow-standalone-state`
   - Historical CafeF foreign flow is source-usable, but the standalone alpha
     path is weak after four negative screens: H327 raw ranks, H328 simple
     conditioning, H333 room-residual discontinuities, and H345 accumulation /
     ownership-change change-points.
   - Do not continue standalone foreign-flow window or threshold tuning. If
     reopened, require a distinct interaction contract such as
     foreign-insider agreement, proprietary-flow conflict/agreement, or
     sector-specific ownership pressure.

5. `foreign-insider-interaction-state`
   - H347 tested the first distinct interaction contract: foreign-flow
     agreement as a conditioner on bullish `C5`, benchmarked against the
     current H340 buy-volume-pressure rewrite.
   - Result: `MIXED`. Foreign agreement improved raw `C5` and held `11 / 11`
     positive years, but the best row still trailed H340 on avg, validation,
     and confirmation IC.
   - Do not tune more foreign-net windows around `C5`. Keep H340 as the
     preferred daily-state form. If flow interactions continue, move to a
     materially different actor surface such as proprietary-flow
     conflict/agreement.

6. `proprietary-flow-pilot-state`
   - H348 tested proprietary-flow ranks plus foreign/proprietary
     agreement/conflict states under a limited-source `2023 / 2024 / 2025`
     pilot.
   - Result: `FAILED`. Best row `xs_prop_buy_share_5d_rank` cleared 2023 dev
     IC at `+0.0144`, then flipped to `-0.0216` in 2024 validation and
     `-0.0110` in 2025 confirmation.
   - Do not continue proprietary-flow rank, agreement, or conflict threshold
     variants on the same S1 target.

7. `daily-side-channel-queue-state`
   - H340 passed: same-day posted buy-volume pressure is the preferred
     positive-side robustness rewrite of bullish C5.
   - H341 failed: stacking exec-rate on top of H340 did not improve the
     current daily contract.
   - Do not spend more cycles stacking the same daily filters. If this family
     continues, move to a distinct official-source bridge rather than another
     order-pressure tweak.

8. `old-ohlcv-queue-state`
   - The stale H135/H136/H137 queue entries are now closed:
     H135 was solved by H283, H136 was solved by H284, and H137 was solved by
     H346. Do not rerun those old gap/compression/long-horizon residual
     variants under the current contract.

9. `timing-vendor-source-decision`
   - Only reopen this if the branch still needs more than daily side channels
     and reduced-shape intraday before the LLM cache is ready.
   - The honest next action is still one exact vendor question about
     historical order-book depth, auction-state coverage, granularity, date
     range, and price.

## Recent State Digest

1. `Session 187`
   - Ran H348 as a limited-source proprietary-flow conflict/agreement pilot.
     The best row cleared 2023 dev, then flipped negative in 2024 and 2025, so
     proprietary-flow rank variants should not continue on this target.
   - Full detail: [session_187_log.md](./session_187_log.md)

2. `Session 186`
   - Ran H347 as a CPU-only foreign-flow interaction pass. Foreign agreement
     improved raw `C5`, but did not beat the stronger H340 order-pressure
     rewrite. Keep it as offline interaction evidence only.
   - Full detail: [session_186_log.md](./session_186_log.md)

3. `Session 185`
   - Ran H346 to close the stale residual long-horizon reversal queue item.
     The sign-flipped residual after removing C11 failed; the continuation
     residual was directionally positive but below gate. Signal-library stale
     H135/H136/H137 rows were cleaned up.
   - Full detail: [session_185_log.md](./session_185_log.md)

4. `Session 184`
   - Ran H345 as a CPU-only CafeF foreign-flow continuation. Accumulation /
     ownership-change change-points failed the unchanged foreign-flow gate, so
     standalone H95 tuning should stop unless a distinct interaction contract
     is introduced.
   - Full detail: [session_184_log.md](./session_184_log.md)

5. `Session 183`
   - Ran H343/H344 as CPU-only existing-data audits. H343 showed
     official-conditioned PhoBERT sentiment clears the broad standalone gate,
     but H344 failed it as a standalone promoted signal under 2025
     confirmation.
   - Full detail: [session_183_log.md](./session_183_log.md)

6. `Session 182`
   - Ran an evergreen artifact-only queue pass while the Ollama residual
     backfill continued as the active heavy job. H340/H341/H342 were treated as
     solved existing hypotheses rather than reopened.
   - Full detail: [session_182_log.md](./session_182_log.md)

7. `Session 181`
   - Added row-level Ollama score caching and checkpoint-cadence migration so
     `checkpoint_rows` changes no longer invalidate expensive scoring outputs.
   - Full detail: [session_181_log.md](./session_181_log.md)

8. `Session 171`
   - The news pipeline now defaults to a local-first contract: PhoBERT for
     sentiment and forward-looking, minimal Ollama residual semantics, and no
     hosted API dependency in the default local-news path.
   - Full detail: [session_171_log.md](./session_171_log.md)

9. `Session 172`
   - Added repo-native PhoBERT `article_scope` and `source_type` head paths by
     reusing the forward-looking staged binary-head pattern.
   - Full detail: [session_172_log.md](./session_172_log.md)

10. `Session 173`
   - Tightened the binary-head trainer so it mirrors the forward-looking lane's
     local-first runtime posture and epoch-level observability.
   - Full detail: [session_173_log.md](./session_173_log.md)

11. `Session 174`
   - Moved the offline PhoBERT runtime guard into repo code so the main local
     PhoBERT commands no longer rely on shell-level offline prefixes.
   - Full detail: [session_174_log.md](./session_174_log.md)

12. `Session 168`
   - The targeted long-job scripts under `data_tools/` now expose canonical
     restart-safe job-status files and stricter durable resume boundaries.
   - Full detail: [session_168_log.md](./session_168_log.md)

13. `Session 175`
   - Confirmed the real WSL runtime sees the RTX 3050 GPU outside the
     restricted sandbox, then hardened heavy PhoBERT train/publish paths to
     fail fast when `/dev/dxg` is hidden instead of silently falling back to
     CPU.
   - Full detail: [session_175_log.md](./session_175_log.md)

14. `Session 176`
   - Upgraded binary-head publish to the same shard-checkpoint/finalize
     contract already used by forward-looking publish, with a focused resume
     test covering the article-scope lane.
   - Full detail: [session_176_log.md](./session_176_log.md)

15. `Session 178`
   - Completed the repaired local PhoBERT `article_scope` and `source_type`
     train/publish sequence on CUDA with mid-epoch train checkpoints,
     resume-safe publish checkpoints, and artifact sanity checks confirming the
     published parquets use the new trained model ids.
   - Full detail: [session_178_log.md](./session_178_log.md)

16. `Session 179`
   - Optimized the local Ollama residual prompt under the hardware cap. The
     safe default is now bottom-schema event-family-only JSON with `num_ctx=512`
     and first-300-word article truncation. A BERT-gated checkpointed backfill
     is running in `tmux` as `ollama_guarded_backfill`.
   - Full detail: [session_179_log.md](./session_179_log.md)

17. `Session 177`
   - Repaired the semantic binary-head contract so `article_scope` and
     `source_type` no longer inherit the forward-looking date split and hard
     `0.5` threshold blindly. Binary-head training now calibrates a per-head
     decision threshold on validation, publish uses that saved threshold, and
     `article_scope` defaults to a stratified article-level split with positive
     class weighting enabled.
   - Full detail: [session_177_log.md](./session_177_log.md)

18. `Session 167`
   - Repo-local planning assumptions are now explicitly constrained to
      `3GB VRAM / 10GB RAM` for safe local-ML work.
   - Full detail: [session_167_log.md](./session_167_log.md)

19. `Session 166`
   - The first real PhoBERT forward-looking canary forced two runtime repairs
     and established the current watchdog and stage-manifest flow.
   - Full detail: [session_166_log.md](./session_166_log.md)

20. `Local encoder branch`
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
    raw surfaces, but H348 failed the first proprietary-flow rank/agreement
    pilot. The next work is bridge-first and audit-first rather than a broad
    alpha promotion claim.

- `foreign-flow`
  - Historical raw source exists, but raw-rank, simple conditioning,
    room-residual, and accumulation / ownership-change paths failed. H347 then
    showed foreign-insider agreement improves raw `C5` but does not beat H340.
    H348 then failed the proprietary-flow conflict/agreement pilot. Do not
    spend more cycles on standalone foreign-flow windows, foreign support
    around `C5`, or proprietary-flow rank/conflict variants. The only honest
    reopening is a materially different thesis such as sector-specific
    ownership pressure or an official-source bridge.

- `old-ohlcv-queue`
  - The stale signal-library queue items H135/H136/H137 are closed by
    H283/H284/H346. Continue only with genuinely new OHLCV contracts, not more
    small variants around C11 or C13.

## Evergreen Research Tree

- `EVG-NEWS-001 local-news-followthrough`
  - Parent: local-news branch. Status: active but blocked on whether to resume
    the stopped Ollama residual backfill. Thesis: a fully local Vietnamese news
    surface may add sparse orthogonal context without reopening hosted LLM cost.
    Mechanism: combine local sentiment, source/scope/forward-looking routing,
    and residual event-family labels. Current evidence: PhoBERT sentiment /
    forward-looking / article-scope / source-type surfaces exist; H343/H344 say
    official-conditioned sentiment is offline evidence but not standalone
    confirmed; Ollama residual has only partial checkpoint state. Best
    artifacts: `notes/session_178_log.md`, `notes/session_183_log.md`,
    `artifacts/run_summaries/latest_research_branch_phobert_official_sentiment_confirmation.json`,
    `artifacts/job_status/ollama_guarded_publish.json`. Latest experiment:
    H344. Children: EVG-TEXT-001. Priority score: `0.78`. Money relevance:
    high if the combined local-news surface survives sparse-news gates. Next
    action: resume Ollama only when multi-day local inference is acceptable;
    otherwise keep BERT-only findings as offline context. Reopening condition:
    combined surface fails all standalone/conditioning gates or residual
    backfill parse quality is unusable.

- `EVG-SIDE-001 c5-daily-state`
  - Parent: C5 insider branch. Status: solved on current daily contract.
    Thesis: daily buy-volume pressure cleans bullish insider conviction.
    Evidence: H340 passed with avg IC `+0.0693`; H341 showed exec-rate stacking
    does not improve it. Best artifacts:
    `artifacts/run_summaries/latest_research_branch_c5_order_pressure_split.json`,
    `artifacts/run_summaries/latest_research_branch_c5_pressure_exec_stack.json`.
    Latest experiment: H341. Children: none active. Priority score: `0.55`.
    Money relevance: medium-high as a sparse robustness
    rewrite. Next action: use H340 as preferred C5 form; do not retest same
    stack. Reopen condition: new official-source bridge provides a genuinely
    distinct event timing dimension.

- `EVG-TEXT-001 phobert-sentiment-alpha`
  - Parent: EVG-NEWS-001. Status: parked as standalone; useful offline
    evidence only. Thesis: whole-article PhoBERT sentiment might become useful
    when conditioned by source/scope/forward-looking routing. Mechanism:
    source-conditioned sentiment should separate higher-authority company news
    from generic media noise. Current evidence: H342 pooled sentiment failed;
    H343 `h343_sentiment_x_official` cleared the broad gate with avg IC
    `+0.0125`, but H344 failed standalone promotion because 2025 confirmation
    was `-0.0042`. Best artifacts:
    `artifacts/run_summaries/latest_research_branch_phobert_news_gate.json`,
    `artifacts/run_summaries/latest_research_branch_phobert_semantic_condition_audit.json`,
    `artifacts/run_summaries/latest_research_branch_phobert_official_sentiment_confirmation.json`.
    Latest experiment: H344. Children: none active. Priority score: `0.42`.
    Money relevance: unknown until combined local-news audit. Next action:
    keep `h343_sentiment_x_official` as a candidate transform for the combined
    local-news audit; do not tune more BERT-only sentiment variants. Reopening
    condition: Ollama event-family completion or a new official-source bridge
    changes the conditioning surface.

- `EVG-FLOW-001 foreign-flow-standalone`
  - Parent: H95 historical foreign-flow branch. Status: parked / nearly killed
    as a standalone feature family; foreign-insider interaction is mixed
    offline evidence only. Thesis: foreign accumulation, ownership pressure, or
    room scarcity might reveal institutional demand not captured by OHLCV.
    Mechanism: foreign investor persistence or room pressure should create
    later follow-through in constrained names. Current evidence: source is
    usable, but H327 raw ranks failed, H328 simple conditioning failed, H333
    room-residual discontinuities failed, and H345 accumulation /
    ownership-change change-points failed with best dev IC only `+0.0020`.
    H347 improved raw `C5` through foreign agreement but still failed to beat
    the stronger H340 order-pressure rewrite.
    Best artifacts:
    `artifacts/run_summaries/latest_research_branch_cafef_foreign_flow_source_audit.json`,
    `artifacts/run_summaries/latest_research_branch_foreign_room_residual_discontinuity.json`,
    `artifacts/run_summaries/latest_research_branch_foreign_accumulation_change_point.json`,
    `artifacts/run_summaries/latest_research_branch_foreign_insider_agreement_split.json`.
    Latest experiment: H347. Children: none active. Priority score: `0.18`.
    Money relevance: low as standalone, medium only if paired with a genuinely
    distinct proprietary-flow or sector-ownership interaction. Next action: do
    not tune standalone windows or foreign-support-on-C5 variants; only reopen
    with a materially different interaction contract. Reopening condition: a
    separate non-price source creates a predeclared agreement/conflict state
    that was not tested by H327/H328/H333/H345/H347.

- `EVG-OHLCV-001 old-queue-cleanup`
  - Parent: old standalone OHLCV queue. Status: closed under current contract.
    Thesis: old queued variants around gap failure, sector-conditioned blow-off,
    and long-horizon residual reversal might add new axes beyond C11/C13.
    Current evidence: H283 found gap-failure exhaustion predictive but
    redundant with C13; H284 found sector / ceiling conditioning did not improve
    H133; H346 found residual long-horizon reversal failed and residual
    continuation stayed below gate. Best artifact:
    `artifacts/run_summaries/latest_research_branch_residual_long_horizon_reversal.json`.
    Latest experiment: H346. Children: none active. Priority score: `0.10`.
    Money relevance: low unless a materially different target or portfolio
    contract is introduced. Next action: do not rerun H135/H136/H137 variants.
    Reopening condition: a new target, execution contract, or non-price state
    changes the meaning of C11/C13 residuals.

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
