# Lab Signal Matrix Pilot

This is the first controlled RL experiment for the research lab's consolidated signal matrix.

## Goal

Test whether the lab signal stack improves RL behavior beyond the base environment features.

Use the same stock, seed, reward setup, and train window across three runs:

1. no external signal features
2. `S1` only
3. full lab matrix (`S1 + C4-C14`)

## Step 1: Export the lab matrix into RL's per-ticker contract

```bash
cd /home/manh/stocks/RL-trading-agent
conda run -n stocks python -m vn_stock_rl.data_tools.export_lab_signal_matrix
conda run -n stocks python -m vn_stock_rl.data_tools.inspect_research_exports --require-lab-matrix --require-lab-adapter
```

Export destination:

- `/home/manh/stocks/data/features/signals/predictions/rl_lab_matrix/`

## Step 2: Smoke-test the RL runtime with adapted lab signals

```bash
cd /home/manh/stocks/RL-trading-agent
conda run -n stocks python -m vn_stock_rl.training.cli \
  --stock FPT \
  --policy mlp \
  --start-date 2016-01-01 \
  --timesteps 1024 \
  --eval-freq 512 \
  --n-eval-episodes 1 \
  --n-envs 1 \
  --seed 1208 \
  --signal-columns s1_proba c4_oc_asym_5d c5_ins_relative_size_5d c5_signal_present c6_contrarian_intra_5d c7_ceiling_count_5d c8_vol_zscore_5d c9_reversal_1d c10_illiq_level_rank c11_ret_60d_lag_rank c12_gap_absorb_3 c13_compress_blowoff_2 c14_clv_volconf_resid_rank \
  --signal-prediction-dir /home/manh/stocks/data/features/signals/predictions/rl_lab_matrix \
  --name smoke_fpt_labmatrix
```

## Step 3: Run the controlled pilot ladder

Shared settings:

- stock: `FPT`
- policy: `mlp`
- start date: `2016-01-01`
- timesteps: `100000`
- eval frequency: `10000`
- eval episodes: `1`
- envs: `4`
- seed: `1208`

Baseline, no signal features:

```bash
conda run -n stocks python -m vn_stock_rl.training.cli \
  --stock FPT \
  --policy mlp \
  --start-date 2016-01-01 \
  --timesteps 100000 \
  --eval-freq 10000 \
  --n-eval-episodes 1 \
  --n-envs 4 \
  --seed 1208 \
  --signal-columns none \
  --name pilot_fpt_nosignal_seed1208
```

`S1` only:

```bash
conda run -n stocks python -m vn_stock_rl.training.cli \
  --stock FPT \
  --policy mlp \
  --start-date 2016-01-01 \
  --timesteps 100000 \
  --eval-freq 10000 \
  --n-eval-episodes 1 \
  --n-envs 4 \
  --seed 1208 \
  --signal-columns s1_proba \
  --signal-prediction-dir /home/manh/stocks/data/features/signals/predictions/rl_lab_matrix \
  --name pilot_fpt_s1_seed1208
```

Full lab matrix:

```bash
conda run -n stocks python -m vn_stock_rl.training.cli \
  --stock FPT \
  --policy mlp \
  --start-date 2016-01-01 \
  --timesteps 100000 \
  --eval-freq 10000 \
  --n-eval-episodes 1 \
  --n-envs 4 \
  --seed 1208 \
  --signal-columns s1_proba c4_oc_asym_5d c5_ins_relative_size_5d c5_signal_present c6_contrarian_intra_5d c7_ceiling_count_5d c8_vol_zscore_5d c9_reversal_1d c10_illiq_level_rank c11_ret_60d_lag_rank c12_gap_absorb_3 c13_compress_blowoff_2 c14_clv_volconf_resid_rank \
  --signal-prediction-dir /home/manh/stocks/data/features/signals/predictions/rl_lab_matrix \
  --name pilot_fpt_labmatrix_seed1208
```

## Step 4: Evaluate all three runs

```bash
conda run -n stocks python -m vn_stock_rl.evaluation.cli --model artifacts/trained_models/pilot_fpt_nosignal_seed1208/model_best.zip --stock FPT --mode test
conda run -n stocks python -m vn_stock_rl.evaluation.cli --model artifacts/trained_models/pilot_fpt_s1_seed1208/model_best.zip --stock FPT --mode test --signal-columns s1_proba --signal-prediction-dir /home/manh/stocks/data/features/signals/predictions/rl_lab_matrix
conda run -n stocks python -m vn_stock_rl.evaluation.cli --model artifacts/trained_models/pilot_fpt_labmatrix_seed1208/model_best.zip --stock FPT --mode test --signal-columns s1_proba c4_oc_asym_5d c5_ins_relative_size_5d c5_signal_present c6_contrarian_intra_5d c7_ceiling_count_5d c8_vol_zscore_5d c9_reversal_1d c10_illiq_level_rank c11_ret_60d_lag_rank c12_gap_absorb_3 c13_compress_blowoff_2 c14_clv_volconf_resid_rank --signal-prediction-dir /home/manh/stocks/data/features/signals/predictions/rl_lab_matrix
```

## What to compare

- total return
- Sharpe
- max drawdown
- trade count / turnover
- sensitivity to rerunning with new seeds

Do not interpret a single seed as conclusive. This pilot is a go/no-go integration test.
