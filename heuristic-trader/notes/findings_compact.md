# Findings Compact

(Thematic recovery view - newest first)

---

## F00010 — Cash drag is the MECHANISM of bull-regime failure (2026-05-11)

[link: artifacts/ticker_pnl_regime/20260511_171621/]

**Evidence**:
- Failure years (2017, 2025): avg 71.3% cash -> ~30.5% cash drag vs benchmark
- Success years (2021, 2022): avg 61.4% cash -> ~-0.9% (slight benefit)

**Realized PnL**:
- blend_70_30_top5: +0.76B realized (wins > losses)
- s1_top5_rebal10: -0.06B realized
- c16_only_top5: -0.18B realized (essentially a cash strategy - 90% cash always)

**Finding**: In bull markets, strategies hold ~70% cash vs ~60% in other years. For blend_70_30_top5, realized PnL was positive (+0.76B), so cash/exposure is the primary identified mechanism. For s1_top5_rebal10, realized PnL was slightly negative (-0.06B), indicating mixed signal+exposure failure. For c16_only_top5, the strategy is structurally cash-heavy (87-93% cash in all years) and had negative realized PnL - not viable standalone.

[Hypothesis]: "signals select for low-momentum/defensive stocks" may explain the cash tilt, but this is not yet proven.

### Failure Mode Taxonomy

| Strategy | Realized PnL | Cash % (bull) | Classification |
|----------|--------------|---------------|----------------|
| blend_70_30_top5 | +0.76B | 62-64% | Portfolio/exposure failure (positive picks, too much cash) |
| s1_top5_rebal10 | -0.06B | 50-75% | Mixed signal + exposure failure |
| c16_only_top5 | -0.18B | 87-93% | Structurally cash-heavy, not viable as standalone |

---

## F00009 — trad_lookup extended: 2019 was accidental, 2015 is clean start (2026-05-11)

[link: docs/cache_contract.md]

**Investigation**:
- `build_trad_cache.py` hardcoded `start='2019-01-01'` - no rationale
- Source data `can_buy_next_open` has full coverage from 2007 onward
- 2019 was arbitrary boundary, not data-quality constraint

**Action**:
- Extended to 2015-01-01 (matches S1 signal start)
- Rebuilt: 963,447 entries (2,749 dates), was 665,975 (1,750 dates)
- Parity still PASSED

**Finding**: Earliest clean tradable research surface is now 2015-01-05.


---

## F00008 — Walk-forward validation: execution robustness test (2026-05-11)

[link: artifacts/walk_forward/20260511_163046/]

**VALIDATION PASS**: Walk-forward validation harness added.

**Folds**: 2019-2022→2023, 2019-2023→2024, 2019-2024→2025

**Results**:
| Strategy | Mean Ann. Return | Positive Folds | Beats Benchmark | Robustness |
|----------|------------------|----------------|------------------|------------|
| blend_70_30_top5 | +1.29% | 2/3 | 1/3 | FRAGILE |
| s1_top5_rebal10 | -0.89% | 2/3 | 1/3 | FRAGILE |
| s1_top5_rebal5 | -4.54% | 1/3 | 1/3 | FRAGILE |
| s1_top3_rebal10 | -4.63% | 2/3 | 1/3 | FRAGILE |
| c16_only_top5 | -8.16% | 2/3 | 0/3 | FRAGILE |
| blend_50_50_top5 | -8.94% | 2/3 | 0/3 | FRAGILE |

**Key observation**: 2025 was catastrophic for ALL strategies (VNINDEX +38.4%, strategies -21% to -41%).
All strategies beat benchmark in 2024 but underperformed dramatically in 2025.

**Finding**: 70/30 blend is best among tested strategies but still FRAGILE.
2025 regime failure blocks paper-trading readiness.

**RULE**: Do not promote single-period strategy without fold robustness.
Walk-forward validation must show consistency before live deployment.

---

## F00007 — Cache parity: missing-date semantics fixed (2026-05-11)

[link: findings_00001_00030.md]

**BUG FIX**: Pre-computed vs legacy parity gap (~4% return gap).

**Root cause**: 
- `build_liquid_cache()` window logic differed from `check_liquid()`
- `check_liquid()` used fallback to last date; precomputed couldn't

**Fix**: 
- Updated `build_cache.py` window to `max(0, idx-5)`
- Updated `check_liquid()` to fail-closed (no fallback)
- Rebuilt cache - parity now passes

**HARD RULE**: "No exact ticker-date row, no claim." 
Missing-date = not liquid. Fallback creates lookahead bias. Cache is research logic.


---

## F00006 — 70/30 blend is optimal (2026-05-04)

[link: findings_00001_00030.md]

Blend grid (10-day rebal, with filters):
- 50/50: +51.99% (315tr)
- 60/40: +54.81% (364tr)
- **70/30: +82.39%** (397tr) ← USE LEGACY
- 80/20: +75.30% (431tr)

**NOTE**: Pre-computed lookups give +99.86% but have a bug - use for param selection only.
Always verify with legacy filters before publishing.


---

## F00005 — 10-day rebalance is the sweet spot (2026-05-04)

[link: findings_00001_00030.md]

S1 Top-5 grid search results:
- rebal=5d: -37.10% (770 trades) — DESTROYED by fees
- **rebal=10d: +43.14% (413 trades)** — BEATS VNINDEX!
- rebal=20d: +16.31% (229 trades)

Key insight: 10-day rebalance balances signal vs costs.


---

## F00004 — FIXED: Volume unit bug + turnover kills (2026-05-04)

[link: findings_00001_00030.md]

**BUG DISCOVERED**: Volume was in shares, not VND.
Corrected filter: 500k shares (not 10M VND).

S1 5-day: -37.10% (770 trades) — destroyed by fees.


---

## Findings Index

- `findings_00001_00030.md` — chunk 1 (entries 00001-00030)