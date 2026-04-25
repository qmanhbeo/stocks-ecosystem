# Agent Workflow

This repo is designed to support one repeatable loop:

1. Form a hypothesis.
2. Pick the smallest valid experiment mode.
3. Run it.
4. Read the saved summary artifact instead of re-parsing terminal output.
5. Write session-level conclusions.
6. Promote durable conclusions into the chunked permanent findings files.
7. Update `notes/signal_library.md` if the signal is confirmed or promoted.

## Standard Experiment Design

Sequential hypothesis ladders are the default lab method.

- Do not treat a branch as a flat bag of experiments.
- Design experiment families so each result either:
  - unlocks the next experiment,
  - narrows the next experiment,
  - or kills the branch cleanly.
- Prefer explicit decision trees over broad unordered sweeps.
- If a simpler candidate fails a stronger validation gate, do not keep locally tuning that same family unless the branch is intentionally reopened.
- When a branch has a live component, freeze the live rule and run new hypotheses in a separate offline track.

The point is to keep the lab falsifiable and to reduce quiet test-set tuning.

Execution reality is shared at the workspace level:

- canonical spec: `../docs/execution_reality.md`
- shared rule code: `../shared-market-rules/shared_market_rules/`
- produced tradability artifact: `data/features/execution/tradability_daily.parquet`

`notes/next_steps.md` is the live small-brain state source. Keep it short and
link out. Use `notes/session_NN_log.md` for full per-session detail. This file
is the working manual.

Artifact writes are anchored to `alpha-research-lab/artifacts/` regardless of launch directory. Do not treat workspace-root `artifacts/` as the canonical lab output location.

## Result Classification

Do not treat every branch as a binary `live winner` vs `failed branch`.

Every finished branch should be classified into exactly one bucket:

### 1. Live promotion

Use this only when the result is strong enough to change an active live or pseudo-live workflow.

Required standard:
- honest locked protocol
- strong enough validation and confirmation
- pseudo-live / forward compatibility is still acceptable
- operationally implementable with current artifacts and execution assumptions

### 2. Offline evidence promotion

Use this when the branch is not live-ready but still found something durable enough to shape the next honest hypothesis.

Use this when:
- a simpler baseline improved before later steps failed
- the branch narrowed the right portfolio contract
- the branch produced a durable negative result that should constrain future work

This bucket matters. It is the guardrail against being too binary.

### 3. Branch kill / park

Use this when the current local path should not continue under the present data or contract.

Use this when:
- repeated honest failures leave no narrowed next step
- the branch only survives by local retuning after failing the stronger gate
- the branch needs data the workspace does not currently have

## Hard Rule

This lab is permanently long-only.

- no synthetic hedges
- no stock shorting assumptions
- no benchmark-hedged or long-short research branches
- if a strategy cannot plausibly make money as a real long-only Vietnam strategy, it is not a valid direction here

Do not suggest synthetic hedge diagnostics as a fallback. If long-only fails, document that plainly and search for a better long-only construction instead.

## Hard Resource Rule

Treat constrained local execution as a real lab constraint.

- prefer modular, incremental, checkpointed, or publish-only commands over full rebuilds
- do not route a narrow refresh through a heavyweight aggregate pipeline when a direct producer/export step is enough
- if a command is a true full rebuild, make that explicit in the name, docs, or required flags
- if a lighter path exists, use it by default
- when adding or refactoring pipelines, split heavyweight rebuild stages from lightweight publish stages instead of letting one entrypoint do everything

Assume local WSL RAM is limited unless the user says otherwise. Avoid large all-at-once joins and rebuilds when a narrower contract-preserving path exists.

## Hard Structure Rule

Treat separation of concerns as a hard lab rule when building or refactoring
non-trivial pipelines.

- keep one canonical operator entrypoint, but move real stage logic into focused
  modules
- prefer a thin orchestrator plus stage files over a single large pipeline
  script
- if the work naturally separates into teacher/stage/train/publish concerns,
  the code should reflect that separation
- do not create new large mixed-responsibility files when a stage split would
  make recovery and review easier
- do not over-split into tiny abstractions either; aim for a small number of
  modules that map to real operational stages

This is explicitly a maintenance and token-discipline rule. Future sessions
should be able to inspect one stage without loading an entire monolith back
into context.

---

## Primary Goal

**Build a library of learnable, orthogonal alpha signals for RL trading agents.**

Each signal is a potential state dimension for an RL agent. Signals do not need to be complete
trading strategies — they need to be independently predictive and diverse.

**Do not evaluate new signals by whether they beat H54 or improve H93.** The comparison bar
for a new signal is whether it has any independent predictive content, not whether it helps
a combined XGBoost model. XGBoost can't use sparse signals effectively; an RL agent can.

### Signal Evaluation Criteria

| Criterion | Threshold | Notes |
|-----------|-----------|-------|
| Standalone IC | > 0.01 | Test alone, not combined with S1 |
| Correlation with primary signal | < 0.30 | Spearman rank corr on matching (day, ticker) pairs |
| IC positive in ≥ years | 60% of years | Consistency gate |
| p-value | < 0.10 | Weak bar — searching, not deploying |

### Current Signal Library

See `notes/signal_library.md` for the full registry. Current promoted RL surface is:

- `S1`
- `C4-C14`

Operationally important summary:
- `S1` remains the strongest standalone signal
- `C7`, `C12`, `C13`, `C10`, and `C8` show the strongest conditional uplift inside liquidity-opening states
- `C1` remains sparse and is not part of the promoted dense RL matrix
- ADV / capacity is parked for the current-account branch, not solved for scale
- the repo is now explicitly split into:
  - selection alpha = choose the right names
  - activation alpha = decide when the selector should be on
  - exit alpha = decide when to stop holding a bought name after entry
- current live implementation uses activation mostly as a **date-level global gate**
- if architecture work is intentionally reopened around ticker-specific buy timing, start from:
  - this file
  - `README.md`
  - `notes/next_steps.md`
  - `notes/session_75_log.md`
  - branch thesis:
    - keep selection alpha as the cross-sectional prior
    - reinterpret activation alpha as a soft exposure prior
    - add stock-specific entry alpha so breadth can vary from `0..K`
  - canonical offline artifacts:
    - `data/features/entry_alpha/candidate_panel_daily.parquet`
    - `data/features/entry_alpha/entry_labels_cycle5.parquet`
    - `data/features/entry_alpha/entry_scores_daily.parquet`
- `H157-H162` tested deterministic binary activation and did not beat the always-on `full_library + k5_r5_eq` selector
- Session 75 executed the first offline stock-specific entry-alpha ladder:
  - `H238-H244`
  - outcome:
    - sparse breadth is real enough to keep as offline evidence
    - no single-family rule, compact model, soft-prior overlay, or live-compatibility variant is promotable
    - do not treat the entry-alpha branch as a live replacement candidate yet
- Session 76 then ran the first explicit contract audit:
  - `H245`
  - outcome:
    - the branch looks historically more like a `top1` contract than a `top5` timing overlay
    - but no audited `top_k` contract survives the honest forward gate
- Session 77 then ran the first small-book overlay follow-through:
  - `H246`
  - outcome:
    - top1 confirmation overlays are effectively a no-op
    - top2 soft-consensus overlays overfit validation and fail later
    - if the branch is intentionally reopened, start from `H247`, not more local confirmation overlays
- `H163-H174` then revisited activation with materially different designs and found the first real winner:
  - `H170` `recentsm__rel3_gt0` on `full_library + k5_r5_eq`
  - `+841.14%` total
  - `+383.07%` relative vs VNINDEX
  - information ratio `0.84`
- `H175-H177` then extended that branch and found a stronger fixed rule:
  - `H175` `h175__rel2_gt0`
  - `+1052.77%` total
  - `+491.69%` relative vs VNINDEX
  - information ratio `0.93`
  - max DD `-20.57%`
- Session 60 completed that direct branch:
  - `H178`: `h175__rel2_gt0` beat always-on in `15 / 16` fee / start-year stress scenarios
  - `H179`: the live-paper activation overlay runner exists
  - `H180`: no small local guard beat the plain champion
- Session 62 completed that operational-and-local branch:
  - `H181`: rebuilt the live `S1` extension plus the shared `full_library` matrix and activation surfaces through `2026-03-27`
  - `H182`: reran the live activation overlay on current data; latest sticky live book is `ANV`, `PGV`, `PTB`, `PTL`, `VSI`
  - `H183`: current-year scoreboard now compares sticky activated vs sticky always-on on current data
  - `H184`: sticky holdings / displacement margin improved the champion
  - `H185`: sector cap `3` helped slightly but did not beat the sticky champion
  - `H186`: local exposure sizing around `rel2_gt0` failed
- Session 63 completed the next local refinement wave:
  - `H187`: sticky + sector cap did not stack
  - `H188`: implementation-pain veto `blocked3<=q80` improved the champion
  - `H189`: basket-coherence / score-dispersion guards failed
  - live reruns on the new winner showed current activation state `OFF / cash`
- Session 64 then followed through on that branch:
  - `H190`: `sector_cap_3` became additive once paired with the stronger `blocked5<=q80` veto family
  - `H191`: the veto family improved again from `blocked3<=q80` to `blocked5<=q80`
  - live reruns on the final winner still show current activation state `OFF / cash`
- Session 65 then resolved the defense-vs-overfit fork:
  - `H192A`: parity passed; the complex historical winner is reproducible
  - `H192B`: the recent live state on that winner was mixed, not trivially all-cash
  - `H193`: the train-only pseudo-live ladder rejected the complex winner and rolled the active live branch back to sticky
- historical max-return system remains:
  - `full_library + k5_r5_eq + h175__rel2_gt0 + sticky_bonus_0p015 + impl__blocked5_q80 + sector_cap_3`
  - `+597.09%` relative vs VNINDEX
  - information ratio `1.0093`
- active live branch is now:
  - `full_library + k5_r5_eq + h175__rel2_gt0 + sticky_bonus_0p015`
  - current live holdings from `2026-03-26` signal / `2026-03-27` execution:
    - `ANV`, `PGV`, `PTB`, `PTL`, `VSI`
- Session 66 reopened `H151/H152` under a locked anti-leakage protocol:
  - dev `2015-2022`
  - validation `2023-2024`
  - one-shot confirmation `2025`
  - forward lockbox `2026+`
- `H151` result:
  - no narrow tradability-conditioned composite from the existing library beat the always-on `full_library` selector baseline
  - no promoted selector candidate
- `H152` result:
  - four new tradability-conditioned candidate signals passed the dev standalone gate inside `liq_open_basic`
  - none showed naive always-on selector relevance
  - treat them as candidate atoms, not promoted selectors
- Session 67 resolved the next selector ladder:
  - `H196`: no `H152` atom survived the locked additive promotion gate on top of `full_library`
  - `H197/H198`: skipped by rule because `H196` produced no promoted atoms
  - `H199`: second-wave search found one worth-carrying atom:
    - `h199_sector_laggard_gap_absorb`
- Session 68 established the current offline lead from the H199 atom:
  - `H200`: additive bakeoff passed
  - `H201`: state-scoped additive blend passed
  - `H202`: sticky-activation compatibility failed
  - current offline lead selector:
    - `state_blend__h199_sector_laggard_gap_absorb__30`
- Session 69 resolved the next selector extension:
  - `H203`: pairwise additive bakeoff passed in always-on form
  - `H205`: state-scoped pairwise extension failed
  - `H204`: fresh-family tradability search found no promoted atom
- Session 70 resolved the first exit-alpha ladder:
  - `H207`: rank-decay exits beat the always-on selector baseline
  - `H211`: strength-exhaustion exits beat the H207 anchor in always-on form
  - `H212`: replacement-pressure exits failed
  - `H213`: the H211 winner failed frozen sticky-activation compatibility
- Session 71 resolved the genuinely new exit-family follow-through:
  - `H214`: thesis inconsistency failed
  - `H215`: failed follow-through was a near-miss but did not clear the locked gate
  - `H216`: time-under-water failed badly on confirmation
  - `H217`: skipped because no new family displaced H211
- Session 72 resolved the continuation / hold-vs-exit hazard branch:
  - `H218`: no dev-trained continuation model cleared the predictive gate
  - `H219`: skipped because H218 produced no promoted continuation model
  - `H220`: skipped because H219 produced no promoted continuation-band winner
- Session 73 resolved the first genuinely new-data exit ladder:
  - `H221`: built `data/features/event_surface_daily.parquet` with held-row coverage `89.59%`
  - `H222`: event predictive screening failed
  - `H223/H224`: skipped because H222 produced no promoted event model
  - `H225`: intraday / auction structure failed the local coverage gate (`0.00%`, only `FPT` 1H exists)
  - `H226-H228`: skipped by rule
  - `H229`: order-book / queue feasibility failed locally; no historical queue/depth archive exists under `data/`
- Session 74 then codified the acquisition-first branch:
  - timing research should now start from:
    - `notes/timing_data_acquisition_plan.md`
    - `notes/timing_data_source_scorecard.csv`
  - next acquisition order:
    - multi-ticker intraday / auction source first
    - richer company-event source second
    - otherwise stop timing research and wait for new data or more live evidence
- the active next branch is now dual-track:
  - live track:
    - keep the live forward scoreboard running on the rollback sticky branch
    - if sticky continues to beat sticky always-on forward, monitor only
    - if sticky falls behind sticky always-on over `>= 2` completed cycles, rerun parity first and then choose between reopening `H194/H195` or moving back to selection-side work
  - research track:
    - keep `state_blend__h199_sector_laggard_gap_absorb__30` as the offline lead selector
    - keep `strength_exhaustion__return_since_entry_threshold_0p15__score_drop_threshold_0p05` as offline-only exit evidence
    - do not replace the live sticky branch from that result alone
    - the current selector-discovery ladder is exhausted
    - the current exit ladder is also exhausted
    - do not reopen:
      - H199 pairwise recombinations
      - H204 atom recombinations
      - H206, because `H205` produced no promoted winner
      - H207-H213 threshold retuning on the same locked window
      - H214-H217 threshold retuning on the same locked window
      - H218-H220 threshold retuning on the same locked window
      - H221-H229 on the same local data stack without new data acquisition
    - exit-side research is now closed on the current local data stack
    - the next honest exit branch now requires actual new data acquisition:
      - richer company-event timestamps
      - multi-ticker intraday / auction data
      - historical order-book / queue archives
    - the next honest selector-side branch must require a genuinely new data family or a new high-level hypothesis family
- the RL branch is now exploratory after `H155`
- `H153` runner now exists at `python -m vn_stock_rl.evaluation.portfolio_baseline`
- `H154` first ladder is complete: `S1`-only RL won on seed `1208`, conditioned sub-core is mixed,
  and full-matrix RL failed
- `H155` is now complete and mixed: `S1`-only RL had two strong wins and two failures across seeds,
  so RL is exploratory again and no longer drives the active research queue

Do not maintain a partial summary table here unless you update it together with `notes/signal_library.md`.

---

## Start Here

Read in this order:

1. `README.md`
2. `notes/next_steps.md`
3. `notes/signal_library.md`
4. `notes/findings.md` index plus the relevant `notes/findings-*.md` chunk
5. `notes/session_NN_log.md` only when you need a detailed traceback

When the active branch is timing-data acquisition rather than modeling, read next:

6. `notes/timing_data_acquisition_plan.md`
7. `notes/timing_data_source_scorecard.csv`

Use this file for:

- exact commands
- experiment mode selection
- result artifact locations
- session log conventions
- data inventory → see `notes/data_sources.md`

---

## Canonical Sources

- `notes/next_steps.md`: live champion, current priorities, short recent digest
- `notes/signal_library.md`: **signal registry — primary deliverable**
- `notes/findings.md`: index for durable scientific truth
- `notes/findings-*.md`: chunked durable scientific truth, padded to 30-block filename ranges
- `notes/data_sources.md`: **data inventory — what's in git, what's not, how to restore**
- `notes/session_NN_log.md`: full per-session record

`README.md` is overview only.

---

## Saved Result Artifacts

Main experiment runners write compact summaries to `artifacts/run_summaries/`.
Read these first when you want the minimal result.

- One-shot: `artifacts/run_summaries/latest_one_shot.json`
- Walk-forward: `artifacts/run_summaries/latest_walk_forward.json`
- Cross-sectional: `artifacts/run_summaries/latest_cross_sectional.json`
- Ensemble: `artifacts/run_summaries/latest_ensemble.json`
- Portfolio: `artifacts/run_summaries/latest_portfolio.json`
- Portfolio baseline: `artifacts/run_summaries/latest_portfolio_baseline.json`
- Portfolio construction sweep: `artifacts/run_summaries/latest_portfolio_construction_sweep.json`
- Portfolio nested selection: `artifacts/run_summaries/latest_portfolio_nested_selection.json`
- Portfolio fixed-menu validation: `artifacts/run_summaries/latest_portfolio_fixed_menu_validation.json`
- Portfolio capacity / fee stress: `artifacts/run_summaries/latest_portfolio_capacity_fee_stress.json`
- Portfolio retail validation: `artifacts/run_summaries/latest_portfolio_retail_validation.json`
- Portfolio capacity-aware sweep: `artifacts/run_summaries/latest_portfolio_capacity_aware_sweep.json`
- Portfolio live candidate blotter: `artifacts/run_summaries/latest_portfolio_live_candidate_blotter.json`
- Portfolio liquidity-aware scoring: `artifacts/run_summaries/latest_portfolio_liquidity_aware_scoring.json`
- Portfolio entry slicing simulation: `artifacts/run_summaries/latest_portfolio_entry_slicing_simulation.json`
- Portfolio volume-confirmed entry filter: `artifacts/run_summaries/latest_portfolio_volume_confirmed_entry_filter.json`
- Portfolio variable breadth: `artifacts/run_summaries/latest_portfolio_variable_breadth.json`
- Portfolio liquidity-state opportunity audit: `artifacts/run_summaries/latest_portfolio_liquidity_state_opportunity_audit.json`
- Portfolio local liquidity-gate refinement: `artifacts/run_summaries/latest_portfolio_local_liquidity_gate_refinement.json`
- Portfolio soft activation score: `artifacts/run_summaries/latest_portfolio_soft_activation_score.json`
- Portfolio conditional alpha decomposition: `artifacts/run_summaries/latest_portfolio_conditional_alpha_decomposition.json`
- Portfolio activation opportunity density: `artifacts/run_summaries/latest_portfolio_activation_opportunity_density.json`
- Portfolio activation tradability breadth: `artifacts/run_summaries/latest_portfolio_activation_tradability_breadth.json`
- Portfolio activation market regime: `artifacts/run_summaries/latest_portfolio_activation_market_regime.json`
- Portfolio activation breadth / dispersion: `artifacts/run_summaries/latest_portfolio_activation_breadth_dispersion.json`
- Portfolio activation recent efficacy: `artifacts/run_summaries/latest_portfolio_activation_recent_efficacy.json`
- Portfolio activation composite: `artifacts/run_summaries/latest_portfolio_activation_composite.json`
- Portfolio activation partial exposure: `artifacts/run_summaries/latest_portfolio_activation_partial_exposure.json`
- Portfolio activation opportunity concentration: `artifacts/run_summaries/latest_portfolio_activation_opportunity_concentration.json`
- Portfolio activation selector agreement: `artifacts/run_summaries/latest_portfolio_activation_selector_agreement.json`
- Portfolio activation tradability acceleration: `artifacts/run_summaries/latest_portfolio_activation_tradability_acceleration.json`
- Portfolio activation selector fragility: `artifacts/run_summaries/latest_portfolio_activation_selector_fragility.json`
- Portfolio activation interaction regime: `artifacts/run_summaries/latest_portfolio_activation_interaction_regime.json`
- Portfolio activation breadth collapse: `artifacts/run_summaries/latest_portfolio_activation_breadth_collapse.json`
- Portfolio activation smoothed recent efficacy: `artifacts/run_summaries/latest_portfolio_activation_smoothed_recent_efficacy.json`
- Portfolio activation drawdown phase: `artifacts/run_summaries/latest_portfolio_activation_drawdown_phase.json`
- Portfolio activation entry-window quality: `artifacts/run_summaries/latest_portfolio_activation_entry_window_quality.json`
- Portfolio activation selector-specific: `artifacts/run_summaries/latest_portfolio_activation_selector_specific.json`
- Portfolio activation hysteresis: `artifacts/run_summaries/latest_portfolio_activation_hysteresis.json`
- Portfolio activation H170 robustness: `artifacts/run_summaries/latest_portfolio_activation_h170_robustness.json`
- Portfolio activation H170 three-state sizing: `artifacts/run_summaries/latest_portfolio_activation_h170_three_state_sizing.json`
- Portfolio activation meta-model: `artifacts/run_summaries/latest_portfolio_activation_meta_model.json`
- Portfolio activation H175 robustness stress: `artifacts/run_summaries/latest_portfolio_activation_h175_robustness_stress.json`
- Portfolio live activation overlay: `artifacts/run_summaries/latest_portfolio_live_activation_overlay.json`
- Portfolio activation H175 small augmentations: `artifacts/run_summaries/latest_portfolio_activation_h175_small_augmentations.json`
- Portfolio exit rank decay: `artifacts/run_summaries/latest_portfolio_exit_rank_decay.json`
- Portfolio exit time-plus-decay: `artifacts/run_summaries/latest_portfolio_exit_time_plus_decay.json`
- Portfolio exit sticky winner: `artifacts/run_summaries/latest_portfolio_exit_sticky_winner.json`
- Portfolio exit liquidity deterioration: `artifacts/run_summaries/latest_portfolio_exit_liquidity_deterioration.json`
- Portfolio exit strength exhaustion: `artifacts/run_summaries/latest_portfolio_exit_strength_exhaustion.json`
- Portfolio exit replacement pressure: `artifacts/run_summaries/latest_portfolio_exit_replacement_pressure.json`
- Portfolio exit activation compatibility: `artifacts/run_summaries/latest_portfolio_exit_activation_compatibility.json`
- Portfolio exit thesis inconsistency: `artifacts/run_summaries/latest_portfolio_exit_thesis_inconsistency.json`
- Portfolio exit failed followthrough: `artifacts/run_summaries/latest_portfolio_exit_failed_followthrough.json`
- Portfolio exit time under water: `artifacts/run_summaries/latest_portfolio_exit_time_under_water.json`
- Portfolio exit new-family activation compatibility: `artifacts/run_summaries/latest_portfolio_exit_new_family_activation_compatibility.json`
- Portfolio exit continuation alpha model: `artifacts/run_summaries/latest_portfolio_exit_continuation_alpha_model.json`
- Portfolio exit continuation bands: `artifacts/run_summaries/latest_portfolio_exit_continuation_bands.json`
- Portfolio exit continuation activation compatibility: `artifacts/run_summaries/latest_portfolio_exit_continuation_activation_compatibility.json`

Execution/tradability producer:

- `data_tools/build_tradability_flags.py` -> `data/features/execution/tradability_daily.parquet`

Permanent logs remain:

- `results_summary.jsonl` for one-shot screens
- `wf_results.jsonl` for walk-forward runs
- `xs_wf_results.jsonl` for cross-sectional and ensemble runs

Mode-specific durable outputs:

- `run_experiment.py`: `experiments/<timestamp>_<name>/metrics.json` plus `results_summary.jsonl`
- `walk_forward.py`: `wf_results.jsonl`
- `cross_sectional_wf.py`: `xs_wf_results.jsonl` plus optional saved probability files
- `ensemble_wf.py`: `xs_wf_results.jsonl`
- `analysis/h40_rank_portfolio.py`: `artifacts/run_summaries/latest_portfolio.json`
- `analysis/h135_signal_library_portfolio_baseline.py`: `artifacts/run_summaries/latest_portfolio_baseline.json` plus daily curves under `artifacts/portfolio_baselines/`
- `analysis/h136_portfolio_construction_sweep.py`: `artifacts/run_summaries/latest_portfolio_construction_sweep.json` plus sweep outputs under `artifacts/portfolio_baselines/`
- `analysis/h137_nested_portfolio_selection.py`: `artifacts/run_summaries/latest_portfolio_nested_selection.json` plus selected-config, train-candidate, and stitched OOS outputs under `artifacts/portfolio_baselines/`
- `analysis/h138_fixed_menu_validation.py`: `artifacts/run_summaries/latest_portfolio_fixed_menu_validation.json` plus fixed-menu results and OOS daily outputs under `artifacts/portfolio_baselines/`
- `analysis/h139_fixed_menu_capacity_fee_stress.py`: `artifacts/run_summaries/latest_portfolio_capacity_fee_stress.json` plus stress-grid outputs under `artifacts/portfolio_baselines/`
- `analysis/h140_retail_capacity_aware_validation.py`: `artifacts/run_summaries/latest_portfolio_retail_validation.json` plus retail-grid outputs under `artifacts/portfolio_baselines/`
- `analysis/h141_capacity_aware_construction_sweep.py`: `artifacts/run_summaries/latest_portfolio_capacity_aware_sweep.json` plus constrained-sweep outputs under `artifacts/portfolio_baselines/`
- `analysis/h142_live_candidate_blotter.py`: `artifacts/run_summaries/latest_portfolio_live_candidate_blotter.json` plus detailed and daily blotter outputs under `artifacts/portfolio_baselines/`
- `analysis/h143_liquidity_aware_scoring.py`: `artifacts/run_summaries/latest_portfolio_liquidity_aware_scoring.json` plus score-variant results under `artifacts/portfolio_baselines/`
- `analysis/h144_entry_slicing_simulation.py`: `artifacts/run_summaries/latest_portfolio_entry_slicing_simulation.json` plus sliced vs unsliced outputs under `artifacts/portfolio_baselines/`
- `analysis/h145_volume_confirmed_entry_filter.py`: `artifacts/run_summaries/latest_portfolio_volume_confirmed_entry_filter.json` plus entry-gate outputs under `artifacts/portfolio_baselines/`
- `analysis/h146_variable_breadth_portfolio.py`: `artifacts/run_summaries/latest_portfolio_variable_breadth.json` plus variable-breadth sweep outputs under `artifacts/portfolio_baselines/`
- `analysis/h238_entry_alpha_candidate_panel.py`: `artifacts/run_summaries/latest_entry_alpha_candidate_panel.json` plus canonical candidate-panel artifacts under `data/features/entry_alpha/`
- `analysis/h239_entry_alpha_sparse_breadth_baseline.py`: `artifacts/run_summaries/latest_entry_alpha_sparse_breadth_baseline.json` plus sparse-breadth baseline outputs under `artifacts/entry_alpha/`
- `analysis/h240_entry_alpha_single_family_screens.py`: `artifacts/run_summaries/latest_entry_alpha_single_family_screens.json` plus screen results and enriched candidate-panel outputs under `artifacts/entry_alpha/`
- `analysis/h241_entry_alpha_compact_model.py`: `artifacts/run_summaries/latest_entry_alpha_compact_model.json` plus compact-model results under `artifacts/entry_alpha/` and canonical score artifact `data/features/entry_alpha/entry_scores_daily.parquet`
- `analysis/h242_entry_alpha_soft_exposure_prior.py`: `artifacts/run_summaries/latest_entry_alpha_soft_exposure_prior.json` plus soft-prior portfolio results under `artifacts/entry_alpha/`
- `analysis/h243_entry_alpha_live_compatibility.py`: `artifacts/run_summaries/latest_entry_alpha_live_compatibility.json` plus pseudo-live compatibility outputs under `artifacts/entry_alpha/`
- `analysis/h244_entry_alpha_sparse_breadth_protocol.py`: `artifacts/run_summaries/latest_entry_alpha_sparse_breadth_protocol.json` plus dev-selected winner and protocol results under `artifacts/entry_alpha/`
- `analysis/h245_entry_alpha_topk_contract_audit.py`: `artifacts/run_summaries/latest_entry_alpha_topk_contract_audit.json` plus per-contract winners and selected-contract daily outputs under `artifacts/entry_alpha/`
- `analysis/h246_entry_alpha_small_book_confirmation.py`: `artifacts/run_summaries/latest_entry_alpha_small_book_confirmation.json` plus small-book overlay results under `artifacts/entry_alpha/`
- `analysis/h147_liquidity_state_opportunity_audit.py`: `artifacts/run_summaries/latest_portfolio_liquidity_state_opportunity_audit.json` plus daily opportunity-count outputs under `artifacts/portfolio_baselines/`
- `analysis/h148_local_liquidity_gate_refinement.py`: `artifacts/run_summaries/latest_portfolio_local_liquidity_gate_refinement.json` plus local-gate refinement outputs under `artifacts/portfolio_baselines/`
- `analysis/h149_soft_activation_score.py`: `artifacts/run_summaries/latest_portfolio_soft_activation_score.json` plus soft-activation outputs under `artifacts/portfolio_baselines/`
- `analysis/h150_conditional_alpha_decomposition.py`: `artifacts/run_summaries/latest_portfolio_conditional_alpha_decomposition.json` plus conditional-IC tables under `artifacts/portfolio_baselines/`
- `data_tools/build_activation_state_features.py`: `data/features/activation_state_daily.parquet`
- `data_tools/build_activation_meta_features.py`: `data/features/activation_meta_daily.parquet`
- `analysis/h157_opportunity_density_gate.py`: `artifacts/run_summaries/latest_portfolio_activation_opportunity_density.json` plus activation-gate outputs under `artifacts/portfolio_baselines/`
- `analysis/h158_tradability_breadth_gate.py`: `artifacts/run_summaries/latest_portfolio_activation_tradability_breadth.json` plus activation-gate outputs under `artifacts/portfolio_baselines/`
- `analysis/h159_market_regime_gate.py`: `artifacts/run_summaries/latest_portfolio_activation_market_regime.json` plus activation-gate outputs under `artifacts/portfolio_baselines/`
- `analysis/h160_breadth_dispersion_gate.py`: `artifacts/run_summaries/latest_portfolio_activation_breadth_dispersion.json` plus activation-gate outputs under `artifacts/portfolio_baselines/`
- `analysis/h161_recent_efficacy_cooldown_gate.py`: `artifacts/run_summaries/latest_portfolio_activation_recent_efficacy.json` plus activation-gate outputs under `artifacts/portfolio_baselines/`
- `analysis/h162_composite_activation_score.py`: `artifacts/run_summaries/latest_portfolio_activation_composite.json` plus activation-gate outputs under `artifacts/portfolio_baselines/`
- `analysis/h163_partial_exposure_sizing.py`: `artifacts/run_summaries/latest_portfolio_activation_partial_exposure.json` plus activation outputs under `artifacts/portfolio_baselines/`
- `analysis/h164_opportunity_concentration_gate.py`: `artifacts/run_summaries/latest_portfolio_activation_opportunity_concentration.json` plus activation outputs under `artifacts/portfolio_baselines/`
- `analysis/h165_selector_agreement_gate.py`: `artifacts/run_summaries/latest_portfolio_activation_selector_agreement.json` plus activation outputs under `artifacts/portfolio_baselines/`
- `analysis/h166_tradability_acceleration_gate.py`: `artifacts/run_summaries/latest_portfolio_activation_tradability_acceleration.json` plus activation outputs under `artifacts/portfolio_baselines/`
- `analysis/h167_selector_fragility_gate.py`: `artifacts/run_summaries/latest_portfolio_activation_selector_fragility.json` plus activation outputs under `artifacts/portfolio_baselines/`
- `analysis/h168_interaction_regime_gate.py`: `artifacts/run_summaries/latest_portfolio_activation_interaction_regime.json` plus activation outputs under `artifacts/portfolio_baselines/`
- `analysis/h169_breadth_collapse_gate.py`: `artifacts/run_summaries/latest_portfolio_activation_breadth_collapse.json` plus activation outputs under `artifacts/portfolio_baselines/`
- `analysis/h170_smoothed_recent_efficacy_gate.py`: `artifacts/run_summaries/latest_portfolio_activation_smoothed_recent_efficacy.json` plus activation outputs under `artifacts/portfolio_baselines/`
- `analysis/h171_selector_drawdown_phase_gate.py`: `artifacts/run_summaries/latest_portfolio_activation_drawdown_phase.json` plus activation outputs under `artifacts/portfolio_baselines/`
- `analysis/h172_entry_window_quality_gate.py`: `artifacts/run_summaries/latest_portfolio_activation_entry_window_quality.json` plus activation outputs under `artifacts/portfolio_baselines/`
- `analysis/h173_selector_specific_activation.py`: `artifacts/run_summaries/latest_portfolio_activation_selector_specific.json` plus activation outputs under `artifacts/portfolio_baselines/`
- `analysis/h174_hysteresis_activation.py`: `artifacts/run_summaries/latest_portfolio_activation_hysteresis.json` plus activation outputs under `artifacts/portfolio_baselines/`
- `analysis/h175_h170_robustness.py`: `artifacts/run_summaries/latest_portfolio_activation_h170_robustness.json` plus robustness outputs under `artifacts/portfolio_baselines/`
- `analysis/h176_h170_three_state_sizing.py`: `artifacts/run_summaries/latest_portfolio_activation_h170_three_state_sizing.json` plus sizing outputs under `artifacts/portfolio_baselines/`
- `analysis/h177_activation_meta_model.py`: `artifacts/run_summaries/latest_portfolio_activation_meta_model.json` plus meta-model outputs under `artifacts/portfolio_baselines/`
- `analysis/h178_h175_robustness_stress.py`: `artifacts/run_summaries/latest_portfolio_activation_h175_robustness_stress.json` plus stress outputs under `artifacts/portfolio_baselines/`
- `analysis/h179_live_activation_overlay.py`: `artifacts/run_summaries/latest_portfolio_live_activation_overlay.json` plus completed-execution and next-open live-overlay outputs under `artifacts/portfolio_baselines/`
- `analysis/h180_h175_small_augmentations.py`: `artifacts/run_summaries/latest_portfolio_activation_h175_small_augmentations.json` plus local-augmentation outputs under `artifacts/portfolio_baselines/`
- `analysis/h207_rank_decay_exit.py`: `artifacts/run_summaries/latest_portfolio_exit_rank_decay.json` plus exit-rule results under `artifacts/portfolio_baselines/`
- `analysis/h208_time_plus_decay_exit.py`: `artifacts/run_summaries/latest_portfolio_exit_time_plus_decay.json` plus exit-rule results under `artifacts/portfolio_baselines/`
- `analysis/h209_sticky_winner_exit.py`: `artifacts/run_summaries/latest_portfolio_exit_sticky_winner.json` plus exit-rule results under `artifacts/portfolio_baselines/`
- `analysis/h210_liquidity_deterioration_exit.py`: `artifacts/run_summaries/latest_portfolio_exit_liquidity_deterioration.json` plus exit-rule results under `artifacts/portfolio_baselines/`
- `analysis/h211_strength_exhaustion_exit.py`: `artifacts/run_summaries/latest_portfolio_exit_strength_exhaustion.json` plus exit-rule results under `artifacts/portfolio_baselines/`
- `analysis/h212_replacement_pressure_exit.py`: `artifacts/run_summaries/latest_portfolio_exit_replacement_pressure.json` plus exit-rule results under `artifacts/portfolio_baselines/`
- `analysis/h213_exit_activation_compatibility.py`: `artifacts/run_summaries/latest_portfolio_exit_activation_compatibility.json` plus compatibility outputs under `artifacts/portfolio_baselines/`
- `analysis/h214_thesis_inconsistency_exit.py`: `artifacts/run_summaries/latest_portfolio_exit_thesis_inconsistency.json` plus exit-rule results under `artifacts/portfolio_baselines/`
- `analysis/h215_failed_followthrough_exit.py`: `artifacts/run_summaries/latest_portfolio_exit_failed_followthrough.json` plus exit-rule results under `artifacts/portfolio_baselines/`
- `analysis/h216_time_under_water_exit.py`: `artifacts/run_summaries/latest_portfolio_exit_time_under_water.json` plus exit-rule results under `artifacts/portfolio_baselines/`
- `analysis/h217_new_exit_activation_compatibility.py`: `artifacts/run_summaries/latest_portfolio_exit_new_family_activation_compatibility.json` plus compatibility outputs under `artifacts/portfolio_baselines/`
- `analysis/h218_continuation_alpha_model.py`: `artifacts/run_summaries/latest_portfolio_exit_continuation_alpha_model.json` plus continuation-model outputs under `artifacts/portfolio_baselines/`
- `analysis/h219_continuation_exit_bands.py`: `artifacts/run_summaries/latest_portfolio_exit_continuation_bands.json` plus continuation-band outputs under `artifacts/portfolio_baselines/`
- `analysis/h220_continuation_exit_activation_compatibility.py`: `artifacts/run_summaries/latest_portfolio_exit_continuation_activation_compatibility.json` plus compatibility outputs under `artifacts/portfolio_baselines/`
- `analysis/h151_tradability_conditioned_composite_bakeoff.py`: `artifacts/run_summaries/latest_portfolio_tradability_composite_bakeoff.json` plus candidate results under `artifacts/portfolio_baselines/`
- `analysis/h152_tradability_conditioned_signal_search.py`: `artifacts/run_summaries/latest_tradability_conditioned_signal_search.json` plus candidate results under `artifacts/portfolio_baselines/`
- `analysis/h196_additive_atom_bakeoff.py`: `artifacts/run_summaries/latest_portfolio_additive_atom_bakeoff.json` plus additive-selector results under `artifacts/portfolio_baselines/`
- `analysis/h197_state_scoped_additive_bakeoff.py`: `artifacts/run_summaries/latest_portfolio_state_scoped_additive_bakeoff.json` plus state-scoped additive outputs under `artifacts/portfolio_baselines/`
- `analysis/h198_selector_activation_compatibility.py`: `artifacts/run_summaries/latest_portfolio_selector_activation_compatibility.json` plus compatibility outputs under `artifacts/portfolio_baselines/`
- `analysis/h199_second_wave_tradability_conditioned_search.py`: `artifacts/run_summaries/latest_tradability_conditioned_signal_search_v2.json` plus second-wave signal-search outputs under `artifacts/portfolio_baselines/`
- `analysis/h200_additive_h199_atom_bakeoff.py`: `artifacts/run_summaries/latest_portfolio_additive_h199_atom_bakeoff.json` plus additive H199 selector outputs under `artifacts/portfolio_baselines/`
- `analysis/h201_state_scoped_h199_atom_bakeoff.py`: `artifacts/run_summaries/latest_portfolio_state_scoped_h199_atom_bakeoff.json` plus state-scoped H199 selector outputs under `artifacts/portfolio_baselines/`
- `analysis/h202_h199_selector_activation_compatibility.py`: `artifacts/run_summaries/latest_portfolio_h199_selector_activation_compatibility.json` plus H199 selector-activation compatibility outputs under `artifacts/portfolio_baselines/`
- `analysis/h203_pairwise_additive_bakeoff.py`: `artifacts/run_summaries/latest_portfolio_pairwise_additive_bakeoff.json` plus pairwise additive selector outputs under `artifacts/portfolio_baselines/`
- `analysis/h204_third_wave_tradability_conditioned_search.py`: `artifacts/run_summaries/latest_tradability_conditioned_signal_search_v3.json` plus third-wave signal-search outputs under `artifacts/portfolio_baselines/`
- `analysis/h205_state_scoped_pairwise_bakeoff.py`: `artifacts/run_summaries/latest_portfolio_state_scoped_pairwise_bakeoff.json` plus state-scoped pairwise outputs under `artifacts/portfolio_baselines/`
- `analysis/h206_pair_selector_activation_compatibility.py`: `artifacts/run_summaries/latest_portfolio_pair_selector_activation_compatibility.json` plus pair-selector compatibility outputs under `artifacts/portfolio_baselines/`

For any new analysis script, keep the large output wherever it naturally belongs, but also write
one compact summary JSON under `artifacts/run_summaries/`.

---

## Result Is Done When

- The experiment has a compact saved summary artifact.
- The permanent output path is recorded.
- The session log states the hypothesis, result, and verdict.
- The verdict is classified using the branch-result buckets in this file and `README.md`.
- Durable conclusions are promoted to the current `notes/findings-*.md` chunk.
- `notes/next_steps.md` is updated if the champion system or next priority changed.
- `notes/signal_library.md` is updated if a signal was confirmed, promoted, or newly rejected.

---

## Mode Selection

### Mode 0: Quick One-Shot Screen (`run_experiment.py`)

- Use for: cheap sanity checks, feature plumbing, quick model smoke tests
- Do not use for: strong scientific claims or new production decisions
- Output:
  `experiments/<timestamp>_<name>/metrics.json`
  `results_summary.jsonl`
  `artifacts/run_summaries/latest_one_shot.json`

```bash
conda run -n stocks python run_experiment.py --config configs/E32_barrier_1pct.json
```

### Mode 1: Single-Stock Walk-Forward (`walk_forward.py`)

- Use for: new FPT-only hypotheses
- Output:
  `wf_results.jsonl`
  `artifacts/run_summaries/latest_walk_forward.json`

```bash
conda run -n stocks python walk_forward.py --config configs/E32_barrier_1pct.json
```

### Mode 2: Cross-Sectional Walk-Forward (`cross_sectional_wf.py`)

- Use for: market-wide hypotheses and anything that depends on the broader stock universe
- Output:
  `xs_wf_results.jsonl`
  optional saved probability files
  `artifacts/run_summaries/latest_cross_sectional.json`

```bash
# Basic run
conda run -n stocks python cross_sectional_wf.py --threshold 0.05

# With barrier labels + FPT proba saving
conda run -n stocks python cross_sectional_wf.py --barrier-pct 0.01 --threshold 0.05 \
  --save-proba data/features/xs_barrier_fpt_proba.csv

# Save probas for all tickers
conda run -n stocks python cross_sectional_wf.py --barrier-pct 0.01 --threshold 0.05 \
  --save-all-probas data/features/xs_barrier_all_probas.parquet
```

### Mode 3: Ensemble (`ensemble_wf.py`)

- Use for: blending saved FPT probability streams, agreement filters, confidence thresholds
- Output:
  `xs_wf_results.jsonl`
  `artifacts/run_summaries/latest_ensemble.json`

```bash
# Generate single-stock probabilities
conda run -n stocks python ensemble_wf.py save-ss \
  --ss-config configs/E32_barrier_1pct.json \
  --out data/features/ss_fpt_proba_e32.csv

# Run ensemble
conda run -n stocks python ensemble_wf.py ensemble \
  --xs-proba data/features/xs_barrier_fpt_proba.csv \
  --ss-proba data/features/ss_fpt_proba_e32.csv \
  --min-conf 0.55 --vix-min 15 --vix-max 30 --agree-only
```

### Mode 4: Portfolio / Meta Analysis (`analysis/*.py`)

- Use for: rank portfolios, cost studies, filter sweeps, execution assumptions, live validation
- Default expectation:
  consume saved artifacts
  write one compact summary under `artifacts/run_summaries/`
  store any larger output in its natural location

Core portfolio evaluator:

- `analysis/h40_rank_portfolio.py` writes `artifacts/run_summaries/latest_portfolio.json`
- `analysis/h135_signal_library_portfolio_baseline.py` is the realistic deterministic baseline for the RL signal library

### Decision Rule

- "Is this FPT-only feature/model valid?" -> `walk_forward.py`
- "Does this signal generalize across the market?" -> `cross_sectional_wf.py`
- "Do these saved models combine better?" -> `ensemble_wf.py`
- "Does this improve the trade or portfolio layer?" -> `analysis/*.py`

---

## Command Guides

### Result Artifacts

After running a main experiment runner, inspect these compact summaries before reading long logs:

- One-shot: `artifacts/run_summaries/latest_one_shot.json`
- Walk-forward: `artifacts/run_summaries/latest_walk_forward.json`
- Cross-sectional: `artifacts/run_summaries/latest_cross_sectional.json`
- Ensemble: `artifacts/run_summaries/latest_ensemble.json`
- Portfolio: `artifacts/run_summaries/latest_portfolio.json`
- Portfolio baseline: `artifacts/run_summaries/latest_portfolio_baseline.json`

### Current Best RL Signal: H93

```bash
# H93 — Volume + 1-day label. IC +0.1491, Sharpe 15.08, edge std 1.60%
# PRIMARY SIGNAL for RL state features
PYTHONIOENCODING=utf-8 /c/Users/manhn/miniconda3/envs/stocks/python.exe cross_sectional_wf.py \
    --use-volume-signals --barrier-pct 0.01 --target-horizon 1 \
    --save-all-probas data/features/xs_barrier_vol_1d_hose_full.parquet
```

### Current Best Uncapped Long-Only Construction

```bash
# H138/H139 corrected engine winner, no ADV cap:
# full_library + k5_r5_eq
# +769.49% total on 2019-2025 holdout, +346.29% vs VNINDEX
# NOT retail-deployable under explicit capacity/tradability gates
conda run -n stocks python analysis/h138_fixed_menu_validation.py

# Fetch any new HOSE stocks
PYTHONIOENCODING=utf-8 conda run -n stocks python data_tools/fetch_hose_universe.py --delay 0.3
```

### Current Best Uncapped Long-Only System

```bash
# Session 64 live champion:
# full_library + k5_r5_eq + h175__rel2_gt0 + sticky_bonus_0p015 + impl__blocked5_q80 + sector_cap_3
# +597.09% relative vs VNINDEX, IR 1.0093 on 2019-2025
conda run -n stocks python analysis/h190_impl_pain_sector_combo.py
```

### Parked Historical Execution Benchmark: H54

```bash
# H54 - 393 HOSE stocks, no VIX filter, N=5, min_proba=0.55
# +25.52% avg edge, Sharpe 9.17, 11/11 years | IC=+0.1515
# PARKED: deployment gap (real fills unverified, net P&L negative at 0.30% RT)
PYTHONIOENCODING=utf-8 conda run -n stocks python analysis/h40_rank_portfolio.py \
    --probas data/features/xs_barrier_all_probas_hose_full.parquet \
    --no-vix-filter
```

### Honest Benchmarks

```bash
# H52 - Nested walk-forward param search (fully honest, no contamination)
conda run -n stocks python analysis/h52_nested_wf_params.py

# H50a - VIX-feature probas, no external VIX filter
conda run -n stocks python analysis/h40_rank_portfolio.py \
    --probas data/features/xs_barrier_vix_feature_all_probas.parquet \
    --no-vix-filter

# H51 - Soft parameterless portfolio
conda run -n stocks python analysis/h51_soft_portfolio.py
```

### Historical Reference: H43 Rank Portfolio

```bash
conda run -n stocks python analysis/h40_rank_portfolio.py
```

### FPT Single-Stock Systems

```bash
# H38 - Best FPT-only system
conda run -n stocks python ensemble_wf.py ensemble \
  --xs-proba data/features/xs_barrier_fpt_proba.csv \
  --ss-proba data/features/ss_fpt_proba_e32.csv \
  --min-conf 0.55 --vix-min 15 --vix-max 30 --agree-only

# H22 - Best risk-adjusted FPT system
conda run -n stocks python ensemble_wf.py ensemble \
  --xs-proba data/features/xs_barrier_fpt_proba.csv \
  --ss-proba data/features/ss_fpt_proba_e32.csv \
  --min-conf 0.55 --vix-min 18 --vix-max 35 --agree-only
```

### Regenerating Pre-Built Probability Files

```bash
# Regenerate XS barrier probabilities for all 52 stocks
conda run -n stocks python cross_sectional_wf.py --barrier-pct 0.01 --threshold 0.05 \
  --save-all-probas data/features/xs_barrier_all_probas.parquet

# Regenerate XS barrier probabilities for FPT only
conda run -n stocks python cross_sectional_wf.py --barrier-pct 0.01 --threshold 0.05 \
  --save-proba data/features/xs_barrier_fpt_proba.csv

# Regenerate E32 single-stock probabilities
conda run -n stocks python ensemble_wf.py save-ss \
  --ss-config configs/E32_barrier_1pct.json \
  --out data/features/ss_fpt_proba_e32.csv
```

### Single-Stock Walk-Forward

```bash
conda run -n stocks python walk_forward.py --config configs/E32_barrier_1pct.json
conda run -n stocks python summarize_wf.py
```

### Cross-Sectional Walk-Forward

```bash
conda run -n stocks python cross_sectional_wf.py --threshold 0.05
conda run -n stocks python cross_sectional_wf.py --barrier-pct 0.01 --threshold 0.05
conda run -n stocks python cross_sectional_wf.py --barrier-pct 0.01 --threshold 0.05 \
  --save-proba data/features/xs_barrier_fpt_proba.csv
conda run -n stocks python cross_sectional_wf.py --barrier-pct 0.01 --threshold 0.05 \
  --save-all-probas data/features/xs_barrier_all_probas.parquet
```

### Analysis Scripts

```bash
conda run -n stocks python analysis/h45_actual_returns.py
conda run -n stocks python analysis/h46_persistence_filter.py
conda run -n stocks python analysis/h47_proba_smoothing.py
conda run -n stocks python analysis/h48_signal_decay.py
conda run -n stocks python analysis/h49_patient_rebalancing.py
```

### Data Refresh

```bash
conda run -n stocks python data_tools/fetch_stock.py
conda run -n stocks python data_tools/fetch_fx_commodities.py
conda run -n stocks python data_tools/fetch_fundamentals.py
conda run -n stocks python data_tools/fetch_hose_universe.py --delay 0.3
conda run -n stocks python data_tools/fetch_refresh_all.py
```

Critical warning:
- `fetch_stock.py --overwrite` deletes the existing target parquet first, then rewrites it with exactly the requested date window
- `fetch_refresh_all.py --start <recent-date>` rewrites every stock parquet with only that requested window
- downstream live scorers and many feature builders require long lookback history, not just “latest date present”
- recent-window refreshes can therefore leave `data/stock/` in a mixed or truncated state and silently break live scoring
- check `data/stock/gia_lich_su_VNINDEX_1D.parquet` explicitly after any refresh; benchmark truncation is enough to break live `S1` even when most stock files look fresh

Safe default for full-history restoration:

```bash
conda run -n stocks python data_tools/fetch_refresh_all.py --start 2000-01-01 --end 2026-12-31
```

Before any live paper-trade attempt:
1. verify long-history continuity for the active universe and `VNINDEX`
2. rerun live `S1`
3. rebuild or ad hoc compute the latest stock-derived `full_library` features

Emergency recovery note:
- a local full-history `VNINDEX` backup currently exists at `../media-output/signal-xs-momentum/data/stock/gia_lich_su_VNINDEX_1D.parquet`
- this is a temporary fallback for recovery, not the canonical data source

### Pre-Generated Files (do not delete)

| File | Content | Used by |
|------|---------|---------|
| `data/features/xs_barrier_vol_1d_hose_full.parquet` | H93 — primary RL signal probas, 394 tickers | S1 (signal library) |
| `data/features/xs_open_close_asymmetry.parquet` | H100/H107 — oc_asym_5d, overnight/intraday, 826k rows | C4 (candidate signal) |
| `data/features/xs_insider_quality_features.parquet` | H108 — xs_ins_relative_size_5d + quality features | C5 (candidate signal, supersedes C2) |
| `data/features/xs_sector_rotation_daily.parquet` | H111 — sector breadth, sector momentum, intra-sector rank | xs_sector_breadth_5d candidate |
| `data/features/xs_news_sentiment_daily.parquet` | H89 — keyword sentiment, 340 tickers | C1 (candidate signal) |
| `data/features/xs_insider_features.parquet` | H97 — raw insider net buy/sell rolling windows | C2 (superseded by C5) |
| `data/features/xs_earnings_quality_daily.parquet` | H109 — EPS accel, ROE delta, margin trend (52 tickers) | H113 pending full-universe re-test |
| `data/features/xs_foreign_demand_daily.parquet` | H110 — VNM ETF affinity (not predictive, archive only) | rejected |
| `data/features/xs_barrier_all_probas_hose_full.parquet` | H54 probas, 393 tickers, all years | H54 (parked strategy) |
| `data/features/sector_classification.parquet` | ICB sector codes for 398 HOSE tickers | H92, sector filter |
| `data/features/macro_regime_daily.parquet` | 31 macro regime indicators | H26, H27 |

---

## Config Schema (`walk_forward.py`)

```json
{
  "experiment_name": "E32_barrier_1pct",
  "note": "Human-readable description of the hypothesis",
  "data": {
    "file_path": "data/stock/gia_lich_su_FPT_1D.parquet",
    "target_col": "future_rel_dir_5d",
    "test_size": 0.15,
    "val_size": 0.15,
    "start_date": "2016-01-01"
  },
  "features": {
    "base_cols": [],
    "use_lags": false,
    "use_ma": false,
    "use_ma_dist": true,
    "ma_windows": [5, 10, 20, 50],
    "use_rsi": true,
    "use_macd": true,
    "use_bb": true,
    "use_atr": true,
    "use_candle": true,
    "use_stoch": true,
    "use_willr": false,
    "use_adx": true,
    "use_hist_vol": true,
    "hist_vol_windows": [5, 10, 20],
    "use_cci": false,
    "use_volume_signals": false,
    "use_market_relative": true,
    "index_file": "data/stock/gia_lich_su_VNINDEX_1D.parquet",
    "rel_lag_days": [1, 2, 3, 5, 10, 20],
    "barrier_pct": 0.01,
    "use_macro": false,
    "use_fundamentals": false,
    "use_market_breadth": false,
    "use_calendar": false,
    "use_xs_features": false
  },
  "model": {
    "type": "xgboost_classifier",
    "params": {
      "n_estimators": 500,
      "max_depth": 3,
      "learning_rate": 0.05,
      "subsample": 0.8,
      "colsample_bytree": 0.8,
      "early_stopping_rounds": 30
    }
  }
}
```

## Core Metrics

- `direction_accuracy`: raw accuracy
- `naive_dir_acc`: baseline drift rate
- `edge_over_naive`: primary metric
- `dir_pvalue_vs_naive`: significance versus the drift baseline

For portfolio scripts, the important outputs are usually average edge, Sharpe, positive-year count,
and any execution-cost adjustments.

---

## Data Inventory

### Stock OHLCV

- Location: `data/stock/gia_lich_su_<TICKER>_1D.parquet`
- Schema: `time, open, high, low, close, volume` plus ticker metadata in some files
- Source: `data_tools/fetch_stock.py`
- Date ranges must be verified locally from the parquet files; do not assume an old repo note is still true after any refresh

Key symbols:

- Indices: `VNINDEX`, `VN30`
- Core names used often: `FPT`, `CMG`, `MWG`, `ACB`, `BID`, `CTG`, `EIB`, `HDB`, `MBB`, `VCB`, `VPB`

### FX, Commodities, Global Indices

- Location: `data/fx-commodities/`
- Source: `data_tools/fetch_fx_commodities.py`
- Common files:
  - `fx_commodities_vix_1D.parquet`
  - `fx_commodities_us10y_1D.parquet`
  - `fx_commodities_shanghai_1D.parquet`
  - `fx_commodities_hsi_1D.parquet`
  - `fx_commodities_nikkei_1D.parquet`
  - `fx_commodities_gold_1D.parquet`
  - `fx_commodities_oil_1D.parquet`
  - `fx_commodities_copper_1D.parquet`
  - `fx_commodities_cny_x_1D.parquet`
  - `fx_commodities_vnm_1D.parquet`
  - `fx_commodities_fx_vnd_usd_1D.parquet`

### News

- Location: `data/news/cafef/raw/<YYYY-MM-DD>.jsonl`
- Coverage in the repo notes: 2015-09-21 to 2026-03-14
- Intended use:
  1. daily mention counts
  2. simple sentiment proxies
  3. date merge into market data

### Pre-Built Feature Files

| File | Description |
|------|-------------|
| `data/features/xs_features_daily.parquet` | Cross-sectional rank features |
| `data/features/fpt_news_daily.parquet` | FPT news mention counts |
| `data/features/fpt_intraday_daily.parquet` | FPT 1H session features |
| `data/features/fpt_fundamentals.parquet` | FPT fundamentals forward-filled to daily |
| `data/features/xs_fpt_proba.csv` | XS walk-forward probabilities for FPT |
| `data/features/ss_fpt_proba.csv` | E8 single-stock probabilities |
| `data/features/ss_fpt_proba_e32.csv` | E32 single-stock probabilities |

### Data Fetching Tools

- `data_tools/fetch_stock.py`
- `data_tools/fetch_fx_commodities.py`
- `data_tools/fetch_news.py`
- `data_tools/fetch_fundamentals.py`
- `data_tools/fetch_fred_macro.py`

---

## Notes Convention

**Rule: append-only for the scientific record. Do not erase failed ideas.**

The `notes/` directory is the durable research record. Every failed experiment, wrong hypothesis,
and regime anomaly is still useful information.

**Important:** A signal that fails to improve a combined XGBoost model is NOT necessarily "failed"
as a learnable signal. Always test standalone IC and orthogonality before writing a signal off.
See `notes/signal_library.md` for evaluation criteria.

### File Roles

- `notes/signal_library.md`: **signal registry — primary output, update after every signal experiment**
- `notes/findings.md`: index for durable scientific conclusions
- `notes/findings-*.md`: durable scientific conclusions, chunked by 30 findings
- `notes/next_steps.md`: current queue plus a short recent digest
- `notes/session_NN_log.md`: detailed session record

### Session Workflow

1. Start by reading `README.md`, `notes/next_steps.md`, `notes/signal_library.md`, this file, and `notes/findings.md` plus the relevant `notes/findings-*.md` chunk.
2. Run the smallest valid experiment.
3. Make sure the run leaves behind a compact summary artifact.
4. Record the experiment in the session log after the result is known.
5. Promote durable conclusions into the current `notes/findings-*.md` chunk and update `notes/findings.md` if a new chunk is created.
6. Update `notes/next_steps.md` when the live state changes.
7. Update `notes/signal_library.md` if the experiment concerned a signal (confirmed, promoted, or rejected).

### Minimum Documentation Standard For A Material Experiment

Every material experiment should leave behind:

- a command or script path
- a compact saved result artifact
- a permanent note in the current session log
- a verdict: PASSED, FAILED, NEUTRAL, or MIXED

### What Not To Do

- Do not treat terminal output as the only record.
- Do not overwrite a session log with a shorter summary.
- Do not delete a failed direction just because it did not work.
- Do not let `next_steps.md` become a long narrative; keep details in session logs.

---

## Session Log Template

Use this structure for `notes/session_NN_log.md`:

```md
# Session NN Log - [Short Title] (YYYY-MM-DD)

## Objectives
- What question are we trying to answer this session?

## System State (entering)
- Current champion:
- Honest benchmark:
- Known open issue:

## Experiments

### HNN - [Experiment Name]
**Hypothesis:**
**Command / code:**
**Inputs:**
**Saved artifact:**

| Metric | Value | Note |
|--------|-------|------|
| ... | ... | ... |

**Result:**
**Verdict: PASSED / FAILED / NEUTRAL / MIXED**

## Session Conclusions
1. ...

## Findings To Promote
- `F??`: ...

## Production System After This Session
## Next Session Priority
```

---

## Rules For New Work

- Prefer the smallest valid mode.
- Do not rely on terminal output alone.
- Every material run should leave behind a compact saved summary.
- Every durable conclusion should be promoted into the notes stack.
- Do not touch 2026 data until user says so
