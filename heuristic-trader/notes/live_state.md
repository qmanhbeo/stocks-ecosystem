# Live State

## Current

**S00008: Parity fixed + cache promoted (2026-05-11)**

- **Parity PASSED**: Pre-computed cached lookup now matches legacy exactly
  - Quick test (Q1 2025): PASS
  - Full test (2024-2025): PASS
  - Both modes: -4.1123% return, 130 trades, 568 filtered

- **Root cause fixed**:
  1. `build_liquid_cache()` window logic: changed from `i-4` to `max(0, idx-5)` to match check_liquid()
  2. `check_liquid()` fallback behavior: changed to fail-closed (no fallback to last date)
  3. Rebuilt `liquid_lookup.joblib`: 4781 dates (was 4764)

- **Cache promoted**: Pre-computed cached lookup is now the primary path. Safe for production use.

- **New scripts**:
  - `validate_liquid_cache.py`: Validates cache matches check_liquid() exactly
  - `debug_parity_diagnostics.py`: Finds exact divergent ticker-date pairs
  - `debug_liquidity_semantics.py`: Diagnoses liquidity filter differences

- **Lesson learned from F00006**: Missing-date semantics are part of the trading rule.
  - "No exact ticker-date row, no claim."
  - Fallback to last date creates stale/lookahead-like liquidity claims
  - Cache parity bug fixed by enforcing fail-closed behavior
  - Cached lookup is research logic, not mere optimization

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
| F00006 | Pre-computed cache vs legacy parity gap | **RESOLVED** | Fixed build_cache.py window logic + check_liquid() fail-closed; rebuilt cache; parity passes |

## Pointers

- run_backtest.py (CLI entrypoint)
- signals.py (lockbox loaders)
- test_parity.py (pre-computed vs legacy parity test)
- test_smoke.py (safety/audit layer)
- artifacts/runs/20260508_104327/ (example output)