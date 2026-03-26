# Session 03 Log — New Data + Relative Momentum Discovery (2026-03-16)

## Objectives
Add multi-stock and macro data. Test market-relative target (does FPT outperform VNINDEX?)
to remove absolute drift bias. Find if any signal exists in relative momentum.

## System State (entering)
OHLCV exhausted. No signal found. Need new features and better target definition.

## New Data Added
- 55 Vietnamese stocks OHLCV parquet files → `data/stock/`
- FX: USD/VND
- Commodities: gold
- News: 706k Cafef.vn articles → `data/news/`

## Infrastructure Built
- Added `future_rel_dir_5d` target: binary, does FPT outperform VNINDEX over 5d?
- Phase 3b OHLCV indicators: candle patterns, stochastic %K/%D, Williams %R, ADX/DI, historical vol, CCI
- Added to `src/feature_engineering.py`: market-relative lag features, macro features

## Experiments

### Phase 3b — Remaining OHLCV Exhaustion

| Config | Features | verdict |
|--------|----------|---------|
| D1 | Candle patterns | No edge |
| D2 | Stochastic + WilliamsR + CCI | No edge |
| D3 | Historical volatility | No edge |
| D4 | All OHLCV (34 features) | No edge, collapses to drift |

OHLCV exhaustion confirmed completely.

### Phase 4 — Market-Relative / Cross-Asset (E-series, rel_dir_5d target)

| Config | Features | avg_wf_edge | sig_years | notes |
|--------|----------|-------------|-----------|-------|
| E1 | Market-relative lags | — | — | Val only, established framing |
| E2 | Macro (USD/VND, gold) | — | — | Val only |
| E3 | All features + rel_dir target (clf) | -1.89% | 2/7 | 2020: +10.32%, 2025: +7.26% |
| E4 | All features + rel_return target (reg) | **+0.74%** | 2/7 | 2020: +8.73%, 2025: +12.90% |
| E5 | Relative lags only | +0.11% | 1/7 | 2020: +7.94% |
| E6 | Rel lags + abs FPT lags | -0.87% | 1/7 | Abs lags hurt |
| E7 | Tech only (rel_dir target) | -1.43% | 0/7 | Tech alone = no signal |
| E8 | Rel lags + tech | **+0.73%** | 1/7 | 2020 sig, 2025 borderline p=0.056 |
| E9 | Rel lags + tech + 60/120d lags | -1.95% | 1/7 | Longer lags hurt |

## Key Findings

1. **Relative momentum (FPT vs VNINDEX, 1-20d lags) = the only real signal.** Absolute OHLCV
   features are noise; relative position to the market is predictive.

2. **2020 signal is the most robust**: appears in every config with relative lags. Likely COVID
   regime flip — FPT dramatically reversed direction relative to market peers.

3. **2025 signal**: fragile, borderline, only in full feature sets.

4. **Best model: E4** (regression, all features, rel_return_target) — avg +0.74%, 2/7 sig.
   **E8** (rel_lags + tech, classifier) — avg +0.73%, 1/7 sig, simpler.

5. **Adding features beyond E8 hurts**: longer lags, absolute FPT lags, and tech-only all regress.
   The ~250 rows/year budget makes single-stock feature space essentially exhausted at E8.

## Session Conclusions
Relative momentum is the core signal. Single-stock feature space is exhausted at E8 (+0.73% avg).
The signal is regime-dependent (fires strongly in 2020 COVID flip; borderline in other years).
Path forward: cross-sectional model using all 52 stocks → 52× more data per year.

## Production System After This Session
**E8**: +0.73% avg edge (walk-forward 2019-2025). Weak but the best single-stock result.

## Next Session Priority
Build cross-sectional model: train on all 52 VN stocks, evaluate on FPT. More data per year
should reveal whether the signal is real or regime-specific.
