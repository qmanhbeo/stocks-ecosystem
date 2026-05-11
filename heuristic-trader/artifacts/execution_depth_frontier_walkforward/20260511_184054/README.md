# Depth Frontier Results (Walk-Forward Canonical)

Generated: 20260511_184054

## Baseline Parity

✅ PASSED - baseline (depth=3) matches original exactly.

## Variants Tested

| Strategy | Scan Depth | Sizing |
|----------|------------|--------|
| blend_70_30_top5 | 3 | fixed_initial |
| blend_70_30_top5_depth5 | 5 | fixed_initial |
| blend_70_30_top5_depth10 | 10 | fixed_initial |
| blend_70_30_top5_depth15 | 15 | fixed_initial |
| blend_70_30_top5_depth20 | 20 | fixed_initial |
| s1_top5_rebal10 | 3 | fixed_initial |
| s1_top5_rebal10_depth5 | 5 | fixed_initial |
| s1_top5_rebal10_depth10 | 10 | fixed_initial |
| s1_top5_rebal10_depth15 | 15 | fixed_initial |
| s1_top5_rebal10_depth20 | 20 | fixed_initial |

## Focus Years

- Failure bull: 2017, 2025
- Success contrast: 2021, 2022
- Secondary: 2019, 2024

## Key Questions

1. Is the trade-off monotonic as depth increases?
2. Does depth5 or depth10 improve 2021 without destroying 2022?
3. Is depth20 too aggressive?
4. Does s1 behave differently from blend?

## Artifacts

- depth_frontier_fold_metrics.csv
- depth_frontier_summary.csv
- focus_year_depth_frontier.csv
- summary.json
