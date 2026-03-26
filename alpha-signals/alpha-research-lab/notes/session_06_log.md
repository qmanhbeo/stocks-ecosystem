# Session 06 Log — Ensemble Breakthrough + Data Audit (2026-03-16)

## Objectives
Build XS + E8 ensemble (X3). Find the best regime filter for when to trust confident predictions.
Full audit of available external data (yfinance, vnstock).

## System State (entering)
Best: E8 +0.73% single-stock. X2 (XS confident): +3.87%. Ensemble infrastructure ready.

## Infrastructure Built This Session
- `analysis/meta_analysis.py` — VIX/vol regime analysis of ensemble predictions
- `data_tools/fetch_fundamentals.py` — FPT quarterly EPS/P/E/ROE from vnstock
- `data_tools/fetch_fred_macro.py` — Vietnam macro from FRED
- `data_tools/fetch_fx_commodities.py` (expanded) — 26/27 global tickers via yfinance

## Experiments

### E29 — FPT Fundamentals (EPS, P/E, ROE)
- 54 quarters of FPT quarterly financials now available
- Result: **-1.77% avg edge** — FAILED
- Why: quarterly data is too slow-moving (already priced in). No additive signal at daily resolution.

### E30 — Global Risk Features (VIX, Shanghai, HSI)
- Added VIX, Shanghai Composite, HSI as daily features to E8
- Result: **-2.81% avg edge** — FAILED
- Why: too many features for ~250 rows/year. Severe overfitting.

### X3 — Ensemble (XS + E8, min-conf=0.55)

**Result: +10.28% avg edge** ← BREAKTHROUGH

| Year | Trades | Edge |
|------|--------|------|
| 2019 | — | — |
| 2020 | — | — |
| 2021 | — | **-4.25%** ← problem year |
| 2022 | — | — |
| 2023 | — | **-7.42%** ← problem year |
| 2024 | — | +39.20% |
| 2025 | — | +27.71% |
| Avg | ~34/yr | **+10.28%** |

X3 selects days where BOTH models agree with ≥55% confidence → 62% confident accuracy vs 55% for XS alone.

**Problem:** 2021 (-4.25%) and 2023 (-7.42%). Root cause: XS model alone is +8.46% in 2021,
but E8 is bad (-4.4% in 2021). The agree-only filter selects days where both models agree —
in 2021, they agree on being wrong.

### X4 — XS + Global Macro Ensemble
- Result: +0.51% avg edge — worse than X3. Global macro features in SS model overfits badly.

### X5 — X3 + VNINDEX Trend Filter (5%)
- Result: +3.52% avg edge — worse than X3. Trend filter removes good years.

### X6 — X3 with xs_weight=0.7 (upweight XS signal)
- Result: +6.91% avg edge — worse than X3. Equal weighting is better.

### X8 — X3 + VIX ≥ 18 Filter + agree-only
- Result: **+8.76% avg edge**
- Removes low-VIX days where signal is unreliable (VIX<18 = complacent market)
- ~31 trades/year, +5.62% per trade

### Meta-Analysis Results
- VIX > 26.6: +5.9% edge (good regime)
- FPT 60d relative return > 15%: +10.6% edge
- **VIX regime is the strongest meta-predictor**

### Data Audit Summary
- yfinance: 26/27 global tickers available (DXY missing). VIX, US10Y, Shanghai, HSI, Nikkei,
  gold, oil, copper, CNY, VNM ETF all available.
- vnstock: 54 quarters FPT fundamentals (EPS/P/E/ROE/margins) → `data/features/fpt_fundamentals.parquet`

## Session Conclusions

1. **Ensemble beats any individual model**: X3 (+10.28%) vs XS alone (+3.87%) vs E8 (+0.73%).
   The agree-only confidence filter is the key — selects days where both models are sure.

2. **2021 and 2023 are the remaining problem years**: both models agree on wrong direction.
   No regime filter tested improves 2021/2023 without hurting other years.

3. **VIX is the strongest external predictor**: VIX>18 = reliable signal. Low VIX = complacency,
   model predictions unreliable.

4. **Adding features to E8 consistently hurts**: fundamentals and global macro both overfit.

## Production System After This Session
**X8** (XS + E8 ensemble, VIX≥18, agree-only, min-conf=0.55): **+8.76% avg edge**, ~31 trades/yr.

## Next Session Priority
Triple barrier labels for E8 SS component (E32). The standard direction labels add noise —
1.0% barrier labels may improve 2021 specifically.
