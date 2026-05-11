# Walk-Forward Validation Results

**Generated**: 2026-05-11T16:27:25.214910
**Timestamp**: 20260511_162719

## Folds

| Fold | Train Period | Test Period |
|------|---------------|--------------|
| fold_2023 | 2019-01-01 to 2022-12-31 | 2023-01-01 to 2023-12-31 |
| fold_2024 | 2019-01-01 to 2023-12-31 | 2024-01-01 to 2024-12-31 |
| fold_2025 | 2019-01-01 to 2024-12-31 | 2025-01-01 to 2025-12-31 |

## Summary

**Total strategies tested**: 6
**Total folds run**: 18
**Failed runs**: 0

### Strategy Rankings by Mean Annualized Return

| Rank | Strategy | Mean Ann. Return | Median Ann. Return | Positive Folds | Beats Benchmark | Robustness |
|------|----------|------------------|--------------------|----------------|------------------|------------|
| 4 | blend_70_30_top5 | 1.29% | 8.73% | 2/3 | 1/3 | FRAGILE: Inconsistent performance across folds |
| 1 | s1_top5_rebal10 | -0.89% | 4.96% | 2/3 | 1/3 | FRAGILE: Inconsistent performance across folds |
| 2 | s1_top5_rebal5 | -4.54% | -3.84% | 1/3 | 1/3 | FRAGILE: Inconsistent performance across folds |
| 3 | s1_top3_rebal10 | -4.63% | 1.32% | 2/3 | 1/3 | FRAGILE: Inconsistent performance across folds |
| 6 | c16_only_top5 | -8.16% | 2.04% | 2/3 | 0/3 | FRAGILE: Inconsistent performance across folds; underperforms benchmark consistently |
| 5 | blend_50_50_top5 | -8.94% | 5.30% | 2/3 | 0/3 | FRAGILE: Inconsistent performance across folds; underperforms benchmark consistently |

## Notes

- This is a VALIDATION pass, NOT a tuning pass
- No parameter optimization was performed
- "Train/context" period is mostly metadata; test periods are what matter
- Robustness assessed by consistency across time periods

## Files

- `fold_metrics.csv`: Detailed metrics for each strategy/fold combination
- `summary.json`: Aggregate summary per strategy
