# Next Steps

This is the live small-brain file for current state, recent direction, and
next priorities.
Use [session_197_log.md](./session_197_log.md) for the latest full session
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
- There is one active heavy local-model job at the moment:
  `tmux` session `ollama_guarded_backfill`, running
  `python -m research_pipelines.news_features.core.build_ollama_guarded_features`.
  The BERT-gated Ollama residual backfill resumed from `12 / 7344` checkpoint
  batches and reached `100 / 7344` with `2,000` processed input rows on the
  later watchdog check. Do not start another heavy local-ML / GPU job while it
  runs.
- H356 found that CafeF posted order-volume pressure is a strong standalone
  candidate signal, and H357 showed it survives full-library residualization
  while improving a frozen label-level selector. Do not publish a consumer
  artifact yet; run one portfolio/tradability audit first.
- Local-ML planning budget is now hard-capped at `3GB VRAM / 10GB RAM`.
- Long news/data scripts now expose canonical machine-readable status files
  under `alpha-research-lab/artifacts/job_status/`.
- Heavy PhoBERT train/publish commands now fail fast on this WSL workstation
  when the session hides CUDA even though the real WSL GPU runtime exists.
  Use `NEWS_FEATURES_ALLOW_CPU=1` only for an explicit CPU fallback.

## Immediate Follow-Up

1. `ollama-residual-backfill-resume`
   - Current state: actively running in tmux session `ollama_guarded_backfill`.
   - Status file:
     `artifacts/job_status/ollama_guarded_publish.json`
   - The no-flag default remains the intended resume command:
     `python -m research_pipelines.news_features.core.build_ollama_guarded_features`
   - Expected scope: BERT-gated priority universe only,
     `phobert_article_scope_prob_positive >= 0.28`, about `146872` article
     rows, `20`-row checkpoint shards, and reusable row-level score cache under
     `data/features/news/datasets/ollama_guarded_score_cache/`.
   - The resumed state reached `100 / 7344` checkpoint batches and `2,000`
     processed input rows on the later watchdog check. Continue monitoring
     status/heartbeat before launching any other heavy work.

2. `local-news-branch-followthrough-after-ollama`
   - After the guarded Ollama residual surface finishes, aggregate the default
     local-first news features:
     `python -m research_pipelines.news_features.core.aggregate_daily_features --sources phobert phobert_forward_looking ollama_guarded`
   - Then run a bounded downstream audit of the combined local-news surface
     before promoting any news feature into the signal library.

3. `order-pressure-standalone-integration`
   - H356 result: `PASSED`.
   - Best feature: `order_volume_ratio_rank`.
   - 1d avg IC / positive years / S1 corr:
     `+0.0738 / 11 of 11 / +0.0342`.
   - Split IC: dev `+0.0799`, validation `+0.0593`, confirmation `+0.0713`.
   - H357 result: `PASSED`. Full-library residual IC `+0.0687`; max library
     corr `0.1877`; validation / confirmation top-5 edge delta
     `+0.0152 / +0.0554`.
   - Next action: run one CPU-only portfolio/tradability audit before
     publishing any new `data/features/...` order-pressure artifact.

4. `phobert-news-signal-audit`
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

5. `foreign-flow-standalone-state`
   - Historical CafeF foreign flow is source-usable, but the standalone alpha
     path is weak after four negative screens: H327 raw ranks, H328 simple
     conditioning, H333 room-residual discontinuities, and H345 accumulation /
     ownership-change change-points.
   - Do not continue standalone foreign-flow window or threshold tuning. If
     reopened, require a distinct interaction contract such as
     foreign-insider agreement, proprietary-flow conflict/agreement, or
     sector-specific ownership pressure.

6. `foreign-insider-interaction-state`
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

7. `proprietary-flow-pilot-state`
   - H348 tested proprietary-flow ranks plus foreign/proprietary
     agreement/conflict states under a limited-source `2023 / 2024 / 2025`
     pilot.
   - Result: `FAILED`. Best row `xs_prop_buy_share_5d_rank` cleared 2023 dev
     IC at `+0.0144`, then flipped to `-0.0216` in 2024 validation and
     `-0.0110` in 2025 confirmation.
   - Do not continue proprietary-flow rank, agreement, or conflict threshold
     variants on the same S1 target.

8. `daily-side-channel-queue-state`
   - H340 passed: same-day posted buy-volume pressure is the preferred
     positive-side robustness rewrite of bullish C5.
   - H341 failed: stacking exec-rate on top of H340 did not improve the
     current daily contract.
   - H353 was `MIXED`: H340 partially transferred to the entry-alpha candidate
     book, but did not cleanly beat raw positive C5 across validation and
     confirmation.
   - H356 was `PASSED`: broad standalone order-volume pressure passed the
     strict 1d gate with avg IC `+0.0738`, `11 / 11` positive years, and S1
     corr `+0.0342`.
   - H357 was `PASSED`: order pressure survived full-library residualization
     and improved validation / confirmation label-level selector top-5 edge.
   - Do not spend more cycles stacking the same C5 filters or promoting H340 as
     an entry prior. The active daily side-channel follow-up is now an
     order-pressure portfolio/tradability audit.

9. `old-ohlcv-queue-state`
   - The stale H135/H136/H137 queue entries are now closed:
     H135 was solved by H283, H136 was solved by H284, and H137 was solved by
     H346. Do not rerun those old gap/compression/long-horizon residual
     variants under the current contract.

10. `smart-exit-post-entry-state`
   - H355 tested the H339 reopening condition by adding CafeF order-pressure
     state to the saved H337 legal-step rows.
   - Result: `MIXED`. Order pressure improved some validation / confirmation
     metrics, and the minimal order-delta set improved both held-out utility
     means versus H337, but the deltas were only about `+0.00065 / +0.00053`.
   - Do not integrate order-pressure exit features or continue linear
     H337/H339 feature-set tweaks. Reopen smart-exit ML only with genuinely
     richer post-entry state/data or a materially different model contract.

11. `calendar-side-channel-state`
   - H354 tested the direct dividend-clock payoff contract after H31 and H298.
   - Result: `MIXED`. The 20-day pre-ex window had small positive validation /
     confirmation matched return lifts and favorable hit-rate / bad-tail-rate
     lifts, but confirmation q10 lift missed the predeclared risk floor and
     the mean lift was too small for promotion.
   - Do not reopen H31-style dividend-calendar model features or tune more
     pre/post dividend windows under the current target. Keep the pre-ex clock
     as offline calendar evidence only.

12. `timing-vendor-source-decision`
   - Only reopen this if the branch still needs more than daily side channels
     and reduced-shape intraday before the LLM cache is ready.
   - The honest next action is still one exact vendor question about
     historical order-book depth, auction-state coverage, granularity, date
     range, and price.

## High-Value Research Queue

1. `event-cascade-entry-label`
   - Claim: H321/H322 may have failed additive promotion because event-cascade
     rows are sparse entry-opportunity states, not full-universe rank boosts.
   - H349 result: `FAILED`. `today_self_accel_high` had enough entry-candidate
     coverage but did not improve validation / confirmation entry labels or
     returns after matching against the existing entry prior.
   - Next action: do not continue event-cascade entry-label variants under the
     current entry target.

2. `official-disclosure-bridge`
   - Claim: H315 was data-blocked, but the HNX official-disclosure surface now
     exists and should first be audited as a timing/source bridge, not promoted
     as an alpha feature.
   - H350 result: `SKIPPED`. The HNX universe is wired, but the current local
     disclosure parquets have only `10` monitor-only news rows for `2` tickers,
     zero pre-2026 rows, zero transaction extracts, and only `1` ticker of
     overlap with the 2015-2025 HOSE matrix.
   - Next action: do not run alpha IC. Reopen only through data acquisition:
     broader HNX / UPCoM history if that market becomes a target, or a resolved
     HOSE / HSX official-disclosure source for the current matrix.

3. `sector-ownership-pressure`
   - Claim: raw foreign/proprietary flow failed at ticker level, but sector
     crowding plus foreign-room scarcity may still identify constrained
     beneficiaries or crowded exits.
   - H351 result: `FAILED`. Seven predeclared sector-level foreign pressure,
     participation, ownership, and sector-heat interaction features failed the
     H95 gate. Best dev IC was only `-0.0007`; the failure was not sector-anchor
     redundancy.
   - Next action: close the current-data flow branch. Reopen H95 only with a
     materially different data source, target, or market contract.

4. `event-v2-optionality-payoff`
   - Claim: first-public and cascade event states may matter as tail-payoff /
     risk-filter features rather than mean IC overlays.
   - H352 result: `MIXED`. Event states showed positive validation /
     confirmation upside-tail lifts, but the best state also had materially
     worse downside tail and a negative confirmation mean lift.
   - Next action: do not integrate event-v2 payoff-shape states under the
     current contract. Reopen only with a stricter portfolio-level convexity
     test, new event data, or a different target.

5. `dividend-clock-payoff`
   - Claim: the old dividend-calendar branch may have failed as broad model
     input while retaining a sparse pre/post ex-dividend payoff clock.
   - H354 result: `MIXED`. `pre_ex_20d` had small positive validation /
     confirmation matched return lifts and favorable hit-rate / bad-tail-rate
     lifts, but confirmation q10 lift missed the risk floor and no state was
     clean enough for promotion.
   - Next action: do not tune more dividend windows under the current target.
     Reopen only through a stricter portfolio-level sparse-clock or risk-filter
     contract.

6. `order-pressure-step-hazard`
   - Claim: H339 parked smart-exit ML until richer post-entry state/data
     existed, and H340 later validated CafeF order pressure as a useful daily
     state.
   - H355 result: `MIXED`. Order-pressure feature sets improved some held-out
     metrics but did not materially beat the H337 refit in both validation and
     confirmation.
   - Next action: do not continue linear smart-exit feature-set tweaks. Reopen
     only with genuinely richer post-entry data or a different model contract.

7. `order-pressure-standalone-gate`
   - Claim: CafeF order-statistics buy-vs-sell pressure may be a broad
     standalone demand signal, not only a conditioner on bullish insider rows.
   - H356 result: `PASSED`. `order_volume_ratio_rank` had 1d avg IC `+0.0738`,
     `11 / 11` positive years, S1 corr `+0.0342`, and dev / validation /
     confirmation IC `+0.0799 / +0.0593 / +0.0713`.
   - H357 result: `PASSED`. The full-library residual kept avg IC `+0.0687`,
     max library corr was only `0.1877`, and full-library-plus-order improved
     validation / confirmation top-5 edge by `+0.0152 / +0.0554`.
   - Next action: run a portfolio/tradability audit before any formal feature
     publication.

8. `local-news-combined-audit`
   - Claim: BERT-only sentiment failed standalone confirmation, but sentiment
     plus source/scope/forward-looking plus Ollama event-family residual may
     still work as sparse routed context.
   - First test: after the guarded Ollama residual surface completes, aggregate
     PhoBERT plus Ollama and run one bounded combined-news audit.

## Recent State Digest

1. `Session 197`
   - Ran H357 as the H356 integration audit. Order pressure survived
     full-library residualization and improved the frozen label-level selector;
     it now needs portfolio/tradability review before publication.
   - Full detail: [session_197_log.md](./session_197_log.md)

2. `Session 196`
   - Ran H356 as a CPU-only standalone order-pressure gate while the Ollama
     residual backfill continued. CafeF posted order-volume pressure passed
     strongly as a broad candidate signal and now needs one integration audit.
   - Full detail: [session_196_log.md](./session_196_log.md)

3. `Session 195`
   - Resumed the guarded Ollama residual backfill in tmux after confirming the
     previous status heartbeat was stale. The job advanced from `12 / 7344` to
     `100 / 7344` batches on the later watchdog check and is now the single
     active heavy local-model job.
   - Full detail: [session_195_log.md](./session_195_log.md)

4. `Session 194`
   - Ran H355 as the order-pressure step-hazard audit. CafeF order pressure
     helped some smart-exit metrics, but the improvement over H337 was too
     small to solve the H337/H339 blocker.
   - Full detail: [session_194_log.md](./session_194_log.md)

5. `Session 193`
   - Ran H354 as the dividend-clock payoff audit. The 20-day pre-ex window has
     a small local payoff hint, but no dividend-clock state cleared the
     validation / confirmation payoff and risk gate.
   - Full detail: [session_193_log.md](./session_193_log.md)

6. `Session 192`
   - Ran H353 as the H340 entry-label transfer audit. H340 remains the
     preferred daily-state C5 rewrite, but it is not a clean entry-alpha prior:
     the loose gate lost confirmation return lift and the strong support state
     did not beat raw C5 in validation.
   - Full detail: [session_192_log.md](./session_192_log.md)

7. `Session 191`
   - Ran H352 as the event-v2 optionality payoff audit. Event states showed
     upside-tail hints, but the payoff distribution was not clean enough:
     downside tails worsened and confirmation mean lift was negative for the
     best state.
   - Full detail: [session_191_log.md](./session_191_log.md)

8. `Session 190`
   - Ran H351 as the sector ownership-pressure audit. Sector-level foreign
     pressure and ownership states failed; the current-data H95 flow branch is
     now closed under this target.
   - Full detail: [session_190_log.md](./session_190_log.md)

9. `Session 189`
   - Ran H350 as an official-disclosure source gate. The HNX universe is wired,
     but the current disclosure history is a two-ticker current sample with no
     pre-2026 rows, no transaction extracts, and no usable HOSE bridge.
   - Full detail: [session_189_log.md](./session_189_log.md)

10. `Session 188`
   - Ran H349 as the first high-value queue experiment. The H321 cascade state
     failed to transfer to the entry-alpha label contract: validation and
     confirmation matched return lifts were both negative.
   - Full detail: [session_188_log.md](./session_188_log.md)

11. `Session 187`
   - Ran H348 as a limited-source proprietary-flow conflict/agreement pilot.
     The best row cleared 2023 dev, then flipped negative in 2024 and 2025, so
     proprietary-flow rank variants should not continue on this target.
   - Full detail: [session_187_log.md](./session_187_log.md)

12. `Session 186`
   - Ran H347 as a CPU-only foreign-flow interaction pass. Foreign agreement
     improved raw `C5`, but did not beat the stronger H340 order-pressure
     rewrite. Keep it as offline interaction evidence only.
   - Full detail: [session_186_log.md](./session_186_log.md)

13. `Session 185`
   - Ran H346 to close the stale residual long-horizon reversal queue item.
     The sign-flipped residual after removing C11 failed; the continuation
     residual was directionally positive but below gate. Signal-library stale
     H135/H136/H137 rows were cleaned up.
   - Full detail: [session_185_log.md](./session_185_log.md)

14. `Session 184`
   - Ran H345 as a CPU-only CafeF foreign-flow continuation. Accumulation /
     ownership-change change-points failed the unchanged foreign-flow gate, so
     standalone H95 tuning should stop unless a distinct interaction contract
     is introduced.
   - Full detail: [session_184_log.md](./session_184_log.md)

15. `Session 183`
   - Ran H343/H344 as CPU-only existing-data audits. H343 showed
     official-conditioned PhoBERT sentiment clears the broad standalone gate,
     but H344 failed it as a standalone promoted signal under 2025
     confirmation.
   - Full detail: [session_183_log.md](./session_183_log.md)

16. `Session 182`
   - Ran an evergreen artifact-only queue pass while the Ollama residual
     backfill continued as the active heavy job. H340/H341/H342 were treated as
     solved existing hypotheses rather than reopened.
   - Full detail: [session_182_log.md](./session_182_log.md)

17. `Session 181`
   - Added row-level Ollama score caching and checkpoint-cadence migration so
     `checkpoint_rows` changes no longer invalidate expensive scoring outputs.
   - Full detail: [session_181_log.md](./session_181_log.md)

18. `Session 171`
   - The news pipeline now defaults to a local-first contract: PhoBERT for
     sentiment and forward-looking, minimal Ollama residual semantics, and no
     hosted API dependency in the default local-news path.
   - Full detail: [session_171_log.md](./session_171_log.md)

19. `Session 172`
   - Added repo-native PhoBERT `article_scope` and `source_type` head paths by
     reusing the forward-looking staged binary-head pattern.
   - Full detail: [session_172_log.md](./session_172_log.md)

20. `Session 173`
   - Tightened the binary-head trainer so it mirrors the forward-looking lane's
     local-first runtime posture and epoch-level observability.
   - Full detail: [session_173_log.md](./session_173_log.md)

21. `Session 174`
   - Moved the offline PhoBERT runtime guard into repo code so the main local
     PhoBERT commands no longer rely on shell-level offline prefixes.
   - Full detail: [session_174_log.md](./session_174_log.md)

22. `Session 168`
   - The targeted long-job scripts under `data_tools/` now expose canonical
     restart-safe job-status files and stricter durable resume boundaries.
   - Full detail: [session_168_log.md](./session_168_log.md)

23. `Session 175`
   - Confirmed the real WSL runtime sees the RTX 3050 GPU outside the
     restricted sandbox, then hardened heavy PhoBERT train/publish paths to
     fail fast when `/dev/dxg` is hidden instead of silently falling back to
     CPU.
   - Full detail: [session_175_log.md](./session_175_log.md)

24. `Session 176`
   - Upgraded binary-head publish to the same shard-checkpoint/finalize
     contract already used by forward-looking publish, with a focused resume
     test covering the article-scope lane.
   - Full detail: [session_176_log.md](./session_176_log.md)

25. `Session 178`
   - Completed the repaired local PhoBERT `article_scope` and `source_type`
     train/publish sequence on CUDA with mid-epoch train checkpoints,
     resume-safe publish checkpoints, and artifact sanity checks confirming the
     published parquets use the new trained model ids.
   - Full detail: [session_178_log.md](./session_178_log.md)

26. `Session 179`
   - Optimized the local Ollama residual prompt under the hardware cap. The
     safe default is now bottom-schema event-family-only JSON with `num_ctx=512`
     and first-300-word article truncation. A BERT-gated checkpointed backfill
     is running in `tmux` as `ollama_guarded_backfill`.
   - Full detail: [session_179_log.md](./session_179_log.md)

27. `Session 177`
   - Repaired the semantic binary-head contract so `article_scope` and
     `source_type` no longer inherit the forward-looking date split and hard
     `0.5` threshold blindly. Binary-head training now calibrates a per-head
     decision threshold on validation, publish uses that saved threshold, and
     `article_scope` defaults to a stratified article-level split with positive
     class weighting enabled.
   - Full detail: [session_177_log.md](./session_177_log.md)

28. `Session 167`
   - Repo-local planning assumptions are now explicitly constrained to
      `3GB VRAM / 10GB RAM` for safe local-ML work.
   - Full detail: [session_167_log.md](./session_167_log.md)

29. `Session 166`
   - The first real PhoBERT forward-looking canary forced two runtime repairs
     and established the current watchdog and stage-manifest flow.
   - Full detail: [session_166_log.md](./session_166_log.md)

30. `Local encoder branch`
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
    raw surfaces. H348 failed the first proprietary-flow rank/agreement pilot,
    but H356 passed a broad standalone CafeF order-pressure gate. The next
    daily-side-channel work is a frozen-matrix / selector integration audit for
    `order_volume_ratio_rank`; official disclosures remain bridge-first until
    source coverage exists.

- `event-v2-timing`
  - H321 remains real sparse timing evidence, but H322 additive integration,
    H349 entry-label transfer, and H352 payoff-shape integration are not clean
    enough to promote. Reopen only with new event data, a stricter
    portfolio-level convexity test, or a materially different target.

- `foreign-flow`
  - Historical raw source exists, but raw-rank, simple conditioning,
    room-residual, and accumulation / ownership-change paths failed. H347 then
    showed foreign-insider agreement improves raw `C5` but does not beat H340.
    H348 then failed the proprietary-flow conflict/agreement pilot, and H351
    failed sector-level ownership pressure. Do not
    spend more cycles on standalone foreign-flow windows, foreign support
    around `C5`, proprietary-flow rank/conflict variants, or sector-pressure
    variants. Reopen only with a materially different data source, target, or
    market contract.

- `old-ohlcv-queue`
  - The stale signal-library queue items H135/H136/H137 are closed by
    H283/H284/H346. Continue only with genuinely new OHLCV contracts, not more
    small variants around C11 or C13.

- `calendar-side-channels`
  - H31-style dividend-calendar model features remain closed. H354 found a
    small 20-day pre-ex payoff hint, but no dividend-clock state passed the
    matched payoff / risk gate. Keep dividend timing as offline calendar
    evidence only unless a stricter sparse-clock portfolio contract explicitly
    needs it.

- `smart-exit-hazard`
  - H337 remains mixed and H339 showed the current daily state cannot learn
    the rare profitable continuation pockets. H355 added CafeF order-pressure
    post-entry state and improved some held-out metrics, but not enough to
    solve the blocker. Keep smart-exit ML parked until genuinely richer
    post-entry state/data or a different model contract exists.

## Evergreen Research Tree

- `EVG-NEWS-001 local-news-followthrough`
  - Parent: local-news branch. Status: active; the guarded Ollama residual
    backfill is running in tmux session `ollama_guarded_backfill`. Thesis: a fully local Vietnamese news
    surface may add sparse orthogonal context without reopening hosted LLM cost.
    Mechanism: combine local sentiment, source/scope/forward-looking routing,
    and residual event-family labels. Current evidence: PhoBERT sentiment /
    forward-looking / article-scope / source-type surfaces exist; H343/H344 say
    official-conditioned sentiment is offline evidence but not standalone
    confirmed; Ollama residual resumed from partial checkpoint state and had
    reached `100 / 7344` batches on the later watchdog check. Best
    artifacts: `notes/session_178_log.md`, `notes/session_183_log.md`,
    `artifacts/run_summaries/latest_research_branch_phobert_official_sentiment_confirmation.json`,
    `artifacts/job_status/ollama_guarded_publish.json`. Latest experiment:
    H344; latest operational action Session 195. Children: EVG-TEXT-001. Priority score: `0.78`. Money relevance:
    high if the combined local-news surface survives sparse-news gates. Next
    action: continue watchdog monitoring until the guarded residual surface is
    complete, then aggregate and run the combined-news audit. Reopening condition:
    combined surface fails all standalone/conditioning gates or residual
    backfill parse quality is unusable.

- `EVG-SIDE-001 c5-daily-state`
  - Parent: C5 insider branch. Status: solved on current daily contract.
    Thesis: daily buy-volume pressure cleans bullish insider conviction.
    Evidence: H340 passed with avg IC `+0.0693`; H341 showed exec-rate stacking
    does not improve it; H353 showed only mixed transfer to the entry-alpha
    candidate-book contract. H356 then showed the same CafeF order-statistics
    source has a separate broad standalone branch; that is tracked as
    `EVG-SIDE-002`. Best artifacts:
    `artifacts/run_summaries/latest_research_branch_c5_order_pressure_split.json`,
    `artifacts/run_summaries/latest_research_branch_c5_pressure_exec_stack.json`,
    `artifacts/run_summaries/latest_research_branch_h340_entry_label_transfer.json`.
    Latest experiment: H353. Children: EVG-SIDE-002. Priority score: `0.48`.
    Money relevance: medium-high as a sparse robustness
    rewrite. Next action: use H340 as preferred C5 form; do not retest same
    stack and do not promote it as an entry prior. Reopen condition: new
    official-source bridge or an explicitly small-book integration contract
    provides a genuinely distinct daily-state dimension.

- `EVG-SIDE-002 order-pressure-standalone`
  - Parent: EVG-SIDE-001 / CafeF order-statistics side-channel. Status:
    active after H356 `PASSED`. Thesis: same-day posted buy-volume pressure is
    a broad demand signal that may deserve its own feature artifact, not just
    a `C5` support variable. Mechanism: cross-sectional posted buy-vs-sell
    volume imbalance captures visible demand pressure after the close and
    before the next open. Current evidence: H356 best feature
    `order_volume_ratio_rank` passed the strict 1d gate with avg IC `+0.0738`,
    `11 / 11` positive years, S1 corr `+0.0342`, and dev / validation /
    confirmation IC `+0.0799 / +0.0593 / +0.0713`; the 5d diagnostic also
    passed with avg IC `+0.0797`. Best artifact:
    `artifacts/run_summaries/latest_research_branch_order_pressure_standalone_gate.json`.
    Latest experiment: H356. Children: none yet. Priority score: `0.72`.
    Money relevance: high because the surface is dense, current-data, and low
    correlation with S1. Next action: run one frozen-matrix / selector
    integration audit before publishing a new feature contract. Reopening
    condition: if integration fails, keep H356 as standalone offline evidence
    and do not tune more order-statistics ranks without a different target.

- `EVG-EVENT-001 event-v2-timing`
  - Parent: H301/H310 event-v2 timing branch. Status: parked as offline timing
    evidence. Thesis: first-public and self-exciting issuer events can identify
    sparse windows where price response is unusually asymmetric. Mechanism:
    event novelty and disclosure cascades can shift attention and payoff
    shape, but may be too sparse for broad daily rank overlays. Current
    evidence: H321 passed as a sparse cascade cohort; H322 failed additive
    integration; H349 failed entry-label transfer; H352 found upside-tail hints
    but worse downside tails and weak confirmation mean. Best artifacts:
    `artifacts/run_summaries/latest_research_branch_hawkes_disclosure_cascade.json`,
    `artifacts/run_summaries/latest_research_branch_cascade_additive_screen.json`,
    `artifacts/run_summaries/latest_research_branch_event_cascade_entry_label.json`,
    `artifacts/run_summaries/latest_research_branch_event_v2_optionality_payoff.json`.
    Latest experiment: H352. Children: none active. Priority score: `0.16`.
    Money relevance: low under the current target; medium only if a stricter
    portfolio-level convexity test can harvest upside without worsening
    downside. Next action: do not tune more event-v2 overlays, entry-label
    variants, or payoff-shape filters. Reopening condition: new event data,
    different target, or an explicitly portfolio-level convexity contract.

- `EVG-CALENDAR-001 dividend-clock-payoff`
  - Parent: old H31 dividend-calendar branch. Status: parked as offline
    calendar evidence only. Thesis: ex-dividend timing may create a sparse
    pre/post payoff or risk-filter clock even though broad calendar model
    inputs add noise. Mechanism: known dividend dates can shift positioning
    before the ex date and mechanical unwinds after it. Current evidence: H31
    failed as broad model features; H298 only found unstable corporate-action
    conditioned slow-data pockets; H354 found a small `pre_ex_20d` payoff hint
    with validation / confirmation mean lifts `+0.0007 / +0.0002`, but no
    state passed the matched payoff / risk gate. Best artifact:
    `artifacts/run_summaries/latest_research_branch_dividend_clock_payoff.json`.
    Latest experiment: H354. Children: none active. Priority score: `0.18`.
    Money relevance: low under the current target; medium only if a portfolio
    contract explicitly needs sparse calendar risk filters. Next action: do not
    tune more dividend windows or reopen H31-style model inputs. Reopening
    condition: a stricter portfolio-level sparse-clock contract or a different
    target makes calendar timing decision-relevant.

- `EVG-EXIT-001 smart-exit-hazard`
  - Parent: H334 legal-exit oracle / H337 replacement-aware step hazard.
    Status: parked as mixed offline evidence. Thesis: legal exit timing may be
    improved if post-entry state can identify the sparse cases where waiting is
    better than exiting at the current legal step. Mechanism: current path
    state, replacement pressure, tradability, event state, and order pressure
    may reveal continuation or exhaustion. Current evidence: H337 improved
    fixed `3d` and local H211 but recovered only about `6%` of oracle uplift in
    validation / confirmation; H339 solved the label ceiling but failed to
    learn the right pockets; H355 added CafeF order pressure and improved some
    held-out metrics, but best two-phase utility deltas vs H337 were only about
    `+0.00065 / +0.00053`. Best artifacts:
    `artifacts/run_summaries/latest_research_branch_replacement_aware_step_hazard.json`,
    `artifacts/run_summaries/latest_research_branch_skip_aware_step_value_hazard.json`,
    `artifacts/run_summaries/latest_research_branch_order_pressure_step_hazard.json`.
    Latest experiment: H355. Children: none active. Priority score: `0.12`.
    Money relevance: low under the current daily state; medium if richer
    post-entry data becomes available. Next action: do not continue linear
    feature-set tweaks. Reopening condition: new post-entry state/data or a
    materially different model contract.

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
    offline evidence only, proprietary-flow agreement/conflict failed its
    source-limited pilot, and sector ownership-pressure failed as the last
    current-data reopening path. Thesis: foreign accumulation, ownership
    pressure, or room scarcity might reveal institutional demand not captured by
    OHLCV.
    Mechanism: foreign investor persistence or room pressure should create
    later follow-through in constrained names. Current evidence: source is
    usable, but H327 raw ranks failed, H328 simple conditioning failed, H333
    room-residual discontinuities failed, and H345 accumulation /
    ownership-change change-points failed with best dev IC only `+0.0020`.
    H347 improved raw `C5` through foreign agreement but still failed to beat
    the stronger H340 order-pressure rewrite. H348 then tested proprietary-flow
    ranks and foreign/proprietary agreement-conflict states; the best row
    cleared 2023 dev but flipped negative in both 2024 validation and 2025
    confirmation. H351 then tested seven sector-level foreign pressure,
    participation, ownership, room-scarcity, and sector-heat interaction
    features; none passed, and the best dev IC was only `-0.0007`.
    Best artifacts:
    `artifacts/run_summaries/latest_research_branch_cafef_foreign_flow_source_audit.json`,
    `artifacts/run_summaries/latest_research_branch_foreign_room_residual_discontinuity.json`,
    `artifacts/run_summaries/latest_research_branch_foreign_accumulation_change_point.json`,
    `artifacts/run_summaries/latest_research_branch_foreign_insider_agreement_split.json`,
    `artifacts/run_summaries/latest_research_branch_proprietary_flow_conflict_agreement.json`,
    `artifacts/run_summaries/latest_research_branch_sector_ownership_pressure.json`.
    Latest experiment: H351. Children: none active. Priority score: `0.05`.
    Money relevance: low under the current data and target contract. Next action: do not tune
    standalone windows, foreign-support-on-C5 variants, or proprietary-flow
    agreement/conflict ranks; do not tune more sector-pressure variants under
    the current S1 target. Reopening condition: a materially different data
    source, target, or market contract changes the mechanism.

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
