# Session 254 Log

**Date**: 2026-05-03
**Focus**: Test eureka queue hypotheses (S254-S258)
**Script**: s254_fundamentals_test.py, s257_ovr_reversal_test.py

## Summary

- **Tested**: 2 eureka hypotheses
- **Passed**: 1 (S257 c16_delta)
- **Failed**: 1 (S254 fundamentals)

---

## Convention

- Compare to Random (~0), not C16 baseline
- Walk-forward: IC per year → average
- IC > 0.05 = REAL

---

## Results Detail

### Test 1: S254 fundamentals_momentum ❌ FAILED

- **Claim**: ROE/ROA predicts C16 quality
- **Data**: fundamentals_cache/ (399 tickers)
- **Result**:
  - High ROE IC: 0.0784
  - Low ROE IC: 0.0853
  - **Verdict**: FAILED (no fundamentals edge)
- **Source**: s254_fundamentals_test.py

### Test 2: S257 c16_delta ✅ PASSED

- **Claim**: C16 change (today→tomorrow) is a NEW signal
- **Data**: order_stats/ OVR → C16 delta
- **Result**:
  | Year | IC |
  |------|-----|
  | 2015 | 0.1446 |
  | 2016 | 0.1579 |
  | 2017 | 0.1406 |
  | 2018 | 0.1185 |
  | 2019 | 0.1131 |
  | 2020 | 0.1153 |
  | 2021 | 0.1218 |
  | 2022 | 0.1164 |
  - **Mean IC**: 0.1285
- **Verdict**: PASSED - NEW SIGNAL (IC > 0.05 vs Random)
- **Source**: s257_ovr_reversal_test.py

### Tests Skipped

- S255: buy_zone_entry_timing - NO DATA (labels/ empty structure)
- S256: article_sentiment_regime - news/ unused, requires scraper
- S258: small_liquidity_premium - market cap column not in fundamentals

---

## Session Deliverables

- Scripts: s254_fundamentals_test.py, s257_ovr_reversal_test.py
- Session log: this file

---

## Next Steps

- **S257 PROMOTED**: c16_delta is a NEW independent signal (Tier 2: 0.1285)
- S254, S255, S256, S258: DEAD ENDs (data unavailable or failed)