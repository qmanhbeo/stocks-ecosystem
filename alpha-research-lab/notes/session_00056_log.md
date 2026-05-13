# Session 56 Log

## Objective
Run `H155` multi-seed robustness for the only promising RL setup from Session 55:
- `S1`-only portfolio-choice RL

Hard rules remained unchanged:
- long-only only
- no synthetic hedges
- no shorting assumptions
- ADV / capacity parked for the current-account branch, not solved

## Configuration

Shared setup:
- environment: `PortfolioChoiceEnv`
- start date: `2016-01-01`
- test split: `2025-06-12` to `2025-12-31`
- universe size: `20`
- top-k: `3`
- policy: PPO `mlp`
- timesteps: `100000`
- eval frequency: `10000`
- signal columns: `s1_proba`
- requested env count: `4`
- actual runtime: single-env fallback after `SubprocVecEnv` startup failed with `PermissionError`

Reference lines:
- deterministic `s1_only` from H153: `-2.50%`
- equal-weight universe benchmark: `+31.74%`

## Seeds run

### Seed 1208
- training: `RL-trading-agent/artifacts/trained_models/pilot_portfolio_s1_seed1208/`
- eval: `RL-trading-agent/artifacts/evaluation_results/pilot_portfolio_s1_seed1208__PORTFOLIO__test/`
- result:
  - return `+40.30%`
  - Sharpe `2.72`
  - max DD `-8.55%`
  - rebalances `1`

### Seed 1209
- training: `RL-trading-agent/artifacts/trained_models/pilot_portfolio_s1_seed1209/`
- eval: `RL-trading-agent/artifacts/evaluation_results/pilot_portfolio_s1_seed1209__PORTFOLIO__test/`
- result:
  - return `+43.44%`
  - Sharpe `1.89`
  - max DD `-21.17%`
  - rebalances `41`

### Seed 1210
- training: `RL-trading-agent/artifacts/trained_models/pilot_portfolio_s1_seed1210/`
- eval: `RL-trading-agent/artifacts/evaluation_results/pilot_portfolio_s1_seed1210__PORTFOLIO__test/`
- result:
  - return `-1.06%`
  - Sharpe `0.12`
  - max DD `-30.59%`
  - rebalances `86`

### Seed 1211
- training: `RL-trading-agent/artifacts/trained_models/pilot_portfolio_s1_seed1211/`
- eval: `RL-trading-agent/artifacts/evaluation_results/pilot_portfolio_s1_seed1211__PORTFOLIO__test/`
- result:
  - return `-17.98%`
  - Sharpe `-1.10`
  - max DD `-36.04%`
  - rebalances `88`

## Aggregated summary

Compact artifact:
- `RL-trading-agent/artifacts/evaluation_results/h155_s1_multiseed_summary/summary.json`
- `RL-trading-agent/artifacts/evaluation_results/h155_s1_multiseed_summary/summary.csv`

Aggregate metrics:
- seeds run: `4`
- mean RL return: `+16.18%`
- median RL return: `+19.62%`
- wins vs equal-weight benchmark: `2 / 4`
- wins vs deterministic `s1_only`: `3 / 4`
- positive-return seeds: `2 / 4`

## Verdict

`S1`-only RL is real enough to be interesting but not stable enough to promote.

Why:
- it produced two very strong wins
- it also produced two weak / failing seeds
- the branch therefore fails the stability standard needed to make RL the main research direction

Practical interpretation:
- RL found something
- RL is not yet dependable
- the correct repo-level decision is to downgrade RL to exploratory status and return the active branch to long-only alpha / construction research

## What was not run

- Optional conditioned sub-core seed sweeps were not run
- Reason: the `S1`-only branch already failed the stability gate, so extra RL compute would not change the main branch decision

## Next steps

1. Resume `H151`: narrow tradability-conditioned composite
2. Then resume `H152`: tradability-conditioned alpha search
3. Keep RL exploratory until a deliberate design-change branch is opened
