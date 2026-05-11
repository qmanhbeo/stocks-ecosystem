# Live State

## Current (Handoff)

**S00020: Memory Hygiene + Handoff (2026-05-11)**

See `notes/session_00020.md` for closing session.

### Current Valid State
- **Candidate**: `s1_top5_rebal10_depth5` is a PROVISIONAL validated candidate
- **Evidence**: Full 11-fold validation improved mean annualized return from -4.68% to +0.98% (+5.67%)
- **Positive folds**: 4/11 → 6/11
- **Improved 8/11 folds**: 2015, 2017, 2019, 2020, 2021, 2022, 2023, 2025
- **Worsened 3/11 folds**: 2016, 2018, 2024 - **RISK AUTOPSY NEEDED**

### Valid Artifacts
- `artifacts/s1_depth5_validation_walkforward/20260511_184754/` (S00019)
- `artifacts/execution_depth_frontier_walkforward/20260511_184054/` (S00015)
- `artifacts/execution_ablation_walkforward/20260511_183421/` (S00014)

### Invalid/Superseded Artifacts
- `artifacts/execution_ablation/20260511_181603/` - baseline mismatch (S00012 INVALID)
- Any custom-loop execution ablation - superseded by canonical walk-forward

### What NOT to Do
- Do NOT promote to paper trading
- Do NOT finalize as durable finding
- Do NOT tune more parameters randomly
- Do NOT run more depth variants before risk autopsy
- Do NOT use non-canonical backtest loops
- Do NOT claim "does not materially worsen downside years" (2018 worsened materially)

### Next Exact Task
Run risk autopsy for `s1_top5_rebal10_depth5` on worsened years (2016, 2018, 2024):
- Compare against improved years (2017, 2020, 2021, 2022, 2025)
- Main question: Did depth5 worsen bad years due to more exposure, worse extra names, or both?

---

**S00019: S1 Depth5 Full 11-Fold Validation (2026-05-11)**

VALIDATED_CANDIDATE ⚠️ (with risk caveat)

Full 11-fold walk-forward comparing s1_top5_rebal10 (baseline) vs s1_top5_rebal10_depth5:

| Metric | Baseline | Depth5 | Delta |
|--------|----------|--------|-------|
| Mean Ann Ret | -4.68% | +0.98% | +5.67% |
| Positive Folds | 4/11 | 6/11 | +2 |
| 2022 (bear) | -7.5% | -5.3% | +2.2% |

⚠️ Risk caveat: Depth5 improved 8 folds but worsened 2016, 2018, 2024

Artifacts: artifacts/s1_depth5_validation_walkforward/20260511_184754/

---

**S00017: Execution ablation CORRECTED - superseded by S00018 (2026-05-11)**

See session_00013.md for corrected results.

Key findings:
- Candidate depth IS a real bottleneck (cash 65% → 18%)
- Fixed sizing is SECONDARY
- Dilemma: depth_only helps 2021 but breaks 2022 protection
- Baseline parity PASSED via test_execution_ablation_baseline_parity.py

Corrected artifacts: artifacts/execution_ablation/20260511_182313/

---

**S00016: Execution ablation INVALID - baseline mismatch (2026-05-11)**

⚠️ WARNING: Session 00012 / artifacts/execution_ablation/20260511_181603/ is INVALID.
- Root cause: reimplemented backtest loop instead of using canonical engine
- Superseded by S00017 and S00018

---

**S00015: Cash mechanics V2 accounting - multi-factor confirmed (2026-05-11)**

See full session log at `notes/session_00011.md`

Key V2 corrected findings:
- **True cash %**: 2017=49%, 2021=62%, 2022=77%, 2025=76%
- **Position underfill %**: 2017=58%, 2021=36%, 2022=51%, 2025=44%
- **Corrected target gap**: 2017=+20% (portfolio below initial, fixed sizing LARGER), 2021/22/25 negative (portfolio grew, fixed smaller)
- **Dynamic sizing would help marginally**: avg +0.76 extra slots in 2017, but NOT primary bottleneck
- **Deeper scan still fixes**: depth_50 = 100% can fill top_k

**Root cause**: multi-factor (filters + depth cap + fixed sizing) - do NOT finalize as single-cause

---

**S00014: Cash mechanics CORRECTED - superseded by V2 (2026-05-11)**

---

**S00013: Cash mechanics autopsy - superseded by S00014 (2026-05-11)**

- **Diagnostics patch**: Added `collect_diagnostics=True` to backtest.py
- **Regression guardrail**: `test_diagnostics_regression.py` - PASS
- **Trade-level analysis**: Cash ~70% in bull markets vs ~60% in success years
- **Ticker PnL analysis**: blend_70_30_top5 had +0.76B realized PnL but underperformed due to cash
- **Finding F00010**: Cash drag (~30%) is the MECHANISM of bull-regime failure

- **NOT tradable**: Strategy family has ~70% cash exposure in bull markets - misses ~30% upside
- **c16_only_top5**: Essentially a cash strategy (87-93% cash always)

**Next**: This is now an alpha-research-lab investigation. No further changes in heuristic-trader.

---

**S00013: Cash mechanics autopsy - FILTER BOTTLENECK identified (2026-05-11)**

- **H510 result**: alpha-research-lab returned NEGATIVE FINDING (no latent state issue)
- **Autopsy method**: Traced every rebalance date for blend_70_30_top5, years 2017/2021/2022/2025
- **Key finding**: FILTER BOTTLENECK - only 2-3 candidates pass filters on average (target is 5)
- **2017 worst**: 2.16 avg candidates passed, 100% rebalances underinvested
- **2021 best**: 3.20 avg candidates passed, 72% rebalances underinvested
- **Not position sizing**: 0% failed due to insufficient cash
- **Not price missing**: 0% failed due to missing prices
- **Not top-k cap**: Candidates filtered out BEFORE the cap

- **Finding F00011**: Filter bottleneck (liquidity/tradability) is the root cause of cash drag

- **Next**: Superseded by S00015 - see session_00011.md for V2 analysis

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