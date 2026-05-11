# Execution Ablation Results (Walk-Forward Canonical)

Generated: 20260511_183421

## Baseline Parity

✅ PASSED - explicit baseline matches original baseline exactly

## Variants Tested

| Variant | Description |
|---------|-------------|
| blend_70_30_top5 | Original baseline (scan=3, fixed) |
| s1_top5_rebal10 | Original baseline (scan=3, fixed) |
| blend_70_30_top5_depth20 | Scan 20, fixed sizing |
| blend_70_30_top5_dynamic | Scan 3, dynamic sizing |
| blend_70_30_top5_depth20_dynamic | Scan 20, dynamic sizing |
| s1_top5_rebal10_depth20 | Scan 20, fixed sizing |
| s1_top5_rebal10_dynamic | Scan 3, dynamic sizing |
| s1_top5_rebal10_depth20_dynamic | Scan 20, dynamic sizing |

## Focus Years

- Failure bull: 2017, 2025
- Success contrast: 2021, 2022
- Secondary: 2019, 2024

## Key Findings

See decision_criteria in summary.json and variant_summary.csv for detailed results.

## Artifacts

- variant_fold_metrics.csv
- variant_summary.csv
- focus_year_comparison.csv
- summary.json
