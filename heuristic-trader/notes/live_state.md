# Live State

## Current

**S00007: Cache path fixed + parity test reveals precomputed bug (2026-05-11)**

- **Cache path fixed**: backtest.py, build_cache.py, build_trad_cache.py all pointed to
  `dumb-trading-agent/cache` (wrong directory). All now resolve relative to
  `Path(__file__).parent / "cache"`. Pre-computed caches were silently missing and
  falling back to legacy on-the-fly filtering.
- **Pre-computed cache is UNSAFE** for production: parity test (test_parity.py) reveals
  a ~4% absolute return gap between pre-computed (+0.21%) and legacy (+4.11%) over
  2024-2025. Root cause: `build_liquid_cache` was built using the *wrong* price cache
  from `dumb-trading-agent/cache` (which never existed, so legacy fallback was used
  during the backtest, not the pre-computed cache). When run_backtest.py overrides
  `bt.CACHE_DIR` to the correct path, the pre-computed liquid cache was built from a
  different (earlier) price cache that has fewer tickers/dates. This causes 2 additional
  tickers to pass the liquidity filter in pre-computed mode, diverging from legacy.
  **Use legacy mode as truth path until the liquid cache is rebuilt from the correct
  price cache.**
- **test_parity.py added**: pre-computed vs legacy parity test. Run with
  `python test_parity.py`. Quick test (Q1 2025) passes; full test (2024-2025) fails.
  Quick test is short enough that the ticker coverage gap is masked.

## Status History

### S00006: Lockbox + CLI + Artifacts (2026-05-09)

- run_backtest.py: CLI with --allow-lockbox flag
- signals.py: automatic 2026 lockbox filtering
- artifacts/runs/<ts>/: config.json, metrics.json, daily_equity.parquet

## Verified (quick run)

- s1_only (2019-2025): +41.57% (416tr, 2.2s) (legacy mode)
- Lockbox reject: 2026 dates fail without --allow-lockbox
- --allow-lockbox works: 2026 data included

## Known Issues

| ID | Issue | Status | Fix |
|----|-------|--------|-----|
| F00006 | Pre-computed cache gives +99.86% vs legacy +82.39% | **CONFIRMED BUG** | Use legacy for truth; rebuild liquid cache after verifying price_cache.parquet coverage |

## Pointers

- run_backtest.py (CLI entrypoint)
- signals.py (lockbox loaders)
- test_parity.py (pre-computed vs legacy parity test)
- test_smoke.py (safety/audit layer)
- artifacts/runs/20260508_104327/ (example output)