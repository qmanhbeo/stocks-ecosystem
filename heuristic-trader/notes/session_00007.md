# Session 00007

Date: 2026-05-11

## Title: Diagnostics + Ticker-Level PnL Attribution

## Work Done

### 1. Diagnostics Patch (backtest.py)

- Added `collect_diagnostics: bool = False` parameter to `simulate_topk_constraint_compliant()`
- When True, returns trade_log, selection_log, filtered_breakdown
- Regression test: diagnostics on/off produce IDENTICAL metrics
- File: `test_diagnostics_regression.py` - permanent guardrail

### 2. Trade-Level Regime Analysis

- Created `analyze_trade_level_regimes.py`
- Analyzed 3 strategies × 4 years (2017, 2021, 2022, 2025)
- Key finding: High cash exposure (~70%) in bull markets vs ~60% in success years

### 3. Ticker-Level PnL Attribution

- Created `analyze_ticker_pnl_regimes.py`
- Computed realized PnL by ticker using FIFO matching
- Artifacts: `artifacts/ticker_pnl_regime/20260511_171621/`

## Key Findings

### Cash Drag is the Mechanism

| Regime | Avg Cash % | Cash Drag Estimate |
|--------|------------|-------------------|
| Failure (2017, 2025) | 71.3% | ~30.5% |
| Success (2021, 2022) | 61.4% | ~-0.9% (benefit) |

### Realized PnL by Strategy

| Strategy | Realized PnL | Winning Trades | Losing Trades |
|----------|--------------|----------------|---------------|
| blend_70_30_top5 | +0.7558B | 117 | 102 |
| s1_top5_rebal10 | -0.0583B | 95 | 116 |
| c16_only_top5 | -0.1782B | 22 | 27 |

### Top Recurring Tickers

TSC (15), VOS (13), CII (12), DIG (10), OGC (10)

### c16_only_top5 is a Cash Strategy

- 87-93% cash in ALL years
- Underperforms in all regimes due to cash position

## Explanation of 2017/2025 Failure

**MECHANISM**: Strategies hold ~70% cash in bull markets, missing ~30% of upside.

- This is NOT just "regime sensitivity" - it's a specific CASH EXPOSURE problem
- blend_70_30_top5 actually had positive realized PnL (+0.76B), but cash position hurt
- c16_only_top5 is essentially a cash strategy (90% cash) - explains constant underperformance

## What Remains Uncertain

- Why signals select for high-cash portfolios in bull markets
- Whether signal decomposition (RL vs C16) explains the tilt
- Whether ticker selection underperformed benchmark leaders (need full name-level comparison)

## Next Action

This is now an alpha-research-lab investigation. Do NOT promote to paper-trading.

Research needed:
1. Regime detection + conditional exposure
2. Signal decomposition
3. Ticker-level vs benchmark comparison