# Session 00008

Date: 2026-05-11

## Title: Signal wiring pass - C17/C18 integration

## Goal

Wire newer alpha-research-lab signals into heuristic-trader as testable signal surfaces, without promoting them as trading strategies.

## Work Done

### 1. Signal Registry Design (signals.py)

Added SIGNAL_REGISTRY dictionary:
```python
SIGNAL_REGISTRY = {
    "s1_proba": {"source": "xs_rl_signal_matrix", "column": "s1_proba", "status": "READY"},
    "c16_rank": {"source": "xs_order_pressure_daily", "column": "order_volume_ratio_rank", "status": "READY"},
    "c17_raw": {"source": "xs_order_pressure_daily", "column": "order_volume_ratio", "status": "READY"},
    "c18_delta": {"source": "xs_order_pressure_daily", "column": "order_volume_ratio_rank_delta", "status": "READY"},
}
```

### 2. Signal Loader Functions

- `load_order_pressure_raw()`: Loads C17 raw order volume ratio (not ranked)
- `load_order_pressure_delta()`: Loads C18 order pressure rank delta
  - Formula: `delta = rank(t) - rank(t-1)` per ticker
  - Fail-closed: missing prior sets delta to 0.0
  - No future leakage: uses only current and prior day data

### 3. Walk-Forward Integration (walk_forward_validate.py)

Added signal_types:
- `c17_only`: returns `order_volume_ratio`
- `c18_only`: returns `order_volume_ratio_rank_delta`

### 4. Strategy Entries (strategies.json)

Added:
- `c17_raw_top5_rebal10`: C17 raw, top 5, 10-day rebalance
- `c18_delta_top5_rebal10`: C18 delta, top 5, 10-day rebalance

### 5. Smoke Test (test_signal_registry.py)

Created test verifying:
- S1, C16 rank, C17 raw, C18 delta all load correctly
- All return required columns (time, ticker, signal)
- No dates beyond 2025-12-31
- C18 null percentage: 0% (fail-closed works)

## Validation Results

| Test | Command | Result |
|------|---------|--------|
| Compile | `python3 -m py_compile signals.py walk_forward_validate.py backtest.py` | ✅ PASS |
| Signal registry | `python3 test_signal_registry.py` | ✅ PASS |
| Diagnostics regression | `python3 test_diagnostics_regression.py` | ✅ PASS |
| Parity test | `python3 test_parity.py` | ✅ PASS |

## Walk-Forward Results (11 folds, 2015-2025)

### C17 Raw (c17_raw_top5_rebal10)
- Mean annualized return: **-1.37%**
- Positive folds: 5/11
- Beats benchmark: 3/11
- Robustness: **FRAGILE**

### C18 Delta (c18_delta_top5_rebal10)
- Mean annualized return: **+0.16%**
- Positive folds: 6/11
- Beats benchmark: 3/11
- Robustness: **FRAGILE**

### Key Observation
C18 (order pressure delta) shows better bull-market performance than C17:
- 2017 (bull): C18 = -3.34%, C17 = -10.76%
- 2025 (bull): C18 = -27.03%, C17 = -28.49%

C18 delta captures flow acceleration better than raw level.

## Signals NOT Wired (NEEDS_EXPORT)

| Signal | Required Source | Status |
|--------|-----------------|--------|
| C19 | Vol expansion (derived from OHLCV) | NEEDS_EXPORT |
| C20 | Buy-heavy imbalance + vol expansion | NEEDS_EXPORT |
| C21 | Imbalance acceleration + vol expansion | NEEDS_EXPORT |
| C22 | Limit proximity (5-7% pct_change) | NEEDS_EXPORT |
| C23 | Amihud illiquidity × vol expansion | NEEDS_EXPORT |
| C24 | Multi-day ceiling pressure | NEEDS_EXPORT |
| C25 | VWAP deviation (needs VWAP computation) | NOT READY |
| C26 | Buy-heavy + illiq + vol expansion | NEEDS_EXPORT |

These signals require derived formulas from alpha-research-lab research and are not currently available as clean feature surfaces.

## Relevance to Cash-Drag / Bull-Regime Failure

- C18 delta: Captures flow acceleration, could improve signal responsiveness
- C18 shows better performance in bull markets vs C17 (but still fragile)
- C18 does NOT directly address cash-drag mechanism (exposure problem)
- Complex signals (C19-C26) are regime-slicers - may address participation but require alpha-research-lab ontology work

## Next

This is wiring infrastructure only. No findings added since no durable validation result achieved.

The new signals are available for testing but should NOT be promoted as trading strategies.