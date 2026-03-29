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

`README.md` is an overview. The live source of truth is `notes/next_steps.md`.

## Data Contract

- Run research scripts from inside `alpha-research-lab/`
- Canonical data lives in the workspace root at `../data/`
- The repo-local `data/` path is a symlink to that shared root so existing lab scripts can keep using `data/...`
- No research data is duplicated inside `alpha-research-lab/`
- The lab publishes the consolidated RL feature surface at `data/features/xs_rl_signal_matrix.parquet`
- The lab publishes the shared execution tradability artifact at `data/features/execution/tradability_daily.parquet`
- The lab publishes the date-level activation surface at `data/features/activation_state_daily.parquet`
- The lab publishes the selector-efficacy activation-meta surface at `data/features/activation_meta_daily.parquet`
- RL consumes that matrix through `../RL-trading-agent` via `python -m vn_stock_rl.data_tools.export_lab_signal_matrix`
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

**`full_library + k5_r5_eq + h175__rel2_gt0`**

- same top-5 equal-weight selector baseline
- activation overlay from smoothed recent selector efficacy
- `+1052.77%` total on the honest `2019-2025` holdout
- `+491.69%` relative vs VNINDEX
- max DD `-20.57%`

## Current Active Branch

- Keep the deterministic paper trade running on `full_library + k5_r5_eq`
- Treat ADV / capacity as parked for the current-account branch, not solved
- Explicitly split the problem into two layers:
  - selection alpha = choose the right names
  - activation alpha = decide when the selector should be on
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
  - `H179`: the live-paper activation overlay runner now exists, but the shared `full_library` matrix still ends at `2025-12-31`
  - `H180`: small local guards did not beat the plain champion
- Active next research branch is now operational rather than exploratory:
  - `H181`: rebuild the current-date `full_library` matrix and activation surfaces
  - `H182`: rerun the live-paper activation overlay on the refreshed matrix
  - `H183`: compare activated vs always-on paper books only after the overlay is current
- After the live branch is current, the next local refinement queue is:
  - `H184`: sticky holdings / displacement margin
  - `H185`: sector concentration cap
  - `H186`: local exposure control around `rel2_gt0`
- Selection-side work (`H151/H152`) remains parked behind the operational activation branch
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

## Live Paper-Trade Prerequisite

Live `full_library` paper trades require intact long-history raw stock files.

- recent-window refreshes can overwrite local parquet files with only the requested date window
- that can leave `data/stock/` historically inconsistent and break live feature generation
- before any live recommendation, verify long-history continuity across the active universe and `VNINDEX`

## Saved Result Artifacts

Main experiment runners write compact JSON summaries to `artifacts/run_summaries/`.

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
- Portfolio activation H175 small augmentations: `latest_portfolio_activation_h175_small_augmentations.json`

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
