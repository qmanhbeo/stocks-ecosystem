# Distilled Scientific Findings
_Permanent record. Only add conclusions you are confident in. Do not delete — annotate if overturned._

---

## F1: The Drift Problem (confirmed 2026-03-16)
FPT stock has a strong upward price drift that varies dramatically across periods:
- Train (2016-2023): 5d positive rate = 56.6%
- Val (2023-2024): 5d positive rate = **59.3%** (strong bull market)
- Test (2024-2026): 5d positive rate = **46.7%** (bearish period)
- 1d returns: near 50% in ALL periods (~49-51%) — near-balanced at daily horizon

**Implication:** Raw direction accuracy is misleading. A model predicting "always up" scores 59% on val
for free. The real metric is `edge_over_naive = dir_acc - naive_dir_acc`.

**Signal threshold:** edge_over_naive > 2% AND pval_vs_naive < 0.05 = genuine signal.

---

## F2: Standard OHLCV Technical Analysis Has No Edge (confirmed 2026-03-16)
Tested exhaustively across 13+ experiments and walk-forward validation (2019-2025, 7 years):

| Feature group | avg_wf_edge | sig_years | verdict |
|---|---|---|---|
| Lag returns (1-60d) | +0.00% | 0/7 | Collapses to drift |
| MA distances (5-100d) | ~+0.55% | 0/7 | Not significant |
| RSI + MACD + BB + ATR | -0.80% | 0/7 | Worse than naive |
| Volume signals | -0.27% | 0/7 | Negative |
| All combined | 0.00% | 0/7 | Collapses completely |
| 1d returns (all features) | -0.17% | 0/7 | Random noise |
| Balanced classifier (AUC) | 0.46 | — | Anti-predictive |

**Conclusion:** FPT at 1d/5d daily resolution is consistent with weak-form EMH when using only
OHLCV-derived features. Standard technical analysis does not work here.

---

## F3: Val/Test Regime Mismatch (confirmed 2026-03-16)
The fixed 70/15/15 train/val/test split puts val in 2023-2024 (bull) and test in 2024-2026 (bear).
Any model that learns "be bullish" scores well on val but fails on test.

**Implication:** Walk-forward validation (year-by-year) is more reliable than the fixed split
for evaluating whether a signal is real or regime-specific.

**Walk-forward tool:** `walk_forward.py --config configs/X.json` (logs to `wf_results.jsonl`)

---

## F4: Market-Relative Target Removes Drift Bias (confirmed 2026-03-16)
Using `future_rel_dir_5d` (binary: does FPT outperform VNINDEX over 5 days) removes the absolute drift
bias entirely. Walk-forward results are qualitatively more interpretable — naive rate varies by year
between ~29% and ~64%, model must beat THAT rate, not a fixed 50%.

**Partial signal found:** 2/7 walk-forward years are statistically significant (p<0.05 vs drift):
- 2020: +8-11% edge (all feature sets — most consistent, likely COVID regime flip)
- 2025: +7-13% edge (only E3/E4 with full tech indicators — regime-specific)

**Experiment hierarchy (avg_edge, 7yr walk-forward):**

| Config | Features | avg_edge | std | sig_yrs |
|---|---|---|---|---|
| E4 | all features, regression | +0.74% | 6.87% | 2/7 |
| E5 | relative lags only | +0.11% | 4.35% | 1/7 |
| E6 | rel lags + abs FPT lags | -0.87% | 5.51% | 1/7 |
| E3 | all features, classifier | -1.89% | 9.06% | 2/7 |

**Key insight:** Absolute FPT price lags ADD noise (E6 worse than E5). Technical indicators (RSI, MACD,
BB, ATR, candle, stoch, ADX, hist_vol) provide the 2025 signal but also inflate variance. Regression
target (E4) is more stable than binary classifier (E3).

---

## F5: Extended OHLCV Still Has No Edge (confirmed 2026-03-16)
Tested all remaining technical indicators on the absolute-return prediction task with walk-forward:
- Candle body/wicks/gap (D1): tested — no edge
- Oscillators: stochastic, Williams %R, CCI (D2): tested — no edge
- ADX trend strength (D3): tested — no edge
- Historical volatility (D3/D4): tested — no edge
- All combined (D4_all_ohlcv, 34 features): no edge, collapses to drift

**Conclusion:** Exhaustive coverage confirms F2. Standard OHLCV technical analysis does not work for
FPT at daily resolution, regardless of which indicators are used.

---

## F6: Ablation Confirms Relative Momentum as Core Signal (confirmed 2026-03-16, Session 3)

E7 (technical indicators ALONE, no lags) → **0/7 sig years**, avg -1.43% edge.
This definitively proves that the 2020/2025 signal in E3/E4 comes from **relative momentum features** (FPT vs VNINDEX excess return lags), not from technical indicators.

**Ablation hierarchy (walk-forward avg_edge):**

| Config | Core features | avg_edge | std | sig |
|---|---|---|---|---|
| E4 | rel+abs lags+tech, regression | +0.74% | 6.87% | 2/7 |
| E8 | rel lags+tech, classifier | +0.73% | 5.81% | 1/7 |
| E5 | rel lags only | +0.11% | 4.35% | 1/7 |
| E6 | rel+abs lags | -0.87% | 5.51% | 1/7 |
| E7 | tech only (no lags) | -1.43% | 2.87% | 0/7 |
| E3 | all features, classifier | -1.89% | 9.06% | 2/7 |

**Key conclusions:**
1. **Relative momentum = core signal driver** (FPT excess returns vs VNINDEX, lags 1-20d)
2. Technical indicators add ~+0.6% avg_edge when combined with rel lags (E8 vs E5), but alone = noise
3. Absolute FPT price lags = noise (E6 worse than E5)
4. Regression target (E4) consistently outperforms binary classifier (E3/E8) with same features
5. 2025 signal is borderline (E8: p=0.056, just misses threshold) — fragile, requires full feature set
6. 2020 signal is robust — appears in E5, E6, E8 (all configurations with rel lags)

---

## F7: Cross-Sectional Model Confirms Signal is Real (confirmed 2026-03-16, Session 4)

Trained XGBoost on ALL 52 Vietnamese stocks simultaneously (157k rows vs FPT's 2.5k).
Features: same E8-style (rel lags + tech), target: `future_rel_dir_5d` for each stock.

**Results (walk-forward 2015-2025):**
- Overall accuracy across all stocks: **53-55% EVERY YEAR** — the relative momentum signal is robust and generalizes across the entire VN market
- FPT-specific: avg +1.55% edge, 3/11 sig years (2019: p=0.0205, 2022: p=0.0000 BUT negative, 2025: p=0.0000 +32.66%)
- The 53-55% overall accuracy is the strongest scientific evidence we have of a real signal

**FPT 2022 anomaly:** Cross-sectional model was significantly WRONG for FPT in 2022 (edge=-17.67%, p=0.0000). In 2022, most stocks with the same momentum pattern underperformed the market, but FPT was an exception (strong defensive IT stock in a crash year). This idiosyncratic behavior makes FPT sometimes unpredictable cross-sectionally.

**Reference index matters:**
- VNINDEX > VN30 as reference for FPT's relative target
- VN30 loses the 2020 signal entirely; VNINDEX preserves it
- This suggests FPT's alpha vs the BROAD market is predictable, not vs its large-cap peers

---

## F8: Additional Feature Source Findings (Session 4)

**Data tools fixed:** `parents[2]` → `parents[1]` in fetch_stock.py and fetch_fx_commodities.py. Scripts now write to correct project directory.

**New data fetched/built:**
- FPT 1H intraday data (2023-09 to 2026-03, 625 trading days)
- Crude oil (CL=F) daily prices added to fx-commodities/
- Pre-built: `data/features/xs_features_daily.parquet` (cross-sectional ranks, 184k rows, 52 stocks)
- Pre-built: `data/features/fpt_news_daily.parquet` (FPT news daily, 3733 days from Cafef)
- Pre-built: `data/features/fpt_intraday_daily.parquet` (1H session features, 625 days)

**Feature group performance (walk-forward, single-stock FPT):**

| Feature addition | vs E8 baseline | Notable |
|---|---|---|
| XS rank features (E10) | -1.65% avg edge BUT captures 2025 (p=0.0038) | Regime-sensitive |
| News sentiment (E11) | -3.31% avg edge | No predictive value |
| Oil + gold + USD macro (E15) | -1.08% but 2025 improved (p=0.0017) | Oil helps 2025 |
| CMG/MWG sector peers (E13) | -2.57% | Hurts |
| XS rank + macro combined (E16) | -2.05%, 2019 disastrous (-12%) | Too many features |
| Long relative lags 60-120d (E9) | -1.68% | Longer lags hurt |
| VN30 as index (E18) | -3.47%, loses 2020 signal | VNINDEX is better |
| Intraday 1H features (E14) | Only 2024-2025 testable, p=0.119 | Limited data |

**Overfitting pattern:** Every feature addition beyond E8 harms 2019 performance (-6 to -20% edge). The model memorizes crisis patterns that don't generalize.

---

## F9: Best Models and Key Conclusions (as of 2026-03-16, Session 4 complete)

**Best single-stock walk-forward performance (7 years, FPT-specific):**
- E4: +0.74% avg, 2/7 sig, std 6.87% — regression on relative return, all features
- E8: +0.73% avg, 1/7 sig, std 5.81% — classifier, rel lags + tech only
- E15: -0.35% avg, 2/7 sig — adds oil/gold/USD macro

**Best cross-sectional walk-forward (11 years, all stocks):**
- X1: 53-55% all-stock accuracy every year, FPT avg +1.55%, 3/11 sig years

**The honest assessment:**
1. Signal is real (cross-sectional confirms) but weak and regime-dependent for FPT specifically
2. Only 2020 (COVID regime flip) and 2025 (bear market) show consistent positive signal for FPT
3. FPT is anomalous vs the cross-section in 2022 (strong outperformer when peers underperformed)
4. No feature combination reliably extracts signal across all market regimes

---

## F10: Open Questions (Session 5+)
1. **Ensemble cross-sectional + single-stock predictions** — could reduce the 2022 FPT anomaly
2. **Regime filter** — only trade when the relative drift is near 50% (when signal fires)
3. **FPT quarterly earnings cycle** — FPT reports earnings quarterly; is there a pre/post-earnings pattern?
4. **Better news NLP** — keyword counting gave avg 1.3 mentions/day; LLM-based sentiment might be more informative
5. **Intraday signal at shorter horizon (1-2 days)** — the 1H data is available but limited to 2.5 years
6. **Different model types** — try LightGBM which handles mixed feature types better; or simple logistic regression for interpretability

---

## F10a: Session 5 — New Signal Directions All Fail to Beat E8 (confirmed 2026-03-16)

Tested 9 new signal directions. **None beat E8 baseline** (avg_edge +0.73%, 1/7 sig):

| Experiment | Hypothesis | avg_edge | sig | 2022 (anomaly) | verdict |
|---|---|---|---|---|---|
| E19 (10d horizon) | Longer prediction = more momentum | -5.13% | 1/7 | -4.0% | **FAILED badly** |
| E20 (20d horizon) | Academic momentum peak 1-12m | -6.35% | 0/7 | +0.0% | **FAILED badly** |
| E21 (Tet calendar) | Pre/post-Tet selling/buying | -1.83% | 2/7 | -0.4% | Overfit 2019 |
| E22 (vol regime) | Signal only fires in high-vol years | -0.87% | 1/7 | -1.2% | Marginal |
| E23 (risk-adj momentum) | Relative Sharpe stable across regimes | -0.52% | 2/7 | **+0.8%** | Improved 2022! |
| E24 (earnings cycle) | Pre/post-earnings FPT drift | -0.18% | 1/7 | +0.0% | Near-baseline |
| E25 (market breadth) | Idiosyncratic signal when breadth low | -0.92% | 2/7 | -0.8% | Marginal |
| E27 (seasonality) | Day-of-week, lunar, quarter effects | -3.85% | 1/7 | +0.0% | Overfit 2019 |
| E28 (full calendar) | Stack all calendar features | -0.47% | 1/7 | -0.4% | Near-baseline |

### Key patterns:
1. **2019 is the overfitting canary** — almost every feature addition makes 2019 worse. E8 baseline is +2.0% in 2019. The best new configs cap 2019 losses (E22=-4%, E23=-4%, E28=-1.6%) vs disasters (E19=-40%, E27=-23.6%).

2. **E23 (risk-adjusted momentum) is the single interesting result**: it fixed 2022 from -7.6% to +0.8% (the anomaly year where FPT diverged from cross-sectional model). But at cost of 2024 collapsing (-6.8% vs +0.4%).

3. **Longer horizons hurt catastrophically**: 10d and 20d are much worse than 5d. The signal operates at weekly timescale (5d) only.

4. **Seasonality/calendar features overfit**: Vietnam has too few market years (7) to learn reliable calendar patterns. Tet, day-of-week, lunar — all look like signal in 2020 but are calendar-coincident, not causal.

5. **X2 (confidence threshold)**: XGBoost cross-sectional model almost never exceeds 60% confidence on FPT. At threshold=0.10, only 6-26 FPT days per year pass the filter, too few for reliable estimation.

### Conclusion:
E8 remains the best single-stock model. The single-stock FPT feature space is **exhausted** at this level of data density (~250 rows/year). The cross-sectional framework (53-55% accuracy, confirmed across all 11 years) is the only validated predictive signal.


---

## F10b: X2 Confidence Threshold — High-Confidence XS Predictions Reveal a New Pattern (2026-03-16)

Running cross-sectional XGBoost with different confidence thresholds on FPT predictions:

| Threshold | Min conf | FPT days/year | Avg FPT edge | Sig years |
|---|---|---|---|---|
| 0.00 (none) | 50% | ~250 | +0.73% | 2/11 (2020,2025) |
| 0.05 | 55% | ~52 | **+3.87%** | 3/11 |
| 0.10 | 60% | ~12 | -7.65% | 0/4 (too sparse) |

**Threshold=0.05 breakdown (most important):**
- 2019: +17.12%* (confident AND correct — 2019 had normal cross-sectional dynamics)
- 2020: **-12.10%** (confident AND WRONG — COVID crash, FPT acted defensively vs model expectation)
- 2021: +8.46% (not significant)
- 2022: **-16.80%*** (statistically significant wrong — FPT defensive tech in bear market, model predicted underperform)
- 2025: **+37.87%*** (largest signal ever observed — 2025 bear market, FPT showed idiosyncratic strength)

### Key insight:
When the XS model is confident it knows where FPT should go, it is:
- **RIGHT** in normal/range-bound market years (2019, 2021, 2024, 2025)
- **WRONG** in broad market crash years (2020 COVID, 2022 bear) — these are the FPT anomaly years where FPT acts as a defensive play against the market

**The anomaly years are identifiable in advance via the vol_regime feature**: 2020 = COVID high-vol, 2022 = gradual bear low-vol. The model being confidently-wrong in high-vol crash years (2020) but correct in other high-vol years (2025) suggests the anomaly is specifically about whether FPT is in a *counter-cyclical defensive* mode.

### Trading implication:
- Trade only when XS model confidence > 55% (~52 days/year, 20% coverage)
- Avg edge on those days: +3.87% over 11 years
- Risk: 2022 shows statistically significant wrong predictions (need to layer vol regime or Tet window as filter)

---

## F11: Ensemble (X3) is the Best Production Candidate (2026-03-16, Session 6)

**X3 = XS model proba + E8 single-stock proba, equal-weight average, min confidence 0.55**

| Year | Confident days | Conf acc | Edge |
|---|---|---|---|
| 2020 | 84 | 60.7% | +10.32% |
| 2021 | 116 | 48.0% | -4.25% |
| 2022 | 15 | 60.0% | -3.86% |
| 2023 | 63 | 49.2% | -7.42% |
| 2024 | 7 | 100.0% | +39.20%* |
| 2025 | 7 | 57.1% | +27.71% |
| **Avg** | **~42/year** | **62.3%** | **+10.28%** |

**Why X3 beats X2 (+3.87%):** The ensemble selects for days where BOTH models agree. This high-agreement filter is stricter than XS alone, but those days have higher edge (62% accuracy vs 55% for XS alone).

**Problem years:**
- 2021 (116 days, -4.25%): Both models confidently predict FPT underperformance, but FPT was in a persistent bull run. XS model ALONE is +8.46% in 2021 — the SS model (E8: -4.4%) corrupts it.
- 2023 (63 days, -7.42%): Similar — recovery year where momentum signal fails.

**Key lesson:** Ensemble's 2021 problem is caused by the SS model, not XS. The XS model alone handles 2021 correctly. The ensemble amplifies bad "confident agreement" days where BOTH models are systematically wrong.

**Weighting experiments (min-conf=0.55):**
- xs_weight=0.5 (equal): avg_edge = +10.28% (best; 2021=-4.25%, 2024=+39.20%, 2025=+27.71%)
- xs_weight=0.9: 2021=+5.45% but 2022=-20.61%; avg_edge = +4.88%
- xs_weight=1.0 (XS only): avg_edge = +4.09% (same as X2)

Equal weighting is still best overall due to high 2024/2025 edges.

---

## F12: Data Sources Available (Session 6 audit)

| Source | Data | Status |
|---|---|---|
| vnstock (VCI) | Vietnamese stock OHLCV, 52+ stocks | ✓ Fetched |
| vnstock finance.ratio | FPT quarterly EPS, P/E, ROE, margins (54 quarters 2007-2025) | ✓ Fetched (fpt_fundamentals.parquet) |
| yfinance | VIX, US10Y, Shanghai, HSI, Nikkei, copper, CNY, VNM ETF (back to 2000) | ✓ Fetched (fx-commodities/) |
| CafeF.vn news | 706k Vietnamese financial news articles | ✓ Available (fpt_news_daily.parquet) |
| FRED API | 330+ Vietnam macro series (interest rates, CPI) | Not yet implemented |
| World Bank API | Vietnam GDP, inflation, trade balance | Not yet implemented |

**Adding global macro to XS model (X4):** avg_edge = +0.51% (worse — global macro not helpful for cross-sectional VN signal)
**FPT fundamentals as features (E29):** avg_edge = -1.77% (overfitting — quarterly data changes too slowly)

---

## F13: VIX Filter Dramatically Improves Ensemble Quality (2026-03-16, Session 6)

**X8 = X3 ensemble + VIX >= 18 filter + agree-only**

| Year | n_conf | Conf acc | Edge |
|---|---|---|---|
| 2020 | 72 | 58.3% | +7.94% |
| 2021 | 46 | 54.3% | **+3.55%** ← was -4.25% |
| 2022 | 15 | 60.0% | -3.86% |
| 2023 | 18 | 55.6% | **-1.07%** ← was -7.42% |
| 2025 | 6 | 66.7% | +37.23% |
| **Avg** | **~31/year** | **59.0%** | **+8.76%** |

**VIX filter rationale:** The ensemble's problem years (2021: VIX=19.8, 2023: VIX=17.1) have LOW/MODERATE US fear index. When global markets are calm (VIX<18), the cross-sectional relative momentum signal becomes unreliable — likely because macro-driven co-movements dominate over idiosyncratic momentum.

**Per-trade quality comparison:**
- X3 (no filter): +1.09% per confident trade, ~49 trades/year
- X8 (VIX>=18): +5.62% per confident trade, ~31 trades/year
- **X8 has 5x better per-trade quality** despite fewer trades

**Meta-analysis insights (from meta_analysis.py):**
- VIX > 26.6 (global stress): +5.9% edge (highest)
- VNINDEX vol 0-31% (local calm): +7.9% edge (good, but only 74 days)
- FPT 60d rel return > 15%: +10.6% edge (FPT momentum strong = reliable signal)
- VIX falling fast (5d ret -8% to -2%): -10.2% edge (worst regime — don't trade into VIX relief)

**Missing (downside of X8):** 2024 had VIX=13.2 (all confident days excluded), missing +39.20% edge on 7 days. But 7 days with 100% accuracy is statistically unreliable anyway.

---

## F14: E32 as Single-Stock Component Dramatically Improves Ensemble (2026-03-16, Session 7)

**Replacing E8 with E32 (triple barrier 1.0%) as the SS component in X3/X8 ensembles:**

### X3-E32 (equal weight, min-conf=0.55):

| Year | n_conf | Conf acc | Edge |
|---|---|---|---|
| 2019 | 65 | 69.2% | +10.03% |
| 2020 | 64 | 62.5% | +12.10% |
| 2021 | 155 | 51.6% | +0.81% |
| 2022 | 104 | 52.9% | -10.97%* |
| 2024 | 75 | 56.0% | -4.80% |
| 2025 | 21 | 76.2% | +46.75%* |
| **Avg** | | | **+8.99%** |

### X8-E32 (VIX>=18, agree-only, min-conf=0.55) — **BEST RESULT EVER**:

| Year | n_conf | Conf acc | Edge |
|---|---|---|---|
| 2019 | 7 | 71.4% | +12.23% |
| 2020 | 53 | 64.2% | +13.75% |
| 2021 | 56 | 60.7% | **+9.91%** ← was -4.25% |
| 2022 | 69 | 47.8% | -16.03%* |
| 2024 | 12 | 91.7% | **+30.87%*** ← was N/A |
| 2025 | 8 | 62.5% | +33.06% |
| **Avg** | **~34/year** | **66.4%** | **+13.96%** |

**vs X8-E8:** +13.96% avg edge (was +8.76%). 2021 fix is the key: +9.91% vs +3.55%.

**Why E32 fixes 2021:** Triple barrier (1.0% threshold) removes ambiguous near-zero samples. In 2021 (persistent bull run), most 5d FPT-vs-VNINDEX returns were near zero (not clearly positive or negative). E8 trained on these noisy labels got confused; E32 only trains/predicts on days with clear directional signals → avoids the "persistent mild outperformance" that the standard classifier misreads.

**New 2022 problem:** With E32 as SS, 2022 gets worse (-16.03%* vs -3.86%). Both XS and E32-SS agree on wrong predictions in 2022. This is the structural bear market year problem: VNINDEX fell ~30%, idiosyncratic relative momentum broke down, both models systematically misjudge direction.

**Remaining open problem:** 2022 cannot be fixed by VIX filter alone (VIX was elevated but not extreme in 2022, Ukraine war). Need a **market trend filter** — only trade when VNINDEX itself is not in a severe bear trend.

---

## F15: H11 — XS 10d Horizon Has Too Much Variance to Be Useful (2026-03-16, Session 7)

Ran cross-sectional walk-forward with `future_rel_dir_10d` target (threshold=0.05):

| Year | n_conf | FPT acc | Edge |
|---|---|---|---|
| 2015 | 67 | 74.6% | +20.19%* |
| 2016 | 42 | 38.1% | -8.12% |
| 2017 | 109 | 47.7% | -6.29% |
| 2018 | 86 | 54.7% | +5.05% |
| 2019 | 30 | 76.7% | +6.27% |
| 2020 | 60 | 26.7% | **-31.27%*** |
| 2021 | 23 | 87.0% | **+34.16%*** |

**Conclusion: Failed hypothesis.** The 10d horizon shows extreme variance — +34% in 2021 and -31% in 2020 in consecutive years with small sample sizes (23-60 confident days). The signal degrades over longer horizons: more noise accumulates, spurious confident predictions hurt when wrong. The 5d horizon remains optimal.

**Why 2020 is catastrophic:** COVID crash played out quickly (within 5d); at 10d, the model sees FPT continuing to "underperform" relative momentum patterns that collapsed, but FPT actually recovered faster than market — so 10d direction was consistently wrong.


---

## F16: VNINDEX Trend Filter Improves 2020 but Cannot Fix 2022 (2026-03-16, Session 8)

**H16:** Add a VNINDEX N-day trend filter to ensemble_wf.py. Skip trades when VNINDEX return over the window is below threshold (avoid sustained bear markets).

**Result: X9 = X8-E32 + VNINDEX 60d >= -5%**

| Config | 2020 n | 2020 edge | 2022 n | 2022 edge | Avg edge |
|--------|--------|-----------|--------|-----------|---------|
| X8-E32 (no filter) | 53 | +13.75% | 69 | -16.03%* | +13.96% |
| +60d >= -5% (X9) | 28 | +35.32%* | 32 | -20.11%* | +16.88% |

**Filter helps 2020:** Removes COVID crash days (VNINDEX 60d return -25%), keeps only the recovery. 2020 improves from +13.75% to +35.32%*.

**Filter cannot fix 2022:** As filter tightens, 2022 edge gets WORSE (-16% -> -20% -> -26%). The filter removes Jun-Aug 2022 where the model actually works (82-83% acc) and keeps Feb-Mar 2022 where the model is wrong 100% of time. Root cause: the 2022 problem is a "defensive rotation" regime in early 2022 - not a VNINDEX trend state issue.

**Best X9 Sharpe: ~0.88. Avg edge: +16.88%.**

---

## F17: XS Triple Barrier Labels Fix 2022 — Best Risk-Adjusted System (2026-03-16, Session 8)

**H17:** Retrain XS cross-sectional model with triple barrier 1.0% labels. This removes ambiguous small-move days from XS training, making the model less confident about near-zero relative movements.

**Result: H17 base = barrier XS + E32, no VN filter**

| System | 2022 edge | Avg Edge | Sharpe |
|--------|-----------|----------|--------|
| X9 (std XS + VN60 filter) | -20.11%* | +16.88% | ~0.88 |
| H17 base (barrier XS, no filter) | -2.07% | +15.22% | ~1.42 |

**Mechanism:** Feb-Mar 2022 "defensive rotation" — FPT outperformed by 0.1-0.9% (small moves). Standard XS trained on these as "confident UP signals" which create false confidence. Barrier XS never learned these near-zero days -> uncertain on 2022 early dates -> prob ~0.5 -> no trade.

**Key negatives of VN60 filter with H17:** Adding VN60 filter to H17 makes 2022 worse (-2% -> -8%) by removing good late-2022 trades. The barrier XS handles 2022 internally; the filter is redundant and harmful.

**Combining std+barrier XS by averaging does not work:** Averaging dilutes the barrier's confidence-suppression. Combined 2022 edge returns to -17%.

**H17 base is recommended for risk-sensitive use.** X9 has higher raw avg edge (+16.88% vs +15.22%) but ~5x worse catastrophic risk in 2022. H17 has better Sharpe (1.42 vs 0.88), more trades (~35/yr vs ~23/yr), no external filter needed.

---

## F18: H24 Failed — XGBoost Outperforms LightGBM for XS Barrier Model (2026-03-17, Session 9)

**H24:** Replace XGBoost with LightGBM in the XS cross-sectional model (barrier 1.0% labels), then ensemble with E32 + H22 filters.

| System | 2022 edge | 2025 edge | Avg Edge | Verdict |
|--------|-----------|-----------|----------|---------|
| H22 (XGBoost barrier XS + E32) | -2.07% | +20.85% | +15.13% | Production |
| H24 (LightGBM barrier XS + E32) | -4.71% | -2.96% | +11.10% | **FAILED** |

LightGBM degrades 2022 (from -2.07% to -4.71%) and catastrophically kills 2025 (from +20.85% to -2.96%). The XGBoost implementation with these hyperparams (max_depth=3, lr=0.05, early stopping on last 12% of train) is better suited for this dataset.

**Conclusion:** XGBoost remains the XS model. LightGBM is not a drop-in improvement here.

---

## F19: H25 Direction Breakdown — 2022 Residual Comes Entirely from DOWN Predictions (2026-03-17, Session 9)

**H25:** Break H22's confident trades into UP (predict FPT outperforms) vs DOWN (predict FPT underperforms) per year.

**H22 full year-by-year breakdown:**

| Year | n_UP | UP_edge | n_DOWN | DOWN_edge | Total_edge |
|------|------|---------|--------|-----------|-----------|
| 2019 | 0 | — | 6 | +26.53% | +28.91% |
| 2020 | 8 | +12.10% | 44 | +20.06% | +18.83%* |
| 2021 | 16 | +30.45% | 56 | +11.70% | +15.87%* |
| 2022 | 40 | **+6.77%** | 33 | **-12.78%** | -2.07% |
| 2023 | 4 | +22.79% | 5 | -12.21% | +3.35% |
| 2024 | 8 | +20.20% | 4 | +20.20% | +20.20% |
| 2025 | 3 | +63.71% | 4 | -11.29% | +20.85% |

**Key finding:** The 2022 residual (-2.07%) is entirely from DOWN predictions (n=33, acc=45.5%, edge=-12.78%). UP predictions in 2022 are actually +6.77% — the model correctly identifies FPT outperformance days.

**Root cause:** In 2022 "defensive rotation" (esp. Feb-Mar), FPT consistently outperformed VNINDEX even when cross-sectional momentum predicted underperformance. DOWN signals = "FPT will underperform" = systematically wrong in this regime. The barrier XS already abstains on near-zero small-move days, reducing this problem vs standard XS; the residual -2% is from higher-confidence DOWN signals that are still wrong.

**2025 pattern:** DOWN predictions also bad (-11.29%*, n=4). UP predictions excellent (+63.71%, n=3 — small sample). Pattern consistent: FPT's defensive/idiosyncratic behavior makes DOWN signals unreliable.

**Implication for future:** A "block-DOWN-when-VNINDEX-downtrend" rule would fix 2022 at the cost of overfitting. Not recommended for implementation without 2026 validation.

---

## F20: H23 Multi-Stock Portfolio — The Real Signal is Across ALL VN Stocks, Not FPT (2026-03-17, Session 9)

**H23:** Save XS barrier model probabilities for ALL 52 Vietnamese stocks, rank by signal quality, build a top-5 portfolio.

**Top 5 tickers by avg edge (XS barrier, threshold=0.05, NO additional filters):**

| Ticker | Avg Edge | Sharpe | Sig Years |
|--------|----------|--------|-----------|
| EIB (Eximbank) | +19.12% | 2.93 | 10/11 |
| STB (Sacombank) | +18.93% | 1.82 | 10/11 |
| POW (PetroVietnam Power) | +18.76% | 1.68 | 6/8 |
| MSN (Masan Group) | +18.58% | 1.75 | 8/11 |
| BID (BIDV Bank) | +18.50% | 1.31 | 7/11 |

**FPT for comparison:** +2.70% avg edge, Sharpe 0.24, 4/11 sig years.

**Top-5 portfolio (equal-weight, ~500 trades/year across 5 stocks):**
- Avg edge: **+21.94%**, Sharpe **2.54**
- ALL 11 years positive (2015–2025), ALL 11 years statistically significant (p<0.05)
- 2022 edge: **+15.71%*** — the portfolio has no 2022 problem!

**Why these stocks?** EIB, STB, BID are banking stocks that follow cross-sectional relative momentum more reliably. FPT is a defensive IT stock that diverges from cross-sectional patterns in bear markets. Banking stocks co-move with the broad market; their relative returns are more predictable by the XS model.

**Critical caveat (contamination):** Stock selection was performed post-hoc by observing 2015–2025 results. This is the same validation-set contamination flagged in `session9_methodology_concerns.md`. The top-5 list may be optimistic. True validation requires 2026 data.

**Scientific value regardless:** Even if the exact stock ranking shifts, the finding that FPT is anomalously hard to predict (Sharpe 0.24 vs field average ~1.2) is robust. The session 1–9 focus on FPT may have been suboptimal; the XS model's general signal is strongest elsewhere.

---

## F21: VIX Momentum + Copper/Gold Ratio are the Key Missing Macro Filters (2026-03-17, Session 10)

**H26:** Sweep of 17 composite macro regime indicators as filters on H22.

**New data built:** `data/features/macro_regime_daily.parquet` — composite indicators from all available FX/commodity data:
- VIX momentum (5d, 20d), VIX vs 60d MA
- US 10Y yield level + 20d change
- VNM ETF vs VNINDEX divergence (5d, 20d) — foreign investor flow signal
- Copper/Gold ratio + 20d momentum — risk appetite proxy
- VND/USD 20d momentum
- Multi-asset breadth score (0-6): count of Shanghai/HSI/Nikkei/Oil/Copper/VNM ETF in 20d uptrend
- News surge and total articles 5d MA

**Top single filters on H22 (baseline: +15.14%, Sharpe 1.52, 2022=-2.07%):**

| Filter | Avg Edge | Sharpe | 2022 | Trades/yr |
|--------|----------|--------|------|-----------|
| vix_mom_5d >= -5% | +23.84% | 1.45 | +5.66% | 23 |
| vix_mom_5d >= -8% | +21.15% | 1.41 | +2.18% | 27 |
| cu_gold_mom_20d >= 0% | +19.18% | 1.20 | -3.69% | 29 |
| vnm_vs_vni_20d >= 0% | +18.94% | **2.20** | +18.69% | 18 |

**Best combinations on H22:**

| Combination | Avg Edge | Sharpe | 2022 | Trades/yr |
|-------------|----------|--------|------|-----------|
| vix_mom_5d>=-8% AND cu_gold_mom>=0% | **+23.97%** | 2.04 | **+12.36%** | 20 |
| vix_mom_5d>=-5% (single) | +23.84% | 1.45 | +5.66% | 23 |
| vix_mom_5d>=-8% AND us10y_mom<=+0.5pp | +22.19% | 1.53 | +13.99% | 25 |
| vix_mom_5d>=-8% AND vnm_vs_vni>=0% | +24.80% | **3.98** | +16.77% | 15 (sparse) |

**Key insight — VIX momentum mechanism:** When VIX drops sharply (>8% in 5 days), global fear is rapidly dissipating. This "calm after storm" regime is when the cross-sectional relative momentum signal fails for FPT — all stocks recover together in a correlated bounce, and idiosyncratic relative predictions become noise. In early-2022 specifically, VIX fell in March-April after the Ukraine shock; that's exactly when H22 makes its bad predictions.

**Key insight — Copper/Gold mechanism:** Rising Cu/Gold ratio = industrial demand beating safety demand = genuine risk appetite. When Cu/Gold is falling (gold outperforming copper), markets are in defensive mode and cross-sectional momentum breaks down. The combination of "fear not dissipating" AND "genuine risk appetite" selects the highest-quality momentum regimes.

**Critical caveat:** All filter thresholds were chosen by sweeping 2015–2025. Same contamination as all prior experiments. Economic logic is sound but specific threshold values are data-fitted.

---

## F22: VNM ETF Divergence + Multi-Asset Breadth Improve H23 Portfolio (2026-03-17, Session 10)

**H27:** Same macro regime sweep applied to H23 top-5 portfolio (EIB/STB/POW/MSN/BID).

The H23 portfolio baseline is already very strong (+18.83%, Sharpe 2.49, 11/11 sig years). Macro filters provide modest but principled improvements:

| Filter | Avg Edge | Sharpe | 2022 | Trades/yr |
|--------|----------|--------|------|-----------|
| BASELINE | +18.83% | 2.49 | +13.94% | 559 |
| vnm_vs_vni_20d >= 0% | +20.61% | 2.43 | +18.96% | 225 |
| breadth_score >= 3 | +18.99% | **2.75** | +14.86% | 369 |
| cu_gold_mom_20d >= -5% | +19.31% | 2.59 | +15.12% | 458 |
| **vnm_vs_vni>=-5% AND breadth>=3** | +19.23% | **2.80** | +16.08% | 346 |
| vnm_vs_vni>=0% AND breadth>=3 | +20.62% | 2.74 | +20.74% | 172 |
| vnm_vs_vni>=0% AND breadth>=3 AND cu_gold>=-5% | **+20.79%** | 2.53 | **+21.60%** | 151 |

**Best balance** (Sharpe 2.80, adequate trade count): `vnm_vs_vni_20d >= -5% AND breadth_score >= 3`
- 346 trades/year across 5 stocks (~69/stock/year)
- All 11 years positive, all significant

**VNM ETF mechanism:** When foreign investors have been roughly in line with domestic investors (VNM ETF 20d return within -5% of VNINDEX), cross-sectional relative momentum signals are more reliable. Foreign institutional flows drive the cross-sectional patterns the model is learning.

**Breadth mechanism:** When 3+ of the 6 major global assets (Shanghai, HSI, Nikkei, Oil, Copper, VNM ETF) are in 20d uptrend, global macro tailwind supports cross-sectional momentum. In correlating bear markets, breadth collapses and momentum signals fail — but banking stocks (the top-5) are less impacted than FPT.

---

## F23: H29 — Cross-Sectional Quarterly Fundamentals Do NOT Improve XS Model (2026-03-17, Session 11)

**What we tested:** Added P/E rank, EPS YoY rank, ROE rank, NPM rank, Debt/Equity rank (from `xs_fundamentals_daily.parquet`) as features to the XS barrier model (40 features total vs 35 baseline).

**Result:** H29 fundamentals XS gives FPT avg edge +6.07% (3/11 sig years). Running through H22 ensemble gives **+11.55% vs H22's +15.13%** — fundamentals-based XS model is worse.

**Why:** Quarterly accounting data (45-day lag after quarter end) is already priced in by the time signals are generated. Cross-sectional momentum (5-20d relative price returns) already captures much of what fundamentals signal. Adding noisy accounting ranks as features dilutes the technical signal, especially since many tickers have missing/NaN fundamentals in early years.

**Conclusion:** Use the standard barrier XS model (no fundamentals) for all ensemble work.

---

## F24: Asian Tech Cycle (TAIEX + KOSPI) is the Strongest New Macro Regime Filter (2026-03-17, Session 11)

**What we found:** Extended macro sweep (`h30_expanded_macro_sweep.py`) with 15 new global indicators (SP500, yield curve, HYG/TLT, EEM, KOSPI, TAIEX, BTC, credit_risk_on) found:

**H22 (FPT) — new filters (standalone):**
| Filter | avg_edge | Sharpe | Years | 2022 |
|--------|----------|--------|-------|------|
| taiex_mom_20d >= 0% | +19.06% | 5.95 | 4/4* | +16.77% |
| yield_curve >= -0.5pp | +17.02% | 1.77 | 6/6 | -2.52% |
| sp500_mom_20d >= 0% | +15.42% | 2.37 | 4/4* | +9.51% |

*Only 4 years after S10 VIX filter already reduced from 7 → 5 years

**H22 stacked on S10 best (vix_mom>=-8% + cu_gold>=0%, only 5 years baseline):**
| Filter | avg_edge | Sharpe | Years | 2022 |
|--------|----------|--------|-------|------|
| + taiex_mom_20d >= 0% | +29.75% | 3.02 | 4 | +21.77% |
| + sp500_mom_20d >= 0% | +28.59% | 2.65 | 4 | +21.77% |

Caution: 4-year samples are not statistically robust enough for H22 (too few trades).

**H23 Portfolio (top-5: EIB/STB/POW/MSN/BID) — new filters:**
| Filter | avg_edge | Sharpe | Years | 2022 | trades/yr |
|--------|----------|--------|-------|------|-----------|
| taiex_mom_20d >= 3% + kospi_mom_20d >= 0% | **+20.94%** | **3.72** | 11/11 | +20.08% | 169 |
| btc_mom_20d >= 10% | +21.35% | 2.24 | 10/11 | +20.74% | 208 |
| btc_mom>=10% + kospi>=0% + breadth>=3 | +21.96% | 2.63 | 11/11 | +22.26% | 114 |
| taiex_mom_20d >= 3% + btc_mom_20d >= 10% | +20.64% | 1.74 | 10/11 | +24.91% | 86 |

**Key insight for H23:** `taiex_mom_20d >= 3%` (Taiwan TAIEX 20d return ≥ 3%) + `kospi_mom_20d >= 0%` (Korea positive) identifies "Asian tech cycle upswing" → Vietnamese bank stocks predictable with Sharpe 3.72 and 11/11 years positive.

**Why TAIEX+KOSPI works:** Regional Asian risk-on environment (Korea/Taiwan tech/manufacturing cycle) reduces "idiosyncratic noise" in Vietnam — when the whole region is trending, cross-sectional momentum signals are cleaner and less subject to FX/global macro disruptions.

**Previous best H23:** S10 vnm>=-5% + breadth>=3 gave +19.23%, Sharpe 2.80, 11/11 years
**New best H23:** taiex>=3% + kospi>=0% gives +20.94%, Sharpe 3.72, 11/11 years ← New champion

---

## F25: VIX Lower Bound of 15 (not 18) is Better for H22 FPT System (2026-03-17, Session 12)

**What we found:** Systematic VIX band sweep over the baseline XS barrier + E32 ensemble reveals that **VIX [15,30] > VIX [18,35]** for avg edge (+18.71% vs +15.13%).

**VIX band sweep results (depth=3 baseline + E32, min_conf=0.55, agree-only):**

| VIX band | avg_edge | n_years | trades/yr | Sharpe |
|----------|----------|---------|-----------|--------|
| [18,35] (H22 baseline) | +15.13% | 6 | ~15 | ~1.52 |
| [15,35] | +18.35% | 7 | ~17 | — |
| **[15,30]** | **+18.71%** | **7** | **~16** | **—** |
| [15,40] | +18.59% | 7 | — | — |

**Why [15,30] beats [18,35]:**
1. The lower bound of 15 (vs 18) admits 2019 and 2021 — both low-volatility years where the XS signal was very accurate:
   - 2019: 27 trades at 85.2% accuracy = +28.39%*
   - 2021: 117 trades at 65.8% accuracy = +15.01%*
2. The upper bound of 30 (vs 35) excludes moderate-high VIX environments (30-35) where the model had mixed results.
3. The original [18,35] band was found by H26 macro sweep on 2019-2025 — this is a refinement using the same data.

**Official ensemble run (H38):**
| Year | n_trades | conf_acc | edge |
|------|----------|----------|------|
| 2019 | 27 | 85.2% | +28.39%* |
| 2020 | 40 | 75.0% | +24.60%* |
| 2021 | 116 | 65.5% | +14.72%* |
| 2022 | 64 | 54.7% | -3.55% |
| 2023 | 14 | 64.3% | +12.08% |
| 2024 | 24 | 75.0% | +20.20% |
| 2025 | 24 | 70.8% | +34.54%* |
| **avg** | **~37** | **70.1%** | **+18.71%** |

**Caveat:** This tuning is still in-sample on 2019-2025. The [18,35] band was also tuned in-sample. Both are contaminated at the meta-level. The genuine test is 2026.

**Model variants tested (all with E32 + VIX [18,35] unless noted):**

| Variant | avg_edge | Verdict |
|---------|----------|---------|
| H22 baseline (depth=3, [18,35]) | +15.13% | — |
| H32: macro regime as training features | +15.76% | MARGINAL |
| H33: Random Forest + [18,35] | +4.82% | FAILED |
| H33b: ExtraTrees | N/A | FAILED (too few confident preds) |
| H34: depth=5, [18,35] | +16.14% | MARGINAL |
| H34: depth=5, [15,30] | +16.70% | — |
| H36: risk-adj features | +11.37% | FAILED |
| H37: MLP classifier | +8.46% | FAILED |
| LGBM with barrier + [18,35] | +11.10% | FAILED |
| **H38: depth=3, VIX [15,30]** | **+18.71%** | **NEW FPT CHAMPION** |

**General pattern confirmed:** XGBoost depth=3 remains the best model type. Adding training features (fundamentals, dividends, macro regime, risk-adj) always hurts. The only valid levers are:
1. Post-hoc regime filters (VIX band, macro indicators)
2. Ensemble architecture (which models to combine)
3. Label quality (barrier %)
4. Confidence threshold (55% is optimal)


---

## F26: Dynamic Rank Portfolio — Strongest and Most Generalizable Signal (2026-03-17, Session 13)

### Core finding

The XS barrier model's **rank ordering** of 52 Vietnamese stocks is genuinely predictive.
Daily, long the top-N stocks by XS proba. This eliminates stock selection bias entirely.

**Quintile Factor Test (no filter, no VIX filter, 2015-2025, 11 years):**
| Year | Q5 rate | Q1 rate | Q5-Q1 spread | IC (Spearman) | p-value |
|------|---------|---------|-------------|---------------|---------|
| 2015 | 56.3% | 40.0% | +16.21% | +0.112 | <0.0001* |
| 2016 | 51.7% | 37.0% | +14.72% | +0.111 | <0.0001* |
| 2017 | 52.7% | 42.1% | +10.61% | +0.078 | <0.0001* |
| 2018 | 53.0% | 42.3% | +10.68% | +0.075 | <0.0001* |
| 2019 | 53.5% | 40.3% | +13.22% | +0.096 | <0.0001* |
| 2020 | 53.2% | 40.5% | +12.61% | +0.089 | <0.0001* |
| 2021 | 51.3% | 39.5% | +11.80% | +0.086 | <0.0001* |
| 2022 | 51.7% | 43.6% | +8.09% | +0.057 | <0.0001* |
| 2023 | 56.8% | 40.5% | +16.30% | +0.112 | <0.0001* |
| 2024 | 50.8% | 40.4% | +10.40% | +0.069 | <0.0001* |
| 2025 | 46.0% | 35.7% | +10.26% | +0.084 | <0.0001* |
| **avg** | — | — | **+12.26%** | **+0.088** | **11/11*** |

Avg IC = +0.088. In academic factor investing, ICs of 0.02-0.05 are considered meaningful. **+0.088 sustained over 11 consecutive years** with p<0.0001 every single year including 2022 is exceptional. No look-ahead: train on year < Y, predict year Y.

### Best practical system: Dynamic Top-N, VIX [15, 30]

**H43 — long top-N stocks daily by XS barrier proba, VIX band [15,30], min_proba = 0.55**

**Dynamic top-5 year-by-year (VIX[15,30], 2015-2025):**

| Year | Trades | Edge |
|------|--------|------|
| 2015 | 53 | +11.54% |
| 2016 | 23 | +16.42% |
| 2017 | 3 | +19.67% |
| 2018 | 34 | +6.26% |
| 2019 | 20 | +14.22% |
| 2020 | 5 | +13.11% |
| 2021 | 39 | +15.07% |
| 2022 | 98 | +13.58% |
| 2023 | 26 | +13.87% |
| 2024 | 10 | +8.65% |
| 2025 | 10 | +8.48% |

**Dynamic Top-5 avg edge: +12.81%, Std: 3.69%, Sharpe: 3.47, 11/11 positive**

**Top-N sweep (VIX [15,30], min_proba=0.55, 2015-2025):**

| N | Avg Edge | Sharpe | Years | Trades/yr |
|---|----------|--------|-------|-----------|
| 1 | +13.73% | 1.88 | 11 | 99 |
| 2 | +12.46% | 2.12 | 11 | 69 |
| 3 | +12.22% | 2.98 | 11 | 49 |
| **5** | **+12.12%** | **3.87** | **10** | **32** |
| 7 | +15.85% | 3.42 | 8 | 25 |
| 10 | +16.20% | 2.93 | 7 | 15 |

**Best full-coverage Sharpe: N=5 → Sharpe 3.87** over 10 years. N=7/10 have higher avg_edge but fewer coverage years (only trade when VIX band + confidence align).

### Why this is better than H22 or H23

| System | Avg Edge | Sharpe | Years | 2022 | Stock selection | Params |
|--------|----------|--------|-------|------|-----------------|--------|
| H22 (FPT fixed) | +15.13% | ~1.52 | 6 | -2.07% | FPT only (arbitrary) | 4 params |
| H23 (top-5 fixed) | +21.94% | 2.54 | 11 | +15.71% | 2015-2025 in-sample | 5 fixed stocks |
| **H43 (dynamic top-5, VIX[15,30])** | **+12.81%** | **3.47** | **11** | **+13.58%** | **None (daily rebalance)** | **1 param** |

H43 advantages:
1. **No stock selection bias**: the top-N stocks change every day — no contamination
2. **2022 works**: +13.58% vs H22's -2.07% and H23's +15.71% (but H23 stock selection is contaminated)
3. **Single parameter**: VIX < 30 (one commonsense rule: don't trade in extreme crises)
4. **Robust Sharpe**: 4.96 vs H22's ~1.52 because variance is much lower
5. **Fixed H23 collapses in 2025** (-41.52%): EIB/STB/POW/MSN/BID became wrong picks. Dynamic portfolio adapts automatically.

### Why VIX < 30 is sensible

VIX > 30 = extreme crisis (COVID, GFC-level events). In these regimes, all stocks become correlated (flight to safety) and cross-sectional momentum is noise. The filter excludes only 7 months of 2020 (peak COVID) from the evaluation period.

---

## F27: The Signal Has Real Monetary Value — H45 Dollar Return Analysis (2026-03-17, Session 15)

All prior edge metrics (H40–H44) were in probability-accuracy units (% hit rate above naive).
H45 converts this to actual dollar returns using OHLC price data.

**Model hit rate in top-5 selections:** P(actual=1) = **60.0%** (497 days, 2485 stock-days, 2015-2025)

| Hold | avg_win | avg_loss | gross/trade | Beat 0.30% RT? |
|------|---------|----------|-------------|----------------|
| 1d | +1.784% | -1.653% | **+0.409%** | YES |
| 2d | +2.289% | -1.914% | **+0.608%** | YES |
| 3d | +2.546% | -1.898% | **+0.768%** | YES |
| 5d | +2.783% | -1.838% | **+0.935%** | YES |
| 10d | +3.203% | -1.878% | **+1.171%** | YES |

**EVERY holding period beats 0.30% RT cost.** The break-even cost is the gross return itself.

**Corrected annual framework (45 active days/year from VIX filter):**
- Gross annual excess vs VNINDEX: 45 days × 0.409% = **~18.4%/yr**
- Annual cost (45 days × 3.45 new stocks/day × 0.30% / 5 positions): **~9.3%/yr**
- **Net annual excess vs VNINDEX: ~9.1%/yr**

All prior "net after cost" calculations in H44/H46/H47/H49 comparing accuracy-edge vs dollar-cost
were comparing different units and are not meaningful. H45 provides the correct dollar framework.

---

## F28: Signal Decay Curve — Fresh Daily Rankings Outperform Any Hold-and-Wait Strategy (2026-03-17, Session 15)

H48 measured actual N-day cumulative returns for top-5 picks selected TODAY.

| Hold | top5_ret | naive | edge | Per-day marginal edge |
|------|----------|-------|------|----------------------|
| 1d | +0.409% | +0.041% | +0.368% | +0.368% |
| 5d | +0.927% | +0.217% | +0.710% | ~+0.085%/day (days 1-5) |
| 10d | +1.160% | +0.449% | +0.711% | ~+0.020%/day (days 5-10) |
| 15d | +1.338% | +0.630% | +0.708% | ~+0.0003%/day (days 10-15) |

**Key finding:** All holding periods are profitable at 0.30% RT cost. BUT the marginal per-day edge
decays rapidly from +0.368%/day on day 1 to near-zero by day 10-15.

**Why daily rebalancing (H43) beats longer holds:**
- Daily strategy: 45 days × 0.409% gross − 9.3% cost = **9.1% net annual excess**
- 10-day hold (4.5 trades/yr): 4.5 × 0.711% gross − 4.5 × 0.30% cost = **1.85% net annual excess**
- Daily wins 5x because fresh model rankings capture 0.368%/day that 10-day-old rankings miss

**2025 anomaly:** At 5-day hold, 2025 shows −0.771% edge (vs +0.099% at 1-day). Potential signal deterioration at medium-term horizon in 2025. Watch in 2026.

**Bottom line:** H43's daily rebalancing is optimal. Don't try to reduce turnover by holding longer — you'll sacrifice far more in alpha than you save in costs.

---

## F29: Turnover Reduction Methods Are Counterproductive (2026-03-17, Session 15)

Three mechanisms tested to reduce H43's 69% daily turnover:

| Method | Result | Data years | Verdict |
|--------|--------|-----------|---------|
| H46: K=2 persistence filter | Only 2 qualifying years | 2/11 | **KILLED** |
| H47: 3-day smoothed ranking | 7 years, 22 days/yr (vs 45) | 7/11 | Marginal |
| H49: Patient exit (top-M) | Edge 10-12% vs 13.75%, Sharpe 4.7 | 11/11 | Not better than H43 |

**Persistence filter (K=2):** Signal is too transient. Stocks rarely stay top-5 for 2+ consecutive days.
K=2 reduces trading opportunities to near-zero.

**Proba smoothing:** When applied to the min_proba filter, smoothing is very strict — rolling averages
rarely sustain 0.55 for multiple days. Results in 22 vs 45 trading days/year, fewer years of data.

**Patient rebalancing (H49):** Holding through low-confidence periods (182 vs 45 days invested)
produces lower quality (11.96% vs 13.75% accuracy edge). H43's strict quality filter is better.

**Conclusion:** H43 as-is is the optimal strategy. The 69% daily turnover is the cost of staying
fresh. Daily rebalancing into the model's latest rankings is worth the cost.

---

## F30: Parameter Contamination Is Real but Modest — Signal Survives Decontamination (2026-03-18, Session 16)

H43's three strategy parameters (VIX_MAX=30, MIN_PROBA=0.55, TOP_N=5) were chosen by observing
2015-2025 results. Session 16 tested three approaches to eliminate this contamination.

**H51 (soft parameterless portfolio):** Replacing TOP_N + MIN_PROBA + VIX filter with softmax
weights over all 52 stocks gives +0.20% edge at T=1.0, +2.18% at T=0.1 (most concentrated).
Conclusion: the parameters do real work. They select the ~45 highest-confidence days per year
from 250 available, concentrating signal 5-10x vs always-invested approach.

**H52 (nested walk-forward, fully honest):** For each test year, grid-search parameters on the
3 prior years. Result: +11.64% avg edge, Sharpe 1.83, 8/9 years positive.

| Year | Params chosen | Test Edge |
|------|--------------|-----------|
| 2017 | N=5,p=0.52,V=25 | +9.67%* |
| 2018 | N=5,p=0.52,V=25 | **-0.15%** |
| 2019 | N=5,p=0.55,V=35 | +14.22%* |
| 2020 | N=5,p=0.55,V=35 | +23.11%* |
| 2021 | N=3,p=0.58,V=25 | +6.73%* |
| 2022 | N=5,p=0.55,V=30 | +13.58%* |
| 2023 | N=7,p=0.52,V=35 | +10.63%* |
| 2024 | N=5,p=0.55,V=25 | +8.65%* |
| 2025 | N=3,p=0.55,V=32 | +18.28%* |

**Key numbers:** H43 contaminated +13.75% Sharpe 4.58 | H52 honest +11.64% Sharpe 1.83
Contamination adds ~2% to edge and inflates Sharpe substantially (partly due to missing 2015-2016).

**H43's parameter choices are sensible priors, not data-mined extremes:**
- TOP_N=5 selected in 5/9 honest years (most common choice)
- MIN_PROBA=0.55 selected in 5/9 honest years (most common choice)
- VIX_MAX=30 selected for 2022 (the most important test, H43's hardest year)

---

## F31: VIX Inside the Model Preserves Signal Without External VIX Filter (2026-03-18, Session 16)

H50: added VIX (level, 5d/20d momentum) as training features in cross_sectional_wf.py.
New probas: `data/features/xs_barrier_vix_feature_all_probas.parquet`

**Result with no external VIX filter:**
- Dynamic top-5 portfolio: +11.85% avg edge, Sharpe 3.10, **11/11 years positive**, ~56 trades/yr
- Quintile IC: +0.0879 avg, all 11 years statistically significant

The model learned to lower probabilities during extreme VIX regimes internally.
Adding the external VIX filter ON TOP of VIX-feature probas does NOT improve performance
(+10.72% Sharpe 3.17) — double-counting the VIX signal reduces trades without improving quality.

**Implication:** For a publication-clean system, H50a (VIX-feature probas, no external VIX filter)
eliminates the VIX_MAX parameter entirely. MIN_PROBA and TOP_N remain as the two residual
contaminated parameters — addressable via H52 nested walk-forward on the H50 probas.

---

## Dead Ends — Exhausted Hypothesis Directions

_Do not revisit these without a strong new reason. Each entry includes the session that closed it and why it failed._

### Signal Sources (features / targets)

| Direction | Tried | Why it failed | Closed |
|-----------|-------|---------------|--------|
| Standard OHLCV technicals (MA, RSI, MACD, BB, ATR, volume) | E1-E7, all combinations | FPT is weak-form efficient on raw OHLCV; 0 significant years in 7-year walk-forward | Session 2 (F2) |
| Lag returns (1-60d) on FPT alone | E2, E3 | Collapses to drift; 0 significant years | Session 2 (F2) |
| FPT-only fundamentals (EPS, P/E, ROE) | E29 | No improvement over E8 baseline; too few quarterly data points | Session 4 (F9) |
| Market breadth indicators | E-series | No edge; 250 rows/year is too few for additional single-stock features | Session 4 (F8) |
| Tet calendar / seasonality | Session 5 | Overfits; not consistent across years | Session 5 (F10a) |
| Earnings cycle effects | Session 5 | No consistent pattern | Session 5 (F10a) |
| Risk-adjusted momentum | Session 5, H36 | No improvement; H36 FAILED | Sessions 5, 12 |
| XS cross-sectional fundamentals (all 52 stocks) | H29 | No improvement over price-only XS model | Session 11 |
| 10-day prediction horizon | Session 7 (F15) | Too much variance — 2020: -31%*, 2021: +34%* | Session 7 (F15) |

### Model Architecture

| Direction | Tried | Why it failed | Closed |
|-----------|-------|---------------|--------|
| LightGBM (vs XGBoost) | H24 | Similar or worse; not worth maintaining separate code path | Session 9 |
| Random Forest | H33 | Worse than XGBoost at same depth | Session 12 |
| ExtraTrees | H33b | Worse than XGBoost | Session 12 |
| MLP classifier | H37 | Worst of all; poor on tabular financial data | Session 12 |
| XGBoost depth=5 (vs depth=3) | H34 | Marginal gain, likely overfit | Session 12 |
| Linear regression (regression target) | Early sessions | No edge; doesn't benefit from the relative momentum structure | Sessions 1-3 |

### Strategy / Portfolio Design

| Direction | Tried | Why it failed | Closed |
|-----------|-------|---------------|--------|
| K=2 persistence filter (must rank top-N for 2 consecutive days) | H46 | Signal fires in 1-day bursts; K=2 reduces to 2/11 qualifying years | Session 15 (F29) |
| Proba smoothing (rolling N-day average before ranking) | H47 | Smoothed proba rarely sustains 0.55 threshold; drops to 7 qualifying years | Session 15 (F29) |
| Patient rebalancing (hold until rank drops below M) | H49 | Holding through low-confidence periods produces lower quality; H43 strict filter is better | Session 15 (F29) |
| Any hold period > 1 day (E=0 terms) | H44, H48, H78 | Daily wins at all cost levels in E=0 — gross decay outpaces cost savings | Sessions 15, 24 (F28, F37) |
| Proba momentum ranking (Zaremba 2020) | H84 | IC and edge degrade monotonically with alpha; no lag structure in daily proba signal | Session 24 (F36) |
| Macro regime filters as external filters (GDP, CPI, credit) | H26, H27 | Modest gains contaminated by filter selection | Session 10 |
| TAIEX / KOSPI correlation features | Session 11 | No durable improvement over core XS model | Session 11 |

### Barrier Parameters

| Direction | Tried | Why it failed | Closed |
|-----------|-------|---------------|--------|
| 0.5% barrier | H21a | Worse than 1.0% — too many timeout samples | Session 8 |
| 1.5% barrier | H21b, E31 | Worse than 1.0% — too few samples hit the barrier | Sessions 7-8 |
| 2.0% barrier | E33 | Worse than 1.0% | Session 7 |
| 10d / 20d training label horizon | H85 | IC identical (+0.152), Sharpe lower (8.46–8.86 vs 9.17); 5d label optimal | Session 24 (F38) |

---

## F32: Universe Expansion — 393 HOSE Stocks Dramatically Improves Cross-Sectional Signal (2026-03-18, Session 17)

**H54:** Expanded universe from 52 → 393 stocks (all 3-letter HOSE listings with ≥300 rows of data).

**IC nearly doubled:**
- H43 (52 stocks): IC = +0.088
- H54 (393 stocks): IC = +0.1515

This is not cherry-picking — IC measures rank correlation across ALL 393 stocks per day, not just the top-N. More stocks give the model more cross-sectional variation to learn from, resulting in better relative ranking of the whole universe.

**Portfolio performance (N=5, no VIX filter):**
- H43 baseline: +13.75% edge, Sharpe 4.58
- H54 full HOSE: **+25.52% edge, Sharpe 9.17, 11/11 years positive**

**VIX filter is obsolete with large universe:**
- With VIX filter: +26.17%, Sharpe 7.61
- Without VIX filter: +25.52%, Sharpe 9.17 (HIGHER Sharpe)
With 393 stocks, qualifying candidates exist on every trading day regardless of VIX regime. The VIX filter was a patch for the 52-stock model's low candidate count on quiet days.

**TOP-N sweep (no VIX filter):**
| N | Edge | Sharpe |
|---|------|--------|
| 1 | +30.30% | 11.04 |
| 2 | +28.27% | 8.88 |
| 3 | +27.23% | 9.96 |
| 5 | +25.52% | 9.17 |
| 7 | +23.99% | 8.76 |

N=3 (Sharpe 9.96) and N=1 (Sharpe 11.04) are the sweet spots. N=1 concentrates exposure in the model's single highest-confidence pick each day.

**Survivorship bias caveat:** The 393 stocks are all currently listed on HOSE. Stocks delisted before 2025 are absent. This creates upward bias (excluded stocks may have performed worse). However:
1. H43's 52 stocks have the same bias
2. Walk-forward training (train on past years only) prevents look-ahead
3. The bias likely explains some — but not all — of the improvement over H43

**Probas file:** `data/features/xs_barrier_all_probas_hose_full.parquet` (824,704 rows, 393 tickers)

---

## F33: H55 Dollar Returns — Execution Timing Matters (2026-03-18, Session 18, REVISED)

H55 (rewritten) measured actual forward relative returns for H54's top-5 picks with three entry timings:

**E=0 (enter T close — NOT EXECUTABLE):** Signal computed from T close data; can't execute at T close.
- Full 393: +1.754%/trade gross | Liquid 210: +1.037%/trade gross

**E=1 (enter T+1 open — CORRECT standard execution):**
- Full 393: **+0.539%/trade gross, +0.239% net** at 0.3% RT, all 11 years positive
- Liquid 210: **+0.279%/trade gross, -0.021% net** at 0.3% RT (barely negative)

**E=3 (enter T+3 open — delayed):** Signal largely gone; +0.131% full, +0.074% liquid

The inflated E=0 numbers reflect the T close → T+1 open overnight gap which is already
realized before the trader can enter. The real executable edge (E=1) is much smaller.

**Practical takeaway:**
- Full universe: net positive after costs — signal survives correct execution
- Liquid stocks only: breaks even / slightly negative at 0.3% RT
- The gap between E=0 and E=1 = "overnight gap effect" not capturable by standard next-open entry
- Compare H43 (5d hold, original E=0 method): +0.409%/trade — also overstated by same timing bias

---

## F34: H56 — Honest Nested WF on Full Universe: Sharpe 7.35 (vs 1.83 for 52 stocks) (2026-03-18, Session 18)

H56 (nested walk-forward, no parameter contamination, 393 stocks):
- **+25.98% avg edge, Sharpe 7.35, 9/9 years positive**
- Compare H52 (52 stocks, honest): +11.64% Sharpe 1.83

The 2018 failure in H52 (-0.15%) is completely resolved (+26.69% in 2018 for H56). With 393
stocks, the pathological near-zero-variance Sharpe from sparse trading (VIX_MAX=25 giving <5
trades/year) is gone — every parameter combo has enough trades to compute a valid meta-Sharpe.

Contamination inflation for H54: contaminated Sharpe 9.17 vs honest Sharpe 7.35 — modest (~20%).
The honest benchmark is strong on its own.

---

## F35: Survivorship Bias Audit — Old Stocks Drive the Signal (2026-03-18, Session 18)

H57 compared performance by stock cohort (based on first year appearing in walk-forward probas):

| Cohort | Tickers | Edge | Sharpe |
|--------|---------|------|--------|
| All 393 | 393 | +25.59% | 8.52 |
| Old (≥2012 stocks, ≤2015 debut) | 268 | +24.58% | 6.67 |
| Mid (2013-2015 listed) | 82 | +12.09% | 2.13 |
| New (2016+ listed) | 43 | +10.98% | 1.55 |

**Key finding:** New stocks perform WORSE than old stocks. Survivorship bias is NOT inflating
the new stocks. The improvement from H43 (+13.75%, 52 stocks) to H54 (+25.52%, 393 stocks)
is driven by pool size: 268 old stocks (same survivorship profile as H43's 52) already give
+24.58% Sharpe 6.67.

Mechanism: more candidates → more selective top-N → better top-5 picks given the same IC.

---

## F37: Holding Period Grid — H=1 Wins in E=0, H=2 Likely Better in E=1 (2026-03-19, Session 24)

**Status note (2026-03-19, Session 26):** The E=1 inference below was later tested directly and overturned by F48. H=1 remains best in the dedicated executable T+1-open simulation.

**H78** simulated fixed-hold portfolios (H=1/2/3/5) on H54 probas (393 stocks, 2015–2025).

**Key observation — turnover:** The top-5 is ~91% reshuffled every trading day (182% portfolio
turnover). Only ~0.45 stocks persist from one day to the next. The H54 signal is extremely
transient — consistent with F28's finding that edge decays to near-zero by day 5.

**H78 simulation (E=0 — closing prices, same methodology as H54):**

| Hold | gross/day | trades/yr | cost/yr @0.30% | net/yr |
|------|-----------|-----------|----------------|--------|
| H=1 | +1.752% | 2246 | 67.4% | +365% |
| H=2 | +1.102% | 1180 | 35.4% | +238% |
| H=3 | +0.766% | 796 | 23.9% | +167% |
| H=5 | +0.485% | 475 | 14.3% | +106% |

**In E=0 terms:** H=1 unambiguously best — gross decay from holding longer (1.752% → 0.485%/day)
far exceeds cost savings (67.4% → 14.3%/yr). Confirms F28/F29.

**E=1 adjustment (inferred from F33):**
Each portfolio entry incurs a ~1.215% overnight gap cost (the T-close→T+1-open gap that is
unrealizable at T+1 open entry). H=2 avoids re-entering ~123 positions/yr vs H=1.
Estimated E=1 net/day at 0.30% RT: H=1 ≈ +0.261%, H=2 ≈ +0.350%, H=3 ≈ +0.266%, H=5 ≈ +0.185%.
**H=2 is likely best in the executeable (E=1) framework.** Would require a dedicated T+1-open
simulation to confirm. (Not tested in H78 — H78 uses E=0 closing prices throughout.)

**K-band variant (K=15):** Identical to H=1. With 393 stocks the top-5 from yesterday almost
always has one stock that falls below rank 15 by tomorrow → K-band triggers every day.
Meaningful K-band would require K≥50+ for 393-stock universe.

**Verdict:**
1. E=0: H=1 (daily) confirmed optimal — consistent with F28/F29.
2. E=1: H=2 estimated best — overnight gap avoidance saves more than alpha decay costs.
3. A dedicated H=2 E=1 simulation (using T+1 open prices) is warranted if targeting lower-cost execution.

---

## F36: Proba Momentum Ranking Does Not Transfer to VN Stocks (2026-03-19, Session 24)

**H84** tested Zaremba 2020 "Opposites Attract" concept: augmenting daily ranking with short-term
proba momentum (`rank_score = xs_proba + alpha * (proba_ma5 - proba_ma20)`).

**Results (393 stocks, no VIX filter, alpha sweep {0.0, 0.3, 0.5, 0.7, 1.0}):**

| alpha | avg_edge | Sharpe | vs H54 |
|-------|----------|--------|--------|
| 0.0 (H54 baseline) | +25.52% | 9.17 | — |
| 0.3 | +25.11% | 9.74 | −0.40% |
| 0.5 | +24.66% | 8.94 | −0.86% |
| 0.7 | +24.78% | 8.43 | −0.74% |
| 1.0 | +24.15% | 7.86 | −1.37% |

**Han 2021 stability filter (proba_std5 ≤ 0.15):** Reduces baseline from +25.52% to +22.63%
— high-variance proba stocks are *high-signal*, not crash risk in VN context.

**IC degrades monotonically:** +0.1515 (alpha=0) → +0.1496 (alpha=0.5) → +0.1443 (alpha=1.0).

**Why it fails:** Zaremba's mechanism operates at monthly rebalancing over countries/industries.
H54's signal decays to near-zero by day 10–15 (F28). At daily rebalancing, the 5d/20d MA of
probas mostly captures stale information already incorporated by the current-day model. There
is no exploitable lag structure in model confidence at the daily horizon.

**Verdict:** CLOSED. Raw `xs_proba` is already the optimal ranking signal at daily frequency.
Do not add lag-based momentum components to the ranking score.

---

## F38: Training Label Horizon — 5d Barrier Is Already Optimal (2026-03-19, Session 24)

**H85** tested whether longer training label horizons (10d, 20d) improve the H54 signal.
Blitz et al. 2023 found monthly-rebalancing ML strategies trained with 3-month/12-month labels
survive transaction costs better than 1-month-label models. H85 tested this for VN stocks.

**Results (393–394 stocks, no VIX filter, 2015–2025):**

| Label horizon | IC (Spearman) | avg_edge | Sharpe | year_std |
|---|---|---|---|---|
| H54: 5d (baseline) | +0.1515 | +25.52% | **9.17** | 2.78% |
| H85: 10d | +0.1521 | +25.46% | 8.46 | 3.01% |
| H85: 20d | +0.1520 | +25.36% | 8.86 | 2.86% |

**IC is nearly identical** across all three (within 0.0006). The model learns essentially the
same cross-sectional ranking patterns regardless of whether the label is "outperforms VNINDEX
by 1% within 5 days" vs "within 10/20 days."

**Why Blitz's mechanism doesn't transfer:**
1. VN market signal decays to near-zero by day 10 (F28). A 20d label assigns credit to stocks
   that will outperform VNINDEX eventually but not necessarily in the near term — introducing
   noise into the signal that H54's 5d label avoids.
2. H85 doesn't actually reduce turnover (portfolio still rebalances daily using the new probas).
   Blitz's saving comes from *holding longer*, not just *training on longer labels*. H78 shows
   the correct lever for turnover reduction.
3. The 10d label has *higher* year-to-year variance (Sharpe 8.46 vs 9.17) — the opposite of
   Blitz's prediction of more stable signals with longer labels.

**Verdict:** CLOSED. 5d barrier label is optimal for VN cross-sectional momentum. Adding label
horizon as a second dimension to barrier amplitude (H83 2D grid) is not warranted.
Also closes the "barrier horizon" axis: the only remaining barrier parameter to test is
amplitude (H83: 0.5%, 1.5% vs current 1.0%).

---

## F39: Barrier Amplitude 1% Is Optimal — 0.5% and 1.5% Both Degrade (2026-03-19, Session 25)

**H83** tested whether the triple barrier amplitude should be tightened (0.5%) or widened (1.5%)
relative to the current 1.0% used by H54.

**Results (394 stocks, no VIX filter, 2015-2025):**

| Barrier | IC (Spearman) | avg_edge | Sharpe | year_std |
|---|---|---|---|---|
| H83a: 0.5% | +0.1519 | +25.15% | 8.80 | 2.86% |
| **H54: 1.0% (baseline)** | **+0.1515** | **+25.52%** | **9.17** | **2.78%** |
| H83b: 1.5% | +0.1460 | +24.17% | 7.18 | 3.36% |

Pattern: 0.5% creates more noise labels (too many neutral outcomes at boundary), 1.5% creates
too many neutral/tie outcomes for 5d window — model cannot distinguish stocks outperforming by
1.5%+ reliably. 1% sits at the sweet spot.

**Verdict:** CLOSED. 1.0% is the optimal barrier amplitude. Closes the barrier amplitude search axis.

---

## F40: VIX as Training Feature Does Not Improve H54 (2026-03-19, Session 25)

**H79** tested adding VIX level + 5d/20d momentum as explicit training features at 393-stock scale.

**Results (394 stocks, no VIX filter, 2015-2025):**

| System | avg_edge | Sharpe | IC |
|---|---|---|---|
| H54 baseline | +25.52% | 9.17 | +0.1515 |
| H79 (VIX feature) | +24.99% | 8.90 | +0.1516 |

IC is essentially identical. With 393 stocks, diversification across regimes is already handled
implicitly by cross-sectional momentum. Contrast: at 52-stock scale (H50a, Session 16), VIX
feature gave significant improvement (+11.85% Sharpe 3.10). Effect disappears at scale.

**Verdict:** FAIL. VIX as training feature adds no value at 393-stock scale.

---

## F41: Dormant Features (Vol Regime, Calendar, CCI, WillR) — Slightly Better Sharpe (2026-03-19, Session 25)

**H77** enabled vol_regime, calendar, CCI, Williams %R on the 393-stock cross-sectional WF.

**Results (394 stocks, no VIX filter, 2015-2025):**

| System | avg_edge | Sharpe | IC | n_features |
|---|---|---|---|---|
| H54 baseline | +25.52% | 9.17 | +0.1515 | 35 |
| H77 (dormant) | +25.19% | **9.68** | +0.1505 | 44 |

Adding 9 features (willr, cci, vnindex_vol_20d, vnindex_vol_pct, high_vol_regime,
days_to_tet, days_since_tet, pre_tet_window, post_tet_window) slightly lowers IC and edge
but increases Sharpe (+0.51). Calendar/vol features add mild diversification without improving
core predictive power.

**Verdict:** NEUTRAL. Sharpe improvement is real but edge decline (-0.33%) means net effect is
neutral for practical trading. H54 remains champion.

---

## F42: Sector-Relative Features — Marginal Edge Gain, Lower Sharpe (2026-03-19, Session 25)

**H80** added sector-relative momentum features: deviation of stock's 1d/5d/20d relative return
from its sector mean. 15 named sectors + "Other" bucket (57% of stocks).

**Results (394 stocks, no VIX filter, 2015-2025):**

| System | avg_edge | Sharpe | IC |
|---|---|---|---|
| H54 baseline | +25.52% | 9.17 | +0.1515 |
| H80 (sector-rel) | +25.70% | 8.35 | +0.1524 |

IC improves marginally (+0.0009). Edge slightly better (+0.18%) but Sharpe degrades (-0.82).
The "Other" bucket (226/393 stocks) receives full-universe mean demeaning — nearly equivalent
to existing market-relative features. Within-sector resolution adds noise more than signal.

**Verdict:** NEUTRAL. Does not improve H54. Sector-relative features are mostly captured by
existing market-relative (vs VNINDEX) features.

---

## F43: IC Stability Filter Does Not Improve Portfolio (2026-03-19, Session 25)

**H81** restricted daily universe to tickers with positive historical IC in >=K of prior 3 years.
Overall IC positivity rate: 88.9% of (year, ticker) pairs. Mean IC = +0.133.

**Results (2015-2025):**

| Filter | avg_edge | Sharpe | Years |
|---|---|---|---|
| H54 baseline (no filter) | +25.52% | 9.17 | 11/11 |
| IC>0 in >=1/3 yrs | +25.46% | 8.29 | 10/10 |
| IC>0 in >=2/3 yrs | +25.45% | 8.13 | 9/9 |
| IC>0 in >=3/3 yrs | +24.81% | 9.57 | 8/8 |

Since 88.9% of tickers already have positive IC, filtering barely changes the universe.
Tighter filters lose years of data and portfolio breadth without compensating gain.

**Verdict:** FAIL. XS model already selects stocks that perform well across the full universe.
IC stability filter provides no filtering signal beyond the model's daily probabilities.

---

## F44: Classifier + Regressor Ensemble — Trades Edge for Sharpe (2026-03-19, Session 25)

**H82** blended XGBoost classifier probas (xs_proba) with rank-normalized regressor scores
using daily rank percentile normalization.

**Results (394 stocks, no VIX filter, 2015-2025):**

| Alpha (clf weight) | avg_edge | Sharpe | Pos years |
|---|---|---|---|
| 1.0 (clf only = H54) | +25.52% | 9.17 | 11/11 |
| 0.7 | +25.06% | 9.22 | 11/11 |
| 0.5 | +25.02% | 9.62 | 11/11 |
| 0.3 | +24.70% | **11.41** | 11/11 |
| 0.0 (reg only) | +22.15% | 8.49 | 11/11 |

Regressor alone is weaker (-3.37% edge). Blending at alpha=0.3 gives Sharpe 11.41 (highest
observed in any system) but at cost of -0.82% edge. Pure risk-return tradeoff.

**Verdict:** NEUTRAL. Classifier (H54) has best edge. Alpha=0.3-0.5 useful if Sharpe stability
is prioritized over max edge. Regressor is a useful complement in multi-objective optimization.

---

## F45: XS Fundamentals (52-Ticker, Zero-Fill) — Higher Sharpe, Slightly Lower Edge (2026-03-19, Session 25)

**H86** added P/E rank, EPS YoY rank, ROE rank, NPM rank, Debt/Equity rank from 52-ticker dataset,
zero-filled for remaining 341 stocks.

**Results (394 stocks, no VIX filter, 2015-2025):**

| System | avg_edge | Sharpe | IC |
|---|---|---|---|
| H54 baseline | +25.52% | 9.17 | +0.1515 |
| H86 (fundamentals) | +25.13% | **9.79** | +0.1505 |

Only 52/394 tickers have real fundamental data, yet Sharpe improves (+0.62) while edge drops
slightly (-0.39%). The model learns that "zero" fundamentals (unmapped stocks) have different
risk characteristics. The 52 tickers with data are among the most liquid and their fundamental
signals reduce portfolio concentration risk.

**Verdict:** NEUTRAL. Not a champion replacement. Sharpe gain (+0.62) is real and reproducible.
Could be combined with H77 or H82 in a future "Sharpe optimizer" session.

---

## F46: Session 25 Convergence — H54 Remains Optimal, Feature Space Exhausted (2026-03-19, Session 25)

After testing 9 hypotheses (H77-H86) across feature augmentation, filtering, ensemble methods,
and barrier amplitude grids, H54 remains the undefeated champion.

**Systematic finding:** Every feature addition tested in Sessions 19-25 fails to beat H54
on avg_edge > 25.52%. Signal appears near its natural limit:
1. Universe size (393 stocks) is near-saturated
2. Feature set (35 technical + relative momentum) captures the core signal
3. 1% barrier + 5d horizon is the optimal label definition
4. No external filter (VIX, IC stability, sector) improves the raw signal

**Sharpe improvements without edge gain (potential future combination):**
- H77 (dormant features): Sharpe +0.51
- H86 (XS fundamentals): Sharpe +0.62
- H82 alpha=0.3 (regressor blend): Sharpe +2.24 but edge -0.82%
- Combined H77+H86+H82(alpha=0.5) → estimate Sharpe ~10+ with edge ~25%

**Verdict:** H54 is the production champion. Cross-sectional momentum in VN stocks is real,
robust, and economically significant (+25.52% edge, Sharpe 9.17, 11/11 years).

---

## F47: H87 Combination - Sharpe-Optimized Near-Champion, But H54 Still Wins on Edge (2026-03-19, Session 26)

**H87a** combined H77 dormant features and H86 XS fundamentals in the 394-stock barrier model.

**Direct classifier result (no VIX filter, TOP_N=5, min_proba=0.55):**

| System | avg_edge | Sharpe | IC |
|---|---|---|---|
| H54 baseline | +25.52% | 9.17 | +0.1515 |
| H87a (dormant + fundamentals) | +24.75% | 9.42 | +0.1502 |

The raw feature combination slightly improves Sharpe (+0.25) but gives back -0.77% edge. This
confirms H77 and H86 mostly act as variance smoothers, not new predictive signal.

**H87b** then applied the H82 classifier-regressor blend on top of H87a:

| Alpha (clf weight) | avg_edge | Sharpe | Pos years |
|---|---|---|---|
| 1.0 | +24.73% | 9.39 | 11/11 |
| 0.7 | +25.03% | 10.25 | 11/11 |
| 0.5 | +24.94% | 9.94 | 11/11 |
| 0.3 | +24.52% | 9.62 | 11/11 |

The planned `alpha=0.5` blend narrowly misses the Session 26 target (Sharpe > 10 while keeping
edge > 24), but `alpha=0.7` clears it. Compared with Session 25's H82 result, the combination
shifts the useful tradeoff toward the classifier-heavy side: it keeps edge above 25% while still
reaching Sharpe > 10.

**Verdict:** NEUTRAL for champion replacement, PASS for Sharpe optimization. H54 remains the
production edge champion. H87(alpha=0.7) is the best near-champion variant so far if the goal is
"Sharpe > 10 without letting edge fall below 25%."

---

## F48: Dedicated H78 E=1 Simulation - Daily Rebalancing Still Wins in Executable Terms (2026-03-19, Session 26)

Session 24 inferred that H=2 might beat H=1 once the T-close -> T+1-open overnight gap was removed.
Session 26 tested this directly using executable T+1-open returns.

**Setup:** H54 saved probabilities, 393-stock HOSE universe, `TOP_N=5`, `MIN_PROBA=0.55`, no VIX filter.
Returns were measured from actual next-open execution onward:
signal at T close -> enter at T+1 open -> first holding-day return is T+1 open to T+2 open.

**Results (2015-2025):**

| Hold | gross/day | trades/yr | net/yr @0.30% RT |
|---|---|---|---|
| H=1 | **+0.542%** | 2246 | **+66.32%** |
| H=2 | +0.348% | 1180 | +50.98% |
| H=3 | +0.216% | 796 | +29.82% |
| H=5 | +0.151% | 475 | +23.27% |

K-band variant (`H=3`, `K=15`) is effectively identical to H=1, confirming again that the
top-5 turns over so aggressively that a narrow stay-in band does not change the portfolio.

**Key conclusion:** Removing the overnight gap does NOT make H=2 optimal. The signal still decays
fast enough that daily rebalancing remains best, even in the executable framework.

This overturns the earlier Session 24 inference. The right interpretation of F33/F37 is:
- the overnight gap is real and should not be counted,
- but the remaining open-to-open alpha at H=1 is still larger than the turnover savings from H=2.

**Verdict:** FAIL for the "H=2 beats H=1 in E=1" hypothesis. CLOSED. Execution realism does not
change the preferred holding period: H=1 remains optimal.

---

## F49: Current H54 No-VIX Cost Stress - Break-Even Near 0.54% RT (2026-03-19, Session 26)

Earlier cost studies were done on the older VIX-filtered execution setup. Session 26 reran cost
sensitivity on the **current production system**: H54 with no external VIX filter.

**Setup:** H54 saved probabilities, 393-stock HOSE universe, executable E=1 open-to-open returns,
`TOP_N=5`, `MIN_PROBA=0.55`, no VIX filter.

**Results:**

| Strategy | gross/trade | trades/yr | exact breakeven RT | ann. net @0.30% RT |
|---|---|---|---|---|
| Daily H=1 | **+0.539%** | 246.8 | **0.54%** | **+59.02%** |
| Weekly H=5 | +0.643% | 50.2 | 0.64% | +17.20% |

**Key conclusions:**
1. The current H54 production strategy is economically viable if actual all-in RT cost stays
   below roughly **0.5%**.
2. Daily H=1 remains the preferred execution mode. Weekly H=5 only improves cost tolerance by
   about **0.10% RT** while sacrificing a large amount of annual net edge.
3. The strategy is robust for large-cap and many mid-cap execution conditions, but likely too
   fragile for thin-stock cost levels above ~0.7% RT.

This updates the practical trading interpretation of the signal:
- edge is real and executable,
- but cost control is a first-order constraint,
- and the correct operating rule for the current champion is still daily H=1, not a slower hold.

**Verdict:** PASS. The current H54 system survives realistic costs, with a quantified and usable
break-even threshold.

---

## F50: H87 Alpha=0.7 Is Operationalizable, But Not a Clear Executable Upgrade Over H54 (2026-03-19, Session 26)

Session 26 turned the H87 `alpha=0.7` blend into a first-class saved artifact:
`data/features/xs_blend_h87_alpha0.7.parquet`

This artifact reproduces the earlier label-space portfolio result:
- avg edge: +25.03%
- Sharpe: 10.25
- 11/11 positive years

But the executable E=1 cost stress shows that the economic advantage over H54 is only marginal:

| Metric | H54 | H87(alpha=0.7) |
|---|---|---|
| E=1 gross/trade, daily H=1 | +0.539% | +0.546% |
| Exact breakeven RT, daily H=1 | 0.54% | 0.55% |
| Annual net @0.30% RT, daily H=1 | +59.02% | +59.19% |
| Exact breakeven RT, weekly H=5 | 0.64% | 0.74% |

**Interpretation:**
1. H87(alpha=0.7) is now easy to run, save, and test like any other system.
2. It does NOT justify replacing H54 as the primary production system.
3. Its main practical value is as an alternate reference or possible higher-cost fallback, not as a new champion.

**Verdict:** NEUTRAL. Operationalization PASS, champion replacement FAIL.

---

## F51: Current H54 No-VIX Live Validation - Signal Alive in 2026, Costs Still First-Order (2026-03-19, Session 26)

Session 26 reran the 2026 holdout as a **live-validation artifact for the current production setup**:
H54 features/model, no external VIX filter, executable E=1 open-to-open returns, `TOP_N=5`,
`MIN_PROBA=0.55`.

**Saved artifact:** `data/features/xs_live_validation_h54_2026.parquet`

**Results (2026-01-05 to 2026-03-11, 389 tickers, 43 days):**

| Metric | Value |
|---|---|
| 2026 IC | **+0.1323** |
| 2025 IC | +0.1201 |
| Equal-weight gross/trade | **+0.155%** |
| Equal-weight net/trade @0.30% RT | -0.145% |
| Square-weight gross/trade | **+0.198%** |
| Square-weight net/trade @0.30% RT | -0.102% |
| Live trades | 42 |

**Key conclusion:** The cross-sectional ranking signal is still clearly alive in 2026. IC remains
strong and is above the last full backtest year (2025). Executable gross returns are positive.
But at current early-2026 realized edge levels, `0.30%` RT costs still push the realized net slightly
negative. The right interpretation is not "signal dead" but "signal alive, costs still binding,
sample still short."

**Verdict:** WEAK PASS. Use as monitoring evidence only, not as a tuning target.

---

## F52: H54 Daily vs H87 Weekly Crossover - Fallback Threshold Near 0.49% RT (2026-03-19, Session 26)

Session 26 compared the current default strategy (H54 daily H=1) against the most plausible
higher-cost fallback (H87 alpha=0.7, weekly H=5), using the saved executable cost-stress summaries.

**Results:**

| RT cost | H54 daily ann. net | H87 weekly ann. net | Winner |
|---|---|---|---|
| 0.30% | **+59.01%** | +21.71% | H54 daily |
| 0.50% | +9.65% | **+11.80%** | H87 weekly |
| 0.70% | -39.71% | **+1.89%** | H87 weekly |

**Crossover:** approximately **0.49% RT**

**Key conclusion:** The deployment rule is now explicit:
1. If actual all-in RT cost is below about **0.49%**, H54 daily remains the best operating mode.
2. If actual RT cost is above about **0.49%**, H87 weekly is the better fallback.
3. H87 weekly is not a new champion. It is a cost-robust alternate for higher-friction names.

**Verdict:** PASS. This closes the higher-cost fallback decision rule.

---

## F53: XS Momentum Signal — Production-Parked, Deployment Gap Defined (2026-03-24, Session 27)

After 26 sessions of validation, the XS cross-sectional momentum signal (H54) is formally **parked**.
It is not a dead signal — the ranking skill is confirmed and alive. It is not a production system —
the execution gap has not been closed.

**What is established:**
- Walk-forward IC = +0.1515 across 11/11 years (2015-2025), p < 0.05 every year
- 2026 live holdout IC = +0.134 (ranking skill intact)
- Gross returns positive in both backtest (+0.539%/trade) and 2026 partial holdout (+0.198%/trade sq-weight)
- 4/4 robustness tests passed (permutation, sector neutrality, mean-reversion decomposition, execution timing)

**What is NOT established (the deployment gap):**
1. **Real fill verification.** The model assumes full fills at T+1 open for all 5 positions. This has never been tested with order-book data. For mid/small-cap names (where the signal is strongest), partial fills and queue position are unknown.
2. **Net P&L positive at actual cost.** 2026 partial-year net is slightly negative at 0.30% RT. Net could be positive at lower actual costs or with longer in-sample, but it has not been confirmed.
3. **Execution infrastructure.** No system exists to generate and act on the daily signal in real time.
4. **Retail-scale constraint.** Restricting to top-50 liquid stocks halves IC. The strategy requires mid/small-cap names where fills are hardest to verify.

**Conditions to unpark:**
- Real fill data available for a sample of opening-auction executions
- Net P&L confirmed positive over at least one full calendar year at actual realized costs
- Execution infrastructure in place for daily rebalancing

**Research direction shift:**
The goal is now to build a library of orthogonal learnable signals for RL training. H54 is the first
validated feature in that library (IC ~0.152). New directions: volume/order-flow signals (H90),
1-day target horizon (H91), sector sub-models (H92), LLM news sentiment (H89).

**Verdict:** PARKED. Signal alive, deployment gap open. Do not trade until gap is closed.

---

## F54: H90 — Volume XS Features Add IC (+0.0084) (2026-03-24, Session 28)

Adding 4 volume features (vol_ratio, obv_roc, vwap_dev_5d, vol_trend) to the cross-sectional XS
model improves average walk-forward IC from +0.1515 to +0.1599 (+0.0084).

**Experiment:** `cross_sectional_wf.py --barrier-pct 0.01 --use-volume-signals`
**Saved probas:** `data/features/xs_barrier_vol_hose_full.parquet`

**Results vs H54 baseline:**

| Metric | H90 (volume) | H54 (baseline) | Delta |
|---|---|---|---|
| Avg IC | +0.1599 | +0.1515 | +0.0084 |
| Avg edge (N=5) | +25.82% | +25.52% | +0.30% |
| Sharpe (N=5) | 9.48 | 9.17 | +0.31 |
| Sig years | 11/11 | 11/11 | — |

The improvement is consistent across most years (IC higher in 8 of 11 years). Volume features
reflect order-flow demand imbalance in the opening auction — consistent with the mechanistic
hypothesis from the alpha-xs-momentum paper.

Features added: `vol_ratio` (vol/20d MA), `obv_roc` (OBV rate of change), `vwap_dev_5d`
(price deviation from 5-day VWAP), `vol_trend` (5d/20d vol MA ratio).

**Verdict:** PASS. Volume features are a real additive signal. Marginal IC improvement; save for
combination with other improvements.

---

## F55: H91 — 1-Day Target: Lower IC, Higher Sharpe — Mixed (2026-03-24, Session 28)

Training on a 1-day barrier label (instead of 5-day) lowers average IC but dramatically increases
Sharpe. The 1-day label is a purer match to the T+1 open execution window.

**Experiment:** `cross_sectional_wf.py --barrier-pct 0.01 --target-horizon 1`
**Saved probas:** `data/features/xs_barrier_1d_hose_full.parquet`

**Results vs H54 baseline:**

| Metric | H91 (1-day) | H54 (5-day) | Delta |
|---|---|---|---|
| Avg IC | +0.1395 | +0.1515 | -0.012 |
| Avg edge (N=5) | +23.90% | +25.52% | -1.62% |
| Edge std (N=5) | 2.06% | higher | lower variance |
| Sharpe (N=5) | **11.63** | 9.17 | +2.46 |
| Best Sharpe (N=10) | **12.33** | ~9.1 | +3.2 |
| Sig years | 11/11 | 11/11 | — |

**Interpretation:** The 1-day model trades some average edge for dramatically lower year-to-year variance.
The model predicts the execution outcome directly, making it more consistent. This is the correct
target for RL training — an agent needs reliable signals, not maximum raw edge.

**Key implication for RL:** The 1-day label is a better RL training signal. Lower variance means
the model's predictions are more trustworthy on any given day.

**Verdict:** MIXED. IC fails success bar (-0.012 vs baseline). Sharpe finding is real and valuable.
See F56 (H93) for the combination result.

---

## F56: H93 — Volume + 1-Day Combined: Sharpe 15.08, Edge Std 1.60% (2026-03-24, Session 28)

Combining H90 (volume features) with H91 (1-day barrier label) produces the highest Sharpe system
found to date — not by increasing edge, but by dramatically reducing year-to-year variance.

**Experiment:** `cross_sectional_wf.py --barrier-pct 0.01 --target-horizon 1 --use-volume-signals`
**Saved probas:** `data/features/xs_barrier_vol_1d_hose_full.parquet`
**Saved artifact:** `artifacts/run_summaries/20260324_211805_h40_rank_portfolio_xs_barrier_vol_1d_hose_full_portfolio.json`

**Full comparison (N=5, no VIX filter):**

| System | IC | Avg Edge | Edge Std | Sharpe |
|---|---|---|---|---|
| H54 (5-day, no vol) | +0.1515 | +25.52% | ~2.8% | 9.17 |
| H90 (5-day + vol) | +0.1599 | +25.82% | ~2.7% | 9.48 |
| H91 (1-day, no vol) | +0.1395 | +23.90% | 2.06% | 11.63 |
| **H93 (1-day + vol)** | +0.1491 | +24.15% | **1.60%** | **15.08** |

**IC by year (H93):** 0.187, 0.166, 0.163, 0.158, 0.159, 0.154, 0.142, 0.101, 0.139, 0.142, 0.129

**Top-N Sharpe sweep:**

| N | Avg Edge | Sharpe |
|---|---|---|
| 1 | +28.36% | 9.02 |
| 2 | +26.40% | 13.44 |
| 3 | +25.83% | 13.97 |
| **5** | **+24.15%** | **15.08** |
| 7 | +22.95% | 14.06 |
| 10 | +21.53% | 13.78 |

**Interpretation:** The 1-day label makes the model predict the execution target directly (what happens
in the next day), reducing label noise from days 2-5 that don't affect P&L. Volume features add IC
on top. Together they produce the lowest year-to-year variance seen (std 1.60%) and a Sharpe of 15.08
— nearly double H54's 9.17.

H93 does not replace H54 as production champion (still parked, execution gap still open). But it is
the best RL training signal found to date: higher Sharpe, lower variance, prediction target aligned
with execution window.

**For RL training:** H93 probas (`xs_barrier_vol_1d_hose_full.parquet`) are the recommended signal
file for RL state features. IC ~0.149 with edge std 1.60% gives a much more reliable daily ranking
signal than H54.

**Verdict:** PASS. Success bar met (Sharpe 15.08 >> 11.63 target). New best-Sharpe system.

---

## F57: H94 — Sector-Relative Features Add Nothing to H93 (2026-03-24, Session 28)

Adding sector-relative momentum features (`sector_rel_1d`, `sector_rel_5d`, `sector_rel_20d`) on
top of H93 (volume + 1-day label) produces no improvement. IC is unchanged (+0.0001), edge
slightly improves (+0.44%) but variance increases (1.60% → 1.73%), lowering Sharpe from 15.08 to 14.21.

| System | IC | Avg Edge | Edge Std | Sharpe |
|---|---|---|---|---|
| H93 | +0.1491 | +24.15% | 1.60% | 15.08 |
| H94 | +0.1492 | +24.59% | 1.73% | 14.21 |

**Interpretation:** The existing `rel_ret_Nd` (market-relative return lags) already encode most of
the cross-sectional signal. Sector-relative features are largely redundant. This replicates the
Session 25 H80 finding under the new H93 configuration — the result is robust to the label change.

**Verdict:** NEUTRAL. H93 remains the best configuration. Do not add sector-relative features.

---

## F58: vnstock Sector Classification Available via company.overview() (2026-03-24, Session 29)

`Vnstock().stock(symbol, source='VCI').company.overview()` returns columns `icb_name2`, `icb_name3`,
`icb_name4` — ICB-coded sector/industry labels. These can be fetched per ticker and joined to build
a full sector map across all 394 HOSE stocks. Enables H92 sector sub-models.

**ICB levels available:**
- `icb_name2`: Top-level sector (e.g., "Công nghệ Thông tin")
- `icb_name3`: Sub-sector (e.g., "Phần mềm & Dịch vụ Máy tính")
- `icb_name4`: Industry (e.g., "Phần mềm")

**Action:** Run `data_tools/fetch_sector_classification.py` to pull all 394 tickers and save
`data/features/sector_classification.parquet`.

---

## F59: Historical Daily Foreign Investor Flow NOT Available via vnstock (2026-03-24, Session 29)

`company.trading_stats()` gives current-day point-in-time foreign stats (foreign_volume, foreign_room,
current_holding_ratio). `trading.price_board()` gives today's intraday accumulated foreign_buy_volume /
foreign_sell_volume / foreign_buy_value / foreign_sell_value. Neither provides historical daily time series.

No `foreign_trading()` method exists on the company or trading objects. Historical daily foreign flow
data would require either:
1. Accumulating from a daily cron starting now (forward-only)
2. An alternative paid data source

**H95 (Foreign Investor Flow signal) is deferred** until a historical data source is identified.
vnstock's current API does not support backtesting foreign flow.

---

## F60: H89 — Keyword News Sentiment Adds No IC (2026-03-24, Session 29)

Adding keyword-based Vietnamese financial news sentiment to the H93 config (volume + 1-day label)
produces a regression in IC. Overall IC drops from +0.1405 (H93) to +0.1361 (H89) — a loss of 0.0044.

**Pipeline:** Parenthetical ticker extraction (`\(([A-Z]{2,5})\)`) + keyword lexicon
(26 positive terms, 25 negative terms) → sentiment_score, positive_ratio, article_count,
sentiment_cs_z. Output: `xs_news_sentiment_daily.parquet` (6,532 rows, 340 tickers, 2016-2026).

**Coverage:** ~0.8% of (trading_day, ticker) pairs have non-zero sentiment. 99.2% zeros (no news).

| System | IC | IC Std | Sharpe |
|---|---|---|---|
| H93 (baseline) | +0.1405 | 0.0945 | — |
| H89 (+ news) | +0.1361 | 0.1001 | — |

**Root cause:** Extreme sparsity. The model sees mostly zeros and learns to ignore sentiment.
The parenthetical ticker extraction is sound (~10.8% match rate) but the lexicon approach
may also be too coarse for Vietnamese financial journalism.

**Next step if revisiting:** (a) Rolling/lagged sentiment (5d/30d sum) to reduce sparsity;
(b) LLM-based extraction if API becomes available; (c) Higher-quality source (e.g., ticker-tagged feeds).

**Verdict (combined XGBoost model):** FAIL — do not include in H93 config.
**Verdict (standalone RL signal):** CANDIDATE — standalone IC +0.043, correlation 0.009 with S1.
Registered as C1 in `notes/signal_library.md`. See F62 for correct evaluation framework.

---

## F61: H92 — Sector Sub-Models Underperform Pooled Model (2026-03-24, Session 29)

Separate XS walk-forward models trained on banking stocks (20 tickers) and real estate stocks
(57 tickers) both underperform the pooled H93 model when evaluated on the same sector stocks.

| Sector | Tickers | Sub-model IC | Pooled IC | Delta |
|---|---|---|---|---|
| Banking | 20 | +0.1077 | +0.1238 | −0.0161 |
| Real Estate | 57 | +0.1308 | +0.1393 | −0.0085 |

**Pattern:** Larger sectors converge toward pooled model performance (RE delta < banking delta).
In some individual years with large real estate cohorts, sub-model matches or slightly beats pooled.

**Root cause:** Training data scarcity. Banking: ~20 stocks × 220 days/year = 4,400 rows/year.
Pooled: ~394 stocks = ~87,000 rows/year. More data matters more than sector specificity.

**Implication:** The cross-sectional momentum signal is sector-agnostic — the XS ranking works
across all sectors, not just within. Sector-specific patterns (if any) are already captured by
the pooled model through its cross-sectional features (`rel_ret_Nd`, `idx_ret_Nd`).

This replicates the H80/H94 findings: sector information (whether as relative features or
as universe filter) does not improve on the pooled cross-sectional model.

**Verdict:** NEUTRAL/FAIL. Do not split into sector sub-models. Pooled model is superior.

---

## F62: Correct Evaluation Framework for RL Signal Library (2026-03-24, Session 29)

Signals should NOT be evaluated by whether they beat H54 (+25.52% edge) or improve H93.
Those are complete strategies / combined models. Individual signals are state features for RL.

**Correct criteria for adding a signal to the library:**

| Criterion | Threshold | Rationale |
|-----------|-----------|-----------|
| Standalone IC | > 0.01 | Any reliable predictive content is learnable |
| Correlation with S1 (primary) | < 0.30 | Orthogonality = RL diversity value |
| IC positive years | ≥ 60% of in-sample years | Consistency, not noise |
| p-value (standalone) | < 0.10 | Weak bar — searching, not deploying |

**Why "fails to improve XGBoost" ≠ "not learnable":**
XGBoost cannot use sparse signals (< 5% coverage) effectively because:
(a) trees split on individual values, gaining nothing from mostly-zero features, and
(b) sparse features may slightly overfit noise, dragging down combined model IC.

An RL agent that observes all signals as separate state dimensions and learns to weight
them contextually can exploit a sparse signal that XGBoost ignores.

**Evidence:** H89 (news sentiment) reduced combined XGBoost IC by 0.0044, but tested
alone on news days has standalone IC +0.043 with correlation 0.009 vs S1.
It is a candidate signal for the RL library despite "failing" the combined model test.

**Implication:** After each signal experiment, always run standalone IC and orthogonality tests
before declaring a verdict. Update `notes/signal_library.md` accordingly.

---

## F63: Rolling News Aggregation Does Not Fix Sparsity for XS WF (2026-03-25, Session 30)

Rolling 5d/30d windows on daily news sentiment (built from title-only extraction) give:
- 5d coverage:  1.1% of (trading_day, ticker) pairs
- 30d coverage: 5.1% of (trading_day, ticker) pairs

Adding these rolling features to H93 XS WF:
- IC: +0.1491 → +0.1483 (−0.0008)
- Edge std: 1.60% → 1.76%
- Sharpe (N=5): 15.08 → 13.86

**Root cause:** 94.9% of rows are still zero after 30d rolling. Model assigns near-zero
feature importance to near-zero columns. Rolling doesn't create signal; it only redistributes
existing sparse signal into a denser format, with no gain in predictive content.

**Verdict:** FAIL. Rolling aggregation is not the fix for sparse news features.

---

## F64: Body-Text Ticker Extraction Increases Coverage but Reduces Quality (2026-03-25, Session 30)

Extracting tickers from article body_text (in addition to title parentheticals):
- Coverage: 5,225 → 27,001 matched (day, ticker) pairs (+5.2×)
- Body mentions: ~25% of articles (vs 0.8% title)

BUT per-observation signal quality drops:
- Standalone IC: H89 +0.041 → H99 +0.018 (body mentions are noisier)
- XS WF IC: H93 +0.1491 → H99 +0.1363 (−0.0128)
- Sharpe drops from 15.08 → 11.52

**Why body is noisier:** Body mentions include price widget sidebars, tangential references,
and articles where the company is mentioned peripherally but is not the subject. Title mentions
are more likely to indicate the stock is the article's primary subject.

**Verdict:** FAIL. Body extraction is not a quality improvement; it adds noise that the
XS WF model can't filter effectively.

---

## F65: News Keyword Lexicon Path Exhausted — LLM Quality Required (2026-03-25, Session 30)

Three approaches to news sentiment as an XS WF feature have all failed:
1. **H89:** Daily title sentiment (sparse, IC −0.0044 when added to H93)
2. **H96:** Rolling 5d/30d aggregation (denser but still 94.9% zero, IC −0.0008)
3. **H99:** Body-text extraction (6× more obs, IC −0.0128 due to lower quality)

**Standalone note:** H89 retains standalone IC +0.043 with near-zero correlation to S1 (0.009).
On days when news fires, the signal is directionally consistent in 5-6/10 years. This is RL-valuable
but XGBoost cannot use it.

**Path forward (H98):** Only higher-quality sentiment from LLM scoring (OpenAI/Claude API)
is likely to move the signal quality above the noise floor. Keyword lexicons are too coarse
for Vietnamese financial articles, which mix formal reporting with promotional language.

**What would help H98:** Score ~40k articles/day × 10 years ≈ 400M tokens → cost ~$800-2000 at
current API rates. Feasible with batching + caching if the research mandate expands.
A smaller test on 1 year of data (~$80-200) could validate the approach before full extraction.

---

## F66: Insider Deal Features — Standalone Signal Exists but Adds Noise to H93 (2026-03-26, Session 31)

**Source:** CafeF GDCoDong API (`cafef.vn/du-lieu/Ajax/PageNew/DataHistory/GDCoDong.ashx`)
- 394/394 HOSE tickers have insider + large-shareholder transaction data
- Date range: 2015–2026, 32k insider rows + 15k large-shareholder rows
- `is_insider` = ShareHolderCode prefix CEO_ (officers/directors) or LQ_ (related persons)
- **Signal key:** `published_date` (disclosure filing date, not transaction completion)

**Standalone IC (insider_net_plan_5d vs 5d relative return):**
- Average IC: +0.0255, 9/11 years positive
- Significant years: 2019 (p=0.042), 2020 (p=0.001), 2023 (p=0.004), 2024 (p=0.020)
- Coverage: 3.57% of (day, ticker) pairs (sparse but meaningfully better than news 0.8%)
- Correlation with H93 probas: −0.027 (near-zero → genuinely independent)

**XS WF test (H93 + insider features):**
| Metric | H93 | H97 (+insider) | Delta |
|--------|-----|----------------|-------|
| IC (Spearman) | +0.1491 | +0.1484 | −0.0007 |
| Sharpe (N=5, no VIX filter) | 15.08 | 10.77 | −4.31 |
| Edge std | 1.60% | 2.26% | +0.66% |
| Sig years | 11/11 | 11/11 | 0 |

**Root cause:** XGBoost model adds insider features as occasional tree splits, but these
features are so sparse (3.57%) that they introduce noise on the 96.43% of non-event rows.
The model learns a slight negative relationship (CEO_ prefix has negative FieldRef — possibly
because insiders sometimes sell to diversify after insider buying lifts the price).

**Verdict: FAIL.** Insider features are genuinely predictive in isolation but hurt the XS WF
due to sparsity and tree-model interaction effects. Like the news signal, this is a
RL-candidate (standalone IC +0.025) rather than an XGBoost feature.

**Infrastructure built:**
- `data/insider_cache/<TICKER>.parquet` — 394 raw per-ticker cache files
- `data/features/xs_insider_deals_raw.parquet` — combined 32k rows
- `data/features/xs_insider_features.parquet` — rolling 5d/30d feature matrix (826k rows)
- `data_tools/fetch_insider_deals.py` — CafeF crawler for all HOSE tickers
- `data_tools/build_insider_features.py` — rolling aggregation feature builder
- `--use-insider` flag in `cross_sectional_wf.py`

---

## F67: H98 LLM News Infrastructure Implemented; Experiment Pending Runtime Ollama Availability (2026-03-26, Session 33)

Implemented per root plan:
- `data_tools/extract_llm_news_features.py` (CafeF JSONL -> `data/llm_cache/YYYY-MM-DD.jsonl`)
- `data_tools/build_llm_news_features.py` (`data/llm_cache` -> ticker/day + market/daily parquets)
- `cross_sectional_wf.py` flags:
  - `--use-llm-news` (sparse ticker-day LLM features)
  - `--use-llm-market` (dense market-daily LLM features)

Smoke verification:
1. 3-day extraction run (`2023-01-01` to `2023-01-03`) created cache files and exercised resume-safe/atomic path.
2. In this runtime, all extraction batches timed out against local Ollama (0 parsed, all timeout fallbacks).
3. Feature builder successfully produced:
   - `xs_llm_news_ticker_day.parquet` (826,404 rows)
   - `xs_llm_news_market_daily.parquet` (2,748 rows)
4. Dense market output has zero NaNs after ffill/fill path.
5. WF smoke test confirmed both H98 merge blocks and feature registration are operational.

**Conclusion:** H98 code path is complete and runnable. Final signal-quality evaluation requires a reachable
local Ollama service (or equivalent LLM endpoint) to produce non-timeout extracted features.

---

## F68: H98 LLM Path Parked by Throughput Constraint (2026-03-26, Session 34)

H98 (LLM news extraction) is explicitly **PARKED** for now.

Reason:
- End-to-end extraction throughput in the current runtime is operationally too slow for full-history runs.
- Prior smoke runs in this environment showed timeout-heavy behavior against local Ollama.

Policy:
- Do not continue H98 runs in active sessions until runtime/inference throughput is resolved.
- Keep the implemented H98 infrastructure intact for later reactivation.

---

## F69: Dense Signals Sweep — Dispersion Regime Passes, Open/Close Asymmetry Fails Risk-Adjusted Bar (2026-03-26, Session 34)

Baseline reference: H93 (`xs_barrier_vol_1d_hose_full.parquet`)
- IC +0.1491
- Top-5 avg edge +24.15%
- Top-5 Sharpe 15.08
- Edge std 1.60%

### H100 (open/close asymmetry features)
- IC: +0.1541 (**+0.0050** vs H93)
- Top-5 edge: +25.36% (**+1.21%**)
- Sharpe: 11.63 (**−3.45**)
- Edge std: 2.18% (**+0.58%**)
- **Verdict:** FAIL (variance blow-up outweighs edge gain).

### H101 (cross-sectional dispersion regime features)
- IC: +0.1474 (**−0.0017** vs H93)
- Top-5 edge: +23.83% (**−0.32%**)
- Sharpe: 15.34 (**+0.26**)
- Edge std: 1.55% (**−0.05%**)
- **Verdict:** PASS (risk-adjusted improvement; dense and stable).

### H102 (H100 + H101 combined)
- IC: +0.1531 (**+0.0040** vs H93)
- Top-5 edge: +25.23% (**+1.08%**)
- Sharpe: 9.96 (**−5.12**)
- Edge std: 2.53% (**+0.93%**)
- **Verdict:** FAIL (asymmetry-driven volatility dominates).

Implication:
- Among tested dense branches, **H101 is the only viable continuation path**.
- H100-style open/close asymmetry should not be promoted in current form.

---

## F70: H103 Return Skewness Fails Both Risk-Adjusted and Standalone Bars (2026-03-26, Session 35)

H103 added dense ticker-day return skewness/tail-shape features:
- `ret_skew_5d`, `ret_skew_20d`, `ret_skew_60d`
- downside/upside volatility and ratio
- left-tail fraction and skew z-score

Portfolio result vs H93 baseline:
- IC: +0.1489 (vs +0.1491, −0.0002)
- Top-5 avg edge: +24.19% (vs +24.15%, +0.04%)
- Sharpe: 10.63 (vs 15.08, **−4.45**)
- Edge std: 2.28% (vs 1.60%, **+0.68%**)

Standalone RL-gate check (`ret_skew_z20` vs `future_rel_return_5d`):
- Avg IC: +0.0019
- Positive years: 6/11
- Corr with S1: −0.0035

Interpretation:
- Orthogonality is good, but standalone predictive strength is below the IC > 0.01 bar.
- In supervised integration, skewness features materially increase variance without improving IC.

**Verdict:** FAIL. Do not continue return-skewness branch in current form.

---

## F71: Earnings Calendar Dense Features Are Too Weak and Degrade Risk-Adjusted Performance (2026-03-26, Session 36)

H104 introduced dense date-level earnings/reporting season features based on quarter-end timing and
typical filing windows.

H104 (H93 + earnings calendar):
- IC: +0.1480 (vs H93 +0.1491, −0.0011)
- Top-5 edge: +24.14% (vs +24.15%, flat)
- Sharpe: 11.80 (vs 15.08, **−3.28**)
- Edge std: 2.05% (vs 1.60%, **+0.45%**)

H105 (H101 + earnings calendar):
- IC: +0.1466 (vs H101 +0.1474, −0.0008)
- Top-5 edge: +24.16% (vs +23.83%, +0.33%)
- Sharpe: 11.96 (vs 15.34, **−3.38**)
- Edge std: 2.02% (vs 1.55%, **+0.47%**)

Standalone gate checks for earnings-calendar features are weak:
- `days_since_q_end` avg IC: +0.0060 (6/11 positive years)
- `in_report_w15_45` avg IC: +0.0059 (8/11)
- `in_report_w20_50` avg IC: +0.0014 (8/11)
- Context vs S1 daily top-5 hit rate: near-zero (e.g., rho −0.004, p=0.832)

Interpretation:
- The features are dense and look structurally plausible, but predictive strength is too weak.
- When injected into supervised ranking, they add noise/variance and reduce Sharpe.

**Verdict:** FAIL. Earnings-calendar branch should not be continued in current form.
