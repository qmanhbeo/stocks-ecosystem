# Session 11 Log — New Data + Banking Sector XS Model (2026-03-17)

## Objectives
1. Expand macro data coverage (9 new global tickers).
2. Add quarterly fundamentals for all 52 stocks (H29 prerequisite).
3. Add dividend calendar for all 52 stocks (H31 prerequisite).
4. H29: XS barrier model + quarterly fundamentals as training features.
5. H31: XS barrier model + dividend calendar features.
6. H30: Expanded macro regime sweep with 15 new global indicators.
7. H28: Banking-sector-only XS model for the H23 portfolio.

## System State (entering)
Best portfolio: H27 +19.23%, Sharpe 2.80. Best FPT: H26 +23.97%, Sharpe 2.04.

## New Data Fetched This Session

Via yfinance (9 new tickers):
- SP500 (^GSPC), EEM (emerging markets ETF), HYG (high yield bonds)
- TLT (long-term treasuries), KOSPI (^KS11), TAIEX (^TWII)
- BTC-USD (Bitcoin), EWH (Hong Kong ETF), US3M (^IRX, 3-month T-bill)

Via vnstock (all 52 stocks):
- `data/features/xs_fundamentals_daily.parquet` — 162k rows, quarterly EPS/P/E/ROE for all stocks
- `data/features/xs_dividend_calendar.parquet` — 174k rows, dividend events for all 52 stocks

Extended `macro_regime_daily.parquet`: 17 → 31 columns (added SP500, KOSPI, TAIEX, BTC, HYG,
TLT, EEM, US3M, yield curve spread)

## Experiments

### H29 — XS Barrier + Quarterly Fundamentals as Training Features

**Hypothesis:** Adding per-stock quarterly EPS/P/E/ROE to XS training gives the model
fundamental information about which stocks are cheaper/growing faster.

**Implementation:** Merged `xs_fundamentals_daily.parquet` into XS training data. New proba file
saved. Ensembled with E32 + H22 filters.

**Result: FAILED. +6.07% XS raw, +11.55% ensemble (vs H22 baseline +15.13%).**

**Why it fails:** Accounting data is already priced in. Quarterly data updates slowly — the
model confuses "stock with high P/E last quarter" with "stock that will outperform next week."
The cross-sectional signal lives in price dynamics, not valuation levels.

### H31 — XS Barrier + Dividend Calendar Features

**Hypothesis:** Stocks with upcoming dividends may show predictable relative price behavior
(ex-dividend effects, institutional positioning).

**Implementation:** Merged `xs_dividend_calendar.parquet` into XS training. Days_to_dividend,
days_since_dividend, pre_div window features.

**Result: FAILED. +5.94% XS raw, +9.51% ensemble.**

**Why it fails:** Adding features to a model trained on ~50-100 observations/stock/year causes
overfitting. The dividend calendar adds noise, not signal, at weekly resolution.

**General pattern confirmed (F24):** Adding training features consistently hurts. Macro regime
filters (post-hoc trade gates) consistently help. The XS model's feature space is essentially
saturated at the current price-momentum feature set.

### H30 — Expanded Macro Sweep (15 New Global Indicators)

**Framework:** Apply all 31 macro regime columns as post-hoc trade gates to both H22 (FPT)
and H23 (portfolio).

**FPT new winners:**
- `taiex_mom_20d >= 0%`: +19.06% avg (4 years) — TAIEX as signal for FPT tech sentiment
- `yield_curve >= -0.5pp`: +17.02% avg (6 years) — non-inverted yield curve = stable regime

**H23 portfolio new winners:**

| Filter | Avg Edge | Sharpe | Sig Years | 2022 |
|--------|----------|--------|-----------|------|
| `taiex_mom_20d >= 3% + kospi_mom_20d >= 0%` | +20.94% | **3.72** | 11/11 | +20.08% |
| `btc_mom_20d >= 10%` | +21.35% | — | 10/11 | +20.74% |
| `btc + kospi + breadth>=3` (combined) | +21.96% | **2.63** | 11/11 | +22.26% |

**New H23 champion:** `taiex_mom_20d >= 3% + kospi_mom_20d >= 0%` → +20.94%, Sharpe 3.72,
11/11 sig years. The Asian equity momentum filter captures the same "risk-on" regime that makes
Vietnamese banking stock relative momentum most reliable.

### H28 — Banking-Sector-Only XS Model

**Hypothesis:** A sector-specific model trained only on banking stocks (~11 tickers) may produce
sharper probabilities for the H23 banking-heavy portfolio than the full 52-stock model.

**Implementation:** Added `--ticker-subset` flag to `cross_sectional_wf.py`. Ran with the 11
banking tickers. Generated per-ticker probas, built top-5 banking portfolio.

**Results:**

Per-ticker (banking model):
| Ticker | Edge | Sharpe |
|--------|------|--------|
| EIB | +18.84% | 2.63 |
| STB | +16.17% | — |
| SHB | +15.29% | — |
| BID | +14.16% | — |

Banking model vs full model: slightly WORSE on most tickers. Full 52-stock context helps
the model calibrate relative rankings better than the sector-only view.

**Best banking model result** (btc + kospi + breadth):
+22.66% avg, Sharpe 2.44, 11/11 sig years, 2022=+26.97%

**Conclusion:** Banking sector model ≈ full model in final results. The full 52-stock model
is preferred (more context, more training data per year).

## Session Conclusions

1. **Adding training features consistently hurts** (H29, H31). The XS model feature space is
   saturated. Further improvements must come from post-hoc filters or architecture changes.

2. **TAIEX + KOSPI is the new H23 portfolio champion**: Sharpe 3.72, 11/11 sig years.
   Asian equity momentum is a strong regime indicator for Vietnamese banking stocks.

3. **BTC momentum is surprisingly powerful**: +21.35% avg, 10/11 sig years. BTC in risk-on
   correlates with Vietnam banking stock relative momentum — institutional risk appetite signal.

4. **Banking-sector XS model ≠ improvement**: Full 52-stock model is better due to broader context.

## Production System After This Session
**H23 + TAIEX/KOSPI filter**: +20.94%, Sharpe 3.72, 11/11 years ← new portfolio champion
**H26 (FPT + macro)**: +23.97%, Sharpe 2.04 ← still FPT champion

## Next Session Priority
Model architecture sweep for H22 (FPT-only): try Random Forest, ExtraTrees, MLP, depth=5 XGB.
VIX band optimization: is VIX [15,30] better than [18,35]?
