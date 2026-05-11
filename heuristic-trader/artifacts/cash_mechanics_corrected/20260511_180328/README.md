# Cash Mechanics Autopsy - CORRECTED

## Strategy
blend_70_30_top5

## Method
- Full 2015-2025 continuous portfolio state (not skipping non-focus years)
- Only recorded detailed rows for focus years: [2017, 2021, 2022, 2025]
- Added candidate-depth diagnostics at multiples: top_k*3, *5, *10, *20, all
- Added position-sizing diagnostic: fixed vs dynamic target

## Focus Years Summary

 year  n_rebalance_dates  avg_cash_pct  avg_invested_pct  avg_n_holdings  avg_pass_count_depth_15  avg_pass_count_depth_25  avg_pass_count_depth_50  avg_pass_count_depth_100  avg_would_fill_topk_depth_15  avg_would_fill_topk_depth_25  avg_would_fill_topk_depth_50  avg_would_fill_topk_depth_100  avg_target_gap_pct  avg_dynamic_would_fill_topk
 2017                 25     57.600000         42.400000        2.120000                 2.160000                     4.08                10.720000                 24.840000                      0.000000                     36.000000                         100.0                     100.000000           19.569729                          4.0
 2021                 25     36.000000         64.000000        3.200000                 3.400000                     5.88                14.160000                 33.840000                     28.000000                     68.000000                         100.0                     100.000000          -40.199729                          0.0
 2022                 24     50.833333         49.166667        2.458333                 2.666667                     4.75                11.458333                 27.041667                     16.666667                     54.166667                          87.5                      95.833333          -54.482822                          0.0
 2025                 25     44.000000         56.000000        2.800000                 2.920000                     5.24                12.440000                 32.440000                     20.000000                     56.000000                         100.0                     100.000000          -57.891398                          0.0

## All Years Summary

 year  n_rebalance_dates  avg_cash_pct  avg_invested_pct  avg_n_holdings  avg_pass_count_depth_15  avg_pass_count_depth_25  avg_pass_count_depth_50  avg_pass_count_depth_100  avg_would_fill_topk_depth_15  avg_would_fill_topk_depth_25  avg_would_fill_topk_depth_50  avg_would_fill_topk_depth_100  avg_target_gap_pct  avg_dynamic_would_fill_topk
 2015                 25     60.800000         39.200000        1.960000                 1.960000                 3.480000                 9.160000                 20.840000                      0.000000                     20.000000                     96.000000                     100.000000            3.184211                          0.0
 2016                 25     60.800000         39.200000        1.960000                 1.960000                 4.120000                 8.480000                 18.640000                      0.000000                     48.000000                     92.000000                     100.000000           18.676834                          0.0
 2017                 25     57.600000         42.400000        2.120000                 2.160000                 4.080000                10.720000                 24.840000                      0.000000                     36.000000                    100.000000                     100.000000           19.569729                          4.0
 2018                 25     79.200000         20.800000        1.040000                 1.040000                 2.720000                 7.680000                 21.400000                      0.000000                     20.000000                     76.000000                     100.000000            7.631408                          0.0
 2019                 25     73.600000         26.400000        1.320000                 1.320000                 3.080000                 8.240000                 20.760000                      0.000000                     20.000000                     92.000000                     100.000000            6.726325                          4.0
 2020                 26     63.076923         36.923077        1.846154                 1.846154                 3.653846                 9.538462                 23.846154                      0.000000                     23.076923                     96.153846                     100.000000          -11.360525                          0.0
 2021                 25     36.000000         64.000000        3.200000                 3.400000                 5.880000                14.160000                 33.840000                     28.000000                     68.000000                    100.000000                     100.000000          -40.199729                          0.0
 2022                 24     50.833333         49.166667        2.458333                 2.666667                 4.750000                11.458333                 27.041667                     16.666667                     54.166667                     87.500000                      95.833333          -54.482822                          0.0
 2023                 25     58.400000         41.600000        2.080000                 2.240000                 4.480000                11.240000                 33.720000                      8.000000                     40.000000                    100.000000                     100.000000          -53.604276                          4.0
 2024                 25     60.800000         39.200000        1.960000                 2.040000                 4.040000                10.840000                 31.080000                      8.000000                     32.000000                    100.000000                     100.000000          -56.425114                          4.0
 2025                 25     44.000000         56.000000        2.800000                 2.920000                 5.240000                12.440000                 32.440000                     20.000000                     56.000000                    100.000000                     100.000000          -57.891398                          0.0

## Key Questions Answered

1. **Does full-state change conclusion?** Compare focus years results to initial run.

2. **Does deeper scan fix underinvestment?** Check avg_pass_count_depth_25/50/100.

3. **Does fixed position sizing contribute?** Check avg_target_gap_pct.

4. **Would dynamic sizing help?** Check avg_dynamic_would_fill_topk.
