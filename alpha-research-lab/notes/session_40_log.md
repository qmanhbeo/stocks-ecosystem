# Session 40 Log (2026-03-28)

## Summary

Short session focused on new microstructure signals while H113 earnings quality fetch was running.

**Net result:** C10 added (Amihud illiquidity). Signal library now has 10 candidates (S1 + C4–C10).

---

## Experiments

### H121 — Amihud Illiquidity Signal ✅ PASS → C10

**Script:** `analysis/h121_amihud_illiquidity_standalone.py`
**Artifact:** `artifacts/run_summaries/20260328_113807_h121_amihud_illiquidity_standalone_signal.json`

ILLIQ = |daily_return| / (close × volume / 1e9)
Cross-sectional rank of 20d rolling average.

| Feature | IC | Pos Years | Corr S1 | Gate |
|---------|-----|-----------|---------|------|
| xs_illiq_level_rank | +0.0206 | 10/11 | +0.008 | **PASS** |
| xs_illiq_spike_rank | −0.0010 | 6/11 | +0.073 | fail |
| xs_illiq_change_5d | −0.0030 | 3/11 | −0.001 | fail |

**Finding F82:** Structural illiquidity level (not spikes) predicts continuation. Less liquid stocks
are under-followed; information incorporation is slower. Classic Amihud premium exists in Vietnam.

**Promoted:** xs_illiq_level_rank → C10 (IC +0.021, 10/11 years, corr S1 = +0.008)

---

### H113 — Earnings Quality 394 Tickers ❌ FAIL

**Script:** `analysis/h113_earnings_quality_394.py`
**Artifact:** `artifacts/run_summaries/20260328_115435_h113_earnings_quality_394_standalone_signal.json`

Full 399-ticker cache built. 824,839 merged rows.

| Feature | IC (394T) | IC (52T H109) | Pos Years | Gate |
|---------|----------|--------------|-----------|------|
| xs_eps_accel_rank | +0.0039 | +0.0029 | 11/11 | fail |
| xs_eps_yoy_rank | +0.0062 | +0.0030 | 8/11 | fail |
| xs_npm_trend_rank | +0.0056 | −0.0033 | 10/11 | fail |
| xs_roe_delta_rank | +0.0053 | +0.0049 | 9/11 | fail |
| xs_debt_trend_rank | +0.0001 | −0.0006 | 7/11 | fail |

**Finding F83:** Earnings quality improves with universe expansion (all ICs move in right direction)
but none crosses the 0.01 gate. Daily application of quarterly data is too coarse.
Fundamental path closed unless event-driven approach (announcement dates) can be implemented.

---

### H122 — Bid-Ask Spread Proxy (Corwin-Schultz) ✍️ WRITTEN, NOT RUN

**Script:** `analysis/h122_bid_ask_spread_standalone.py`

Uses consecutive-day high/low to estimate effective spread (Corwin & Schultz 2012).
Features: xs_spread_level_rank, xs_spread_spike_rank, xs_spread_change_5d.

**To run:**
```bash
conda run -n stocks python analysis/h122_bid_ask_spread_standalone.py
```

---

## Signal Library Status (End of Session 40)

| Signal | IC | Corr w/ S1 | Coverage | Artifact |
|--------|----|------------|----------|---------|
| S1/H93 | +0.149 | N/A | 100% | xs_barrier_vol_1d_hose_full.parquet |
| C4 oc_asym_5d | +0.023 | +0.147 | 100% | xs_open_close_asymmetry.parquet |
| C5 ins_relative_size | +0.037 | −0.008 | 3.4% | xs_insider_quality_features.parquet |
| C6 contrarian_intra_5d | +0.030 | +0.142 | 100% | xs_sector_rotation_daily.parquet (computed on-fly) |
| C7 xs_ceiling_count_5d | +0.012 | +0.064 | 100% | xs_price_limit_daily.parquet |
| C8 xs_vol_zscore_5d | +0.011 | +0.068 | 100% | xs_volume_zscore_daily.parquet |
| C9 xs_reversal_1d | +0.028 | +0.161 | 100% | xs_shortterm_reversal.parquet |
| C10 xs_illiq_level_rank | +0.021 | +0.008 | 100% | computed on-fly from OHLCV |

**RL signal matrix:** `data/features/xs_rl_signal_matrix.parquet`
Contains: S1 + C4 + C5 + C6 + C7 + C8 + C9 (826k rows × 11 cols).
**C10 NOT yet added** — update `data_tools/build_rl_signal_matrix.py` next session.

---

## Files Created This Session

| File | Purpose |
|------|---------|
| `analysis/h121_amihud_illiquidity_standalone.py` | H121 analysis — Amihud ILLIQ (PASS) |
| `analysis/h122_bid_ask_spread_standalone.py` | H122 analysis — Corwin-Schultz spread (NOT RUN) |
