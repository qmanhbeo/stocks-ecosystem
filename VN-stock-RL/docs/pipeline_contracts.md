# Pipeline Contracts

This file is a compact input/output map for the main pipelines.

## Shared Rules

- `/home/manh/stocks/data` stores durable datasets and generated features.
- `artifacts/` stores runtime outputs and trained models.
- Producer pipelines live outside this repo.
- Signal prediction parquet files are RL-consumable features.

## Research-Owned Producers

These workflows moved out of `VN-stock-RL`:

- stock/news/helper-data fetch and feature generation -> `alpha-signals/alpha-research-lab`
- heuristic auto labelling -> `alpha-signals/alpha-research-lab`
- supervised signal dataset/model/probability generation -> `alpha-signals/alpha-research-lab`
- manual buy-zone labelling -> `alpha-signals/manual-label-factory`

The RL repo now consumes their published outputs from shared data paths.

Key exported inputs:

- stock parquet files: `data/stock/*.parquet`
- helper assets: `data/fx-commodities/*.parquet`
- news features: `data/features/news/predictions/*_news_features.parquet`
- signal features: `data/features/signals/predictions/auto/*_signal_predictions.parquet`

## RL Training / Evaluation

Commands:
- `vn-stock-train`
- `vn-stock-evaluate`

Inputs:
- `data/stock/*.parquet`
- optional helper market files in `data/stock/` and `data/fx-commodities/`
- optional news features in `data/features/news/predictions/`
- optional signal features in `data/features/signals/predictions/auto/` by default

Outputs:
- trained runs: `artifacts/trained_models/<run_name>/`
- evaluations: `artifacts/evaluation_results/`

Signal default:
- if signal features are enabled and no explicit directory is passed, RL uses `data/features/signals/predictions/auto/`

## What To Change Together

If a file path convention changes:
- update `vn_stock_rl/external_features.py`
- update docs
- update CLI help text if a user-facing default changed

If a new signal column is added:
- update the producing research pipeline
- update `vn_stock_rl/config/cli_shared.py`
- update `vn_stock_rl/env/base.py`

If a new external feature family is added:
- update the producing pipeline
- update the env merge point
- update metadata round-tripping if evaluation should reuse it
