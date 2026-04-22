# RL Trading Agent

Consumer-only RL runtime for Vietnamese equity experiments.

This repo no longer owns data fetching, news feature generation, manual labelling, or supervised signal production. Those producer pipelines now live in `../alpha-research-lab` and `../manual-label-factory`.

The RL runtime reads shared research exports from `/home/manh/stocks/data` by default.
It does not consume raw CafeF source archives under `../data/foreign_flow/`,
`../data/order_stats/`, or `../data/proprietary_trading/` directly; those
remain research-side acquisition surfaces until a separate feature contract is
published.

## Quick start

```bash
cd /home/manh/stocks
conda create -n stocks python=3.10
conda activate stocks
pip install -r requirements.txt
```

The RL runtime now depends on the workspace-shared `shared-market-rules` and `shared-recommendation` packages.

If you are on WSL with an NVIDIA GPU and want CUDA-enabled PyTorch in the shared `stocks` env, run the optional workspace bootstrap after the base install:

```bash
cd /home/manh/stocks
conda activate stocks
bash scripts/bootstrap_wsl_cuda.sh
conda deactivate && conda activate stocks
python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else None)"
```

This is intentionally optional. The repo keeps generic `torch` dependencies so CPU-only setups still install cleanly.

## Run test suite first to make sure everything is ok

```bash
python -m pytest
```

## Inspect shared research data

```bash
python -m vn_stock_rl.data_tools.inspect_research_exports
python -m vn_stock_rl.data_tools.inspect_research_exports --require-news --require-signal
```

## Build research-side features outside this repo

```bash
cd ../alpha-research-lab
python -m research_pipelines.news_features
python -m research_pipelines.signal_labelling.auto_label
python -m research_pipelines.supervised_label.core.rebuild_bar_labels
python -m research_pipelines.supervised_label.core.export_supervised_dataset
python -m research_pipelines.supervised_label.models.train_signal_model
python -m research_pipelines.supervised_label.models.generate_signal_probs
```

For manual buy-zone labelling:

```bash
cd ../manual-label-factory
python -m manual_label_factory.manual_label
```

RL defaults to shared `data/features/news/predictions/` and `data/features/signals/predictions/auto/` when `--news-prediction-dir` / `--signal-prediction-dir` are omitted.
Those default paths are now resolved through the shared artifact registry in `../shared-recommendation/`, so alpha and RL consume the same workspace path contract.

## Consume the lab RL signal matrix

The research lab publishes a consolidated matrix at `../data/features/xs_rl_signal_matrix.parquet`.
RL does not read that file directly. Adapt it into the existing per-ticker signal contract first:

```bash
cd /home/manh/stocks/RL-trading-agent
conda run -n stocks python -m vn_stock_rl.data_tools.export_lab_signal_matrix
conda run -n stocks python -m vn_stock_rl.data_tools.inspect_research_exports --require-lab-matrix --require-lab-adapter
```

This writes per-ticker files to `../data/features/signals/predictions/rl_lab_matrix/`.
Then point training/evaluation at that directory with `--signal-prediction-dir` and pass the desired lab columns via `--signal-columns`.
In `--portfolio-choice` mode, RL defaults to that lab-adapter directory automatically when `--signal-prediction-dir` is omitted.

Current workspace direction:

- long-only only
- ADV / capacity is parked for the current-account branch, not solved for scale
- RL is currently exploratory, not the active main branch
- RL results must be compared against a same-universe deterministic top-k baseline, not only against an equal-weight universe benchmark
- H153 comparator command: `python -m vn_stock_rl.evaluation.portfolio_baseline`
- first H154 ladder result on seed `1208`: `S1`-only RL is currently best, conditioned sub-core is secondary, full matrix failed
- H155 multi-seed result: `S1`-only RL is mixed high-variance across seeds, so RL should be treated as exploratory until the design changes or the result stabilizes

Shared recommendation artifacts also live at the workspace level:

- package: `../shared-recommendation/`
- candidate root: `../data/features/recommendations/<profile>/`
- default candidate artifact: `../data/features/recommendations/<profile>/latest_candidates.parquet`
- default manifest: `../data/features/recommendations/<profile>/manifest.json`

RL does not yet train directly from that candidate artifact, but it now shares the same artifact registry defaults for matrix, news, signal, help-asset, and stock/market data resolution.

Execution realism is shared with the research lab:

- canonical spec: `../docs/execution_reality.md`
- shared rule code: `../shared-market-rules/shared_market_rules/`
- producer artifact: `../data/features/execution/tradability_daily.parquet`
- strict core: T+1 entry, first legal sell decision at T+3 close, earliest exit fill at T+4 open, zero-volume blocks both sides, ceiling blocks buys, floor blocks sells

## Train and evaluate RL

```bash
# Cut off from 2016 bcuz CafeF starts in 2016ish
# With news
vn-stock-train --stock FPT --policy cnn --help-tickers VNINDEX VN30 --help-assets fx_vnd_usd gold --news-columns tabular --signal-columns default --start-date 2016-01-01 --timesteps 1000000 --ent-coef-start 0.08 --ent-coef-end 0.005 --ent-coef-schedule linear --train-episode-sampling --train-episode-min-fraction 0.05 --train-episode-max-fraction 0.25 --benchmark-relative-reward --reward-benchmark self_buy_hold --benchmark-weight 1.0 --eval-freq 25000 --n-eval-episodes 1 --n-envs 16 --seed 1208 --name cnn_fpt_news_tabular_2016on


vn-stock-evaluate --model artifacts/trained_models/cnn_fpt_news_tabular_2016on/model_best.zip --stock FPT --mode val
```

First portfolio-choice pilot with the lab matrix:

```bash
vn-stock-train --portfolio-choice --policy mlp --start-date 2016-01-01 --timesteps 100000 --eval-freq 10000 --n-eval-episodes 1 --n-envs 4 --seed 1208 --portfolio-universe-size 20 --portfolio-top-k 3 --signal-columns s1_proba c4_oc_asym_5d c5_ins_relative_size_5d c5_signal_present c6_contrarian_intra_5d c7_ceiling_count_5d c8_vol_zscore_5d c9_reversal_1d c10_illiq_level_rank c11_ret_60d_lag_rank c12_gap_absorb_3 c13_compress_blowoff_2 c14_clv_volconf_resid_rank --name pilot_portfolio_labmatrix_seed1208
```

See [docs/lab_signal_matrix_pilot.md](docs/lab_signal_matrix_pilot.md) for the benchmark-first portfolio-mode run ladder.

## Hyperparameters & Trading Env configs

vn_stock_rl/config/defaults.py: default RL settings and policy defaults. If you want to change default hyperparameters, start here.

vn_stock_rl/config/types.py: trading environment configs.

## Docs

- [docs/data.md](docs/data.md)
- [docs/training.md](docs/training.md)
- [docs/evaluation.md](docs/evaluation.md)
- [docs/architectures.md](docs/architectures.md)
- [docs/testing.md](docs/testing.md)
- [docs/repo_map.md](docs/repo_map.md)
- [docs/pipeline_contracts.md](docs/pipeline_contracts.md)

The canonical runtime surface is:
- `vn-stock-train`
- `vn-stock-evaluate`
- `vn-stock-count-params`

## Project Flow

```mermaid
flowchart TD
    A[Set up env and install deps] --> B[Run test suite<br/>python -m pytest]
    B --> C[Inspect shared research exports<br/>python -m vn_stock_rl.data_tools.inspect_research_exports]
    C --> D[/home/manh/stocks/data]
    D --> E[Trading environment<br/>vn_stock_rl/env]
    E --> F[Train RL policy<br/>vn-stock-train]
    F --> G[Run artifacts<br/>artifacts/trained_models/<run_name>/]
    G --> H[Evaluate agent<br/>vn-stock-evaluate]
    H --> I[Metrics, plots, and outputs<br/>artifacts/evaluation_results/]
```
