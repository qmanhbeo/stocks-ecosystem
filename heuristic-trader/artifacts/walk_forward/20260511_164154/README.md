# Walk-Forward Validation Results

**Generated**: 2026-05-11T16:42:12.574687
**Timestamp**: 20260511_164154

## Provenance

This walk-forward validation harness adapts patterns from alpha-research-lab principles:

- **Explicit temporal folds**: Train/context periods followed by distinct test windows
- **No 2026 lockbox access**: All test windows end at 2025-12-31
- **No tuning inside validation**: Parameters fixed from strategies.json; this is validation, not optimization
- **Artifact-first reporting**: CSV + JSON + Markdown for reproducibility
- **Robustness judged across folds**: Consistency over single-period headline numbers

**Key distinction**: This is PnL/execution validation, NOT IC (Information Coefficient) research. The goal is to assess whether strategies survive realistic portfolio/execution assumptions, not whether signals have predictive power.

## Folds

| Fold | Train Period | Test Period |
|------|---------------|--------------|
| fold_2015 | 2015-01-01 to 2014-12-31 | 2015-01-01 to 2015-12-31 |
| fold_2016 | 2015-01-01 to 2015-12-31 | 2016-01-01 to 2016-12-31 |
| fold_2017 | 2015-01-01 to 2016-12-31 | 2017-01-01 to 2017-12-31 |
| fold_2018 | 2015-01-01 to 2017-12-31 | 2018-01-01 to 2018-12-31 |
| fold_2019 | 2015-01-01 to 2018-12-31 | 2019-01-01 to 2019-12-31 |
| fold_2020 | 2015-01-01 to 2019-12-31 | 2020-01-01 to 2020-12-31 |
| fold_2021 | 2015-01-01 to 2020-12-31 | 2021-01-01 to 2021-12-31 |
| fold_2022 | 2015-01-01 to 2021-12-31 | 2022-01-01 to 2022-12-31 |
| fold_2023 | 2015-01-01 to 2022-12-31 | 2023-01-01 to 2023-12-31 |
| fold_2024 | 2015-01-01 to 2023-12-31 | 2024-01-01 to 2024-12-31 |
| fold_2025 | 2015-01-01 to 2024-12-31 | 2025-01-01 to 2025-12-31 |

## Summary

**Total strategies tested**: 6
**Total folds run**: 66
**Failed runs**: 0

### Strategy Rankings by Mean Annualized Return

| Rank | Strategy | Mean Ann. Return | Median Ann. Return | Positive Folds | Beats Benchmark | Robustness |
|------|----------|------------------|--------------------|----------------|------------------|------------|
| 4 | blend_70_30_top5 | 8.29% | 1.98% | 7/11 | 5/11 | FRAGILE: Inconsistent performance across folds |
| 5 | blend_50_50_top5 | 0.70% | 0.18% | 6/11 | 4/11 | FRAGILE: Inconsistent performance across folds |
| 6 | c16_only_top5 | -1.37% | -0.11% | 5/11 | 3/11 | FRAGILE: Inconsistent performance across folds |
| 3 | s1_top3_rebal10 | -1.37% | 0.03% | 6/11 | 3/11 | FRAGILE: Inconsistent performance across folds |
| 2 | s1_top5_rebal5 | -3.56% | -4.57% | 4/11 | 4/11 | FRAGILE: Inconsistent performance across folds |
| 1 | s1_top5_rebal10 | -4.68% | -7.09% | 4/11 | 2/11 | FRAGILE: Inconsistent performance across folds |

## Notes

- This is a VALIDATION pass, NOT a tuning pass
- No parameter optimization was performed
- "Train/context" period is mostly metadata; test periods are what matter
- Robustness assessed by consistency across time periods

## Files

- `fold_metrics.csv`: Detailed metrics for each strategy/fold combination
- `strategy_summary.csv`: Aggregate summary per strategy (CSV format)
- `summary.json`: Aggregate summary per strategy (JSON format)
