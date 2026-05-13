# Session 116 Log — 2026-05-08

## H463: amihud_illiquidity_regime_combo

**Decision: PASSED**

### Hypothesis
C10 (Amihud illiquidity, IC +0.0206 standalone) might be STRONGER in vol_expansion regime. Illiquid stocks (under-followed) might respond more to regime effects.

### Results

**Illiq alone:**
- high_illiq: IC=0.2029 (+0.0731 lift vs baseline 0.1298) — VERY strong standalone
- mid_illiq: IC=0.1172
- low_illiq: IC=0.0652
- C10 standalone reference: +0.0206 — much weaker, our amihud_20d_avg is much stronger

**Illiq × Vol regime:**
- high_illiq_expansion: IC=0.2616 (+0.1318 lift) — **STRONGEST signal found so far!**
- low_illiq_expansion: IC=0.0808
- high_illiq_contraction: IC=0.1790

**Cross signals:**
- buy_heavy_expansion (baseline): IC=0.2105
- high_illiq_buy_expansion: IC=0.2396 (+0.1098 lift)

### Key insight
Amihud illiquidity × vol_expansion is THE strongest signal discovered. Illiquid stocks (under-followed) amplify regime effects dramatically. IC=0.2616 is +101% boost over baseline.

### Signal promotion: C23 — illiquidity_expansion_combo

- **IC:** +0.2616 (vs baseline +0.1298 = **+101% boost**)
- **Lift vs vol_expansion alone:** +0.0862
- **Consistency:** 11/11 positive years
- **Formula:** amihud_20d_avg rank ≥ 0.80 (top 20% illiquid) AND vol_expansion (top 20% 5d vol change)
- **Source:** derived from gia_lich_su_*_1D.parquet (OHLCV), ticker extracted from filename
- **Cross-check vs buy_heavy_expansion:** buy_heavy_expansion IC=0.2105 — illiq_expansion is +0.0511 stronger

### Technical notes
- OHLCV data: 1227 per-ticker parquet files under data/stock/gia_lich_su_*_1D.parquet
- Ticker extracted from filename: gia_lich_su_AAA_1D.parquet → ticker=AAA
- OHLCV columns: ['time', 'open', 'high', 'low', 'close', 'volume'] — no ticker column inside files
- Amihud = |daily_return| / (turnover_billions_VND) with 20d rolling average
- Imbalance from order_stats for cross signal check

### Next step
H464: time_of_day_pattern (VN T+2 settlement / Monday effect / month-end). Check data availability first.

## H463 summary
- PASSED — NEW SIGNAL C23: illiquidity_expansion_combo
- ic: 0.2616, lift: +0.1318 vs baseline, 11/11 positive years
- panel rows: 809019, states evaluated: 11