# H510: Bull Participation State Audit

## Objective

Determine whether existing C23/C24/C25/C26-family emissions can explain bull-market
participation failure observed by heuristic-trader.

## Context

heuristic-trader reported that strategy failure in strong bull years is mainly an
under-participation / cash-drag problem:
- Failure bull years: 2017, 2025
- Success / contrast years: 2021, 2022
- Secondary comparison years: 2019, 2024

## Method

- Reused H509 clustered panel (k=6)
- Computed yearly distributions of latent clusters and symbolic states
- Computed yearly IC by state to measure signal quality within each state
- Compared distributions across failure vs success bull years

## Key Findings

### Yearly State Distribution (Focus Years)
|   year |   total_rows |   unique_tickers |   state_quiet_share |   c23_share |   c24_share |   c16_low_share |   c16_high_share |
|-------:|-------------:|-----------------:|--------------------:|------------:|------------:|----------------:|-----------------:|
|   2017 |        64216 |              318 |            0.930329 |   0.0581786 |  0.0130964  |        0.151345 |         0.184279 |
|   2019 |        72968 |              361 |            0.927009 |   0.0654259 |  0.0094699  |        0.13287  |         0.178029 |
|   2021 |        85763 |              382 |            0.943892 |   0.0361228 |  0.021128   |        0.177061 |         0.181973 |
|   2022 |        87526 |              386 |            0.945525 |   0.04329   |  0.0119393  |        0.171737 |         0.187685 |
|   2024 |        86320 |              392 |            0.959975 |   0.0350556 |  0.00537535 |        0.166133 |         0.182732 |
|   2025 |        87117 |              394 |            0.956805 |   0.0328179 |  0.0108016  |        0.166146 |         0.186757 |

### Yearly IC by State
|   year | year_category    |   all_rows_ic |   cluster_0_ic |   cluster_1_ic |   cluster_2_ic |   cluster_3_ic |   cluster_4_ic |   cluster_5_ic |
|-------:|:-----------------|--------------:|---------------:|---------------:|---------------:|---------------:|---------------:|---------------:|
|   2017 | failure_bull     |     0.148744  |      0.127938  |      0.131036  |      0.112671  |       0.250022 |       0.23112  |      0.141832  |
|   2019 | secondary        |     0.144877  |      0.118719  |      0.145691  |      0.156296  |       0.18675  |       0.219112 |      0.135835  |
|   2021 | success_contrast |     0.12319   |      0.0921009 |      0.0818619 |      0.184016  |       0.215628 |       0.193756 |      0.131095  |
|   2022 | success_contrast |     0.0816368 |      0.0550311 |      0.0713734 |      0.0783022 |       0.102377 |       0.213795 |      0.0806233 |
|   2024 | secondary        |     0.131676  |      0.110954  |      0.115157  |      0.239048  |       0.174372 |       0.225962 |      0.147045  |
|   2025 | failure_bull     |     0.108946  |      0.0936192 |      0.0703228 |      0.259637  |       0.249233 |       0.186707 |      0.118105  |

### Focus Year Comparisons
| comparison   |   year_a |   year_b |   state_quiet_share_diff |   c23_share_diff |   c24_share_diff |   c16_low_share_diff |   c16_high_share_diff |   all_rows_ic_a |   all_rows_ic_b |   all_rows_ic_diff |   cluster_0_ic_diff |   cluster_1_ic_diff |   cluster_2_ic_diff |   cluster_3_ic_diff |   cluster_4_ic_diff |   cluster_5_ic_diff |
|:-------------|---------:|---------:|-------------------------:|-----------------:|-----------------:|---------------------:|----------------------:|----------------:|----------------:|-------------------:|--------------------:|--------------------:|--------------------:|--------------------:|--------------------:|--------------------:|
| 2017 vs 2021 |     2017 |     2021 |              -0.013563   |       0.0220558  |      -0.00803157 |         -0.0257158   |            0.00230613 |       0.148744  |        0.12319  |         0.0255541  |          0.0358371  |           0.0491745 |          -0.0713452 |           0.0343943 |          0.0373636  |          0.010737   |
| 2025 vs 2021 |     2025 |     2021 |               0.0129133  |      -0.00330487 |      -0.0103264  |         -0.0109152   |            0.00478468 |       0.108946  |        0.12319  |        -0.0142434  |          0.00151833 |          -0.0115391 |           0.0756216 |           0.0336051 |         -0.00704913 |         -0.0129896  |
| 2022 vs 2021 |     2022 |     2021 |               0.00163287 |       0.00716719 |      -0.00918868 |         -0.00532377  |            0.00571282 |       0.0816368 |        0.12319  |        -0.0415528  |         -0.0370699  |          -0.0104886 |          -0.105714  |          -0.11325   |          0.020039   |         -0.0504718  |
| 2019 vs 2017 |     2019 |     2017 |              -0.00331979 |       0.00724729 |      -0.00362652 |         -0.0184755   |           -0.00624984 |       0.144877  |        0.148744 |        -0.00386628 |         -0.00921916 |           0.0146547 |           0.0436256 |          -0.0632721 |         -0.012008   |         -0.00599731 |
| 2024 vs 2025 |     2024 |     2025 |               0.0031693  |       0.00223767 |      -0.00542622 |         -1.29545e-05 |           -0.00402502 |       0.131676  |        0.108946 |         0.0227296  |          0.0173353  |           0.0448341 |          -0.0205893 |          -0.0748603 |          0.0392545  |          0.0289394  |

## Output Files

- `year_state_summary.csv` - Full yearly state distribution
- `yearly_ic_by_state.csv` - Yearly IC by cluster and symbolic state
- `focus_years_summary.csv` - Focus years only
- `transition_summary.csv` - Cluster transitions by year
- `focus_year_comparison.csv` - Direct comparisons
- `summary.json` - Machine-readable summary

## Conclusion

See live_state.md for interpretation.
