# Session 00004 FIXED

Date: 2026-05-04

## Strategy Definitions (CLARIFIED)

### VNINDEX (Benchmark)
- **Buy what**: VNINDEX ETF
- **Buy when**: First day open (2019-01-02)
- **Sell when**: Last day open (2025-12-31)
- **Trades**: 2 (1 buy + 1 sell)

### S1 Top-5 (10-day rebalance)
- **Buy what**: Top 5 tickers by S1 signal rank
- **Buy when**: Decision at close[T-1], entry at open[T]
- **Sell when**: Hold min 3 days + exit at open[T+3], rebalance every 10 decision days
- **Trades**: 413

### C16 Top-5 (10-day rebalance)
- **Buy what**: Top 5 tickers by C16 order_volume_ratio_rank
- **Buy when**: Decision at close[T-1], entry at open[T]
- **Sell when**: Hold min 3 days, rebalance every 10 days
- **Trades**: 68

### S1+C16 Blend (50/50)
- **Buy what**: Top 5 by (S1 + C16) / 2
- **Buy when**: Decision close[T-1], entry open[T]  
- **Sell when**: Hold 3+ days, rebalance 10 days
- **Trades**: 315

## Filters Applied
- Volume: >500k shares over last 5 days
- Price change: >0.1% (detect stale)
- Tradability: can_buy_next_open

## Results Summary

| Strategy | Return | Trades | vs VNINDEX |
|----------|--------|--------|------------|
| VNINDEX | +94.72% | 2 | baseline |
| S1 5-day | -37.10% | 770 | -132% |
| **S1 10-day** | **+43.14%** | 413 | -52% |
| S1 20-day | +16.31% | 229 | -78% |
| C16 10-day | +31.97% | 68 | -63% |
| **S1+C16 blend** | **+51.99%** | 315 | -43% |

## Key Finding F00005: 10-day rebalance is sweet spot

5-day rebalance destroyed by fees (770 trades × ~0.25% = 192% fees).
10-day rebalance balances signal freshness vs transaction costs.

## Key Finding F00006: Blend beats single signal

S1 + C16 blend (50/50) outperforms both individual signals.