# Pipeline Contracts

This file is a compact input/output map for the main pipelines.

## Shared Rules

- `/home/manh/stocks/data` stores durable datasets and generated features.
- `artifacts/` stores runtime outputs and trained models.
- Producer pipelines live outside this repo.
- Signal prediction parquet files are RL-consumable features.

## Research-Owned Producers

These workflows moved out of `RL-trading-agent`:

- stock/news/helper-data fetch and feature generation -> `alpha-research-lab`
- heuristic auto labelling -> `alpha-research-lab`
- supervised signal dataset/model/probability generation -> `alpha-research-lab`
- manual buy-zone labelling -> `manual-label-factory`

The RL repo now consumes their published outputs from shared data paths.

Key exported inputs:

- stock parquet files: `data/stock/*.parquet`
- helper assets: `data/fx-commodities/*.parquet`
- news features: `data/features/news/predictions/*_news_features.parquet`
- signal features: `data/features/signals/predictions/auto/*_signal_predictions.parquet`
- consolidated lab RL matrix: `data/features/xs_rl_signal_matrix.parquet`
- adapted lab signal features: `data/features/signals/predictions/rl_lab_matrix/*_signal_predictions.parquet`
- execution tradability flags: `data/features/execution/tradability_daily.parquet`
- raw historical foreign-flow archive: `data/foreign_flow/cafef/` (not consumed by RL directly; raw source only)
- forward-only foreign-flow board snapshots: `data/foreign_flow_forward/vci_price_board/` (raw acquisition surface, not consumed by RL and not historical/backtestable yet)

## RL Training / Evaluation

Commands:
- `vn-stock-train`
- `vn-stock-evaluate`

Inputs:
- `data/stock/*.parquet`
- optional helper market files in `data/stock/` and `data/fx-commodities/`
- optional news features in `data/features/news/predictions/`
- optional signal features in `data/features/signals/predictions/auto/` by default
- optional adapted lab signal features in `data/features/signals/predictions/rl_lab_matrix/` when exported and selected explicitly

Outputs:
- trained runs: `artifacts/trained_models/<run_name>/`
- evaluations: `artifacts/evaluation_results/`

Signal default:
- if signal features are enabled and no explicit directory is passed, RL uses `data/features/signals/predictions/auto/`
- in `--portfolio-choice` mode, RL defaults to `data/features/signals/predictions/rl_lab_matrix/`
- if the consolidated lab matrix should be used, first run `python -m vn_stock_rl.data_tools.export_lab_signal_matrix` and then pass `--signal-prediction-dir data/features/signals/predictions/rl_lab_matrix/`

## What To Change Together

If a file path convention changes:
- update `vn_stock_rl/external_features.py`
- update docs
- update CLI help text if a user-facing default changed

If a new signal column is added:
- update the producing research pipeline
- if it lands in the consolidated lab matrix, rerun `python -m vn_stock_rl.data_tools.export_lab_signal_matrix`
- update `vn_stock_rl/config/cli_shared.py` only if CLI shortcuts/default bundles should change
- update `vn_stock_rl/env/base.py` only if merge semantics or fill behavior should change

If the consolidated lab matrix contract changes:
- update the research producer docs
- update `vn_stock_rl/data_tools/export_lab_signal_matrix.py`
- update this file and `README.md`

If execution/tradability rules change:
- update `../docs/execution_reality.md`
- update `../shared-market-rules/`
- update the lab producer `data_tools/build_tradability_flags.py`
- update RL env rule consumers

If a new external feature family is added:
- update the producing pipeline
- update the env merge point
- update metadata round-tripping if evaluation should reuse it

If `data/foreign_flow_forward/vci_price_board/` is promoted from raw
forward-only acquisition data into an RL feature:
- first run a source-quality audit after enough collection days exist
- build a research-owned feature artifact under `data/features/`
- update `vn_stock_rl/external_features.py` and env merge behavior only after
  that feature artifact exists

If `data/foreign_flow/cafef/` is promoted from raw historical source data into
an RL feature:
- first run a source-quality audit and align it against the trading calendar
- build a research-owned feature artifact under `data/features/`
- update `vn_stock_rl/external_features.py` and env merge behavior only after
  that feature artifact exists
