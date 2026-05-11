# Live State

## Current

**S00011: Ticker-level PnL attribution - cash drag is the mechanism (2026-05-11)**

- **Diagnostics patch**: Added `collect_diagnostics=True` to backtest.py
- **Regression guardrail**: `test_diagnostics_regression.py` - PASS
- **Trade-level analysis**: Cash ~70% in bull markets vs ~60% in success years
- **Ticker PnL analysis**: blend_70_30_top5 had +0.76B realized PnL but underperformed due to cash
- **Finding F00010**: Cash drag (~30%) is the MECHANISM of bull-regime failure

- **NOT tradable**: Strategy family has ~70% cash exposure in bull markets - misses ~30% upside
- **c16_only_top5**: Essentially a cash strategy (87-93% cash always)

**Next**: This is now an alpha-research-lab investigation. No further changes in heuristic-trader.

---

**S00012: Signal wiring pass - C17/C18 available for testing (2026-05-11)**

- **Wired signals**: Added C17 raw (`order_volume_ratio`) and C18 delta (`order_volume_ratio_rank_delta`)
- **SIGNAL_REGISTRY**: Added to signals.py with source/column/derivation info
- **New strategies**: c17_raw_top5_rebal10, c18_delta_top5_rebal10 added to strategies.json
- **Test results**: test_signal_registry.py PASS
- **Walk-forward C17**: -1.37% ann, 5/11 positive, FRAGILE
- **Walk-forward C18**: +0.16% ann, 6/11 positive, FRAGILE
- **C18 shows promise**: Better than C17 in bull markets (2017: -3.34% vs -10.76%)

- **Signals NOT wired**: C19-C26 require derived formulas (vol expansion, imbalance, etc.)
- **NEEDS_EXPORT**: C19-C26, C22, C23, C24, C25, C26 require alpha-research-lab export

## Status History

### S00010: trad_lookup extended to 2015 + walk-forward default 2015-2025 (2026-05-11)

- **trad_lookup extended**: Changed from 2019-01-01 to 2015-01-01 (was accidental hardcode)
- **Investigation**: can_buy_next_open has full coverage from 2007, 2019 was arbitrary
- **Clean surface now**: 2015-01-05 to 2025-12-31 (2,749 dates, 963,447 entries)
- **Coverage artifact**: `artifacts/cache_coverage/20260511_164714/`
- **Parity still passes**: test_parity.py PASSED

- **Walk-forward uses 2015-2025** (11 folds) as the only validation mode
- **Standard (3-fold)**: blend_70_30_top5 best (1.29% ann, 2/3 positive), all FRAGILE
- **Expanded (11-fold)**: blend_70_30_top5 shows 8.29% ann, 7/11 positive - but still FRAGILE

- **Key insight from expanded**: 2017 (VNINDEX +46.59%) destroyed all strategies; 2021 (VNINDEX +33.1%) blend_70_30 got +82%; 2025 (VNINDEX +38.4%) destroyed all strategies. Regime-sensitivity confirmed.

- **RULE**: Do NOT promote single-period strategy without fold robustness
- **NOT tradable**: Strategy family sensitive to market regimes, needs signal refresh or regime adaptation

## Status History

### S00009: Walk-forward validation added (2026-05-11)

- **Walk-forward validation**: Added `walk_forward_validate.py`
- **Folds**: 2019-2022→2023, 2019-2023→2024, 2019-2024→2025
- **Results**:
  - Top strategy: `blend_70_30_top5` (1.29% mean annualized, 2/3 positive folds)
  - All strategies FRAGILE: 2025 was catastrophic (VNINDEX +38.4%, strategies -21% to -41%)
  - Current best (s1_top5_rebal10): NOT tradable (-0.89% mean annualized)
- **Key finding**: 2025 regime failure blocks paper-trading readiness
- **Rule**: Do not promote single-period strategy without fold robustness

## Status History

### S00008: Parity fixed + cache promoted (2026-05-11)

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