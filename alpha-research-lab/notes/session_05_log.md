# Session 05 Log — Nine New Signal Directions (2026-03-16)

## Objectives
Test 9 new signal directions on top of E8: Tet calendar, vol regime, risk-adjusted momentum,
earnings cycle, market breadth, longer horizons, LightGBM. Build ensemble infrastructure.

## System State (entering)
Best single-stock: E8 +0.73%. XS model confirmed signal real. Need ensemble infrastructure.

## Infrastructure Built This Session

**New feature functions in `src/feature_engineering.py`:**
- `_add_vol_regime()` — VNINDEX 20d realized vol + rolling percentile
- `_add_calendar()` — Tet holiday features (days_to_tet, days_since_tet, pre/post windows)
- `_add_risk_adj_momentum()` — relative Sharpe ratio (rel_sharpe_5d/10d/20d)
- `_add_earnings_cycle()` — FPT quarterly earnings cycle (days_to/from earnings, windows)
- Updated `_add_cross_sectional()` to expose market breadth columns

**New scripts:**
- `ensemble_wf.py` — NEW. Subcommands:
  - `save-ss`: generates single-stock walk-forward probabilities
  - `ensemble`: merges XS + SS probas, reports confident/agree-only accuracy
- `src/model_factory.py`: added `lightgbm_classifier`

**New experiment configs (E19-E28):**
- E19/E20: 10d/20d prediction horizons
- E21: E8 + Tet calendar (V2)
- E22: E8 + VNINDEX vol regime (V1)
- E23: E8 + risk-adjusted momentum
- E24: E8 + earnings cycle
- E25: E8 + market breadth
- E26: LightGBM (E8 features)
- E27, E28: calendar combinations

## Experiments

### All 9 Signal Directions — Verdict

| Experiment | Hypothesis | avg_wf_edge | verdict |
|-----------|-----------|-------------|---------|
| E21 (Tet calendar) | Tet rally/sell-off seasonality | ~ 0% | FAILED |
| E22 (vol regime) | Signal better in high-vol environments | ~ 0% | FAILED |
| E23 (risk-adj momentum) | Sharpe-weighted rel momentum cleaner | -0.18% | FAILED (but fixed 2022: -7.6% → +0.8%) |
| E24 (earnings cycle) | Earnings windows predict FPT direction | -0.18% | FAILED |
| E25 (market breadth) | Breadth predicts FPT relative strength | ~ 0% | FAILED |
| E26 (LightGBM) | Different model generalizes better | ~ 0% | FAILED |
| E19 (10d horizon) | Longer horizon more predictable | — | FAILED (too much variance) |
| E20 (20d horizon) | Longer horizon more predictable | — | FAILED (too much variance) |
| E28 (full calendar) | Combined calendar effects | -0.47% | FAILED |

**None beat E8 (+0.73%).**

### Notable: E23 (risk-adjusted momentum)
Fixes 2022 anomaly: -7.6% → +0.8% by normalizing relative returns by volatility.
However, it hurts 2024. Not an improvement overall, but useful diagnostic.

### X2 Breakthrough: XS Model with Confidence Filter

Running XS model at threshold=0.05 (only trade when |prob-0.5| > 0.05 → model has ≥55% confidence):
- XS model avg edge on confident days: **+3.87%** (~52 days/year)
- 2019: +17%*, 2025: +38%*** — model is accurate when confident
- 2020: -12%, 2022: -17%* — model is confidently WRONG in crash/defensive years

The confidence filter reveals the signal's structure: model is often right when confident, but
crash regimes break it.

## Session Conclusions

1. **All 9 new feature directions failed to beat E8.** Single-stock feature space is truly exhausted.
   No calendar, regime, or momentum modification improves on E8's relative momentum signal.

2. **XS model with confidence filter (X2) is the path forward**: +3.87% on confident days vs E8's
   +0.73%. The cross-sectional model's confidence score is a meaningful quality filter.

3. **2020 and 2022 identified as regime-specific**: COVID crash (2020) and bear market (2022) are
   the same pattern — FPT defensive behavior diverges from cross-sectional expectations.

4. **Ensemble infrastructure is ready**: `ensemble_wf.py` can combine XS + SS probabilities.

## Production System After This Session
**E8**: still +0.73% avg edge (best single-stock). **X2**: +3.87% on ~52 confident days/year.

## Next Session Priority
Build X3 ensemble (XS + E8). Apply VIX and regime filters. Find the best meta-predictor
for when to trust the XS model's confident predictions.
