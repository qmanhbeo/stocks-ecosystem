# Lab Signal Matrix Pilot

This is the first controlled portfolio-choice RL experiment for the research lab's consolidated signal matrix.

## Goal

Test whether the lab signal stack improves portfolio-choice RL behavior beyond a simpler `S1`-only setup.

Use the same universe, seed, reward setup, and train window across the first two RL runs:

1. `S1` only
2. full lab matrix (`S1 + C4-C14`)

Keep the equal-weight universe benchmark from evaluation as the non-RL reference point until a dedicated deterministic top-`K` rank baseline is added.

## Step 1: Export the lab matrix into RL's per-ticker contract

```bash
cd /home/manh/stocks/RL-trading-agent
conda run -n stocks python -m vn_stock_rl.data_tools.export_lab_signal_matrix
conda run -n stocks python -m vn_stock_rl.data_tools.inspect_research_exports --require-lab-matrix --require-lab-adapter
```

Export destination:

- `/home/manh/stocks/data/features/signals/predictions/rl_lab_matrix/`

## Step 2: Smoke-test portfolio mode with adapted lab signals

```bash
cd /home/manh/stocks/RL-trading-agent
conda run -n stocks python -m vn_stock_rl.training.cli \
  --portfolio-choice \
  --policy mlp \
  --start-date 2016-01-01 \
  --timesteps 1024 \
  --eval-freq 512 \
  --n-eval-episodes 1 \
  --n-envs 1 \
  --seed 1208 \
  --portfolio-universe-size 20 \
  --portfolio-top-k 3 \
  --signal-columns s1_proba c4_oc_asym_5d c5_ins_relative_size_5d c5_signal_present c6_contrarian_intra_5d c7_ceiling_count_5d c8_vol_zscore_5d c9_reversal_1d c10_illiq_level_rank c11_ret_60d_lag_rank c12_gap_absorb_3 c13_compress_blowoff_2 c14_clv_volconf_resid_rank \
  --name smoke_portfolio_labmatrix
```

## Step 3: Run the controlled pilot ladder

Shared settings:

- policy: `mlp`
- start date: `2016-01-01`
- timesteps: `100000`
- eval frequency: `10000`
- eval episodes: `1`
- envs: `4`
- seed: `1208`
- universe size: `20`
- top-k: `3`

`S1` only:

```bash
conda run -n stocks python -m vn_stock_rl.training.cli \
  --portfolio-choice \
  --policy mlp \
  --start-date 2016-01-01 \
  --timesteps 100000 \
  --eval-freq 10000 \
  --n-eval-episodes 1 \
  --n-envs 4 \
  --seed 1208 \
  --portfolio-universe-size 20 \
  --portfolio-top-k 3 \
  --signal-columns s1_proba \
  --name pilot_portfolio_s1_seed1208
```

Full lab matrix:

```bash
conda run -n stocks python -m vn_stock_rl.training.cli \
  --portfolio-choice \
  --policy mlp \
  --start-date 2016-01-01 \
  --timesteps 100000 \
  --eval-freq 10000 \
  --n-eval-episodes 1 \
  --n-envs 4 \
  --seed 1208 \
  --portfolio-universe-size 20 \
  --portfolio-top-k 3 \
  --signal-columns s1_proba c4_oc_asym_5d c5_ins_relative_size_5d c5_signal_present c6_contrarian_intra_5d c7_ceiling_count_5d c8_vol_zscore_5d c9_reversal_1d c10_illiq_level_rank c11_ret_60d_lag_rank c12_gap_absorb_3 c13_compress_blowoff_2 c14_clv_volconf_resid_rank \
  --name pilot_portfolio_labmatrix_seed1208
```

## Step 4: Evaluate both runs

```bash
conda run -n stocks python -m vn_stock_rl.evaluation.cli --model artifacts/trained_models/pilot_portfolio_s1_seed1208/model_best.zip --portfolio-choice --mode test
conda run -n stocks python -m vn_stock_rl.evaluation.cli --model artifacts/trained_models/pilot_portfolio_labmatrix_seed1208/model_best.zip --portfolio-choice --mode test
```

## What to compare

- total return
- Sharpe
- max drawdown
- rebalance count / average cash weight
- sensitivity to rerunning with new seeds

Do not interpret a single seed as conclusive. This pilot is a go/no-go integration test for portfolio-choice RL on the lab matrix.
