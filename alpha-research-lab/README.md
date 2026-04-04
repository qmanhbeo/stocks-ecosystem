# Alpha Signal Research Lab

Research repo for finding statistically valid equity signals in Vietnamese stocks, with an
agent-oriented workflow built around hypothesis → experiment → saved result → findings.

## What This Repo Is For

The **primary goal** is to build a library of learnable, orthogonal alpha signals that can
serve as state features for RL trading agents. Each signal should be independently predictive
and ideally uncorrelated with existing signals.

A secondary goal is tracking which signals combine into tradeable strategies. The strongest
uncapped long-only construction currently is the corrected `full_library + k5_r5_eq` branch from
H138/H139. ADV / capacity work is now **parked for the current-account branch, not solved**.
That branch is still **not** proven deployable under explicit retail liquidity constraints.
H54 remains the parked historical execution benchmark.

**This is not a race to beat H54. New signals are evaluated on their own merit as independent
information sources, not on whether they improve a combined model.**

## Research Method

This lab now defaults to sequential hypothesis ladders.

- each experiment family should have explicit pass / fail branch logic
- one result should determine whether the next experiment is needed, narrowed, or rejected
- prefer decision trees over broad unordered sweeps
- when a live branch is active, freeze it and run new hypotheses offline under a separate protocol
- classify finished branch outcomes explicitly instead of treating every branch as a binary live winner vs failure

## Branch Result Classification

Keep live-promotion standards strict, but do not throw away useful offline evidence.

Every finished branch should be classified into exactly one of these buckets:

### 1. Live promotion

Use this only when a branch is strong enough to change an active live or pseudo-live workflow.

Required standard:
- honest locked protocol for that branch
- result stayed strong enough on validation and confirmation
- pseudo-live / forward compatibility did not materially break the edge
- rule is operationally implementable with current artifacts and execution assumptions

Typical action:
- update `notes/next_steps.md` and the active branch description

### 2. Offline evidence promotion

Use this when a branch is not live-ready but still found something structurally real enough to anchor the next hypothesis.

Typical signs:
- a simpler baseline improved before later steps failed
- the branch narrowed the right portfolio contract
- the branch produced a durable negative result that should constrain future work

Typical action:
- record it in the session log and findings
- state clearly that it is offline evidence, not a live candidate

### 3. Branch kill / park

Use this when the current local path should not continue under the present data or contract.

Typical signs:
- repeated honest failures with no remaining narrowed path
- the branch only survives by local retuning after failing the stronger gate
- the branch depends on data the workspace does not currently have

Typical action:
- mark the branch closed or parked in `notes/next_steps.md`
- record what would need to change before reopening it

## Hard Trading Rule

This lab is permanently long-only.

- no synthetic hedges
- no stock shorting assumptions
- no “research-only” constructions that cannot be traded realistically in Vietnam
- if a construction cannot plausibly make money as a real long-only strategy, it is not a valid path for this repo

Index futures overlays are out of scope for this repo. Stay long-only.

## Signal Evaluation Criteria

For a signal to enter the library it must meet:

| Criterion | Threshold | Rationale |
|-----------|-----------|-----------|
| Standalone IC | > 0.01 | Any reliable predictive content is useful |
| Correlation with primary signal | < 0.30 | Orthogonality = RL diversity value |
| IC positive in ≥ years | 60% of in-sample years | Consistency, not noise |

Note: a signal that "fails" to improve a combined XGBoost model may still be RL-valuable.
XGBoost handles sparse signals poorly. An RL agent can selectively attend to signals.

## Start Here

- `notes/next_steps.md`: live system state, current priorities, session history
- `notes/signal_library.md`: **the registry of confirmed and candidate signals**
- `README_for_AGENTS.md`: exact agent loop, commands, result artifacts, data, note conventions
- `notes/findings.md`: index for the chunked durable findings files
- if you are continuing the active timing-research branch, then read:
  - `notes/timing_data_acquisition_plan.md`
  - `notes/timing_data_source_scorecard.csv`

`README.md` is an overview. The live source of truth is `notes/next_steps.md`.

## Data Contract

- Run research scripts from inside `alpha-research-lab/`
- Canonical data lives in the workspace root at `../data/`
- Lab scripts now resolve the workspace-root `data/` directory directly; a repo-local `data/` symlink is optional compatibility only
- Artifact outputs are anchored to `alpha-research-lab/artifacts/` regardless of launch directory
- No research data is duplicated inside `alpha-research-lab/`
- The lab publishes the consolidated RL feature surface at `data/features/xs_rl_signal_matrix.parquet`
- The lab publishes the shared execution tradability artifact at `data/features/execution/tradability_daily.parquet`
- The lab publishes the date-level activation surface at `data/features/activation_state_daily.parquet`
- The lab publishes the selector-efficacy activation-meta surface at `data/features/activation_meta_daily.parquet`
- The lab now also publishes the ticker-day corporate-event surface at `data/features/event_surface_daily.parquet`
- The lab can publish canonical recommendation candidate tables at `data/features/recommendations/<profile>/latest_candidates.parquet`
- The lab can publish stock-specific entry-alpha research artifacts under `data/features/entry_alpha/`
- RL consumes that matrix through `../RL-trading-agent` via `python -m vn_stock_rl.data_tools.export_lab_signal_matrix`
- Recommendation contracts are shared with RL-adjacent consumers via `../shared-recommendation/`
- Execution reality is shared with RL via `../docs/execution_reality.md` and `../shared-market-rules/`

## Current Best RL Signal

**H93 — Volume + 1-day label cross-sectional model**

- IC +0.1491, edge std 1.60%, Sharpe 15.08, 11/11 positive years (2015–2025)
- Lowest year-to-year variance of any system tested
- Artifact: `data/features/xs_barrier_vol_1d_hose_full.parquet`

## Current Best Uncapped Long-Only Selector Baseline

**`full_library + k5_r5_eq` (H138/H139 corrected engine, no ADV cap)**

- top-5 equal-weight
- rebalance every 5 signal days
- `+769.71%` total on the honest `2019-2025` holdout
- `+346.40%` relative vs VNINDEX
- not yet retail-deployable under the explicit capacity/tradability gate

## Current Best Uncapped Long-Only System

**`full_library + k5_r5_eq + h175__rel2_gt0 + sticky_bonus_0p015 + impl__blocked5_q80 + sector_cap_3`**

- same top-5 equal-weight selector baseline
- activation overlay from smoothed recent selector efficacy
- incumbent retention bonus at rebalance
- implementation-pain veto on slower blocked-buy pressure
- mild sector cap (`max 3 names / sector`)
- `+597.09%` relative vs VNINDEX on the honest `2019-2025` holdout
- information ratio `1.01`
- avg daily turnover `0.2036`

This is still the strongest **historical** system.
It is no longer the active live branch after Session 65's pseudo-live rollback test.

## Current Active Live Branch

**`full_library + k5_r5_eq + h175__rel2_gt0 + sticky_bonus_0p015`**

- Session 65 validated that the complex `blocked5 + sector_cap_3` winner is reproducible
- but `H193` rejected it on the expanding-train / next-year pseudo-live ladder
- the sticky branch beat all blocked-buy variants on mean relative return and mean IR over `2023-2025`
- current live overlay state from the `2026-03-30` signal / `2026-03-31` execution:
  - `OFF`
  - holdings: none
  - cash: `100.00%`
- current `2026` YTD scoreboard:
  - activated sticky: `+3.28%` relative vs VNINDEX
  - sticky always-on: `-12.71%` relative

## Current Active Branch

- Keep the deterministic paper trade / live scoreboard running on the frozen sticky branch:
  - `full_library + k5_r5_eq + h175__rel2_gt0 + sticky_bonus_0p015`
- Treat ADV / capacity as parked for the current-account branch, not solved
- Explicitly split the problem into three layers:
  - selection alpha = choose the right names
  - activation alpha = decide when the selector should be on
  - exit alpha = decide when to stop holding a bought name after entry
- Run the repo in two tracks:
  - live track: freeze the sticky branch and monitor it forward only
  - research track: reopen alpha discovery under the locked protocol
    - dev `2015-2022`
    - validation `2023-2024`

## Parked Entry-Alpha Branch

This is a parked architecture branch, not the active research priority.

Thesis:
- keep selection alpha as the cross-sectional prior
- reinterpret activation alpha as a soft exposure prior, not a hard global veto
- add stock-specific entry alpha so portfolio breadth can vary from `0..K`

Current status:
- Sessions 75-77 executed `H238-H246` offline
- strongest structural results were `H239` sparse breadth and the `H245` small-book contract audit
- `H245` says the branch behaves more like a historical `top1` contract than a `top5` timing overlay
- `H246` says local confirmation overlays do not rescue that contract:
  - top1 overlays are effectively a no-op
  - top2 soft-consensus overlays overfit validation badly
- no rule, model, soft-prior overlay, audited `top_k` contract, or local confirmation overlay is promotable
- classify the branch as offline evidence, not a live replacement candidate

Canonical offline artifacts:
- `data/features/entry_alpha/candidate_panel_daily.parquet`
- `data/features/entry_alpha/entry_labels_cycle5.parquet`
- `data/features/entry_alpha/entry_scores_daily.parquet`

If intentionally reopened:
- start from `notes/session_75_log.md`, `notes/session_76_log.md`, `notes/session_77_log.md`, and `notes/next_steps.md`
- next honest continuation is `H247`: keep the branch small-book but stop testing more local overlays on the current label; sharpen the label / target for the compact entry-model branch instead
- keep it lower priority than the active timing-data acquisition branch
    - one-shot confirmation `2025`
    - forward lockbox `2026+`
- Session 57 tested deterministic binary activation (`H157-H162`) and did **not** beat the always-on `full_library + k5_r5_eq` selector
- Session 58 tested materially different activation designs (`H163-H174`) and found the first real winner:
  - `H170` smoothed recent selector efficacy
  - `recentsm__rel3_gt0` on `full_library + k5_r5_eq`
  - `+841.14%` total
  - `+383.07%` relative vs VNINDEX
  - IR `0.84`
- Session 59 then robustified that family (`H175-H177`) and found a stronger fixed rule:
  - `H175` `h175__rel2_gt0`
  - `+1052.77%` total
  - `+491.69%` relative vs VNINDEX
  - IR `0.93`
  - max DD `-20.57%`
- Session 60 then completed the direct follow-up queue (`H178-H180`):
  - `H178`: `h175__rel2_gt0` beat always-on in `15 / 16` start-year / fee stress scenarios
  - `H179`: the live-paper activation overlay runner now exists
  - `H180`: small local guards did not beat the plain champion
- Session 62 then completed the live-refresh and local-refinement wave (`H181-H186`):
  - `H181`: current-date `full_library` matrix and activation surfaces rebuilt through `2026-03-27`
  - `H182`: live overlay rerun on current data; latest sticky book is `ANV`, `PGV`, `PTB`, `PTL`, `VSI`
  - `H183`: activated book beats always-on in `2026` YTD so far, though both trail VNINDEX
  - `H184`: sticky holdings / displacement margin improved the champion
  - `H185`: sector cap `3` helped slightly but did not beat the sticky champion
  - `H186`: local exposure sizing around `rel2_gt0` failed
- Session 63 then completed the next local refinement wave (`H187-H189`) and reran the live branch on the new winner:
  - `H187`: sticky + sector cap did not stack
  - `H188`: implementation-pain veto `blocked3<=q80` improved the champion again
  - `H189`: basket-coherence / score-dispersion guards failed
  - current live overlay state on the new champion is `OFF / cash`
  - current-year activated-vs-always-on scoreboard is positive for the new champion because it is staying out
- Session 64 then followed through on that winner:
  - `H190`: `sector_cap_3` finally became additive once paired with the stronger `blocked5<=q80` veto family
  - `H191`: the blocked-buy veto family improved again from `blocked3<=q80` to `blocked5<=q80`
  - current live overlay state on the final winner remains `OFF / cash`
- Session 65 then resolved the defense-vs-overfit fork:
  - `H192A`: parity passed; the complex historical winner is reproducible
  - `H192B`: recent live state on the complex winner was mixed, not trivially all-cash
  - `H193`: pseudo-live ladder rejected the complex winner and rolled the active live branch back to sticky
- Session 66 then reopened offline alpha discovery without changing the live branch:
  - `H151`: the H150-derived narrow composites did **not** beat the always-on `full_library` selector baseline
  - `H152`: four new tradability-conditioned signals passed the dev standalone gate inside `liq_open_basic`, but none showed naive always-on selector relevance
- Session 67 then resolved the first additive ladder cleanly:
  - `H196`: the `H152` atoms did **not** survive the locked additive promotion gate on top of `full_library`
  - `H197/H198`: skipped by rule because `H196` produced no promoted atoms
  - `H199`: second-wave search found one worth-carrying atom:
    - `h199_sector_laggard_gap_absorb`
- Session 68 then advanced that one promoted H199 atom:
  - `H200`: additive bakeoff passed
  - `H201`: state-scoped additive blend passed
  - `H202`: sticky-activation compatibility failed
  - current offline lead selector:
    - `state_blend__h199_sector_laggard_gap_absorb__30`
- Session 69 then resolved the next selector extension cleanly:
  - `H203`: pairwise additive bakeoff passed in always-on form
  - `H205`: state-scoped pairwise extension failed
  - `H204`: fresh-family tradability search found no promoted atom
- Session 70 then resolved the first exit-alpha ladder cleanly:
  - `H207`: rank-decay exits beat the always-on selector baseline
  - `H211`: strength-exhaustion exits beat the H207 anchor in always-on form
  - `H212`: replacement-pressure exits failed
  - `H213`: the H211 exit winner failed frozen sticky-activation compatibility
- Session 71 then tested genuinely new exit families:
  - `H214`: thesis inconsistency failed
  - `H215`: failed follow-through was a near-miss but did not clear the locked gate
  - `H216`: time-under-water failed badly on confirmation
  - `H217`: skipped because no new family displaced H211
- Session 72 then changed the exit target itself:
  - `H218`: continuation / hold-vs-exit model failed at the first predictive gate
  - `H219`: skipped because H218 produced no promoted continuation model
  - `H220`: skipped because H219 produced no promoted continuation-band winner
- Session 73 then completed the first genuinely new-data exit ladder:
  - `H221`: built `data/features/event_surface_daily.parquet` with held-row coverage `89.59%`
  - `H222`: corporate-event predictive screening failed
  - `H223/H224`: skipped because H222 produced no promoted event model
  - `H225`: intraday / auction structure failed the local coverage gate (`0.00%`, only `FPT` 1H exists)
  - `H226-H228`: skipped by rule
  - `H229`: order-book / queue feasibility failed locally; no historical queue/depth archive exists under `data/`
- Session 74 then codified the acquisition-first follow-up:
  - timing research now starts from `notes/timing_data_acquisition_plan.md`
  - acquisition order is:
    - multi-ticker intraday / auction source
    - richer company-event source
    - otherwise stop timing research and wait for new data or more forward live evidence
- Active next branch is now dual-track:
  - live track:
    - keep the live forward scoreboard running on the rollback sticky branch
    - if sticky keeps beating sticky always-on forward, monitor only
    - if sticky falls behind sticky always-on for `>= 2` completed cycles, rerun parity first and then choose between reopening `H194/H195` or abandoning local activation tuning
  - research track:
    - keep `state_blend__h199_sector_laggard_gap_absorb__30` as the offline lead selector
    - keep `strength_exhaustion__return_since_entry_threshold_0p15__score_drop_threshold_0p05` as offline-only exit evidence
    - do not replace the live sticky branch from that result alone
    - the current selector-discovery ladder is exhausted
    - the current exit ladder is also exhausted
    - do not reopen:
      - H199 pairwise recombinations
      - H204 atom recombinations
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
- RL remains exploratory only

## Parked Historical Execution Benchmark

**H54 — Full HOSE Rank Portfolio**

- +25.52% avg edge, Sharpe 9.17, 11/11 positive years
- parked: deployment gap (real fills unverified, net P&L borderline at 0.30% RT)
- artifact: `data/features/xs_barrier_all_probas_hose_full.parquet`

See `notes/next_steps.md` for the live champion, honest benchmark, and next priorities.

## Setup

```bash
conda env create -f environment.yml
conda activate stocks
python setup_data.py
```

All commands above are intended to be run from `alpha-research-lab/`.
The environment also installs the workspace-shared `shared-market-rules` package.
It also installs the workspace-shared `shared-recommendation` package used for candidate generation and artifact resolution.

## Main Experiment Modes

- `run_experiment.py`: quick one-shot screen on a fixed split. Cheap, not authoritative.
- `walk_forward.py`: default for new FPT-only hypotheses.
- `cross_sectional_wf.py`: default for market-wide hypotheses.
- `ensemble_wf.py`: combine saved FPT probability streams.
- `analysis/*.py`: portfolio, ranking, filter, and meta-analysis scripts on saved outputs.
- `analysis/h135_signal_library_portfolio_baseline.py`: realistic deterministic portfolio baseline for `S1`, `recent_core`, and `full_library`
- `analysis/h136_portfolio_construction_sweep.py`: realistic construction sweep for the corrected `full_library` blend
- `analysis/h137_nested_portfolio_selection.py`: honest walk-forward selector over the H136 construction menu
- `analysis/h138_fixed_menu_validation.py`: honest holdout validation for a tiny fixed menu of simple constructions
- `analysis/h139_fixed_menu_capacity_fee_stress.py`: capacity and fee stress for the fixed-menu long-only candidates
- `analysis/h140_retail_capacity_aware_validation.py`: retail-sized deployability grid over the fixed-menu candidates
- `analysis/h141_capacity_aware_construction_sweep.py`: tiny construction sweep inside any H140-viable liquidity region
- `analysis/h142_live_candidate_blotter.py`: execution-facing blotter export for the current capacity-aware candidate
- `analysis/h143_liquidity_aware_scoring.py`: soft tradability-aware score variants for the long-only retail branch
- `analysis/h144_entry_slicing_simulation.py`: pending multi-day buy plans under the existing long-only settlement rule
- `analysis/h145_volume_confirmed_entry_filter.py`: liquidity-opening / volume-confirmed entry gates for long-only construction
- `analysis/h146_variable_breadth_portfolio.py`: variable-breadth long-only sweep on the strongest score-plus-gate combination
- `analysis/h147_liquidity_state_opportunity_audit.py`: sparse-opportunity audit around the H145 near-miss
- `analysis/h148_local_liquidity_gate_refinement.py`: narrow H145-neighborhood gate refinement only
- `analysis/h149_soft_activation_score.py`: softer liquidity-opening activation scores on top of the H145 score family
- `analysis/h150_conditional_alpha_decomposition.py`: per-signal conditional IC decomposition inside tradable states
- `data_tools/build_activation_state_features.py`: dense date-level activation-state artifact for selector timing experiments
- `analysis/h157_opportunity_density_gate.py`: selector-confidence activation gates on top of the frozen long-only selector
- `analysis/h158_tradability_breadth_gate.py`: buyability / liquidity-breadth activation gates
- `analysis/h159_market_regime_gate.py`: benchmark / macro regime activation gates
- `analysis/h160_breadth_dispersion_gate.py`: cross-sectional breadth / dispersion activation gates
- `analysis/h161_recent_efficacy_cooldown_gate.py`: recent-selector-efficacy cooldown gates
- `analysis/h162_composite_activation_score.py`: interpretable composite activation score
- `data_tools/build_activation_meta_features.py`: selector-efficacy activation-meta artifact with forward cycle labels and recent selector-path features
- `analysis/h163_partial_exposure_sizing.py`: 0/50/100 exposure sizing overlays
- `analysis/h164_opportunity_concentration_gate.py`: score-shape / concentration activation gates
- `analysis/h165_selector_agreement_gate.py`: selector agreement / disagreement activation gates
- `analysis/h166_tradability_acceleration_gate.py`: tradability acceleration activation gates
- `analysis/h167_selector_fragility_gate.py`: recent implementation-pain activation gates
- `analysis/h168_interaction_regime_gate.py`: interaction-only regime gates
- `analysis/h169_breadth_collapse_gate.py`: breadth-collapse risk-off gates
- `analysis/h170_smoothed_recent_efficacy_gate.py`: smoothed selector-efficacy activation gates
- `analysis/h171_selector_drawdown_phase_gate.py`: selector drawdown-phase activation gates
- `analysis/h172_entry_window_quality_gate.py`: entry-window quality activation gates
- `analysis/h173_selector_specific_activation.py`: selector-specific vs global activation comparison
- `analysis/h174_hysteresis_activation.py`: streak / hysteresis activation schedules
- `analysis/h175_h170_robustness.py`: threshold/window sweeps and yearly walk-forward calibration around the H170 family
- `analysis/h176_h170_three_state_sizing.py`: 3-state exposure sizing on top of smoothed selector efficacy
- `analysis/h177_activation_meta_model.py`: compact walk-forward logistic activation model
- `analysis/h178_h175_robustness_stress.py`: honest start-year / fee stress for the fixed activation champion
- `analysis/h179_live_activation_overlay.py`: execution-facing live/paper overlay runner for the activation champion
- `analysis/h180_h175_small_augmentations.py`: constrained local guard sweep around `rel2_gt0`
- `analysis/h192a_champion_parity_audit.py`: parity check between archived champion reference, direct runner, live overlay, and live scoreboard
- `analysis/h192b_forward_monitor_diagnostic.py`: recent-window live-state occupancy and offense/defense classification for the current activation branch
- `analysis/h193_pseudo_live_robustness_ladder.py`: expanding-train / next-year ladder for sticky and blocked-buy activation variants
- `analysis/h194_blocked_buy_sector_recalibration.py`: blocked-buy + sector-cap recalibration family, only if the blocked-buy branch is intentionally reopened
- `analysis/h195_blocked_buy_hysteresis.py`: blocked-buy hysteresis family, only if the blocked-buy branch is intentionally reopened
- `analysis/h151_tradability_conditioned_composite_bakeoff.py`: locked-protocol bakeoff for the H150-derived narrow sub-core composites
- `analysis/h152_tradability_conditioned_signal_search.py`: locked-protocol tradable-state signal search with standalone gates plus naive selector relevance
- `analysis/h196_additive_atom_bakeoff.py`: one-atom additive selector bakeoff for the strongest `H152` atoms on top of `full_library`
- `analysis/h197_state_scoped_additive_bakeoff.py`: state-scoped additive selector bakeoff, only if `H196` promotes atoms
- `analysis/h198_selector_activation_compatibility.py`: sticky-activation compatibility test for a promoted additive selector winner
- `analysis/h199_second_wave_tradability_conditioned_search.py`: second-wave tradability-transition signal search after the first additive path fails
- `analysis/h200_additive_h199_atom_bakeoff.py`: additive selector bakeoff for the promoted H199 atom(s) on top of `full_library`
- `analysis/h201_state_scoped_h199_atom_bakeoff.py`: state-scoped selector bakeoff for promoted H200 atom(s)
- `analysis/h202_h199_selector_activation_compatibility.py`: sticky-activation compatibility test for the promoted H201 selector winner
- `analysis/h203_pairwise_additive_bakeoff.py`: always-on pairwise additive selector bakeoff around the H201 winner
- `analysis/h204_third_wave_tradability_conditioned_search.py`: fresh-family tradability-conditioned signal search after the H203/H205 pair branch dies
- `analysis/h205_state_scoped_pairwise_bakeoff.py`: state-scoped pairwise selector bakeoff for promoted H203 pair candidates
- `analysis/h206_pair_selector_activation_compatibility.py`: sticky-activation compatibility test for a promoted H205 pair-selector winner
- `analysis/h238_entry_alpha_candidate_panel.py`: candidate-panel and cycle-label artifact builder for the stock-specific entry-alpha branch
- `analysis/h239_entry_alpha_sparse_breadth_baseline.py`: sparse-breadth threshold baseline for the stock-specific entry-alpha branch
- `analysis/h240_entry_alpha_single_family_screens.py`: simple implementation-context and price-state entry-screen sweep for the stock-specific entry-alpha branch
- `analysis/h241_entry_alpha_compact_model.py`: compact candidate-level logistic entry model and thresholded portfolio evaluation
- `analysis/h242_entry_alpha_soft_exposure_prior.py`: soft exposure-prior integration that reuses activation alpha as threshold, breadth, or weight modulation
- `analysis/h243_entry_alpha_live_compatibility.py`: pseudo-live compatibility audit against the frozen sticky live branch
- `analysis/h244_entry_alpha_sparse_breadth_protocol.py`: honest dev/validation/confirmation/forward protocol for the H239 sparse-breadth branch
- `analysis/h245_entry_alpha_topk_contract_audit.py`: contract audit for whether the entry-alpha branch really wants `top1/top2` sparse books instead of `top5` timing overlays
- `analysis/h246_entry_alpha_small_book_confirmation.py`: light confirmation / calibration overlays on top of the H245 small-book contracts

## Live Paper-Trade Prerequisite

Live `full_library` paper trades require intact long-history raw stock files.

- recent-window refreshes can overwrite local parquet files with only the requested date window
- that can leave `data/stock/` historically inconsistent and break live feature generation
- before any live recommendation, verify long-history continuity across the active universe and `VNINDEX`
- current-date refresh now runs through:
  - `data_tools/build_s1_live_extension.py`
  - `data_tools/build_rl_signal_matrix.py`
  - `data_tools/build_activation_state_features.py`
  - `data_tools/build_activation_meta_features.py`

## Shared Live Recommendation Export

The lab now has a canonical recommendation export path built on the shared recommendation engine.

Use:

```bash
cd /home/manh/stocks/alpha-research-lab
python analysis/live_recommendation.py --strategy full_library --profile-name alpha_full_library_live
```

This reads:

- `data/features/xs_rl_signal_matrix.parquet`
- `data/features/execution/tradability_daily.parquet`
- `artifacts/run_summaries/latest_portfolio_live_activation_overlay.json` by default for the sticky live overlay gate

And writes:

- `data/features/recommendations/<profile>/latest_candidates.parquet`
- `data/features/recommendations/<profile>/manifest.json`
- `artifacts/run_summaries/latest_recommendation_candidates_<profile>.json`

The shared candidate table is inference-only. Training, selector discovery, and portfolio backtests remain owned by the existing lab scripts.

## Saved Result Artifacts

Main experiment runners write compact JSON summaries to `artifacts/run_summaries/`.
These artifact paths are repo-anchored, so running a lab script from the workspace root should still write into `alpha-research-lab/artifacts/`.

- One-shot: `latest_one_shot.json`
- Walk-forward: `latest_walk_forward.json`
- Cross-sectional: `latest_cross_sectional.json`
- Ensemble: `latest_ensemble.json`
- Portfolio: `latest_portfolio.json`
- Portfolio baseline: `latest_portfolio_baseline.json`
- Portfolio construction sweep: `latest_portfolio_construction_sweep.json`
- Portfolio nested selection: `latest_portfolio_nested_selection.json`
- Portfolio fixed-menu validation: `latest_portfolio_fixed_menu_validation.json`
- Portfolio capacity / fee stress: `latest_portfolio_capacity_fee_stress.json`
- Portfolio retail validation: `latest_portfolio_retail_validation.json`
- Portfolio capacity-aware sweep: `latest_portfolio_capacity_aware_sweep.json`
- Portfolio live candidate blotter: `latest_portfolio_live_candidate_blotter.json`
- Portfolio liquidity-aware scoring: `latest_portfolio_liquidity_aware_scoring.json`
- Portfolio entry slicing simulation: `latest_portfolio_entry_slicing_simulation.json`
- Portfolio volume-confirmed entry filter: `latest_portfolio_volume_confirmed_entry_filter.json`
- Portfolio variable breadth: `latest_portfolio_variable_breadth.json`
- Portfolio liquidity-state opportunity audit: `latest_portfolio_liquidity_state_opportunity_audit.json`
- Portfolio local liquidity-gate refinement: `latest_portfolio_local_liquidity_gate_refinement.json`
- Portfolio soft activation score: `latest_portfolio_soft_activation_score.json`
- Portfolio conditional alpha decomposition: `latest_portfolio_conditional_alpha_decomposition.json`
- Portfolio activation opportunity density: `latest_portfolio_activation_opportunity_density.json`
- Portfolio activation tradability breadth: `latest_portfolio_activation_tradability_breadth.json`
- Portfolio activation market regime: `latest_portfolio_activation_market_regime.json`
- Portfolio activation breadth / dispersion: `latest_portfolio_activation_breadth_dispersion.json`
- Portfolio activation recent efficacy: `latest_portfolio_activation_recent_efficacy.json`
- Portfolio activation composite: `latest_portfolio_activation_composite.json`
- Portfolio activation partial exposure: `latest_portfolio_activation_partial_exposure.json`
- Portfolio activation opportunity concentration: `latest_portfolio_activation_opportunity_concentration.json`
- Portfolio activation selector agreement: `latest_portfolio_activation_selector_agreement.json`
- Portfolio activation tradability acceleration: `latest_portfolio_activation_tradability_acceleration.json`
- Portfolio activation selector fragility: `latest_portfolio_activation_selector_fragility.json`
- Portfolio activation interaction regime: `latest_portfolio_activation_interaction_regime.json`
- Portfolio activation breadth collapse: `latest_portfolio_activation_breadth_collapse.json`
- Portfolio activation smoothed recent efficacy: `latest_portfolio_activation_smoothed_recent_efficacy.json`
- Portfolio activation drawdown phase: `latest_portfolio_activation_drawdown_phase.json`
- Portfolio activation entry-window quality: `latest_portfolio_activation_entry_window_quality.json`
- Portfolio activation selector-specific: `latest_portfolio_activation_selector_specific.json`
- Portfolio activation hysteresis: `latest_portfolio_activation_hysteresis.json`
- Portfolio activation H170 robustness: `latest_portfolio_activation_h170_robustness.json`
- Portfolio activation H170 three-state sizing: `latest_portfolio_activation_h170_three_state_sizing.json`
- Portfolio activation meta-model: `latest_portfolio_activation_meta_model.json`
- Portfolio activation H175 robustness stress: `latest_portfolio_activation_h175_robustness_stress.json`
- Portfolio live activation overlay: `latest_portfolio_live_activation_overlay.json`
- Recommendation candidates by profile: `latest_recommendation_candidates_<profile>.json`
- Portfolio activation H175 small augmentations: `latest_portfolio_activation_h175_small_augmentations.json`
- Portfolio live activation scoreboard: `latest_portfolio_live_activation_scoreboard.json`

Large daily portfolio baseline outputs are written under `artifacts/portfolio_baselines/`.

Permanent logs remain:

- `results_summary.jsonl` for one-shot screens
- `wf_results.jsonl` for walk-forward runs
- `xs_wf_results.jsonl` for cross-sectional and ensemble runs

## Repo Structure

```text
.
├── README.md
├── README_for_AGENTS.md
├── walk_forward.py
├── cross_sectional_wf.py
├── ensemble_wf.py
├── run_experiment.py
├── src/
├── configs/
├── analysis/
├── data_tools/
├── notes/
│   ├── signal_library.md      ← signal registry (primary output)
│   ├── findings.md            ← index for chunked scientific truth
│   ├── findings-001-030.md    ← chunked durable conclusions
│   ├── findings-031-060.md    ← chunked durable conclusions
│   ├── findings-061-090.md    ← chunked durable conclusions
│   ├── findings-091-120.md    ← chunked durable conclusions
│   ├── next_steps.md          ← live state & queue
│   └── session_NN_log.md      ← per-session records
├── experiments/
├── artifacts/run_summaries/
├── wf_results.jsonl
├── xs_wf_results.jsonl
└── results_summary.jsonl
```

## Notes Policy

The repo treats `notes/` as a permanent scientific record:

- Session logs are the detailed record
- `findings.md` is the index for the durable truth layer
- `findings-*.md` are the chunked durable truth files
- `signal_library.md` is the signal registry — the primary deliverable
- `next_steps.md` is the active queue
- Failed ideas stay documented instead of being erased

See `README_for_AGENTS.md` for the working convention and agent protocol.
