# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Workspace Overview

This is a unified Vietnamese stock trading ecosystem with three interdependent sub-projects sharing a canonical data root at `/home/manh/stocks/data/`. Changes across producer/consumer boundaries must be coordinated.

- **`alpha-research-lab/`** — Research producer: generates signals, labels, and features
- **`RL-trading-agent/`** — RL consumer: trains and evaluates trading agents using published features
- **`manual-label-factory/`** — Manual labeling UI: writes buy-zone labels consumed by the research pipelines
- **`data/`** — Canonical shared data root (never duplicate locally)

`alpha-research-lab/data` is a symlink to the root `data/` directory.

## Key Documentation

Read these before making significant changes:

- `AGENTS.md` — Root coordination: path conventions, cross-repo change map
- `alpha-research-lab/README_for_AGENTS.md` — Detailed research workflows, config schema, artifact locations
- `alpha-research-lab/notes/signal_library.md` — Registry of confirmed/candidate/rejected signals (primary research deliverable)
- `RL-trading-agent/AGENTS.md` — RL repo-specific conventions
- `RL-trading-agent/docs/pipeline_contracts.md` — Producer/consumer input/output contracts

## Commands

### Alpha Research Lab

```bash
cd alpha-research-lab
conda activate stocks

# Data refresh
python data_tools/fetch_stock.py
python data_tools/fetch_fx_commodities.py
python data_tools/fetch_fundamentals.py

# Experiment modes (use smallest valid mode)
python run_experiment.py --config configs/E32_barrier_1pct.json        # quick one-shot (not authoritative)
python walk_forward.py --config configs/E32_barrier_1pct.json          # single-stock WF (FPT hypotheses)
python cross_sectional_wf.py --barrier-pct 0.01 --threshold 0.05 \    # market-wide WF (generalization)
  --save-all-probas data/features/xs_barrier_all_probas.parquet
python ensemble_wf.py                                                   # model blending
python analysis/h40_rank_portfolio.py \                                 # portfolio analysis
  --probas data/features/xs_barrier_all_probas_hose_full.parquet --no-vix-filter

# Research pipelines (produces features for RL)
python -m research_pipelines.news_features
python -m research_pipelines.supervised_label.core.rebuild_bar_labels
python -m research_pipelines.supervised_label.models.generate_signal_probs
```

### RL Trading Agent

```bash
cd RL-trading-agent
conda activate stocks
pip install -e ".[dev]"

# Tests
python -m pytest
python -m pytest tests/test_specific.py  # single test file

# Inspect research exports
python -m vn_stock_rl.data_tools.inspect_research_exports
python -m vn_stock_rl.data_tools.inspect_research_exports --require-news --require-signal

# Train
vn-stock-train --stock FPT --policy cnn --start-date 2016-01-01 --timesteps 1000000 \
  --ent-coef-start 0.08 --ent-coef-end 0.005 --ent-coef-schedule linear \
  --train-episode-sampling --benchmark-relative-reward --name my_run

# Evaluate
vn-stock-evaluate --model artifacts/trained_models/my_run/model_best.zip --stock FPT --mode val
```

### Manual Label Factory

```bash
cd manual-label-factory
python -m manual_label_factory.manual_label
```

## Architecture

### Data Flow

```
Raw Sources → data_tools/fetch_*.py → data/stock/, data/fx-commodities/, data/news/
Manual Labels → manual-label-factory → data/labels/supervised/
Research Pipelines (alpha-research-lab) → data/features/
  ├── news/predictions/<TICKER>_news_features.parquet
  └── signals/predictions/auto/<TICKER>_signal_predictions.parquet
RL env (RL-trading-agent) ← reads all of the above via external_features.py
```

### RL Environment

The base environment (`RL-trading-agent/vn_stock_rl/env/base.py`) merges data in sequence:
1. OHLCV from `data/stock/*.parquet`
2. Helper assets (VIX, FX, indices) from `data/fx-commodities/`
3. Optional news features (`--use-news`)
4. Optional signal predictions (`--use-signal`)

Feature merging contracts are defined in `vn_stock_rl/external_features.py`. Default data paths are relative to `data/` and can be overridden via `--data-root` or `STOCKS_DATA_ROOT` env var.

Policy architectures are registered in `vn_stock_rl/policies/registry.py`. Available policies: `cnn`, `mlp`, `transformer`, etc.

### Research Experiment Artifacts

- `artifacts/run_summaries/latest_*.json` — read first for quick metrics
- `results_summary.jsonl`, `wf_results.jsonl`, `xs_wf_results.jsonl` — permanent append-only logs
- `experiments/<timestamp>/metrics.json` — per-experiment detail
- Never delete failed experiments; the record is append-only.

### Signal Evaluation Gate

A signal qualifies for promotion when:
- Standalone IC > 0.01
- Rank correlation with primary signal (S1/H93) < 0.30
- IC positive in ≥ 60% of years
- p-value < 0.10

### Current Champion Signal

**H93** — Cross-Sectional Relative Momentum with volume filter and 1-day barrier label:
- IC: +0.1491, Sharpe: 15.08, positive in 11/11 years
- Output: `data/features/xs_barrier_vol_1d_hose_full.parquet`

## Environment Setup

Both `alpha-research-lab` and `RL-trading-agent` use the same conda environment (`stocks`, Python 3.10). The RL agent requires `pip install -e ".[dev]"` from the `RL-trading-agent/` directory.
