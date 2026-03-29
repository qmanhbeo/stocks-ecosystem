# Agent Workflow

This repo is designed to support one repeatable loop:

1. Form a hypothesis.
2. Pick the smallest valid experiment mode.
3. Run it.
4. Read the saved summary artifact instead of re-parsing terminal output.
5. Write session-level conclusions.
6. Promote durable conclusions into the chunked permanent findings files.
7. Update `notes/signal_library.md` if the signal is confirmed or promoted.

Execution reality is shared at the workspace level:

- canonical spec: `../docs/execution_reality.md`
- shared rule code: `../shared-market-rules/shared_market_rules/`
- produced tradability artifact: `data/features/execution/tradability_daily.parquet`

`notes/next_steps.md` is the live small-brain state source. This file is the working manual.

## Hard Rule

This lab is permanently long-only.

- no synthetic hedges
- no stock shorting assumptions
- no benchmark-hedged or long-short research branches
- if a strategy cannot plausibly make money as a real long-only Vietnam strategy, it is not a valid direction here

Do not suggest synthetic hedge diagnostics as a fallback. If long-only fails, document that plainly and search for a better long-only construction instead.

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
- the active next branch is benchmark-first long-only portfolio-choice RL
- `H151/H152` are parked research hypotheses; the live queue is `H153/H154/H155`

Do not maintain a partial summary table here unless you update it together with `notes/signal_library.md`.

---

## Start Here

Read in this order:

1. `README.md`
2. `notes/next_steps.md`
3. `notes/signal_library.md`
4. `notes/findings.md` index plus the relevant `notes/findings-*.md` chunk
5. `notes/session_NN_log.md` only when you need a detailed traceback

Use this file for:

- exact commands
- experiment mode selection
- result artifact locations
- session log conventions
- data inventory → see `notes/data_sources.md`

---

## Canonical Sources

- `notes/next_steps.md`: live champion, current priorities, session status
- `notes/signal_library.md`: **signal registry — primary deliverable**
- `notes/findings.md`: index for durable scientific truth
- `notes/findings-*.md`: chunked durable scientific truth, padded to 30-block filename ranges
- `notes/data_sources.md`: **data inventory — what's in git, what's not, how to restore**
- `notes/session_NN_log.md`: full per-session record
- `notes/experiments_log.md`: legacy historical detail for earlier sessions

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
- `analysis/h147_liquidity_state_opportunity_audit.py`: `artifacts/run_summaries/latest_portfolio_liquidity_state_opportunity_audit.json` plus daily opportunity-count outputs under `artifacts/portfolio_baselines/`
- `analysis/h148_local_liquidity_gate_refinement.py`: `artifacts/run_summaries/latest_portfolio_local_liquidity_gate_refinement.json` plus local-gate refinement outputs under `artifacts/portfolio_baselines/`
- `analysis/h149_soft_activation_score.py`: `artifacts/run_summaries/latest_portfolio_soft_activation_score.json` plus soft-activation outputs under `artifacts/portfolio_baselines/`
- `analysis/h150_conditional_alpha_decomposition.py`: `artifacts/run_summaries/latest_portfolio_conditional_alpha_decomposition.json` plus conditional-IC tables under `artifacts/portfolio_baselines/`

For any new analysis script, keep the large output wherever it naturally belongs, but also write
one compact summary JSON under `artifacts/run_summaries/`.

---

## Result Is Done When

- The experiment has a compact saved summary artifact.
- The permanent output path is recorded.
- The session log states the hypothesis, result, and verdict.
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
- `notes/next_steps.md`: current queue plus session history
- `notes/session_NN_log.md`: detailed session record
- `notes/experiments_log.md`: legacy historical record

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
