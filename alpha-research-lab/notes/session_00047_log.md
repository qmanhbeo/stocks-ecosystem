# Session 47 Log

## Objective
Implement the next session after H136: test whether portfolio construction can be selected
honestly from data instead of fixed by a full-sample grid search.

## Implementation

Added:
- `src/portfolio_construction_search.py`
  - config-grid enumeration
  - score-gate parsing
  - candidate ranking
  - expanding / rolling year split generation
- `analysis/h137_nested_portfolio_selection.py`
  - nested walk-forward selector for H136-style portfolio configs
  - train on past years only
  - freeze config and test on the next year
  - stitch test years into one out-of-sample curve
- `tests/test_portfolio_construction_search.py`
  - split generation
  - config sorting
  - grid enumeration

Refactored:
- `analysis/h136_portfolio_construction_sweep.py` now imports shared search helpers instead of
  duplicating config-grid logic

## Validation
Passed:
- `python -m py_compile`
- `pytest tests/test_deterministic_portfolio.py tests/test_portfolio_construction_search.py tests/test_tradability_flags.py`
- `git diff --check`

## H137 design
- strategy: `full_library`
- years: `2015-2025`
- minimum train years: `4`
- train window: expanding
- test window: next calendar year
- execution realism unchanged from H135/H136

Candidate construction menu:
- `top_k = 3, 5, 8, 10`
- rebalance cadence `= 3, 5, 10`
- weighting `= equal, linear, square`
- min-score gates derived from train-split quantiles

## H137 result
Artifacts:
- `artifacts/run_summaries/20260328_171925_h137_nested_portfolio_selection_portfolio_nested_selection.json`
- `artifacts/portfolio_baselines/20260328_171925_h137_nested_portfolio_selection_selected_configs.parquet`
- `artifacts/portfolio_baselines/20260328_171925_h137_nested_portfolio_selection_train_candidates.parquet`
- `artifacts/portfolio_baselines/20260328_171925_h137_nested_portfolio_selection_oos_daily.parquet`

Per-test-year selected configs:

| Test Year | Selected Config | Test Return | Relative vs VNINDEX |
|---|---|---:|---:|
| 2019 | `top_k=3`, `cadence=5`, `equal`, gate `0.523` | +10.06% | +3.00% |
| 2020 | `top_k=10`, `cadence=5`, `equal`, gate `0.523` | +49.23% | +30.48% |
| 2021 | `top_k=3`, `cadence=5`, `equal`, gate `0.522` | +22.39% | -8.27% |
| 2022 | `top_k=5`, `cadence=10`, `equal`, gate `0.522` | -37.20% | -6.89% |
| 2023 | `top_k=5`, `cadence=10`, `equal`, gate `0.521` | +25.01% | +11.72% |
| 2024 | `top_k=5`, `cadence=10`, `equal`, gate `0.521` | -3.66% | -13.94% |
| 2025 | `top_k=5`, `cadence=10`, `equal`, gate `0.521` | -20.16% | -42.46% |

Stitched out-of-sample result (`2019-2025`):
- total return `+21.38%`
- annualized return `+2.84%`
- relative vs VNINDEX `-42.46%`
- information ratio `-0.08`
- max drawdown `-55.65%`

Selection pattern:
- `top_k=5`, `cadence=10`, `equal` chosen `4/7` years
- no sign that complex weighting or aggressive thresholding improves robustness

## Conclusion
The honest version of “machine-learn the portfolio construction” is **not** ready to be trusted.

What H137 proved:
- H136 full-sample results were too optimistic
- a simple nested selector still underperforms benchmark-relative out of sample
- the likely bottleneck is not optimizer sophistication, but the weakness of the long-only
  construction itself under honest validation

## Next queue
1. Reduce to a tiny fixed candidate menu and test simple rules honestly
2. If long-only still cannot beat benchmark-relative, move to hedged constructions
3. Only stress capacity/fees on candidates that survive that honest validation
4. Do not add more ML complexity yet
