# S1 Depth5 Full 11-Fold Validation

**Timestamp:** 20260511_184754

## Strategies Compared
- s1_top5_rebal10
- s1_top5_rebal10_depth5

## Folds: 2015-2025 (11 folds)

## Summary Statistics

| strategy               |   mean_annualized_return |   median_annualized_return |   mean_total_return |   positive_folds |   total_folds |   beats_benchmark |   mean_excess_return |   max_drawdown_mean |   total_trades |   total_filtered |
|:-----------------------|-------------------------:|---------------------------:|--------------------:|-----------------:|--------------:|------------------:|---------------------:|--------------------:|---------------:|-----------------:|
| s1_top5_rebal10        |              -0.0468396  |                   -0.07087 |          -0.0465146 |                4 |            11 |                 0 |                    0 |           -0.220694 |            985 |             3373 |
| s1_top5_rebal10_depth5 |               0.00981355 |                    0.03249 |           0.00968   |                6 |            11 |                 0 |                    0 |           -0.254719 |           1568 |             5049 |

## Year-by-Year Comparison

| fold_name   |   total_return_baseline |   total_return_depth5 |   benchmark_return_baseline |   excess_return_baseline |   excess_return_depth5 |   delta_total |   delta_excess | depth5_improved   |
|:------------|------------------------:|----------------------:|----------------------------:|-------------------------:|-----------------------:|--------------:|---------------:|:------------------|
| fold_2015   |                0.022891 |              0.126666 |                    0.060178 |                        0 |                      0 |      0.103775 |              0 | True              |
| fold_2016   |               -0.182876 |             -0.245279 |                    0.144203 |                        0 |                      0 |     -0.062403 |              0 | False             |
| fold_2017   |               -0.012166 |              0.202637 |                    0.465879 |                        0 |                      0 |      0.214803 |              0 | True              |
| fold_2018   |               -0.327529 |             -0.442912 |                   -0.08589  |                        0 |                      0 |     -0.115383 |              0 | False             |
| fold_2019   |               -0.128584 |             -0.078047 |                    0.065802 |                        0 |                      0 |      0.050537 |              0 | True              |
| fold_2020   |               -0.07087  |              0.157455 |                    0.14087  |                        0 |                      0 |      0.228325 |              0 | True              |
| fold_2021   |                0.288174 |              0.387936 |                    0.331045 |                        0 |                      0 |      0.099762 |              0 | True              |
| fold_2022   |               -0.074975 |             -0.052812 |                   -0.327619 |                        0 |                      0 |      0.022163 |              0 | True              |
| fold_2023   |                0.049024 |              0.16529  |                    0.116213 |                        0 |                      0 |      0.116266 |              0 | True              |
| fold_2024   |                0.138854 |              0.032232 |                    0.116761 |                        0 |                      0 |     -0.106622 |              0 | False             |
| fold_2025   |               -0.213604 |             -0.146686 |                    0.384377 |                        0 |                      0 |      0.066918 |              0 | True              |

## Decision Rules Applied
1. If depth5 improves mean annualized return AND does not reduce positive folds AND does not materially worsen downside years -> VALIDATED_CANDIDATE
2. If depth5 only helps selected years but worsens broader folds -> FOCUS_YEAR_OVERFIT
3. If depth5 improves return but increases drawdown materially -> RISK_TRADEOFF
