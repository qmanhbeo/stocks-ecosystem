# Repo Map

Use this file to find the right area quickly before opening code.

## Top Level

- `vn_stock_rl/`: core RL runtime package
- shared `/home/manh/stocks/data`: durable datasets and generated features
- `artifacts/`: runtime outputs, trained models, evaluation outputs
- `docs/`: focused reference docs
- `tests/`: repo-wide tests

## Fast Lookup

If you want to change RL training flags:
- `vn_stock_rl/training/args.py`
- `vn_stock_rl/training/runner.py`

If you want to change RL evaluation flags:
- `vn_stock_rl/evaluation/args.py`
- `vn_stock_rl/evaluation/runner.py`

If you want to change env observation inputs, feature merging, or defaults:
- `vn_stock_rl/env/base.py`
- `vn_stock_rl/env/single_stock.py`
- `vn_stock_rl/env/multi_stock.py`

If you want to change policy/extractor selection:
- `vn_stock_rl/policies/registry.py`
- `vn_stock_rl/policies/extractors/`

If you want to change repo-wide CLI parsing helpers:
- `vn_stock_rl/config/cli_shared.py`

If you want to change research-export defaults or merge behavior:
- `vn_stock_rl/external_features.py`
- `vn_stock_rl/config/cli_shared.py`
- `vn_stock_rl/env/base.py`

If you want to change where data and artifacts live:
- `vn_stock_rl/external_features.py`
- `vn_stock_rl/config/types.py`

## Canonical Runtime Surface

Use these entrypoints first:

- `vn-stock-train`
- `vn-stock-evaluate`
- `vn-stock-count-params`
- `python -m vn_stock_rl.data_tools.inspect_research_exports`
- `python -m vn_stock_rl.data_tools.export_lab_signal_matrix`

## Storage Rules

- `/home/manh/stocks/data` = durable inputs, labels, features, predictions
- `artifacts/` = trained models, logs, evaluation results, labeling sessions
- producer pipelines live outside this repo

## Current Signal Default

RL uses shared `data/features/signals/predictions/auto/` by default when signal features are enabled and `--signal-prediction-dir` is omitted.

The consolidated lab matrix at `data/features/xs_rl_signal_matrix.parquet` is adapted into that per-ticker contract through `python -m vn_stock_rl.data_tools.export_lab_signal_matrix`.
