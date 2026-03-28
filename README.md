# Stocks Ecosystem

Workspace root for the VN stock research and RL ecosystem.

This is no longer a set of fully self-contained repos. The projects below now operate as one shared system around a common root data store:

- `data/`: canonical shared data root
- `alpha-research-lab/`: alpha research, feature generation, auto-labelling, supervised signal pipeline
- `manual-label-factory/`: manual buy-zone labelling UI
- `RL-trading-agent/`: RL training, evaluation, and feature consumption
- `media-output/signal-xs-momentum/`: older signal-specific project kept alongside the ecosystem

## Canonical Ownership

- Raw and published research data live under `data/`
- Research producer code lives under `alpha-research-lab/`
- Manual label UI code lives under `manual-label-factory/`
- RL consumer/runtime code lives under `RL-trading-agent/`
- `alpha-research-lab/data` is a symlink back to root `data/` so lab scripts can be run from inside the lab without duplicating files

## Data Layout

Shared `data/` currently contains both raw inputs and processed research outputs, including:

- `data/stock/`
- `data/news/`
- `data/fx-commodities/`
- `data/features/`
- `data/labels/`
- `data/dividend_cache/`
- `data/fundamentals_cache/`
- `data/insider_cache/`
- `data/llm_cache/`

This means the root data directory is the canonical dataset surface for the whole ecosystem.

## Workflow

1. Research and feature generation happen in `alpha-research-lab/`
2. Manual buy-zone annotation happens in `manual-label-factory/`
3. Published artifacts are written into root `data/`
4. The lab publishes a consolidated RL signal matrix at `data/features/xs_rl_signal_matrix.parquet`
5. The lab publishes shared execution tradability flags at `data/features/execution/tradability_daily.parquet`
6. RL training/evaluation in `RL-trading-agent/` reads from root `data/`, either directly from existing per-ticker exports or via the adapter command `python -m vn_stock_rl.data_tools.export_lab_signal_matrix`

## Strategy Guardrails

This workspace is long-only by policy.

- no synthetic hedges
- no equity shorting assumptions
- no research branches that depend on unrealistic short exposure
- if a strategy cannot make money realistically as long-only in Vietnam, it is not a valid direction for this ecosystem

This rule applies to both research in `alpha-research-lab/` and any future RL runtime work in `RL-trading-agent/`.

## Bootstrap

From the workspace root, install the current shared Python stack with:

```bash
conda create -n stocks python=3.10
conda activate stocks
pip install -r requirements.txt
```

This installs the shared `shared-market-rules` package, `RL-trading-agent` in editable mode, and the extra research/UI packages used by `alpha-research-lab` and `manual-label-factory`.

For a stricter pinned install focused on reproducibility, use:

```bash
conda create -n stocks python=3.10
conda activate stocks
pip install -r requirements.lock.txt
```

Use `requirements.txt` for a live editable dev setup. Use `requirements.lock.txt` when you want the workspace dependency surface to stay fixed.
The lock file is intentionally Python-3.10-focused and pins the direct dependency surface only; it is not a full transitive hash lock.

## Shared Market Rules

Execution reality is an ecosystem-level contract, not a repo-local detail.

- Canonical spec: `docs/execution_reality.md`
- Shared rule code: `shared-market-rules/shared_market_rules/`
- Producer artifact: `data/features/execution/tradability_daily.parquet`

Current strict-core defaults:
- signal at `T` close
- fill at `T+1` open
- earliest legal sell decision after a buy at `T+1` open is `T+3` close
- earliest exit fill is `T+4` open
- zero-volume blocks both sides
- ceiling blocks buys
- floor blocks sells

## Current Reality

- `alpha-research-lab/data/` has been fully moved into root `data/`
- `RL-trading-agent` has already been cleaned up toward a consumer-only role
- The workspace behaves like one ecosystem even though code is still split across multiple git repos

## Recommended Next Step

If you want the repository structure to match reality, promote this root into the long-term ecosystem repo and treat the child repos as subprojects inside it.
