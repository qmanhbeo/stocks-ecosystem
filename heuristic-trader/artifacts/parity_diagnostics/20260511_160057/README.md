# Parity Diagnostics Output

Generated: 2026-05-11T16:03:30.566078

## What Was Compared

- **Strategy**: s1_top5_rebal10
- **Period**: 2024-01-01 to 2025-12-31
- **Rebalance frequency**: 10 days

Both legacy (on-the-fly) and pre-computed filter paths were applied to each candidate at each rebalance date.

## Output Files

- `divergent_rows.csv` - Exact (date, ticker) where legacy and precomputed differ
- `summary.json` - Summary statistics
- `README.md` - This file

## What Was NOT Changed

- No backtest behavior modified
- No caches rebuilt
- No research conclusions altered
- Legacy mode remains authoritative until parity passes

## Known Issue

Parity failure is proven (~4.11% vs ~0.21% return gap). Root cause is NOT yet proven.
This diagnostic helps isolate the exact divergence points.
