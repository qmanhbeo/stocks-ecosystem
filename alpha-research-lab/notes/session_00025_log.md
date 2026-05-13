# Session 25 Log (2026-03-19)

## Goal
Run the 7 remaining experiments from the Session 24 plan: H77, H79, H80, H81, H82, H83, H86.
H54 remains champion at session start: +25.52% avg_edge, Sharpe 9.17, 11/11 years.

## Experiments Run

### H81: IC Stability Filter (quick analysis on existing probas)

**Method:** For each test year Y, restrict daily universe to tickers with IC > 0 in >=K of prior 3 years.
**Script:** `analysis/h81_ic_stability_filter.py` (new)

| Filter | avg_edge | Sharpe | Years |
|---|---|---|---|
| No filter (H54 baseline) | +25.52% | 9.17 | 11/11 |
| IC>0 in >=1/3 yrs | +25.46% | 8.29 | 10/10 |
| IC>0 in >=2/3 yrs | +25.45% | 8.13 | 9/9 |
| IC>0 in >=3/3 yrs | +24.81% | 9.57 | 8/8 |

**Verdict: FAIL.** 88.9% of (year, ticker) pairs already have IC > 0 (mean IC = +0.133).
Filtering barely changes the universe. Tighter filters just reduce breadth without improving returns.
→ See F43

### H82: Classifier + Regressor Ensemble (quick analysis on existing probas)

**Method:** Blend xs_proba (classifier) with rank-normalized regressor scores. Sweep alpha={0.0, 0.3, 0.5, 0.7, 1.0}.
**Script:** `analysis/h82_regressor_ensemble.py` (new)

| Alpha (clf weight) | avg_edge | Sharpe | Pos years |
|---|---|---|---|
| 1.0 (H54 baseline) | +25.52% | 9.17 | 11/11 |
| 0.7 | +25.06% | 9.22 | 11/11 |
| 0.5 | +25.02% | 9.62 | 11/11 |
| 0.3 | +24.70% | **11.41** | 11/11 |
| 0.0 (reg only) | +22.15% | 8.49 | 11/11 |

**Verdict: NEUTRAL.** Pure classifier has best edge. Regressor blending (alpha=0.3) gives the
highest Sharpe ever seen (11.41) but at cost of -0.82% edge. Useful for risk-averse trading.
→ See F44

### H79: VIX as Training Feature (WF run on 393 stocks)

**Run:** `cross_sectional_wf.py --use-vix-feature --barrier-pct 0.01 --threshold 0.05`
**Output:** `data/features/xs_barrier_vix_feature_hose_full.parquet`

WF summary: avg overall acc 56.12%, IC +0.1516

Portfolio eval (h40_rank_portfolio.py --no-vix-filter):
- avg_edge: **+24.99%**, Sharpe: **8.90**, 11/11 years
- vs H54: -0.53% edge, -0.27 Sharpe

**Verdict: FAIL.** VIX as training feature adds no value at 393-stock scale. Regime information
already captured implicitly by cross-sectional momentum across 393 stocks. Contrast: at 52-stock
scale (H50a, Session 16), VIX feature gave significant improvement. Effect disappears at scale.
→ See F40

### H77: Dormant Features (vol_regime, calendar, CCI, WillR)

**Run:** `cross_sectional_wf.py --use-dormant-features --barrier-pct 0.01 --threshold 0.05`
**Output:** `data/features/xs_barrier_dormant_hose_full.parquet`

WF summary: avg overall acc 55.95%, IC +0.1505 (baseline: 56.28%, +0.1515)
Features: 44 (added willr, cci, vnindex_vol_20d, vnindex_vol_pct, high_vol_regime,
          days_to_tet, days_since_tet, pre_tet_window, post_tet_window)

Portfolio eval (h40_rank_portfolio.py --no-vix-filter):
- avg_edge: **+25.19%**, Sharpe: **9.68**, 11/11 years
- vs H54: -0.33% edge, +0.51 Sharpe

**Verdict: NEUTRAL.** Lower edge but higher Sharpe. Calendar and vol regime features reduce
year-to-year variance while slightly dulling the signal. Sharpe improvement is consistent
across the TOP-N sweep (N=3: Sharpe 10.35, vs H54's N=3: ~9.5).
→ See F41

### H83a: Barrier Amplitude 0.5%

**Run:** `cross_sectional_wf.py --barrier-pct 0.005 --threshold 0.05`
**Output:** `data/features/xs_barrier_0.5pct_hose_full.parquet`

WF summary: avg overall acc 56.73%, IC +0.1519

Portfolio eval (h40_rank_portfolio.py --no-vix-filter):
- avg_edge: **+25.15%**, Sharpe: **8.80**, 11/11 years
- vs H54: -0.37% edge, -0.37 Sharpe

**Verdict: FAIL.** Tighter barrier creates more noise labels at the 0.5% boundary.
→ See F39

### H83b: Barrier Amplitude 1.5%

**Run:** `cross_sectional_wf.py --barrier-pct 0.015 --threshold 0.05`
**Output:** `data/features/xs_barrier_1.5pct_hose_full.parquet`

WF summary: avg overall acc 55.90%, IC +0.1460 (notably lower than 1% baseline)

Portfolio eval (h40_rank_portfolio.py --no-vix-filter):
- avg_edge: **+24.17%**, Sharpe: **7.18**, 11/11 years
- vs H54: -1.35% edge, -1.99 Sharpe

**Verdict: FAIL.** Wider barrier significantly degrades IC and Sharpe. 1% is the clear optimum.
→ See F39

### H86: XS Fundamentals (52-ticker, zero-fill for 341)

**Run:** `cross_sectional_wf.py --use-xs-fundamentals --barrier-pct 0.01 --threshold 0.05`
**Output:** `data/features/xs_barrier_fundamentals_hose_full.parquet`

WF summary: avg overall acc 56.39%, IC +0.1505
Features: 40 (added pe_ratio_rank, eps_yoy_rank, roe_rank, npm_rank, debt_eq_rank;
           52/394 tickers have real data, rest = 0)

Portfolio eval (h40_rank_portfolio.py --no-vix-filter):
- avg_edge: **+25.13%**, Sharpe: **9.79**, 11/11 years
- vs H54: -0.39% edge, +0.62 Sharpe

**Verdict: NEUTRAL.** Despite only 13% of tickers having real fundamental data, the Sharpe
improves meaningfully (+0.62). Model learns that "zero" = unmapped stock with different
risk profile. N=1 Sharpe = 12.59 (highest single-stock Sharpe seen!).
→ See F45

### H80: Sector-Relative Features

**Run:** `cross_sectional_wf.py --use-sector-relative --barrier-pct 0.01 --threshold 0.05`
**Output:** `data/features/xs_barrier_sector_rel_hose_full.parquet`

New code:
- `src/feature_engineering.py`: `add_sector_relative_features(all_df, sector_map)` function
- `cross_sectional_wf.py`: `--use-sector-relative` flag

WF summary: avg overall acc 56.55%, IC +0.1524 (marginally higher than H54)

Portfolio eval (h40_rank_portfolio.py --no-vix-filter):
- avg_edge: **+25.70%**, Sharpe: **8.35**, 11/11 years
- vs H54: +0.18% edge, -0.82 Sharpe

**Verdict: NEUTRAL.** Marginally better edge but significantly lower Sharpe. "Other" bucket
(57% of stocks) receives universe-mean demeaning ≈ already-existing market-relative features.
→ See F42

---

## Complete Results Summary

| H# | Hypothesis | avg_edge | Sharpe | Years | vs H54 | Verdict |
|----|-----------|---------|--------|-------|--------|---------|
| H54 | **BASELINE** (1% barrier, 393 stocks) | **+25.52%** | **9.17** | 11/11 | — | CHAMPION |
| H77 | Dormant features (vol+cal+CCI+WillR) | +25.19% | 9.68 | 11/11 | -0.33% edge, +0.51 Sharpe | NEUTRAL |
| H79 | VIX as training feature | +24.99% | 8.90 | 11/11 | -0.53%, -0.27 | FAIL |
| H80 | Sector-relative momentum | +25.70% | 8.35 | 11/11 | +0.18%, -0.82 | NEUTRAL |
| H81 | IC stability filter | +24.81-25.46% | 8.13-9.57 | 8-10 | — | FAIL |
| H82 | Clf + Reg ensemble | +24.70-25.52% | 9.17-11.41 | 11/11 | — | NEUTRAL |
| H83a | Barrier 0.5% | +25.15% | 8.80 | 11/11 | -0.37%, -0.37 | FAIL |
| H83b | Barrier 1.5% | +24.17% | 7.18 | 11/11 | -1.35%, -1.99 | FAIL |
| H86 | XS Fundamentals (52-ticker, 0-fill) | +25.13% | 9.79 | 11/11 | -0.39%, +0.62 | NEUTRAL |

**H54 remains champion.**

---

## New Findings

- F39: Barrier 1% is optimal (H83 grid CLOSED)
- F40: VIX feature no value at 393-stock scale
- F41: Dormant features improve Sharpe slightly (+0.51), neutral overall
- F42: Sector-relative features — marginal edge, lower Sharpe
- F43: IC stability filter — no value
- F44: Clf+Reg ensemble — trades edge for Sharpe (alpha=0.3 gives Sharpe 11.41)
- F45: XS fundamentals — improves Sharpe (+0.62), neutral overall
- F46: Session 25 convergence — H54 optimal, feature space exhausted

---

## Code Changes Made

| File | Change |
|------|--------|
| `cross_sectional_wf.py` | Added `--use-dormant-features` and `--use-sector-relative` flags |
| `src/feature_engineering.py` | Added `add_sector_relative_features(all_df, sector_map)` |
| `analysis/h81_ic_stability_filter.py` | New script |
| `analysis/h82_regressor_ensemble.py` | New script |
| `run_session25_wf.sh` | Sequential WF runner script |

---

## New Parquet Files Created

| File | Content |
|------|---------|
| `data/features/xs_barrier_dormant_hose_full.parquet` | H77 — dormant features, 394 tickers |
| `data/features/xs_barrier_vix_feature_hose_full.parquet` | H79 — VIX feature, 394 tickers |
| `data/features/xs_barrier_0.5pct_hose_full.parquet` | H83a — 0.5% barrier, 394 tickers |
| `data/features/xs_barrier_1.5pct_hose_full.parquet` | H83b — 1.5% barrier, 394 tickers |
| `data/features/xs_barrier_fundamentals_hose_full.parquet` | H86 — XS fundamentals, 394 tickers |
| `data/features/xs_barrier_sector_rel_hose_full.parquet` | H80 — sector-relative, 394 tickers |

---

## Session 26 Directions

1. **H87: Combination test** — H77 + H86 + H82(alpha=0.5): can combining all three Sharpe-improvers
   push Sharpe > 10 while keeping edge > 24%? (need new WF run with dormant + fundamentals, then
   apply alpha=0.5 blend with regressor)
2. **H78 E=1** — Dedicated H=2 simulation using T+1 open entry prices (not testable via existing probas).
   Estimate: +1.0-1.2%/trade net after costs vs current +0.409% (H43).
3. **Cost sensitivity**: What transaction cost level makes H54 unprofitable? Current estimate: 0.30% RT.
4. **Live validation**: 2026 data (Jan-Mar) — IC=+0.132 already confirmed (H75). Portfolio P&L tracking.
