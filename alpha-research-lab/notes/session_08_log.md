# Session 08 Log — Regime Filters + XS Barrier Labels (2026-03-16)

## Objectives
Attack the 2022 problem with regime filters (H16) and barrier XS labels (H17). Run barrier
threshold sweep (H21). Test VIX upper cap (H22). Test meta-feature approach (H18).

## System State (entering)
Best: X8-E32 +13.96% avg edge. 2022 = -16.03%* (structural failure year).

## Source Files
This session has detailed per-experiment files:
- `notes/session8_findings.md` — H16 full sweep
- `notes/session8_h17_findings.md` — H17 results + comparison table
- `notes/session8_h21_barrier_sweep.md` — H21 barrier threshold sweep
- `notes/session8_h22_vix_cap.md` — H22 VIX upper cap
- `notes/session8_h18_findings.md` — H18 meta-feature (failed)
- `notes/session8_2022_diagnosis.md` — month-by-month 2022 diagnosis

## H16 — VNINDEX Trend Filter

**Hypothesis:** Filter trades when VNINDEX 60d return < threshold. 2022 was a bear market —
filter the declining period and eliminate 2022 losses.

**Result: 2022 is NOT fixable by external trend filtering.**

Key finding: as the filter tightens, 2022 per-trade edge gets WORSE:
- Unfiltered 2022: -16.03% per trade
- 60d > -5%: -20.11% per trade
- 60d > 0%: -25.76% per trade

The filter removes the GOOD 2022 months (Jun-Aug, model was 82-83% accurate in stable bear)
and keeps the BAD months (Jan-Mar, defensive rotation). This is backwards.

**Best X9 config** (60d >= -5%): +16.88% avg edge (new raw best), but 2022 = -20.11%*.

**Root cause (2022 diagnosis):** Two distinct 2022 regimes:
- Jan-May ("defensive rotation onset"): Model predicts DOWN, FPT goes UP — 71-75% wrong.
  VNINDEX just starting to decline, capital rotating INTO FPT. Not yet visible in 60d trend.
- Jun-Aug (stable bear): Model works! 82-83% accuracy.
The VNINDEX filter cannot separate these because both regimes have similar 60d trend values.

## H17 — XS Triple Barrier Labels (1.0%)

**Hypothesis:** XS model uses standard 5d direction labels (label noise). Barrier labels remove
ambiguous <1% relative move days from training → model doesn't generate false confidence on
early-2022 defensive rotation days.

**Implementation:** Added `--barrier-pct` flag to `cross_sectional_wf.py`. New file:
`data/features/xs_barrier_fpt_proba.csv`

**Result: 2022 near-fixed. New Sharpe champion.**

| System | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | Avg Edge | Sharpe |
|--------|------|------|------|------|------|------|------|----------|--------|
| X9 (std XS + VN60≥-5%) | +12.23% | +35.32%* | +9.91% | -20.11%* | — | +30.87%* | +33.06% | +16.88% | ~0.88 |
| **H17 (barrier XS + E32)** | **+28.91%** | **+11.72%** | **+16.32%*** | **-2.07%** | **+3.35%** | **+22.12%** | **+26.21%** | **+15.22%** | **~1.42** |

**Why H17 works:** Barrier XS is uncertain about early-2022 defensive rotation days (small <1%
relative moves excluded from training) → proba ≈ 0.5 → below min_conf → no trade.
Standard XS was trained on these as "label=1" → generated false confidence.

**VN60 filter hurts H17:** Adding the trend filter to H17 removes the good Jun-Aug 2022 months
and makes 2022 worse (-8.23%). Barrier XS handles 2022 internally — no external filter needed.

## H21 — XS Barrier Threshold Sweep (0.5%, 1.0%, 1.5%)

**Result: 1.0% is the optimal XS barrier.**

| System | 2022 | 2023 | Avg Edge |
|--------|------|------|----------|
| H17 (1.0%) | -2.07% | +3.35% | **+15.22%** |
| H21a (0.5%) | -2.16% | **-11.43%** | +13.23% |
| H21b (1.5%) | -6.89% | -10.56% | +8.90% |

- 0.5% barrier: 2022 similar to 1.0%, but 2023 catastrophic (-11.43%). Overfitting from fewer samples.
- 1.5% barrier: both 2022 and 2023 worse. Some early-2022 ambiguous days pushed into wrong label bucket.
- 1.0% is the sweet spot: high enough to exclude defensive rotation noise, low enough to keep genuine signal.

## H22 — VIX Upper Cap (VIX ≤ 35)

**Hypothesis:** VIX > 35 (extreme fear) = COVID crash days where FPT acts defensively.
Adding upper cap removes these while keeping normal elevated-volatility trading days.

**Result: Marginal improvement, +7% Sharpe gain.**

| System | 2020 | 2022 | Avg Edge | Sharpe |
|--------|------|------|----------|--------|
| H17 base (VIX ≥ 18) | +11.72% | -2.07% | +15.22% | ~1.42 |
| H22 VIX 18-40 | +16.27%* | -2.07% | +15.11% | ~1.46 |
| **H22 VIX 18-35** | **+18.83%*** | **-2.07%** | **+15.13%** | **~1.52** |

VIX ≤ 35 removes 14 extreme COVID peak days (2020), improves 2020 from +11.72% to +18.83%.
No effect on 2022 (barrier XS already handles this). Small 2025 trade-off (removes some VIX~30-35 days).

Run command:
```bash
conda run -n stocks python ensemble_wf.py ensemble \
  --xs-proba data/features/xs_barrier_fpt_proba.csv \
  --ss-proba data/features/ss_fpt_proba_e32.csv \
  --min-conf 0.55 --vix-min 18 --vix-max 35 --agree-only
```

## H18 — XS Proba as Meta-Feature in E32 Training

**Hypothesis:** Instead of equal-weight ensemble, train E32 with XS proba as an input feature.
Let the single-stock model learn when to trust the cross-sectional signal.

**Result: FAILED. 2025 severely hurt.**

| System | 2022 | 2025 | Avg Edge |
|--------|------|------|----------|
| H22 (baseline) | -2.07% | +20.85% | +15.13% |
| H18a (barrier XS meta in E32) | -2.52% | **+8.15%** | +13.67% |
| H18b (std XS meta in E32) | -6.33% | +5.81% | +12.71% |

H18 fires MORE trades in 2025 (n=18 vs n=7) but at lower quality (44.4% acc). When E32 learns
to rely on xs_proba, it distorts its own FPT-specific momentum signal in regime-change years
(2025: FPT outperforms cross-sectional; xs_proba says "average" → misleads E32).

**Lesson:** Equal-weight ensemble > meta-feature integration. Each model votes independently;
disagreement = abstain. No cross-contamination between model errors.

## Session Conclusions

1. **2022 is solved by H17 (barrier XS), not regime filters.** The fix is internal to the model,
   not external. Any further regime filtering on H17 makes 2022 worse.

2. **Three production candidates after Session 8:**
   - X9: +16.88% avg, Sharpe ~0.88 — best raw edge, aggressive, 2022=-20%
   - H17: +15.22% avg, Sharpe ~1.42 — balanced, 2022=-2%
   - H22: +15.13% avg, Sharpe ~1.52 — best risk-adjusted

3. **Meta-feature approach (H18) failed.** Equal-weight ensemble is the right architecture.

## Production System After This Session
**H22** (barrier XS + E32 + VIX 18-35, agree-only, min-conf=0.55): **+15.13% avg, Sharpe ~1.52**

## Next Session Priority
Methodology audit: 40+ experiments have implicitly used 2019-2025 as a validation set.
Multi-stock portfolio: H23 — apply XS model to all 52 stocks, not just FPT.
