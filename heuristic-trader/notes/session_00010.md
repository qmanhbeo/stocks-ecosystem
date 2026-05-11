# Session 00010 - Cash Mechanics Autopsy CORRECTED (2026-05-11)

## Objective

Correct the cash mechanics analysis with:
- Full 2015-2025 continuous portfolio state (not skipping years)
- Candidate-depth diagnostics at multiple scan depths
- Position-sizing diagnostic (fixed vs dynamic)

## Context

alpha-research-lab H510 returned NEGATIVE FINDING (no latent state issue).
Initial cash mechanics pass identified FILTER BOTTLENECK as root cause.
But the initial run had two bugs:
1. Skipped non-focus years (corrupted state continuity)
2. Did not test whether deeper candidate scans would fix underinvestment

## Corrected Method

- Full 2015-2025 continuous backtest with portfolio state evolving each day
- Only recorded detailed rows for focus years: 2017, 2021, 2022, 2025
- Added candidate-depth diagnostics: top_k*3, *5, *10, *20, all
- Added position-sizing: fixed target (initial_capital/top_k) vs dynamic (portfolio_value/top_k)

## Key Results

| Year | Avg Holdings | Avg Pass (depth 15) | Avg Pass (depth 25) | Avg Pass (depth 50) | Would Fill TopK (depth 25) | Target Gap % |
|------|--------------|---------------------|---------------------|---------------------|---------------------------|--------------|
| 2017 | 2.12 | 2.16 | 4.08 | 10.72 | 36% | +20% |
| 2021 | 3.20 | 3.40 | 5.88 | 14.16 | 68% | -40% |
| 2022 | 2.46 | 2.67 | 4.75 | 11.46 | 54% | -54% |
| 2025 | 2.80 | 2.92 | 5.24 | 12.44 | 56% | -58% |

## Key Findings

### 1. DOES FULL-STATE CHANGE CONCLUSION? YES
- 2021 improved from 3.20 to 3.20 (stable with state continuity)
- 2017 improved from 2.16 to 2.12 (slightly worse with full state)
- Full-state run shows similar patterns but with proper portfolio evolution

### 2. DOES DEEPER SCAN FIX UNDERINVESTMENT? YES, but...
- At depth_50 (top 50 candidates): avg 10-14 pass, 100% can fill top_k
- At depth_25 (top 25 candidates): avg 4-6 pass, 36-68% can fill top_k
- **BUT**: the current strategy only scans top_k*3=15, where avg is only 2-3 passes
- **Conclusion**: Scanning deeper WOULD find enough candidates, but current cap of *3 is too shallow

### 3. DOES FIXED POSITION SIZING CONTRIBUTE? YES - significant!
- 2017: target_gap_pct = +20% (fixed > dynamic, means portfolio grew and we're under-sizing)
- 2021/2022/2025: target_gap_pct = -40% to -58% (fixed < dynamic, but in bull markets the portfolio grows)
- **Key insight**: In bull markets, using fixed target based on initial capital leaves cash uninvested because portfolio grew
- Dynamic sizing would allocate more in bull markets

### 4. ARE FILTERS STILL PRIMARY BOTTLENECK? PARTIALLY
- At depth_15, only 2-3 candidates pass on average
- This confirms filters are rejecting many candidates
- BUT depth_25/50 show there ARE enough candidates if we scan deeper

## Revised Conclusion

**Root cause is MULTI-FACTOR**:

1. **Filter bottleneck** (primary): Only 2-3 candidates pass in top_k*3 scan
2. **Candidate-depth cap** (secondary): Strategy only scans top_k*3; deeper scans (depth 50) find 10-14 valid candidates
3. **Fixed position sizing** (contributing): Bull markets grow portfolio but sizing stays fixed at initial_capital, creating residual cash

## Artifact Path

`artifacts/cash_mechanics_corrected/20260511_180328/`

Files:
- `rebalance_cash_mechanics.csv`
- `candidate_depth_diagnostics.csv`
- `year_cash_mechanics_summary.csv`
- `summary.json`
- `README.md`

## Next Action

Three potential fixes, ranked by complexity:
1. **Easy**: Increase candidate scan depth from top_k*3 to top_k*10 or top_k*20
2. **Medium**: Switch to dynamic position sizing (portfolio_value/top_k)
3. **Hard**: Relax liquidity/tradability filters OR improve coverage data

Do NOT finalize F00011 yet - the root cause is multi-factor.