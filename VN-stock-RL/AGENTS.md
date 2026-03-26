# AGENTS.md

Repo-specific lookup notes for coding agents. Keep this short and practical.

## Start Here

Read these first when you need orientation:

- `docs/repo_map.md`
- `docs/pipeline_contracts.md`
- `README.md`

## Change Map

To change RL training flags or defaults:
- `vn_stock_rl/training/args.py`
- `vn_stock_rl/training/runner.py`
- `vn_stock_rl/config/types.py`

To change RL evaluation flags or output behavior:
- `vn_stock_rl/evaluation/args.py`
- `vn_stock_rl/evaluation/runner.py`
- `vn_stock_rl/evaluation/metadata.py`

To change env feature merging or observation composition:
- `vn_stock_rl/env/base.py`
- `vn_stock_rl/env/single_stock.py`
- `vn_stock_rl/env/multi_stock.py`

To change policy/extractor wiring:
- `vn_stock_rl/policies/registry.py`
- `vn_stock_rl/policies/extractors/`

To change external research feature defaults or merge behavior:
- `vn_stock_rl/external_features.py`
- `vn_stock_rl/config/cli_shared.py`
- `vn_stock_rl/env/base.py`

To change canonical data/artifact paths:
- `vn_stock_rl/external_features.py`
- `vn_stock_rl/config/types.py`
- `.gitignore`

## Repo Conventions

- Shared data lives in `/home/manh/stocks/data` by default.
- `artifacts/` is for trained models, logs, evaluation outputs, and labeling sessions.
- Canonical RL runtime surface is:
  - `vn-stock-train`
  - `vn-stock-evaluate`
  - `vn-stock-count-params`
- Canonical research-export inspection command is:
  - `python -m vn_stock_rl.data_tools.inspect_research_exports`

## Important Defaults

- RL defaults to shared `data/features/news/predictions/` and `data/features/signals/predictions/auto/`.
- Producer pipelines now live outside this repo in `alpha-signals/alpha-research-lab` and `alpha-signals/manual-label-factory`.

## Keep In Mind

- Prefer updating one canonical entrypoint/path, not compatibility wrappers.
- If you change a user-facing default path or command, update docs at the same time.
- If a new produced column becomes an RL feature, update both the producing pipeline and the env merge path.
