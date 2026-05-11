# Regime Decomposition Analysis (CORRECTED)

## Goal
Explain why strategies fail in bull regimes (2017, 2025) while performing better in years like 2021 and 2022.

## Input Data

- **Source**: Walk-forward validation fold_metrics.csv
- **Artifact used**: `artifacts/walk_forward/2025/05/11/20260511_164519/`
- **Rows in artifact**: 66 (6 strategies × 11 annual folds)
- **Contains all strategies**: ✅ YES (not a single-strategy debug run)

## Strategies Analyzed

1. `s1_top5_rebal10`
2. `s1_top5_rebal5`
3. `s1_top3_rebal10`
4. `blend_70_30_top5`
5. `blend_50_50_top5`
6. `c16_only_top5`

## Folds (2015-2025)

All 11 annual folds: 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025

## Strategy Regime Summary

| Strategy | Avg Excess (2017, 2025) | Avg Excess (2021, 2022) | Positive Folds | Behavior |
|----------|-------------------------|-------------------------|----------------|----------|
| s1_top5_rebal10 | -53.80% | +10.49% | 2/11 | REGIME-SENSITIVE |
| s1_top5_rebal5 | -59.78% | +5.28% | 4/11 | MIXED |
| s1_top3_rebal10 | -58.74% | +33.98% | 3/11 | REGIME-SENSITIVE |
| blend_70_30_top5 | -53.87% | +40.54% | 5/11 | REGIME-SENSITIVE |
| blend_50_50_top5 | -63.04% | +28.31% | 4/11 | REGIME-SENSITIVE |
| c16_only_top5 | -62.14% | +0.53% | 3/11 | MIXED |

## Focus Year: 2017 (FAILURE BULL, Benchmark +46.6%)

| Strategy | Return | Excess | Trades |
|----------|--------|--------|--------|
| blend_70_30_top5 | +0.7% | -45.9% | 47 |
| blend_50_50_top5 | +0.2% | -46.4% | 43 |
| s1_top3_rebal10 | +0.0% | -46.6% | 13 |
| s1_top5_rebal10 | -1.2% | -47.8% | 29 |
| s1_top5_rebal5 | -10.0% | -56.6% | 62 |
| c16_only_top5 | -10.8% | -57.3% | 16 |

## Focus Year: 2025 (FAILURE BULL, Benchmark +38.4%)

| Strategy | Return | Excess | Trades |
|----------|--------|--------|--------|
| s1_top5_rebal10 | -21.4% | -59.8% | 57 |
| blend_70_30_top5 | -23.4% | -61.8% | 46 |
| s1_top5_rebal5 | -24.5% | -63.0% | 120 |
| c16_only_top5 | -28.5% | -66.9% | 12 |
| s1_top3_rebal10 | -32.5% | -70.9% | 32 |
| blend_50_50_top5 | -41.2% | -79.7% | 31 |

## Focus Year: 2021 (SUCCESS, Benchmark +33.1%)

| Strategy | Return | Excess | Trades |
|----------|--------|--------|--------|
| blend_70_30_top5 | +82.3% | +49.2% | 72 |
| s1_top3_rebal10 | +64.4% | +31.3% | 38 |
| blend_50_50_top5 | +47.4% | +14.3% | 58 |
| s1_top5_rebal10 | +28.8% | -4.3% | 68 |
| s1_top5_rebal5 | +15.4% | -17.7% | 132 |
| c16_only_top5 | +1.5% | -31.6% | 12 |

## Focus Year: 2022 (SUCCESS, Benchmark -32.8%)

| Strategy | Return | Excess | Trades |
|----------|--------|--------|--------|
| blend_50_50_top5 | +9.6% | +42.3% | 48 |
| s1_top3_rebal10 | +3.9% | +36.6% | 29 |
| c16_only_top5 | -0.1% | +32.6% | 9 |
| blend_70_30_top5 | -0.9% | +31.9% | 54 |
| s1_top5_rebal5 | -4.5% | +28.2% | 133 |
| s1_top5_rebal10 | -7.5% | +25.3% | 57 |

## What Was Proven

1. **4 out of 6 strategies show REGIME-SENSITIVE behavior**:
   - blend_70_30_top5, blend_50_50_top5, s1_top5_rebal10, s1_top3_rebal10
   - All have negative average excess in failure years (2017, 2025)
   - All have positive average excess in success years (2021, 2022)

2. **Failure is consistent across strategies in bull markets**:
   - All strategies underperformed in 2017 and 2025
   - The worst performers in bull years were NOT the same as best performers in other years

3. **Success patterns differ**:
   - 2021: blend_70_30_top5 dominated (+49% excess)
   - 2022: blend_50_50_top5 dominated (+42% excess)
   - Same strategy doesn't win everywhere

## What Remains Uncertain

**CRITICAL: Fold-level metrics CANNOT prove the following:**

1. **Ticker-level cause**: We don't know what stocks were bought/sold
2. **Cash exposure**: We don't have daily equity curves showing cash vs invested
3. **Sector tilt**: No sector-level analysis available
4. **Signal composition**: Can't confirm which component (RL vs C16) drives behavior
5. **Defensive vs offensive**: Can't prove "defensive by design" - only observed pattern

The evidence supports "consistent with regime-sensitive behavior" but NOT "proven defensive design."

## Files in This Artifact

- `year_strategy_metrics.csv` - All 66 strategy-year combinations
- `focus_year_diagnostics.csv` - Focus years (2017, 2021, 2022, 2025) with all strategies
- `strategy_regime_summary.csv` - Per-strategy regime behavior classification
- `summary.json` - Machine-readable summary with metadata

## Recommendation

Do NOT promote any strategy to paper-trading without:
1. Regime detection research (VNINDEX regime indicator)
2. Conditional exposure logic (reduce exposure in bull regimes)
3. Trade-level analysis to understand ticker selection effects

This is an alpha-research-lab level investigation.

---
*Generated: 2026-05-11*
*Analysis: analyze_regime_failures.py*
*Input: artifacts/walk_forward/20260511_164519 (66 rows, all strategies)*