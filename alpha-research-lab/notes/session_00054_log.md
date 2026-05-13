# Session 54 Log

## Objective
Implement the first concrete piece of the new RL branch:
- `H153`: same-universe deterministic benchmark for portfolio-choice RL

Hard rules remained unchanged:
- long-only only
- no synthetic hedges
- no shorting assumptions

## What was implemented

### RL-side deterministic comparator
Added a reusable RL-side runner:
- `python -m vn_stock_rl.evaluation.portfolio_baseline`

Implementation properties:
- reuses `PortfolioChoiceEnv`
- therefore inherits the exact same:
  - universe selection logic
  - signal panel intersection
  - long-only execution timing
  - settlement / sellability constraints
  - zero-volume and ceiling/floor blocking rules

Supported deterministic strategies:
- `s1_only`
- `full_library`
- `conditioned_subcore`

Artifacts written by the runner:
- `artifacts/evaluation_baselines/<name>/summary.json`
- `artifacts/evaluation_baselines/<name>/<strategy>_daily.parquet`

### Tests
Added targeted RL tests for:
- score composition
- same-universe baseline generation on synthetic data

### Docs
Updated RL and lab docs so the active next branch is now operationally clear:
- ADV / capacity parked for the current-account branch, not solved
- `H153` implemented
- `H154/H155` still pending

## What was run

### H153 real baseline run
Ran the first real same-universe deterministic comparator:
- command: `python -m vn_stock_rl.evaluation.portfolio_baseline`
- output: `RL-trading-agent/artifacts/evaluation_baselines/h153_portfolio_baseline_u20_k3/summary.json`

Resolved universe:
- `STB`, `VNM`, `VRE`, `VJC`, `VHM`, `POW`, `HPG`, `VPB`, `TCB`, `NVL`,
  `CTG`, `MSN`, `BAF`, `MSB`, `PVD`, `BSR`, `HSG`, `PLX`, `DXG`, `VCB`

Test-period results:
- `s1_only`: `-2.50%` total, `-25.99%` relative
- `full_library`: `+0.41%` total, `-23.78%` relative
- `conditioned_subcore`: `+6.32%` total, `-19.30%` relative
- equal-weight universe benchmark: `+31.74%`

Interpretation:
- the same-universe deterministic comparator now exists and is honest
- the conditioned sub-core is the strongest deterministic baseline in the RL universe
- RL still has a real bar to beat, but the bar is not obviously unbeatable

### H154 smoke run
Ran a full-lab-matrix portfolio-choice RL smoke:
- model name: `smoke_portfolio_labmatrix_h154`
- output dir: `RL-trading-agent/artifacts/trained_models/smoke_portfolio_labmatrix_h154/`

Result:
- training path completed end to end
- the original smoke blocker was cosmetic:
  - trainer assumed SB3 progress-bar extras were installed
  - patched the trainer to disable the progress bar automatically when `rich` / `tqdm` extras are missing
- also added a workspace-path fallback for `shared-market-rules` inside the RL runtime, so future
  RL commands do not depend on a manual `PYTHONPATH` injection in this workspace

Smoke eval trace:
- eval mean return: about `-0.141`
- best model artifact written successfully

## What was not done

- No full H154 pilot ladder was executed yet
- No H155 multi-seed evaluation was executed yet

## Next steps
1. Run the real `H154` pilot ladder against the existing H153 comparator:
   - `S1` only
   - full matrix `S1 + C4-C14`
   - conditioned sub-core `S1 + C7 + C8 + C10 + C12 + C13`
2. Compare every RL run against:
   - the matching H153 deterministic comparator
   - the equal-weight universe benchmark only as secondary context
3. If any H154 run looks promising, move to `H155` multi-seed robustness
