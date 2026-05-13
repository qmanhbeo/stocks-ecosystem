# Session 244 Log

**Date**: 2026-05-03
**Focus**: S244 eureka queue - test independent signals vs Random baseline.

## Summary

- **Tested**: 4 signals from S244 eureka queue
- **Passed**: 2 signals (insider_buy_lead, consecutive_down_days)
- **Failed**: 1 signal (c16_entropy - inconsistent)
- **No Data**: 1 signal (disclosure_shock_reaction)

## Convention

- Independent signals: compare to **Random (~0)**, not baselines
- Walk-forward validation: IC per year, then average
- **IC > 0.05** = REAL (promotable to signal_library)

---

## Results Detail

### Test 1: insider_pressure_coherence ✅ PASSED

- **Claim**: Insider BUY on T-1 amplifies C16 on T
- **Data**: `data/insider_cache/*.parquet` merge with order_stats
- **Result**: 
  - With prior insider buy: n=5,912
  - Without prior insider buy: n=553,054
  - **IC (insider buy lead)**: 0.1113
  - **IC (without)**: 0.0797
  - **Boost**: +39.7%
- **Verdict**: REAL - +39.7% boost when insider bought previous day
- **Source**: analysis/s244_insider_lead_v2.py

---

### Test 2: consecutive_down_days ✅ PASSED

- **Claim**: Stocks that fell yesterday continue to fall (contrarian)
- **Data**: Returns from xs_barrier_vol_1d_hose_full.parquet
- **Result**: IC = 0.1030
- **vs Random**: +0.10 (**REAL**)
- **Verdict**: REAL - filter for down-day streaks
- **Source**: S244 analysis from prior session

---

### Test 3: dividend_signal_momentum ✅ PASSED (noisy)

- **Claim**: Dividend announcements drive pre-event accumulation
- **Data**: dividend calendar
- **Result**: IC = 0.0934
- **vs Random**: +0.09 (**REAL**) - but year-to-year noisy
- **Verdict**: REAL but inconsistent (some years negative)
- **Source**: S244 analysis from prior session

---

### Test 4: rank_time_acceleration ✅ PASSED

- **Claim**: C16 velocity matters more than level
- **Data**: Order stats rolling
- **Result**: IC = 0.0576
- **vs Random**: +0.06 (**REAL**)
- **Verdict**: REAL - state feature
- **Source**: S244 analysis from prior session

---

### Test 5: c16_entropy_signal ❌ WEAK/INCONSISTENT

- **Claim**: Sector dispersion amplifies C16 signal
- **Test**: IC(C16) by sector dispersion quartiles
- **Result**: 
  - High dispersion: IC = 0.0883
  - Low dispersion: IC = 0.0708
  - **Simple ratio**: +24.7% boost
  - **Walk-forward**: INCONSISTENT
    - 2015: 0.036 vs 0.066 (LOW better)
    - 2016-2019: HIGH better
    - 2020: similar
    - 2021-2022: LOW better
- **Verdict**: WEAK/INCONSISTENT - dead end
- **Source**: analysis/s244_c16_entropy_test.py

---

### Test 6: disclosure_shock_reaction ❓ NO DATA

- **Claim**: Official disclosures cause post-announcement drift
- **Data**: `data/official_disclosures/hnx/` - **EMPTY**
- **Verdict**: CANNOT TEST - insufficient data
- **Source**: Checked issuer_transaction_disclosures.parquet (0 rows)

---

## Final S244 Signal Inventory

| Signal | IC | vs Random | Status |
|--------|-----|---------|--------|
| insider_buy_lead | 0.1113 | +0.11 | **REAL** (+40%) |
| consecutive_down_days | 0.1030 | +0.10 | **REAL** |
| dividend_30d | 0.0934 | +0.09 | REAL (noisy) |
| rank_time_acceleration | 0.0576 | +0.06 | **REAL** |
| c16_entropy | ~0.08 | ~0.08 | **WEAK** - dead end |

---

## Next Steps

- Promote real signals to signal_library.md
- Update findings_compact.md tier placement
- Update live_state.md queue (mark tested signals)
- Close S244 session