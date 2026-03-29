# Lab Signal Matrix Pilot

This is the benchmark-first portfolio-choice RL experiment for the research lab's consolidated signal matrix.

## Goal

Test whether the lab signal stack improves portfolio-choice RL behavior beyond simpler deterministic
and RL baselines.

Run order:

1. build a same-universe deterministic top-`K` comparator
2. run `S1`-only RL
3. run full-matrix RL (`S1 + C4-C14`)
4. run conditioned sub-core RL (`S1 + C7 + C8 + C10 + C12 + C13`)

Do not interpret RL against the old equal-weight universe benchmark alone. The active non-RL
reference point is now the same-universe deterministic top-`K` baseline.

## Step 1: Export the lab matrix into RL's per-ticker contract

```bash
cd /home/manh/stocks/RL-trading-agent
conda run -n stocks python -m vn_stock_rl.data_tools.export_lab_signal_matrix
conda run -n stocks python -m vn_stock_rl.data_tools.inspect_research_exports --require-lab-matrix --require-lab-adapter
```

Export destination:

- `/home/manh/stocks/data/features/signals/predictions/rl_lab_matrix/`

## Step 2: Build the deterministic comparator first

Before interpreting any RL run, build a deterministic top-`K` baseline on the exact universe used by
`PortfolioChoiceEnv`.

Minimum comparator set:
- `S1` only
- full lab matrix composite

This comparator is a required gate for the RL branch. If it does not exist yet as a one-command
helper, add it before calling any RL result meaningful.

Current command:

```bash
cd /home/manh/stocks/RL-trading-agent
conda run -n stocks python -m vn_stock_rl.evaluation.portfolio_baseline \
  --mode test \
  --start-date 2016-01-01 \
  --portfolio-universe-size 20 \
  --portfolio-top-k 3 \
  --signal-columns s1_proba c4_oc_asym_5d c5_ins_relative_size_5d c5_signal_present c6_contrarian_intra_5d c7_ceiling_count_5d c8_vol_zscore_5d c9_reversal_1d c10_illiq_level_rank c11_ret_60d_lag_rank c12_gap_absorb_3 c13_compress_blowoff_2 c14_clv_volconf_resid_rank \
  --strategies s1_only full_library conditioned_subcore \
  --name h153_portfolio_baseline_u20_k3
```

## Step 3: Smoke-test portfolio mode with adapted lab signals

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

## Step 4: Run the controlled pilot ladder

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

Conditioned sub-core:

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
  --signal-columns s1_proba c7_ceiling_count_5d c8_vol_zscore_5d c10_illiq_level_rank c12_gap_absorb_3 c13_compress_blowoff_2 \
  --name pilot_portfolio_subcore_seed1208
```

## Step 5: Evaluate all runs

```bash
conda run -n stocks python -m vn_stock_rl.evaluation.cli --model artifacts/trained_models/pilot_portfolio_s1_seed1208/model_best.zip --portfolio-choice --mode test
conda run -n stocks python -m vn_stock_rl.evaluation.cli --model artifacts/trained_models/pilot_portfolio_labmatrix_seed1208/model_best.zip --portfolio-choice --mode test
conda run -n stocks python -m vn_stock_rl.evaluation.cli --model artifacts/trained_models/pilot_portfolio_subcore_seed1208/model_best.zip --portfolio-choice --mode test
```

## What to compare

- same-universe deterministic top-`K` baseline
- total return
- Sharpe
- max drawdown
- rebalance count / average cash weight
- sensitivity to rerunning with new seeds

Do not interpret a single seed as conclusive. This pilot is only the first gate. Promote RL only if
it beats the matching deterministic comparator and survives reruns on additional seeds.

## Observed first-seed result (`2026-03-29`, seed `1208`)

This ladder has now been run once on the shared test split `2025-06-12` to `2025-12-31`.

Deterministic comparators from `H153`:
- `s1_only`: `-2.50%`
- `full_library`: `+0.41%`
- `conditioned_subcore`: `+6.32%`
- equal-weight universe benchmark: `+31.74%`

First-seed RL outcomes:
- `pilot_portfolio_s1_seed1208`
  - test return `+40.30%`
  - Sharpe `2.72`
  - max drawdown `-8.55%`
  - rebalances `1`
- `pilot_portfolio_labmatrix_seed1208`
  - test return `-7.90%`
  - Sharpe `-0.27`
  - max drawdown `-30.65%`
  - rebalances `90`
- `pilot_portfolio_subcore_seed1208`
  - test return `+15.60%`
  - Sharpe `1.01`
  - max drawdown `-18.59%`
  - rebalances `97`

Interpretation:
- `S1`-only RL is the current leader
- conditioned sub-core is better than its deterministic comparator but still below the benchmark
- the full matrix should not get more compute without a design change

## Active next step

Run `H155` as multi-seed robustness on `pilot_portfolio_s1_seed1208` first.

Optional:
- run a smaller confirmatory seed sweep on `pilot_portfolio_subcore_seed1208`

Do not escalate the full-matrix run until the source of its churn / underperformance is understood.
