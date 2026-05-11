# Cache Contract Documentation

## Status: PARITY PASSED - CACHE PROMOTED

**Last Updated**: 2026-05-11

---

## 2026-05-11 Update: trad_lookup Extended to 2015

**Investigation findings**:
- `trad_lookup.joblib` was hardcoded to start at 2019-01-01 in `build_trad_cache.py:17`
- Source data `xs_order_pressure_daily.parquet` has full `can_buy_next_open` coverage from 2007 onward
- 2019 was an **accidental** boundary, not a documented data-quality boundary
- 2015 matches S1 signal matrix start, enabling clean execution validation

**Action taken**:
- Changed `build_trad_cache.py` start from `'2019-01-01'` to `'2015-01-01'`
- Rebuilt `trad_lookup.joblib`: 963,447 entries (was 665,975), 2,749 dates (was 1,750)

**Coverage now**:
| Year | Entries | Tickers | True | False |
|------|---------|---------|------|-------|
| 2015 | 65,300 | 275 | 60,073 | 5,227 |
| 2016 | 70,280 | 292 | 65,094 | 5,186 |
| ... | ... | ... | ... | ... |
| 2025 | 98,675 | 402 | 92,943 | 5,732 |

**Parity verification**: PASSED - precomputed mode matches legacy exactly.

**Implication**: Clean execution-validation surface now starts at 2015-01-05.

---

## Hard Rule Learned

**"No exact ticker-date row, no claim."**

1. **Missing ticker-date = not liquid / not tradable / not selectable**
   - If the exact (ticker, date) pair is not in the data, return False (fail closed)
   - Do NOT fallback to previous/nearest/last date unless explicitly part of a documented, causal strategy contract

2. **Fallback can create stale/lookahead-like claims**
   - Using the last available date when queried date is missing can introduce lookahead bias
   - The model would "know" about future data when making historical decisions

3. **Cached lookup is research logic, not mere optimization**
   - The cache implements the trading rule
   - Any semantic difference between cache and runtime is a bug

4. **Cache promotion requires parity**
   - `test_parity.py` must pass on both short and full windows
   - `validate_liquid_cache.py` must show zero differences
   - Rebuild alone is NOT sufficient

---

## Proven Facts

1. **Parity is NOW PROVEN**: Pre-computed mode matches legacy mode exactly.
   - Quick test (Q1 2025): PASS
   - Full test (2024-2025): PASS
   - Total return: -4.1123% (both modes)
   - Trade count: 130 (both modes)
   - Filtered count: 568 (both modes)

2. **Path Bug Fixes are Proven**: All cache path references now use self-relocating `Path(__file__).parent / "cache"`.

3. **Root Cause is Proven**: The liquidity filter had two issues:
   - Semantic mismatch: `build_liquid_cache()` used `i-4` window vs `check_liquid()` uses `max(0, idx-5)`
   - Fallback behavior: `check_liquid()` fell back to last date when date not found; precomputed couldn't replicate this

4. **Fix Applied**: 
   - Updated `build_cache.py` to use `max(0, idx-5)` window (matching check_liquid)
   - Updated `check_liquid()` to fail closed (no fallback) - matching precomputed behavior
   - Rebuilt `liquid_lookup.joblib` with corrected logic

---

## Contract Decisions

### A. Authoritative Truth Path

**DECISION**: Precomputed cached lookup is now the primary path. Legacy on-the-fly remains available for validation.

- Pre-computed mode is now PROMOTED - safe for production use
- Both modes produce identical results (parity proven)
- Precomputed is preferred for performance
- Legacy mode available for debugging/validation if needed

### B. Missing Date/Ticker Behavior

**DECISION**: Unknown date or unknown ticker must fail closed. No fallback to previous/nearest date unless explicitly documented and tested.

- `is_liquid()`: Returns `False` if date not in lookup or ticker not in liquid set.
- `can_buy_fast()`: Returns `False` if (ticker, date) not in lookup.
- No implicit fallback to nearest date behavior.

### C. Precomputed Cache Promotion Rule

**DECISION**: Precomputed may only be promoted if:

1. `test_parity.py` passes on short window (Q1 2025)
2. `test_parity.py` passes on full window (2024-2025)
3. Divergent ticker-date diagnostic shows zero differences
4. Cache coverage report is written to `artifacts/parity_diagnostics/<timestamp>/`

### D. Rebuild Rule

**DECISION**: Rebuilding caches alone is NOT sufficient. Rebuilt caches must pass parity before use.

- A rebuild does not automatically validate correctness
- Parity test must pass after any cache rebuild
- Document rebuild procedure and resulting coverage

### E. Scientific Interpretation

**DECISION**: No backtest result from precomputed mode is authoritative until parity passes.

- Pre-computed results are for internal development only
- Production reporting must use legacy mode
- All experiments must note which mode was used

---

## Cache File Specifications

### 1. price_cache.parquet

| Attribute | Value |
|-----------|-------|
| Source Data | Daily OHLCV data from CafeF daily cache |
| Schema | `ticker: str`, `time: datetime64`, `open, high, low, close, volume: float` |
| Key Semantics | Dict[ticker] -> DataFrame indexed by date |
| Date Semantics | Exact date match required |
| Expected Coverage | All trading days for tickers in universe |

### 2. liquid_lookup.joblib

| Attribute | Value |
|-----------|-------|
| Source Data | Derived from price_cache volume filter (min_volume=500,000) |
| Schema | Dict[date] -> Set[ticker] |
| Key Semantics | Date -> set of liquid tickers for that date |
| Date Semantics | Exact date match required |
| Expected Coverage | All trading days where liquid tickers exist |

### 3. trad_lookup.joblib

| Attribute | Value |
|-----------|-------|
| Source Data | Derived from order_pressure can_buy_next_open flag |
| Schema | Dict[(ticker, date)] -> bool |
| Key Semantics | (ticker, date) tuple -> can_buy flag |
| Date Semantics | Exact date match required |
| Expected Coverage | All (ticker, date) combinations with tradability data |

### 4. vnindex_baseline.parquet

| Attribute | Value |
|-----------|-------|
| Source Data | VNIndex benchmark data |
| Schema | `time: datetime`, `close: float` |
| Key Semantics | Single time series |
| Date Semantics | Daily index values |
| Expected Coverage | Full backtest period |

---

## Filter Semantics

### Liquidity Filter

- **Definition**: A ticker is liquid on date D if:
  1. At least 3 trading days of data exist in the 5-day window [D-4, D]
  2. Average volume >= 500,000 VND
  3. Price change >= 0.1% over the window

- **Missing Behavior**: If no data for ticker/date, returns False (fail closed)

- **Parity Rule**: Pre-computed lookup must exactly match legacy on-the-fly computation

### Tradability Filter

- **Definition**: A ticker is tradable on date D if:
  1. `can_buy_next_open` is True in order_pressure data
  2. (ticker, date) exists in lookup

- **Missing Behavior**: If no data for ticker/date, returns False (fail closed)

- **Parity Rule**: Pre-computed lookup must exactly match legacy on-the-fly computation

---

## Pass/Fail Definitions

### Parity Test Pass

All of the following must be true:
- `abs(total_return_diff) <= 1e-6` (0.0001%)
- `abs(n_trades_diff) <= 0`
- `abs(n_filtered_diff) <= 0`

### Parity Test Fail

Any of the following:
- Total return difference exceeds tolerance
- Trade count differs
- Filtered count differs

---

## Rebuild Procedure

1. **Prerequisite**: Ensure source data is up to date
2. **Build caches**: Run `build_cache.py`, `build_trad_cache.py`
3. **Verify paths**: Confirm all caches use `Path(__file__).parent / "cache"`
4. **Run parity test**: Execute `test_parity.py` on short window
5. **Run parity test**: Execute `test_parity.py` on full window
6. **If FAIL**: Do not promote, investigate root cause

---

## Issue Resolution (2026-05-11)

**ISSUE**: Pre-computed mode diverged from legacy mode.

**Root Cause**: 
1. `build_liquid_cache()` used `i-4` window vs `check_liquid()` uses `max(0, idx-5)`
2. `check_liquid()` used fallback to last date when date not found; precomputed couldn't replicate

**Fix Applied**:
- Updated `build_cache.py` line ~28-40: Changed window logic to `max(0, idx-5)` matching check_liquid
- Updated `backtest.py` `check_liquid()`: Changed to fail-closed (no fallback) matching precomputed
- Rebuilt `liquid_lookup.joblib`: Now 4781 dates (was 4764)

**Verification**:
- `validate_liquid_cache.py`: PASS (0/56 sample differences)
- `test_parity.py`: PASS on both quick (Q1 2025) and full (2024-2025) windows

---

## Next Recommended Action

Cache is now promoted. For any future changes:
1. If modifying filter logic, update both `build_cache.py` AND `backtest.py`
2. Run `validate_liquid_cache.py` to verify cache matches check_liquid
3. Run `test_parity.py` to prove parity before promoting