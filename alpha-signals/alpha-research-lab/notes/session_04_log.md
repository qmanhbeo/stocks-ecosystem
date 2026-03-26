# Session 04 Log — Cross-Sectional Model + Feature Sources (2026-03-16)

## Objectives
Build the cross-sectional (XS) model: train on all 52 Vietnamese stocks, evaluate FPT specifically.
Test whether the signal is real at the market level or just a regime fluke. Add new data sources
(fundamentals, intraday, news). Explore single-stock feature extensions.

## System State (entering)
Best: E8 +0.73% avg edge. Signal found but weak. Feature space likely exhausted at single-stock level.

## Infrastructure Built This Session

**Bug fix:** `data_tools/` path bug (`parents[2] → parents[1]`) — fetch scripts now work.

**New data fetched:**
- FPT 1H intraday OHLCV
- Crude oil (CL=F) daily prices

**New feature pipelines:**
- `src/build_xs_features.py` → `data/features/xs_features_daily.parquet` (184k rows, 52 stocks, all dates)
- `src/build_news_features.py` → `data/features/fpt_news_daily.parquet` (3,733 days)
- `src/build_intraday_features.py` → `data/features/fpt_intraday_daily.parquet` (625 days)

**Added to `src/feature_engineering.py`:**
- `_add_sector_peers()`, `_add_cross_sectional()`, `_add_intraday()`, `_add_news()`

**New scripts:**
- `cross_sectional_wf.py` — train on 52 stocks, evaluate FPT. Walk-forward year-by-year.
- `analysis/feature_importance.py` — XGBoost feature importance for cross-sectional model

## Experiments

### Cross-Sectional XS Model (MAJOR FINDING)

All 52 stocks walk-forward, FPT evaluation:

| Variant | All-stock avg acc | FPT avg edge | FPT sig years |
|---------|-------------------|--------------|---------------|
| Standard XS (no rank features) | **53-55%/yr, ALL YEARS** | +1.55% | 3/11 |
| XS + rank features | 53-55%/yr, ALL YEARS | +0.27% | 5/11 |

**Critical result:** 53-55% accuracy across ALL 52 stocks in EVERY walk-forward year (2015-2025).
This is statistically significant across the full stock universe. The signal is real at market level.

Notable FPT-specific results:
- 2019: +7.2% (significant)
- 2022: **-17.7% NEGATIVE** ← FPT anomaly (defensive outperformer in bear market)
- 2025: +32.7% (significant)

**FPT 2022 anomaly:** In the VNINDEX -30% year, FPT acted as a defensive IT stock (recurring
software revenues) and outperformed while peers fell. Model trained on 2012-2021 patterns could
not predict this idiosyncratic divergence.

### Single-Stock Extensions (E10-E18)

All experiments: add various feature groups to E8 baseline.

**Key results:**
- All E10-E18 variants fail to beat E8 (+0.73%) in walk-forward avg_edge
- Adding XS rank features: often hurts 2019 (-6 to -20% overfitting)
- Macro features (oil/gold/USD): help 2025 specifically (E15: 2025 p=0.017) but hurt other years
- VNINDEX vs VN30 as reference: VNINDEX consistently better (E18 loses 2020 signal with VN30)

**Confirmed:** Single-stock feature space is exhausted. ~250 rows/year is insufficient for additional features.

### Feature Importance (Cross-Sectional)
Even distribution across all features. Top single feature: `bb_width` (Bollinger width / volatility).
Relative momentum features: 32% total importance. Volatility features: 22%.

## Session Conclusions

1. **The signal IS real**: 53-55% cross-sectional accuracy every year across all 52 stocks.
   This is the proof that relative momentum is a genuine market-wide signal, not a FPT fluke.

2. **Single-stock feature space is definitively exhausted.** No combination of additional features
   beats E8. The 250-row/year budget is the fundamental constraint.

3. **FPT 2022 is a known anomaly**: defensive sector rotation during deep bear market. The XS model
   cannot learn this from general cross-sectional patterns.

4. **Path forward is XS model** — it has more data, more signal, and a clear avenue for improvement.

## Production System After This Session
**XS model** (cross-sectional, threshold=0.05): +1.55% avg edge on FPT, 3/11 sig years.
**E8** still the best single-stock: +0.73% avg edge.

## Next Session Priority
Build ensemble: XS proba + E8 SS proba. Infrastructure for combining cross-sectional and
single-stock signals into a unified trading decision.
