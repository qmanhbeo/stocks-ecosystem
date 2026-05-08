# Live State

## Current

**S00006: Lockbox + CLI + Artifacts implemented**

- run_backtest.py: CLI with --allow-lockbox flag
- signals.py: automatic 2026 lockbox filtering
- artifacts/runs/<ts>/: config.json, metrics.json, daily_equity.parquet

## Verified (quick run)

- s1_only (2019-2025): +41.57% (416tr, 2.2s) ✅
- Lockbox reject: 2026 dates fail without --allow-lockbox ✅
- --allow-lockbox works: 2026 data included ✅

## Pointers
- run_backtest.py (new CLI)
- signals.py (lockbox loaders)
- artifacts/runs/20260508_104327/ (example output)