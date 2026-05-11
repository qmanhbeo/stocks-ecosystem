# Session 00011 - Cash Mechanics V2 Accounting Cleanup (2026-05-11)

## Objective

Correct accounting errors in previous cash mechanics analysis:
- Fix cash % metrics to be actual cash / portfolio value
- Add position underfill % (position count based)
- Correct target_gap_pct interpretation
- Improve dynamic sizing diagnostic with open_slots logic

## Context

S00010 identified multi-factor root cause but had accounting issues:
- avg_cash_pct was actually position underfill %, not actual cash %
- target_gap_pct interpretation was reversed
- dynamic sizing diagnostic was misleading (didn't account for open slots)

## V2 Key Fixes

1. **True Cash Metrics**:
   - `actual_cash_pct`: cash_after / portfolio_value_after * 100
   - `actual_invested_pct`: holdings_value_after / portfolio_value_after * 100
   - `position_underfill_pct`: (top_k - n_holdings) / top_k * 100

2. **Corrected target_gap_pct**:
   - Positive = portfolio value BELOW initial, FIXED sizing > dynamic
   - Negative = portfolio value ABOVE initial, FIXED sizing < dynamic
   - 2017: +20% means portfolio below initial-equivalent, fixed is LARGER than dynamic

3. **Improved Dynamic Sizing**:
   - `open_slots_before`: top_k - n_holdings_before
   - `fixed_slots_affordable`: cash / (fixed_target * (1+fee))
   - `dynamic_slots_affordable`: cash / (dynamic_target * (1+fee))
   - `dynamic_vs_fixed_slot_delta`: how many more slots dynamic could fill

## V2 Key Results

| Year | Actual Cash % | Actual Invested % | Position Underfill % | Target Gap % | Dyn Could Fill % |
|------|---------------|------------------|---------------------|--------------|------------------|
| 2017 | 49.1% | 50.9% | 57.6% | +19.6% | 88% |
| 2021 | 62.2% | 37.8% | 36.0% | -40.2% | 96% |
| 2022 | 77.4% | 22.6% | 50.8% | -54.5% | 92% |
| 2025 | 76.5% | 23.5% | 44.0% | -57.9% | 100% |

## Interpretation

**True cash % is HIGHER than position underfill % suggests**:
- 2017: 49% actual cash vs 58% position underfill (some positions are large)
- 2021: 62% actual cash vs 36% position underfill (fewer but larger positions)
- 2022/2025: 77%/77% actual cash vs 45%/44% underfill

**Target gap interpretation**:
- 2017: +20% = portfolio BELOW initial (cash drag), but fixed sizing is LARGER than dynamic would be
- 2021/2022/2025: negative = portfolio grew, fixed sizing is SMALLER than dynamic

**Dynamic sizing would help**:
- In all years, dynamic sizing would allow more slots to be filled
- 2017: dynamic would fill +0.76 extra slots on average
- But this is NOT the primary bottleneck - filters are

**Deeper candidate scan still fixes underfill**:
- At depth_50: 100% can fill top_k in all years
- At depth_25: 36-68% can fill top_k

## Artifact Path

`artifacts/cash_mechanics_corrected_v2/20260511_180701/`

Files:
- `rebalance_cash_mechanics.csv`
- `candidate_depth_diagnostics.csv`
- `year_cash_mechanics_summary.csv`
- `summary.json`
- `README.md`

## Conclusion

The root cause remains MULTI-FACTOR:
1. **Filters** (primary): At depth_15, only 2-3 pass
2. **Candidate depth cap** (secondary): Scanning deeper finds 10-14 at depth_50
3. **Fixed position sizing** (contributing but minor): Dynamic sizing would help marginally

Do NOT finalize F00011 as single-cause finding. This remains a diagnostic.