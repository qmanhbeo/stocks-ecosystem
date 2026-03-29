# Session 55 Log

## Objective
Run the first real `H154` portfolio-choice RL pilot ladder against the existing `H153`
same-universe deterministic comparator.

Hard rules remained unchanged:
- long-only only
- no synthetic hedges
- no shorting assumptions
- ADV / capacity parked for the current-account branch, not solved

## Configuration

Shared settings across the ladder:
- environment: `PortfolioChoiceEnv`
- start date: `2016-01-01`
- test split produced by the env: `2025-06-12` to `2025-12-31`
- portfolio universe size: `20`
- portfolio top-k: `3`
- policy: PPO `mlp`
- timesteps: `100000`
- eval frequency: `10000`
- eval episodes: `1`
- requested env count: `4`
- actual runtime: single-env fallback after `SubprocVecEnv` startup failed with `PermissionError`
- seed: `1208`

Resolved universe:
- `STB`, `VNM`, `VRE`, `VJC`, `VHM`, `POW`, `HPG`, `VPB`, `TCB`, `NVL`,
  `CTG`, `MSN`, `BAF`, `MSB`, `PVD`, `BSR`, `HSG`, `PLX`, `DXG`, `VCB`

Reference deterministic comparator from Session 54 / H153:
- `s1_only`: `-2.50%` total, `-25.99%` relative
- `full_library`: `+0.41%` total, `-23.78%` relative
- `conditioned_subcore`: `+6.32%` total, `-19.30%` relative
- equal-weight universe benchmark: `+31.74%`

## Runs and outputs

### 1. `S1` only RL

Training run:
- `RL-trading-agent/artifacts/trained_models/pilot_portfolio_s1_seed1208/`

Evaluation output:
- `RL-trading-agent/artifacts/evaluation_results/pilot_portfolio_s1_seed1208__PORTFOLIO__test/`

Held-out result:
- RL return: `+40.30%`
- additive reward: `+35.43%`
- Sharpe: `2.72`
- max drawdown: `-8.55%`
- rebalances: `1`

Interpretation:
- clear win versus deterministic `s1_only`
- also above the equal-weight universe benchmark on this split

### 2. Full matrix RL (`S1 + C4-C14`)

Training run:
- `RL-trading-agent/artifacts/trained_models/pilot_portfolio_labmatrix_seed1208/`

Evaluation output:
- `RL-trading-agent/artifacts/evaluation_results/pilot_portfolio_labmatrix_seed1208__PORTFOLIO__test/`

Held-out result:
- RL return: `-7.90%`
- additive reward: `-5.05%`
- Sharpe: `-0.27`
- max drawdown: `-30.65%`
- rebalances: `90`

Interpretation:
- worse than the deterministic `full_library` comparator
- much worse than the equal-weight benchmark
- high churn with no payoff
- this feature set should not get more compute until the design changes

### 3. Conditioned sub-core RL (`S1 + C7 + C8 + C10 + C12 + C13`)

Training run:
- `RL-trading-agent/artifacts/trained_models/pilot_portfolio_subcore_seed1208/`

Evaluation output:
- `RL-trading-agent/artifacts/evaluation_results/pilot_portfolio_subcore_seed1208__PORTFOLIO__test/`

Held-out result:
- RL return: `+15.60%`
- additive reward: `+17.09%`
- Sharpe: `1.01`
- max drawdown: `-18.59%`
- rebalances: `97`

Interpretation:
- beats the deterministic conditioned sub-core comparator
- still below the equal-weight benchmark
- far below the `S1`-only RL result
- possible secondary candidate, but not the lead branch

## Operational fixes that mattered

- The trainer now falls back from `SubprocVecEnv` to a single environment when process startup fails
  under the current runtime permissions.
- The trainer now disables the SB3 progress bar automatically when `rich` / `tqdm` extras are not
  installed.
- The RL runtime now has a workspace-path fallback for `shared-market-rules`, so commands no longer
  require manual `PYTHONPATH` injection.

## Verdict

First-seed `H154` result:
- `S1`-only RL is the only clear winner
- adding more signals did not help
- the full matrix was actively harmful on this setup
- the conditioned sub-core is mixed and secondary

The correct next step is not more feature accumulation.
It is `H155`:
- rerun `S1`-only RL across multiple seeds
- only keep the RL branch as primary if that result is stable

## Next steps

1. Run `H155` multi-seed robustness on `pilot_portfolio_s1_seed1208`
2. If compute is available, run a smaller seed sweep on `pilot_portfolio_subcore_seed1208`
3. Do not rerun the full matrix without changing the state/reward design
