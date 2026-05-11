# Session 19: S1 Depth5 Full 11-Fold Validation

**Date:** 2026-05-11
**Status:** VALIDATED_CANDIDATE (provisional until risk controls verified)

## Context
- Focus year analysis (S00015) found `s1_top5_rebal10_depth5` improves both 2021 and 2022
- Need to validate whether this holds across full 2015-2025 (11-fold)

## Pre-flight
- ✅ test_execution_ablation_walkforward_parity.py: PASSED
- ✅ test_diagnostics_regression.py: PASSED
- ✅ test_parity.py: PASSED

## Full 11-Fold Results

### Strategy Summary
| Strategy | Mean Ann Ret | Median Ann Ret | Positive Folds | Total Folds |
|----------|-------------|----------------|----------------|-------------|
| s1_top5_rebal10 (baseline) | -4.68% | -7.09% | 4/11 | 11 |
| s1_top5_rebal10_depth5 | **+0.98%** | +3.25% | **6/11** | 11 |

**Delta: +5.67% mean annualized return improvement**

### Year-by-Year Comparison
| Year | Baseline | Depth5 | Delta | Improved? |
|------|----------|--------|-------|-----------|
| 2015 | +2.3% | +12.7% | +10.4% | ✅ |
| 2016 | -18.3% | -24.5% | -6.2% | ❌ |
| 2017 | -1.2% | +20.3% | +21.5% | ✅ |
| 2018 | -32.8% | -44.3% | -11.5% | ❌ |
| 2019 | -12.9% | -7.8% | +5.1% | ✅ |
| 2020 | -7.1% | +15.7% | +22.8% | ✅ |
| 2021 | +28.8% | +38.8% | +10.0% | ✅ |
| 2022 | -7.5% | -5.3% | +2.2% | ✅ |
| 2023 | +4.9% | +16.5% | +11.6% | ✅ |
| 2024 | +13.9% | +3.2% | -10.7% | ❌ |
| 2025 | -21.4% | -14.7% | +6.7% | ✅ |

**Depth5 improved in 8/11 folds**

### Key Findings
1. **Mean annualized return**: -4.68% → +0.98% (+5.67% improvement)
2. **Positive folds**: 4/11 → 6/11 (more winning years)
3. **2022 (bear year)**: -7.5% → -5.3% (IMPROVED, not worsened!)
4. **Downside years**: 2016, 2018, 2024 became worse
5. **Beats benchmark**: 0 for both (neither consistently beats VN30)

## Decision Rule Application
1. **Improves mean annualized return?** ✅ YES (+5.67%)
2. **Reduces positive folds?** ✅ NO (4→6, more positive)
3. **Materially worsens downside years?** ⚠️ MIXED - 2022 improved, but 2018/2016/2024 worsened

## Verdict: VALIDATED_CANDIDATE with RISK CAVEAT ⚠️

- Depth5 improves overall mean return (+5.67%) AND increases positive folds (4→6)
- Improved 8/11 folds: 2015, 2017, 2019, 2020, 2021, 2022, 2023, 2025
- Worsened 3/11 folds: **2016, 2018, 2024** - risk autopsy needed
- 2022 (key bear year) improved, but 2018 got worse
- Do NOT call it "tradable" - this is a provisional candidate, not final
- Do NOT claim "does not materially worsen downside years" - 2018 worsened materially

## Next Steps
- Consider regime-aware approach: depth5 in bull years, baseline in bear years?
- Document that s1_top5_rebal10_depth5 is a validated improvement candidate
- Do NOT finalize as durable finding - more validation needed for risk controls

## Artifact
- `artifacts/s1_depth5_validation_walkforward/20260511_184754/`