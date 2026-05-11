# Cash Mechanics Autopsy - V2 (CORRECTED ACCOUNTING)

## Strategy
blend_70_30_top5

## Key Fixes in V2

1. **True Cash Metrics**:
   - `actual_cash_pct`: cash_after / portfolio_value_after * 100
   - `actual_invested_pct`: holdings_value_after / portfolio_value_after * 100
   - `position_underfill_pct`: (top_k - n_holdings) / top_k * 100

2. **Corrected target_gap_pct interpretation**:
   - positive = portfolio below initial-equivalent, but FIXED sizing is LARGER than dynamic
   - negative = portfolio above initial, FIXED sizing is SMALLER than dynamic

3. **Improved dynamic sizing diagnostic**:
   - `open_slots_before`: top_k - n_holdings_before
   - `fixed_slots_affordable`: cash / (fixed_target * (1+fee))
   - `dynamic_slots_affordable`: cash / (dynamic_target * (1+fee))
   - `dynamic_vs_fixed_slot_delta`: dynamic - fixed

## Focus Years Summary

 year  n_rebalance_dates  avg_actual_cash_pct  avg_actual_invested_pct  avg_position_underfill_pct  avg_n_holdings  avg_pass_count_depth_15  avg_pass_count_depth_25  avg_pass_count_depth_50  avg_pass_count_depth_100  avg_would_fill_topk_depth_15  avg_would_fill_topk_depth_25  avg_would_fill_topk_depth_50  avg_would_fill_topk_depth_100  avg_target_gap_pct  avg_dynamic_could_fill_open_slots  avg_dynamic_vs_fixed_slot_delta
 2017                 25            49.068471                50.931529                   57.600000        2.120000                 2.160000                     4.08                10.720000                 24.840000                      0.000000                     36.000000                         100.0                     100.000000           19.569729                          88.000000                         0.760000
 2021                 25            62.206815                37.793185                   36.000000        3.200000                 3.400000                     5.88                14.160000                 33.840000                     28.000000                     68.000000                         100.0                     100.000000          -40.199729                          96.000000                        -3.760000
 2022                 24            77.376125                22.623875                   50.833333        2.458333                 2.666667                     4.75                11.458333                 27.041667                     16.666667                     54.166667                          87.5                      95.833333          -54.482822                          91.666667                        -6.541667
 2025                 25            76.475507                23.524493                   44.000000        2.800000                 2.920000                     5.24                12.440000                 32.440000                     20.000000                     56.000000                         100.0                     100.000000          -57.891398                         100.000000                        -6.960000

## All Years Summary

 year  n_rebalance_dates  avg_actual_cash_pct  avg_actual_invested_pct  avg_position_underfill_pct  avg_n_holdings  avg_pass_count_depth_15  avg_pass_count_depth_25  avg_pass_count_depth_50  avg_pass_count_depth_100  avg_would_fill_topk_depth_15  avg_would_fill_topk_depth_25  avg_would_fill_topk_depth_50  avg_would_fill_topk_depth_100  avg_target_gap_pct  avg_dynamic_could_fill_open_slots  avg_dynamic_vs_fixed_slot_delta
 2015                 25            59.654868                40.345132                   60.800000        1.960000                 1.960000                 3.480000                 9.160000                 20.840000                      0.000000                     20.000000                     96.000000                     100.000000            3.184211                          88.000000                        -0.120000
 2016                 25            54.519715                45.480285                   60.800000        1.960000                 1.960000                 4.120000                 8.480000                 18.640000                      0.000000                     48.000000                     92.000000                     100.000000           18.676834                          96.000000                         0.560000
 2017                 25            49.068471                50.931529                   57.600000        2.120000                 2.160000                 4.080000                10.720000                 24.840000                      0.000000                     36.000000                    100.000000                     100.000000           19.569729                          88.000000                         0.760000
 2018                 25            77.974316                22.025684                   79.200000        1.040000                 1.040000                 2.720000                 7.680000                 21.400000                      0.000000                     20.000000                     76.000000                     100.000000            7.631408                          64.000000                        -0.120000
 2019                 25            71.710619                28.289381                   73.600000        1.320000                 1.320000                 3.080000                 8.240000                 20.760000                      0.000000                     20.000000                     92.000000                     100.000000            6.726325                          68.000000                         0.120000
 2020                 26            67.425637                32.574363                   63.076923        1.846154                 1.846154                 3.653846                 9.538462                 23.846154                      0.000000                     23.076923                     96.153846                     100.000000          -11.360525                          84.615385                        -1.000000
 2021                 25            62.206815                37.793185                   36.000000        3.200000                 3.400000                 5.880000                14.160000                 33.840000                     28.000000                     68.000000                    100.000000                     100.000000          -40.199729                          96.000000                        -3.760000
 2022                 24            77.376125                22.623875                   50.833333        2.458333                 2.666667                 4.750000                11.458333                 27.041667                     16.666667                     54.166667                     87.500000                      95.833333          -54.482822                          91.666667                        -6.541667
 2023                 25            80.656886                19.343114                   58.400000        2.080000                 2.240000                 4.480000                11.240000                 33.720000                      8.000000                     40.000000                    100.000000                     100.000000          -53.604276                          92.000000                        -5.800000
 2024                 25            82.931986                17.068014                   60.800000        1.960000                 2.040000                 4.040000                10.840000                 31.080000                      8.000000                     32.000000                    100.000000                     100.000000          -56.425114                          88.000000                        -6.760000
 2025                 25            76.475507                23.524493                   44.000000        2.800000                 2.920000                 5.240000                12.440000                 32.440000                     20.000000                     56.000000                    100.000000                     100.000000          -57.891398                         100.000000                        -6.960000
