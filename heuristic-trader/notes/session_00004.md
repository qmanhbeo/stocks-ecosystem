# Session 00004

Date: 2026-05-04

## Experiment

**Hypothesis**: C16 (order pressure) should outperform S1 under proper constraints
because C16 has different predictive properties.

**Method**: Walk-forward validation 2019-2025, constraint-compliant backtest
(decision @ close[T-1], entry @ open[T], earliest exit @ open[T+3])

## Initial Results

### Constraint-Compliant Backtest (5-day rebalance, 3-day hold)

| Strategy | Return | Sharpe | Trades |
|----------|--------|--------|--------|
| VNINDEX | +94.43% | 0.55 | 2 |
| S1 Top-5 | -69.85% | -0.05 | 1673 |
| **C16 Top-5** | **+225.68%** | **1.02** | 1667 |

## CRITICAL BUG FOUND — INVALID RESULTS

**Issue**: Backtest does NOT filter by tradability/liquidity.

Evidence:
- C16 picks include zombie stocks (ADP, BRC, CLL, CMV) with zero volume for days
- ADP showed `open=5.62, close=5.62, volume=0` for entire week
- Backtest uses stale prices for dead stocks → fake "gains"

- S1 picks include liquid stocks but they lost real money

**Both results are unreliable** due to lack of:
1. Volume/liquidity filtering
2. Tradability check (can_buy_next_open from C16 data)
3. Price staleness detection

## Verdict

**INVALID** — Results cannot be trusted without tradability filter.

## Fix Required

Add:
1. Filter by `can_buy_next_open` from C16/C5 data
2. Filter by volume > 0
3. Filter by price change > 0 (detects stale data)

## Next Action

Re-run with tradability filter from constraints.py