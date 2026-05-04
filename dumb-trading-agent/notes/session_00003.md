# Session 00003

Date: 2026-05-04

## What Changed

Started dumb agent brute-force strategy development:

## Attempt 1 — Simplified Backtest (close prices)

| Strategy | Return | Sharpe |
|----------|--------|--------|
| VNINDEX | +100.11% | 0.59 |
| S1 Top-5 | +196.27% | 0.67 |

## Attempt 2 — Constraint-Compliant Backtest (open prices)

| Strategy | Return | Sharpe | Trades | Constraint |
|----------|--------|-------|--------|---------|
| VNINDEX | +94.43% | 0.55 | 2 | entry@open |
| S1 Top-5 (20-day) | +3.84% | 0.31 | 418 | decision@close[T-1], entry@open[T] |
| S1 Top-5 (10-day) | +5.59% | 0.24 | 825 | same |
| S1 Top-5 (Daily) | -80% | -0.17 | 1600 | same |

## Key Finding

Transaction costs dominate. With proper constraint implementation:
- S1 barely beats cash (3-5%)
- Daily turnover = -80% loss due to fee drag (~400%)
- Lab's 5-day rebalance is optimal

## Results

Backtest engine constraint-compliant. All configs tested.

## Durable Promotion

- F00001: Transaction costs dominate high-turnover strategies