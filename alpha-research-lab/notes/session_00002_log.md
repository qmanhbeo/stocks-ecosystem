# Session 02 Log — OHLCV Exhaustion (2026-03-16)

## Objectives
Fix the drift-baseline metric issue. Exhaustively test all standard OHLCV feature combinations
at 1d and 5d horizons. Determine if any technical analysis has edge on FPT.

## System State (entering)
Broken metric (comparing to 50% instead of drift). No walk-forward validation.

## Infrastructure Built This Session
- Added `edge_over_naive`, `dir_pvalue_vs_naive` to `src/evaluator.py`
- Test set made sacred (`--eval-test` flag)
- Built `walk_forward.py` — year-by-year walk-forward validation (train on years < Y, test on Y)
- Added `xgboost_classifier` + AUC support to `src/model_factory.py`

## Experiments

### Phase 1 — 5d Target Feature Ablation (XGBoost)

| Config | Features | avg_wf_edge | sig_years | verdict |
|--------|----------|-------------|-----------|---------|
| A1 | Lag returns 1-60d | +0.00% | 0/7 | Collapses to drift |
| A2 | MA distances (5-100d) | +0.55% | 0/7 | Not significant |
| A3 | RSI + MACD + BB + ATR | -0.80% | 0/7 | Worse than naive |
| A4 | Volume (OBV, ratio) | -0.27% | 0/7 | Negative |
| A5 | All combined | 0.00% | 0/7 | Model collapsed to "always up" |

### Phase 2 — 1d Target

| Config | Features | avg_wf_edge | verdict |
|--------|----------|-------------|---------|
| B1 | Lag returns 1d | -0.17% | Noise |
| B2 | Tech indicators 1d | +0.27% | Noise |
| B3 | All features 1d | +1.10% | Not significant (pval 0.357) |

### Phase 3a — Balanced Classifier
- C1 balanced clf lags 5d: dir_acc 38.9%, AUC 0.463 — anti-predictive

## Key Discovery
The ~62% val dir_acc from Session 1 was entirely market drift. Val period (2023-2024) was a bull
market: val=59.3% positive rate, test=46.7% positive rate (opposite regimes). The XGBoost model
had learned "always predict up" and scored well by coincidence.

## Session Conclusions
**F2 confirmed:** Standard OHLCV technical analysis has zero statistically significant edge on FPT
at any horizon. Consistent with weak-form EMH. No further OHLCV-only experiments warranted.

**Regime mismatch (F3):** Fixed 70/15/15 split puts val in bull market (2023-2024), test in bear
(2024-2026). Walk-forward (year-by-year) is the correct validation method for this problem.

## Production System After This Session
None. All OHLCV combinations = 0 edge.

## Next Session Priority
New data (multi-stock, FX, commodities). Market-relative target to remove drift bias.
