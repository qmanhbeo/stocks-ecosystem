# Cash Mechanics Autopsy

## Strategy
blend_70_30_top5

## Focus Years
[2017, 2021, 2022, 2025]

## Key Finding

**Main cash-idle mechanism**: 2017.0: FILTER BOTTLENECK (avg 2.2 candidates passed); 2021.0: FILTER BOTTLENECK (avg 3.2 candidates passed); 2022.0: FILTER BOTTLENECK (avg 2.5 candidates passed); 2025.0: FILTER BOTTLENECK (avg 2.8 candidates passed)

## Year Summary

 year  n_rebalance_dates  avg_cash_pct  avg_invested_pct  avg_n_holdings  avg_candidates_passed  avg_buys_successful  avg_target_position_value  rebalance_dates_with_fewer_than_topk  pct_rebalances_underinvested  failed_price_pct_of_passed  failed_cash_pct_of_passed
 2017                 25     56.474140         43.525860        2.160000               2.160000             2.160000                200000000.0                                    25                    100.000000                         0.0                        0.0
 2021                 25     55.408381         44.591619        3.200000               3.200000             3.200000                200000000.0                                    18                     72.000000                         0.0                        0.0
 2022                 24     74.404650         25.595350        2.458333               2.458333             2.458333                200000000.0                                    20                     83.333333                         0.0                        0.0
 2025                 25     70.420878         29.579122        2.800000               2.800000             2.800000                200000000.0                                    20                     80.000000                         0.0                        0.0

## Per-Rebalance Details

See `rebalance_cash_mechanics.csv` for full per-rebalance breakdown.

## Hypotheses Tested

A. **Filter bottleneck**: If avg candidates passed < 5, filters are rejecting too many.

B. **Price missing**: If buys_failed_due_to_price_missing > 30% of passed, price cache is the issue.

C. **Cash/shares bottleneck**: If buys_failed_due_to_insufficient_cash > 20% of passed, position sizing leaves cash.

D. **Top-k * 3 cap**: If candidates_passed_filters >= top_k but still underinvested, cap is not the issue.
