# Walk-Forward Validation Results

**Generated**: 2026-05-11T16:30:51.351218
**Timestamp**: 20260511_163046

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
- `strategy_summary.csv`: Aggregate summary per strategy (CSV format)
- `summary.json`: Aggregate summary per strategy (JSON format)
