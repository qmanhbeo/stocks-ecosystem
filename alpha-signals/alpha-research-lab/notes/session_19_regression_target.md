# Session 19: Regression Target vs Binary Classifier

## Hypothesis
Replace binary triple-barrier labels with continuous excess return as regression target.
Two expected benefits:
1. Model learns magnitude, not just direction
2. Softmax portfolio eliminates contaminated TOP_N/MIN_PROBA parameters

## Experiments

### H58: XGBoost Regressor Walk-Forward
- Target: `future_rel_return_5d` (continuous 5d excess return vs VNINDEX)
- Model: XGBRegressor, same features as H54 (35 cols), expanding window, depth=3
- Implementation fixes needed: NaN/inf/extreme-value filter on regression target (last 5 rows per stock have NaN; some stocks have inf returns from zero-price days)
- Output: `data/features/xs_regressor_scores_hose_full.parquet` (824,704 rows, 393 tickers, 2015-2025)
- FPT avg edge: -0.06% (basically no FPT-specific signal — regression doesn't improve single-stock prediction)

### H59a: Softmax Portfolio (parameterless, no VIX filter)
- Temperature sweep: best at temp=0.1, Sharpe **1.80**, avg edge +0.37%, 10/11 years
- Root cause of weakness: scores in [-0.03, +0.03] → even at temp=0.1, softmax weights barely concentrate
- VIX-filtered (15-30): Sharpe 0.38, avg edge +1.01% — also weak

### H59b: Top-N Ranking Portfolio (no min_proba, no VIX filter)
**Quintile test:**
| Year | Q5 rate | Q1 rate | Spread | IC | Sig |
|------|---------|---------|--------|----|-----|
| Avg | 53.9% | 39.4% | +13.69% | 0.099 | 11/11 |

The regressor does rank stocks (real signal). But portfolio performance:
| TOP_N | Avg Edge | Sharpe | Years |
|-------|----------|--------|-------|
| 5 | +14.44% | 3.82 | 11/11 |
| 7 | +13.37% | 3.90 | 11/11 |
| 10 | +12.45% | 4.36 | 11/11 |

Best is TOP_N=10 at Sharpe 4.36.

### H60: Nested WF (h52)
- Failed: MIN_PROBA grid (0.5, 0.52, 0.55, 0.58) eliminates all regression scores (range ~[-0.03, +0.03])
- Not viable for regression scores without major h52 rewrite

## Comparison vs Baselines
| | H54 (classifier) | H56 (honest nested) | H59a (regressor softmax) | H59b (regressor top-10) |
|---|---|---|---|---|
| Avg edge | +25.52% | +25.98% | +0.37% | +12.45% |
| Sharpe | 9.17 | 7.35 | 1.80 | 4.36 |
| IC | ~0.12 | — | 0.099 | 0.099 |
| Contaminated params | TOP_N, MIN_PROBA | 0 | 0 | TOP_N |

## Conclusion
**REGRESSION FAILS.** Neither success criterion met:
- Primary: Sharpe ≥ 7.35 (zero params, H59a) → got 1.80 ✗
- Fallback: Sharpe > 5.0 (any config) → best is 4.36 (TOP_N=10) ✗

Root cause: The classifier's 0/1 boundary creates sharper probability gradients that distinguish the true top-5 from the next 5 better than the regression's continuous scores. The regressor's signal is real but weaker as a ranking device.

**Decision: Revert to H54 classifier as production system.**

## Technical Notes
- XGBRegressor already existed in model_factory.py — only cross_sectional_wf.py needed changes
- 6 changes to cross_sectional_wf.py: MODEL_MAP already had xgboost_reg (from prior session), target_col logic too; new: early stopping branch, probas fallback, actual_label binarization, accuracy reporting, NaN/inf filter
- Filter `y_train.abs() < 10` clips returns > 1000% (data quality issue, not real trades)
