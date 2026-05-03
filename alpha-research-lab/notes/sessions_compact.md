# Sessions Compact

What this file is for: compact per-session recovery notes. Keep one unnumbered
one-liner or short paragraph per material session, newest first. Do not use
manual list numbering; prepend new entries at the top. Every entry must link
to its source session or state an explicit source anchor.

## Recent Sessions

- [Session 242](session_242_log.md): January effect + volume regime confirmation.
  january_first_10 IC=0.0817 (+5% boost), vol_high IC=0.0941 (+21%).
  Reusable x240_wf_ic_test.py script updated.
- [Session 232](session_232_log.md): Triple Storm Extensions — 6 PASSED, 3 FAILED.
  Universal: works on order/volume/reversal/skewness, NOT on position (foreign/sector).
  x232_triple_test.py reusable script.
  All signals 9/9 years positive. Triple Storm +92% in WF.
- [Session 230](session_230_log.md): Triple Storm HOLDOUT — CONFIRMED.
- [Session 229](session_229_log.md): triple_storm — **DISCOVERED** (+104%).
  Liquid + DOWN + divergence = IC +0.158 vs baseline +0.078.
- [Session 228](session_228_log.md): c16_divergence — WEAK PASS (+39%).
  Price disagree with C16 = IC +0.108 vs baseline +0.078 (+39%). Divergence works.
- [Session 227](session_227_log.md): c16_acceleration — FAILED.
  C16 level IC +0.078 vs ROC IC +0.056 (-28%). Level wins.
- [Sessions 224-226](session_224_226_log.md): New C16 branches.
  X224 sector-relative: FAILED (-15%). X225 persistence: FAILED (-17%).
  X226 market-state: PASSED - C16 +26% stronger in DOWN markets (+0.098 vs +0.056).
- [Session 223](session_223_log.md): sector_convergence_contrarian — FAILED.
  Fragmented + high C16: IC +0.035 vs baseline +0.078 (-55%).
  Kill branch.
- [Session 222](session_222_log.md): dynamic_liquidity_regime — WEAK PASS.
  High market regime: +0.081 vs Low: +0.074 (diff +0.007, ~8%)
  Not enough for regime switching, could use for sizing only.
- [Session 221](session_221_log.md): liquid_braid_stack TEST — MIXED.
  X53 (liquid): +25% IC ✅. X54 (braid): +3%. Stack: -18% ❌.
  Stacking FILTERS HURTS. Use X53 alone, not both.
- [Session 220](session_220_log.md): X51-X55 stochastic resonance batch - SUPER PASS.
  X53 (Liquid C16): C16 + high move >80%ile = IC +0.137 (+52% vs baseline +0.090).
  X54 (Braid): Low sector kurtosis = unanimous pressure = IC +0.080 vs +0.031 (+160%).
  Scripts: x51, x52, x53v2, x54, x55.
- [Session 219](session_219_log.md): H365-H378 + X1-X5 batch — ALL FAILED except C16 baseline.
  Tested: H372 (vol→price), H373 (sector), H374 (early session), H375 (ROC), H377 (curvature), X1 (auction), X2 (exhaustion), X5 (lunar). C16 remains champion +0.077 to +0.084.
- [Session 218](session_218_log.md): X72 volume regime — FAILED (c8 combo hurts C16).
- [Session 217](session_217_log.md): X75 Benford Law — FAILED (IC +0.0023).
- [Session 216](session_216_log.md): H366 order+ceiling — FAILED.
- [Session 215](session_215_log.md): H367 order+gap — FAILED.
- [Session 214](session_214_log.md): H365 C16 standalone — PASSED.
  C16 standalone beats full_library baseline on val IR 1.98 (vs 0.85), val ret +1.47%
  (vs +0.45%), clean execution health. PASSED as offline evidence.

- [Session 212](./session_212_log.md): Recovered the evergreen loop while
  `ollama_guarded_backfill` was running, found the active run had reverted to
  an empty cutoff and the non-lockbox `146,872`-row input, stopped it before it
  reached the known post-2025 tail, verified the `120` newly appended score
  cache rows were all Dec 2023, and relaunched the checkpoint-safe
  `--max-published-at 2025-12-31T23:59:59+07:00` command. The corrected input
  manifest is back to `142,296` rows with `4,576` date-filtered articles, H364
  readiness now blocks until the final Ollama ticker-day dataset exists, and
  H364 was hardened to reject missing lockbox cutoffs.

- [Session 211](./session_211_log.md): Resumed the guarded Ollama residual
  backfill at the user's request, but first found that the existing input cache
  included a `2026` tail. Added a cutoff-aware `--max-published-at` path,
  rebuilt the input cache to `142,296` rows with max timestamp
  `2025-12-31T20:40:05+07:00`, launched `ollama_guarded_backfill` in tmux with
  `2026+` excluded, then stopped it for the day at `3,638 / 7,115` checkpoint
  batches and `72,760 / 142,296` processed input rows. H364 is prepared as the
  fixed combined local-news audit to run after completion.

- [Session 210](./session_210_log.md): Stopped the guarded Ollama residual
  backfill at the user's request. The tmux job session closed, no
  `build_ollama_guarded_features` process remained, `qwen2.5-coder:3b` was
  unloaded from Ollama, and the status file was marked `stopped_by_user` at
  `2281 / 7344` checkpoint batches with `45,620` processed input rows.

- [Session 209](./session_209_log.md): Implemented and ran H363 Vietnam legal
  holiday timing. The calendar builder generated `436` 2015-2025 sparse
  pre/post trading-day rows across `53` VNINDEX-inferred closure clusters with
  no `2026+` leakage. Matched payoff found one passing state,
  `all_holidays__post_5`, but the single fixed `+0.015` sparse portfolio bonus
  produced `0.00% / 0.00%` validation/confirmation relative deltas and failed
  the portfolio gate, so legal-holiday timing stays offline evidence only.

- [Session 208](./session_208_log.md): Resumed the guarded Ollama residual
  backfill in tmux from the Session 207 checkpoint, then completed two
  scheduled 5-minute watchdog checks. Latest status was healthy/running at
  `780 / 7344` checkpoint batches, `15,600` processed rows, with
  `qwen2.5-coder:3b` loaded at about `2.3GB` VRAM.

- [Session 207](./session_207_log.md): Stopped the guarded Ollama residual
  backfill at the user's request, verified the tmux session and Ollama model
  runner were gone, updated `live_state.md`, then prepared the repository for
  commit and push.

- [Session 206](./session_206_log.md): Added the session closeout checklist,
  `Last verified` marker, and strict compact source-anchor rule to the repo
  memory stack and `manh-memory-system`; also verified the guarded Ollama
  backfill is still running at `744 / 7344` checkpoint batches.

- [Session 205](./session_205_log.md): Made the `live_state.md` contract
  explicit: current state, active constraints, immediate next actions,
  do-not-reopen conditions, and pointers. Tightened this repo's live-state file
  from a branch ledger into a short operational brain, and updated
  `manh-memory-system` to require immediate next actions inside `live_state.md`.

- [Session 204](./session_204_log.md): Renamed the alpha-lab live-state note to
  `live_state.md`, updated repo pointers and historical note links, and
  upgraded `manh-memory-system` so fresh repos prefer `live_state.md` while
  grandfathering coherent legacy names.

- Memory note migration (2026-04-28): Added compact full-history findings and
  derived dead-end recovery views in
  [findings_compact.md](./findings_compact.md) and
  [deadends_compact.md](./deadends_compact.md), keeping chunked
  `findings-*.md` files as the append-only source of truth. Source anchor:
  [Session 206](./session_206_log.md) reconciliation of the prior unsourced
  compact entry.

- [Session 203](./session_203_log.md): Ran H362 as the dividend pre-ex sparse-clock portfolio reopening test. The fixed calendar bonus failed the portfolio gate, so dividend-clock timing remains offline evidence under the current selector contract.

- [Session 202](./session_202_log.md): Ran H361 as the strict event-v2 sparse-clock portfolio reopening test. The fixed event bonus failed the portfolio gate, so event-v2 remains parked under the current target and executable selector contract.

- [Session 201](./session_201_log.md): Ran H360 as a fixed published-contract parity audit. The published C16 artifact reproduced the H359 winner within floating-point noise and still passed portfolio plus execution-health gates.

- [Session 200](./session_200_log.md): Published the scoped C16 order-pressure artifact at `data/features/xs_order_pressure_daily.parquet`, registered it in `shared-recommendation`, and updated producer/consumer docs while keeping RL and recommendation defaults unchanged.

- [Session 199](./session_199_log.md): Ran H359 as the bounded C16 sizing / state-scope audit. The scoped 5% order-pressure blend on next-open-buyable rows passed both portfolio and execution-health gates, which led to the Session 200 publisher work.

- [Session 198](./session_198_log.md): Resumed the stalled guarded Ollama residual backfill from stale `505 / 7344` checkpoint state and ran H358. Order pressure had strong executable portfolio relevance, but the equal-weight full-library addition was `MIXED` because validation cash drag narrowly breached the health limit.

- [Session 197](./session_197_log.md): Ran H357 as the H356 integration audit. Order pressure survived full-library residualization and improved the frozen label-level selector; H358 completed the required portfolio/tradability review, and H359 / Session 200 later promoted the scoped contract.

- [Session 196](./session_196_log.md): Ran H356 as a CPU-only standalone order-pressure gate while the Ollama residual backfill continued. CafeF posted order-volume pressure passed strongly as a broad candidate signal; H357-H359 and Session 200 are the current follow-up evidence.

- [Session 195](./session_195_log.md): Resumed the guarded Ollama residual backfill in tmux after confirming the previous status heartbeat was stale. The job advanced from `12 / 7344` to `100 / 7344` batches on the later watchdog check and is now the single active heavy local-model job.

- [Session 194](./session_194_log.md): Ran H355 as the order-pressure step-hazard audit. CafeF order pressure helped some smart-exit metrics, but the improvement over H337 was too small to solve the H337/H339 blocker.

- [Session 193](./session_193_log.md): Ran H354 as the dividend-clock payoff audit. The 20-day pre-ex window has a small local payoff hint, but no dividend-clock state cleared the validation / confirmation payoff and risk gate.

- [Session 192](./session_192_log.md): Ran H353 as the H340 entry-label transfer audit. H340 remains the preferred daily-state C5 rewrite, but it is not a clean entry-alpha prior: the loose gate lost confirmation return lift and the strong support state did not beat raw C5 in validation.

- [Session 191](./session_191_log.md): Ran H352 as the event-v2 optionality payoff audit. Event states showed upside-tail hints, but the payoff distribution was not clean enough: downside tails worsened and confirmation mean lift was negative for the best state.

- [Session 190](./session_190_log.md): Ran H351 as the sector ownership-pressure audit. Sector-level foreign pressure and ownership states failed; the current-data H95 flow branch is now closed under this target.

- [Session 189](./session_189_log.md): Ran H350 as an official-disclosure source gate. The HNX universe is wired, but the current disclosure history is a two-ticker current sample with no pre-2026 rows, no transaction extracts, and no usable HOSE bridge.

- [Session 188](./session_188_log.md): Ran H349 as the first high-value queue experiment. The H321 cascade state failed to transfer to the entry-alpha label contract: validation and confirmation matched return lifts were both negative.

- [Session 187](./session_187_log.md): Ran H348 as a limited-source proprietary-flow conflict/agreement pilot. The best row cleared 2023 dev, then flipped negative in 2024 and 2025, so proprietary-flow rank variants should not continue on this target.

- [Session 186](./session_186_log.md): Ran H347 as a CPU-only foreign-flow interaction pass. Foreign agreement improved raw `C5`, but did not beat the stronger H340 order-pressure rewrite. Keep it as offline interaction evidence only.

- [Session 185](./session_185_log.md): Ran H346 to close the stale residual long-horizon reversal queue item. The sign-flipped residual after removing C11 failed; the continuation residual was directionally positive but below gate. Signal-library stale H135/H136/H137 rows were cleaned up.

- [Session 184](./session_184_log.md): Ran H345 as a CPU-only CafeF foreign-flow continuation. Accumulation / ownership-change change-points failed the unchanged foreign-flow gate, so standalone H95 tuning should stop unless a distinct interaction contract is introduced.

- [Session 183](./session_183_log.md): Ran H343/H344 as CPU-only existing-data audits. H343 showed official-conditioned PhoBERT sentiment clears the broad standalone gate, but H344 failed it as a standalone promoted signal under 2025 confirmation.

- [Session 182](./session_182_log.md): Ran an evergreen artifact-only queue pass while the Ollama residual backfill continued as the active heavy job. H340/H341/H342 were treated as solved existing hypotheses rather than reopened.

- [Session 181](./session_181_log.md): Added row-level Ollama score caching and checkpoint-cadence migration so `checkpoint_rows` changes no longer invalidate expensive scoring outputs.

- [Session 179](./session_179_log.md): Optimized the local Ollama residual prompt under the hardware cap. The safe default is bottom-schema event-family-only JSON with `num_ctx=512` and first-300-word article truncation. A BERT-gated checkpointed backfill is running in `tmux` as `ollama_guarded_backfill`.

- [Session 178](./session_178_log.md): Completed the repaired local PhoBERT `article_scope` and `source_type` train/publish sequence on CUDA with mid-epoch train checkpoints, resume-safe publish checkpoints, and artifact sanity checks confirming the published parquets use the new trained model ids.

- [Session 177](./session_177_log.md): Repaired the semantic binary-head contract so `article_scope` and `source_type` no longer inherit the forward-looking date split and hard `0.5` threshold blindly. Binary-head training now calibrates a per-head decision threshold on validation, publish uses that saved threshold, and `article_scope` defaults to a stratified article-level split with positive class weighting enabled.

- [Session 176](./session_176_log.md): Upgraded binary-head publish to the same shard-checkpoint/finalize contract already used by forward-looking publish, with a focused resume test covering the article-scope lane.

- [Session 175](./session_175_log.md): Confirmed the real WSL runtime sees the RTX 3050 GPU outside the restricted sandbox, then hardened heavy PhoBERT train/publish paths to fail fast when `/dev/dxg` is hidden instead of silently falling back to CPU.

- [Session 174](./session_174_log.md): Moved the offline PhoBERT runtime guard into repo code so the main local PhoBERT commands no longer rely on shell-level offline prefixes.

- [Session 173](./session_173_log.md): Tightened the binary-head trainer so it mirrors the forward-looking lane's local-first runtime posture and epoch-level observability.

- [Session 172](./session_172_log.md): Added repo-native PhoBERT `article_scope` and `source_type` head paths by reusing the forward-looking staged binary-head pattern.

- [Session 171](./session_171_log.md): The news pipeline now defaults to a local-first contract: PhoBERT for sentiment and forward-looking, minimal Ollama residual semantics, and no hosted API dependency in the default local-news path.

- [Session 168](./session_168_log.md): Targeted long-job scripts under `data_tools/` now expose canonical restart-safe job-status files and stricter durable resume boundaries.

- [Session 167](./session_167_log.md): Repo-local planning assumptions are now explicitly constrained to `3GB VRAM / 10GB RAM` for safe local-ML work.

- [Session 166](./session_166_log.md): The first real PhoBERT forward-looking canary forced two runtime repairs and established the current watchdog and stage-manifest flow.
