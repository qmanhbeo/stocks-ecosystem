# Session 46 Log

## Objective
Continue from the initial H135 deterministic portfolio baseline by testing whether portfolio
construction can rescue the promoted RL signal library under the shared execution-reality contract.

## What changed

### 1. Blend-logic correction in the deterministic engine
Updated `src/deterministic_portfolio.py` so that:
- every non-presence signal is cross-sectionally ranked by date before it is averaged into a blend
- `_present` flags stay as bounded `0/1`
- portfolio construction can use `equal`, `linear`, or `square` weights across the selected names

This fixed a structural bug in the original H135 baseline. The earlier implementation averaged raw
matrix columns directly, which let raw-scale features such as `C4` and `C5` distort the blend.

### 2. New construction sweep experiment
Added `analysis/h136_portfolio_construction_sweep.py` to sweep:
- `top_k`
- rebalance cadence
- weighting rule
- score gate

### 3. Local robustness plumbing
Added:
- `tests/conftest.py` so lab tests can import the sibling `shared-market-rules` package
- extra deterministic portfolio tests for:
  - weighting behavior
  - cross-sectional score normalization

## Validation
Passed:
- `python -m py_compile`
- `pytest tests/test_deterministic_portfolio.py tests/test_tradability_flags.py`

## Corrected H135 baseline
Artifact:
- `artifacts/run_summaries/20260328_165717_h135_signal_library_portfolio_baseline_portfolio_baseline.json`
- `artifacts/portfolio_baselines/20260328_165717_h135_signal_library_portfolio_baseline_daily.parquet`

Corrected results under the same realistic contract:

| Strategy | Total Return | Annualized | Relative vs VNINDEX | Info Ratio |
|---|---:|---:|---:|---:|
| `s1_only` | -68.33% | -10.01% | -90.20% | -0.57 |
| `recent_core` | -46.81% | -5.63% | -83.54% | -0.40 |
| `full_library` | +72.10% | +5.11% | -46.75% | -0.05 |

Interpretation:
- the library is not economically dead
- the initial Session 45 `full_library` fail was driven by a score-scaling bug
- default realistic construction is still too weak to justify an RL pivot

## H136 portfolio construction sweep
Artifact:
- `artifacts/run_summaries/20260328_170102_h136_portfolio_construction_sweep_portfolio_construction_sweep.json`
- `artifacts/portfolio_baselines/20260328_170102_h136_portfolio_construction_sweep.parquet`
- `artifacts/portfolio_baselines/20260328_170102_h136_portfolio_construction_sweep_best_daily.parquet`

Sweep grid:
- `top_k = 3, 5, 8, 10`
- rebalance cadence `= 3, 5, 10`
- weighting `= equal, linear, square`
- score gate `= none, 0.521, 0.570, 0.600`

Best configuration:
- `top_k = 5`
- rebalance every `5` signal days
- `equal` weighting
- score gate `= none / 0.521 / 0.570` (tie)

Best result:
- total return `+1105.71%`
- annualized return `+25.66%`
- relative vs VNINDEX `+273.09%`
- information ratio `0.50`
- max drawdown `-59.76%`
- positive years `8/11`
- avg daily turnover `33.54%`

Grid pattern:
- `5d` cadence dominates the grid
- `10d` cadence is second-best
- `3d` cadence is materially worse
- `equal` weighting beats `linear` and `square`
- `top_k = 5` is best absolute performer
- moderate score gating does not matter in the winning region

## Strategic conclusion
The correct next bottleneck is no longer “find more signals” and not “train RL immediately.”

The next bottleneck is:
1. honest validation of the H136 winner
2. capacity / fee / turnover realism on that winner
3. only then RL as an overlay that must beat the deterministic baseline

## Next queue
1. Honest out-of-sample validation of the H136 winner
2. Capacity sensitivity grid on the H136 winner
3. Execution stress on the H136 winner
4. Only after that, revisit hedged constructions or portfolio RL
