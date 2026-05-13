# Session 39 Log — 2026-03-28

## Objective
Run queued experiments from Session 38: H112 (contrarian intra-sector), H113 (earnings quality 394 tickers), H114 (VN30 rebalancing pressure). Also queue H115 (price limit reversal).

## Experiments

### H112 — Contrarian Intra-Sector Signal
**Script:** `analysis/h112_contrarian_intra_sector.py`
**Hypothesis:** H111 found xs_intra_sector_rank (buy leaders in hot sectors) is strongly anti-predictive (IC = −0.047, 0/11 years). Flipping it — buying laggards in hot sectors — should give IC ≈ +0.047.
**Result:** PASS — all three formulations pass the gate

| Feature | IC | Pos Years | Corr S1 | Gate |
|---------|-----|-----------|---------|------|
| contrarian_intra_5d | +0.0299 | 11/11 | +0.142 | PASS |
| contrarian_intra_20d | +0.0345 | 11/11 | +0.171 | PASS |
| reverse_intra (1 − intra_rank) | +0.0466 | 11/11 | +0.256 | PASS |
| xs_sector_breadth_5d (confirm) | +0.0143 | 8/11 | −0.004 | PASS |

**Finding (F77):** Intra-sector mean reversion dominates sector herding in Vietnamese equities. The stock that has underperformed its sector peers over 5d tends to outperform next day (vs VNINDEX). T+2 settlement and ±7% limits create short-term dislocations when forced sellers exit sector rotations.

The signal lives in all three forms:
- `reverse_intra` — highest IC (+0.047) but highest corr with S1 (+0.256)
- `contrarian_intra_5d = sector_mom_5d_rank × (1 − intra_sector_rank)` — sector-conditioned contrarian (only fires in hot sectors), IC +0.030, corr +0.142
- `contrarian_intra_20d` — same using 20d sector momentum, IC +0.034, corr +0.171

**Promoted to candidates:**
- **C6** = `contrarian_intra_5d` (IC +0.030, 11/11 years, corr +0.142) — primary candidate (best independence)
- Also note: `reverse_intra` as a higher-IC alternative (C6b)

**Key insight:** xs_sector_breadth_5d confirmed again at IC +0.0143 (8/11 years), consistent with H111.

**New artifact:** None (computed on the fly from `xs_sector_rotation_daily.parquet`)
**Run summary:** `artifacts/run_summaries/20260328_105013_h112_contrarian_intra_sector_standalone_signal.json`

---

### H113 — Earnings Quality at 394 Tickers
**Scripts:** `data_tools/build_earnings_quality_features.py`, `analysis/h113_earnings_quality_394.py`
**Hypothesis:** H109 showed xs_roe_delta_rank IC = +0.0049 (8/11 years) at 52 tickers. Expanding to 394 tickers should improve the cross-section enough to push IC above 0.01.
**Status:** PARTIAL COMPLETE

**Limitation:** vnstock VCI API rate limit (20 req/min for guest tier). Fetch script was using 0.3s sleep (too fast); corrected to 3.5s sleep. Background fetch running (~20 min for 332 remaining tickers).

**Interim result (62 tickers):** ICs unchanged from H109 (52-ticker parquet not yet rebuilt — fetch must complete first before parquet is written). Full results pending.

**Run summary:** Will be updated after fetch completes.

---

### H114 — VN30 Rebalancing Proximity Signal
**Scripts:** `data_tools/build_vn30_rebalancing_features.py`, `analysis/h114_vn30_rebalancing_standalone.py`
**Hypothesis:** Stocks approaching top-30 trading-value rank (VN30 threshold) attract passive ETF inflows from VN30 index trackers, creating predictable price pressure.
**Result:** FAIL

| Feature | IC | Pos Years | Corr S1 | Gate |
|---------|-----|-----------|---------|------|
| xs_vn30_rank_pctile | −0.0217 | 1/11 | −0.007 | fail |
| xs_vn30_boundary_score | −0.0201 | 1/11 | +0.013 | fail |
| xs_vn30_rank_change_5d | +0.0075 | 10/11 | +0.038 | fail |
| xs_vn30_add_pressure | +0.0055 | 8/11 | +0.024 | fail |

**Finding (F78):** VN30 liquidity level is anti-predictive (IC = −0.022). Large-cap VN30 stocks underperform relative to the full cross-section — consistent with the retail-driven market preference for smaller, higher-beta names. The rank-change signal (`xs_vn30_rank_change_5d` IC = +0.0075, 10/11 years) is directionally consistent but below the IC > 0.01 threshold. This captures a mild liquidity momentum effect but not the rebalancing mechanism specifically.

**Conclusion:** VN30 rebalancing is not a standalone alpha source at this granularity. The level effect (being a large-cap VN30 stock) is actually negative for cross-sectional returns.

**New artifact:** `data/features/xs_vn30_rebalancing.parquet` (not predictive; archive only)
**Run summary:** `artifacts/run_summaries/20260328_105334_h114_vn30_rebalancing_standalone_signal.json`

---

---

### H115 — Price Limit Momentum Signal ✅ PASS → C7

**Script:** `analysis/h115_price_limit_standalone.py`
**Data builder:** `data_tools/build_price_limit_features.py`
**Artifact:** `artifacts/run_summaries/20260328_110603_h115_price_limit_standalone_signal.json`

Tests whether ceiling/floor touches (hitting the ±7% daily limit) predict next-day continuation or reversal.

| Feature | IC | Pos Years | Corr S1 | Gate |
|---------|-----|-----------|---------|------|
| xs_ceiling_count_5d | +0.0121 | 8/11 | +0.064 | **PASS** |
| xs_floor_count_20d | +0.0104 | 8/11 | +0.034 | **PASS** |
| xs_ceiling_count_20d | +0.0059 | 9/11 | +0.064 | fail |
| xs_floor_count_5d | +0.0029 | 7/11 | +0.010 | fail |
| xs_limit_net_5d | +0.0070 | 7/11 | +0.026 | fail |

**Finding (F79):** Ceiling touches predict continuation (pent-up demand queue). Stocks hitting the +7% ceiling have buyers who couldn't fill at the limit; they return the next day at open.

**Promoted to C7:** `xs_ceiling_count_5d` (IC +0.012, 8/11 years, corr S1 = +0.064)

**New artifact:** `data/features/xs_price_limit_daily.parquet`

---

### H116 — Volume Zscore Signal ✅ PASS → C8

**Script:** `analysis/h116_volume_zscore_standalone.py`
**Data builder:** `data_tools/build_volume_zscore_features.py`
**Artifact:** `artifacts/run_summaries/20260328_110904_h116_volume_zscore_standalone_signal.json`

Tests whether stocks with unusual volume relative to their own 60d baseline outperform next day.

| Feature | IC | Pos Years | Corr S1 | Gate |
|---------|-----|-----------|---------|------|
| xs_vol_zscore_1d | +0.0353 | 11/11 | +0.192 | PASS (higher S1 overlap) |
| xs_vol_zscore_5d | +0.0110 | 10/11 | +0.068 | **PASS** |
| xs_value_zscore_5d | +0.0120 | 10/11 | +0.065 | PASS |
| xs_vol_surge_5d | +0.0074 | 9/11 | +0.055 | fail |

**Finding (F80):** Volume zscore is independent of S1's internal volume encoding (corr +0.068). The simple volume zscore captures a different dimension than XGBoost's learned volume representation.

**Preferred feature for RL state:** `xs_vol_zscore_5d` (IC +0.011, corr +0.068) over `xs_vol_zscore_1d` (IC +0.035, corr +0.192) — smoother and more independent.

**Promoted to C8:** `xs_vol_zscore_5d` (IC +0.011, 10/11 years, corr S1 = +0.068)

**New artifact:** `data/features/xs_volume_zscore_daily.parquet`

---

### H117 — Short-Term Return Reversal ✅ PASS → C9

**Script:** `analysis/h117_shortterm_reversal_standalone.py`
**Data builder:** `data_tools/build_shortterm_reversal_features.py`
**Artifact:** `artifacts/run_summaries/20260328_111601_h117_shortterm_reversal_standalone_signal.json`

Tests 1-day excess return rank as a predictor: negative IC = reversal signal; negate for buy signal.

| Feature | IC (raw) | Pos Years (raw) | Negated IC | Gate |
|---------|---------|----------------|-----------|------|
| xs_ret_1d_lag_rank | −0.0284 | 0/11 | +0.028 (11/11 negated) | **PASS** |
| xs_ret_2d_lag_rank | −0.0345 | 0/11 | +0.035 (11/11 negated) | PASS |
| xs_ret_1d_abs_rank | +0.0353 | 11/11 | — | PASS (activity persistence) |

Corr with S1: xs_ret_1d_lag_rank = −0.161 (complementary — negative correlation confirms independence from 5d momentum).

**Finding (F81):** Vietnam has systematic 1-day mean reversion. 1-day reversal coexists with 5-day continuation — RL agent can exploit both.

**Signal for RL state:** `xs_reversal_1d = 1 − xs_ret_1d_lag_rank` (buy yesterday's underperformers) → C9

**Promoted to C9:** `xs_reversal_1d` (IC +0.028 after negation, 11/11 years, corr S1 = −0.161)

**New artifact:** `data/features/xs_shortterm_reversal.parquet`

---

### H118, H119, H120 — Quick Inline Tests ❌ FAIL (no formal scripts/artifacts)

These were tested as quick inline analyses during session 39. No standalone scripts or run artifacts were generated.

| Hypothesis | Key Feature | IC | Reason for Fail |
|-----------|------------|-----|----------------|
| H118: 52-week high proximity | xs_52w_high_prox | +0.0065 (9/11) | Below IC > 0.01 gate |
| H119: Low-volatility anomaly | xs_low_vol_20d | −0.011 (1/11) | Anti-predictive; Vietnam = high-beta market |
| H120: Intraday reversal | xs_intraday_reversal | +0.041 | Corr with C4 (oc_asym_5d) = +0.394 — redundant |

---

## Session 39 Final Signal Library Update

| Signal | Feature | IC | Pos Years | Corr S1 | Status |
|--------|---------|-----|-----------|---------|--------|
| S1/H93 | xs_proba | +0.149 | 11/11 | — | CONFIRMED |
| C4 | oc_asym_5d | +0.023 | 11/11 | +0.147 | Candidate |
| C5 | xs_ins_relative_size_5d | +0.037 | 10/11 | −0.008 | Candidate |
| **C6** | **contrarian_intra_5d** | **+0.030** | **11/11** | **+0.142** | **NEW** |
| **C7** | **xs_ceiling_count_5d** | **+0.012** | **8/11** | **+0.064** | **NEW** |
| **C8** | **xs_vol_zscore_5d** | **+0.011** | **10/11** | **+0.068** | **NEW** |
| **C9** | **xs_reversal_1d** | **+0.028** | **11/11** | **−0.161** | **NEW** |
| C1 | sentiment_cs_z | +0.043 | 5/8 | +0.009 | Candidate (inconsistent) |

**RL signal matrix built:** `data/features/xs_rl_signal_matrix.parquet` (S1+C4+C5+C6+C7+C8+C9, 826k rows × 11 cols)
