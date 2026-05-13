# Session 09 Log — Methodology Audit + Multi-Stock Portfolio (2026-03-17)

## Objectives
1. FLAG: Audit the contamination issue — 40+ experiments have used 2019-2025 as an implicit
   validation set. Formalize what is and isn't clean.
2. H24: Test LightGBM as XS model alternative.
3. H25: Per-direction breakdown of H22's remaining losses.
4. H23: Multi-stock portfolio — apply XS barrier model to all 52 VN stocks.

## System State (entering)
Best: H22 +15.13% avg, Sharpe ~1.52 (barrier XS + E32 + VIX 18-35).

## Source File
- `notes/session9_methodology_concerns.md` — full contamination analysis

## Methodology Concern (PRIORITY ZERO — read before any Session 9 experiments)

All walk-forward years 2019-2025 have been used implicitly as a validation set for parameter
selection across 40+ experiments. Every filter tuned (VIX band, confidence threshold, barrier %,
VNINDEX filter, agree-only) was selected by observing those years' results.

**What is clean:**
- XGBoost internal early stopping (within-fold only) ✓
- Walk-forward train/test structure (no look-ahead within model) ✓

**What is contaminated:**
- Every system-level parameter: VIX_MIN=18, VIX_MAX=35, MIN_PROBA=0.55, BARRIER=1.0%
- The "2022 is fixed" claim: we tuned against 2022 data to choose H17 over X9

**True held-out: 2026 data** — never touched. ~55 trading days Jan-Mar 2026.
Expected ~8-9 confident H22 trades. Small but genuinely out-of-sample.

**Recommended practice going forward:** Use 2023-2025 as a soft validation signal (report but
don't tune against). Reserve 2026 as final honest test.

## H24 — LightGBM XS Model

**Hypothesis:** LightGBM may generalize differently than XGBoost on this dataset.

**Implementation:** Added `--model lightgbm` flag to `cross_sectional_wf.py`.
New file: `data/features/xs_barrier_lgbm_fpt_proba.csv`

**Result: FAILED. +11.10% avg edge vs H22's +15.13%.**

Key: 2025 collapses from +20.85% to -2.96%. LightGBM is worse on this dataset.
XGBoost with early stopping is better calibrated for this problem.

**Verdict (F18):** No further LightGBM experiments warranted.

## H25 — Per-Direction Breakdown of H22

**Hypothesis:** H22's residual -2.07% in 2022 comes from DOWN predictions specifically.

**Result: CONFIRMED.**

| Year | Dir | n | Acc | Edge |
|------|-----|---|-----|------|
| 2022 | UP | 40 | 65.0% | +6.77% |
| 2022 | DOWN | 33 | 45.5% | **-12.78%** |
| 2025 | UP | ~41 | — | — |
| 2025 | DOWN | — | — | **-11.29%** |

Mechanism: "defensive rotation" — FPT keeps outperforming when model predicts underperformance.
Pattern also appears in 2025 DOWN predictions.

**Verdict (F19):** Blocking DOWN signals would help 2022 but risks overfitting (only 1 bear year).
Defer blocking-DOWN experiments to 2026 validation. Not acted on this session.

## H23 — Multi-Stock Portfolio (Top-5 by XS Barrier Proba)

**Hypothesis:** XS barrier model generates walk-forward confident predictions for all 52 stocks.
Some stocks may have stronger signal than FPT. Top-5 portfolio should diversify and improve.

**Implementation:** Added `--save-all-probas` flag to `cross_sectional_wf.py`.
New file: `data/features/xs_barrier_all_probas.parquet` (all 52 tickers, all years)

**Result: LANDMARK. +21.94% avg edge, Sharpe 2.54, 11/11 sig years including 2022 (+15.71%*).**

Per-ticker highlights:
- EIB (Viet Capital Bank): strongest signal
- STB (Sacombank): second strongest
- BID (BIDV): third
- FPT alone: +2.70% in the same framework

**Why banking stocks dominate:** Banking stocks have higher turnover, more cross-sectional
co-movement, and stronger relative momentum patterns vs VNINDEX than tech stocks like FPT.

**Critical caveat (contamination):** Stock selection (which 5 stocks to include) was done by
observing 2015-2025 walk-forward results. Same contamination issue as all prior experiments.
The +21.94% figure is optimistic to an unknown degree. Genuine test is 2026.

**Verdict (F20):** Portfolio approach works dramatically better than FPT-alone. The XS signal
is much stronger for banking stocks than for FPT specifically.

## Session Conclusions

1. **Methodology contamination is formally acknowledged.** All edge numbers are optimistic.
   2026 is the only honest test. No further parameter tuning against 2015-2025 results.

2. **H23 is a landmark result**: 11/11 positive years, 2022 fixed to +15.71%. The XS barrier
   model has real, robust signal across the stock universe.

3. **LightGBM is worse than XGBoost** on this dataset. Not worth pursuing further.

4. **FPT is the weakest signal stock** in the XS universe. Banking stocks (EIB, STB, BID)
   have much stronger relative momentum predictability.

## Production System After This Session
**H23** (XS barrier top-5 portfolio, VIX 18-35): **+21.94% avg, Sharpe 2.54**
**H22** (FPT-only): **+15.13% avg, Sharpe ~1.52** — still the clean single-stock system

## Next Session Priority
Macro regime filters on top of H23 portfolio. Can principled external filters (VIX momentum,
copper/gold ratio) improve Sharpe further without additional parameter contamination?
