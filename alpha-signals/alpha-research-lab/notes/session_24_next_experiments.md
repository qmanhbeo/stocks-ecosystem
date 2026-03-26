# Session 24: Proposed Experiments — Alpha Improvement Roadmap

## Context

As of Session 23 (2026-03-18), H75 full-universe results:
- IC_2026 = +0.1323 (PASS, top of expected range)
- Gross/trade = +0.258% (positive)
- Net/trade = -0.042% (BORDERLINE — 0.30% RT cost is the binding constraint)

**The core problem:** Gross is real (+0.258%) but 0.30% RT assumption eats the edge.
Three levers: increase gross, reduce cost drag, reduce turnover.

---

## Proposed Experiments

### Tier 1 — High confidence, easy to implement

**H76: Cost sensitivity audit**
- The 0.30% RT assumption may be conservative. VCI broker fees for mid-cap stocks
  are often 0.15–0.20% RT in practice.
- Map net/trade vs RT cost across [0.10%, 0.15%, 0.20%, 0.25%, 0.30%, 0.40%].
- If real cost = 0.20% RT, we're already profitable today (+0.058% net).
- Also: compute breakeven cost for 2026 (should be ~0.26% RT from gross).
- Easy: just re-run portfolio simulation with different COST_RT values.

**H77: Enable dormant features in XS WF BASE_CONFIG**
Several feature groups are coded in src/feature_engineering.py but switched OFF:
- `use_vol_regime` — VNINDEX realized vol percentile (VNINDEX data already present)
- `use_calendar` — Tet pre/post windows (Vietnamese market effect, well-documented)
- `use_seasonality` — day-of-week, lunar phase, turn-of-month effects
- `use_cci` — Commodity Channel Index (additional oscillator)
- `use_willr` — Williams %R (already coded, just off)

Method: enable one group at a time (or all at once), re-run cross_sectional_wf.py,
compare IC and nested WF Sharpe to baseline.
Zero new data required. Could lift IC from 0.13 toward 0.14-0.15.

**H78: Intermediate holding period (H=2 or H=3)**
- H=1: 87.8% daily turnover (K=10), breakeven 0.70% RT
- H=5: higher gross/trade (+1.14%) but needs 1.50% RT to break even
- Sweet spot hypothesis: H=2 or H=3 reduces turnover vs H=1 without the steep
  breakeven of H=5. Test grid: H in {1, 2, 3, 5} with K=10 stay-in rule.

---

### Tier 2 — Higher upside, more work

**H79: VIX as training feature (not just filter)**
- Currently VIX is a hard post-hoc filter [15, 30]. The model never sees VIX.
- Add VIX level + 5d/20d momentum as features (already in fx_commodities_vix_1D.parquet).
- Let the model learn which VIX regimes amplify the signal, rather than hard-cutting.
- flag: `use_macro=True` with only VIX in macro_files. Compare IC to baseline.

**H80: Sector-relative features**
- H72 proved signal is NOT sector timing (IC dropped only 8.8% after demeaning).
- But sector-relative momentum (stock vs sector peers) could be a useful feature.
- We have sector map from H72 (155/393 stocks across 15 sectors).
- Compute each stock's excess return vs sector mean (1d, 5d, 20d), add as features.
- Hypothesis: within-sector momentum is an additional signal layer.

**H81: Per-stock IC stability filter**
- Some of the 393 stocks consistently contribute positive IC; others are noise.
- Compute per-stock IC over rolling 3-year windows. Filter universe to stocks
  with IC > 0 in 2 of last 3 years (stable signal contributors).
- Run portfolio only within this filtered subset (~150-200 stocks?).
- Smaller but cleaner universe may improve gross/trade.

---

### Tier 3 — Exploratory

**H82: Model ensembling (classifier + regressor)**
- xs_regressor_scores_hose_full.parquet still exists.
- In H19, regressor alone (IC=0.099) was weaker than classifier (~0.12).
- As a second opinion in a blend, it may add information.
- Test: rank by 0.5*classifier_proba + 0.5*regressor_score (normalized).
- Evaluate IC and portfolio vs classifier-only baseline.

**H83: Alternative barrier threshold**
- Current: 1% barrier (barrier_pct=0.01). Test 0.5% and 1.5%.
- Tighter (0.5%): more labels, faster signal turnover, shorter average hold.
- Wider (1.5%): more selective, fewer positive labels, potentially higher gross.
- Run nested WF Sharpe comparison across {0.5%, 1.0%, 1.5%} barriers.

---

## Recommended Order for Session 24

| Priority | Experiment | Rationale |
|----------|-----------|-----------|
| 1 | H76 cost audit | May reveal we're already profitable — quick sanity check |
| 2 | H77 dormant features | Easiest IC lift, zero new data needed |
| 3 | H78 H=2/H=3 hold | Directly attacks turnover/cost problem |
| 4 | H79 VIX as feature | Converts filter into learned signal |
| 5 | H80 sector-relative features | Natural extension of H72 work |

---

## Constraints (do not violate)

- No model changes or parameter adjustments in response to 2026 results.
  Next evaluation checkpoint is mid-year 2026 (~June, ~120+ trades).
- All new experiments must use walk-forward methodology (no lookahead).
- Any new feature must be available at T+0 (prediction time), not T+1.
- H74 constraint remains: must enter at T+1 open. No T+2 entries.

---

## Session 24 Results (2026-03-19)

### H84: Proba Momentum Ranking (Zaremba 2020 + Han 2021)
**Script:** `analysis/h84_proba_momentum_ranking.py`

| alpha | avg_edge | Sharpe | vs H54 |
|-------|----------|--------|--------|
| 0.0 (H54 baseline) | +25.52% | 9.17 | — |
| 0.3 | +25.11% | 9.74 | −0.40% |
| 0.5 | +24.66% | 8.94 | −0.86% |
| 0.7 | +24.78% | 8.43 | −0.74% |
| 1.0 | +24.15% | 7.86 | −1.37% |

Han stability filter (proba_std5 ≤ 0.15): reduces baseline to +22.63% — high-variance stocks are high-signal.
IC degrades monotonically: +0.1515 → +0.1443.
**Verdict: FAIL → F36**

### H78: Holding Period Grid H={1,2,3,5}
**Script:** `analysis/h78_holding_period_grid.py`

Top-5 portfolio has ~91% daily turnover (only ~0.45 stocks persist day-to-day).

| Hold | gross/day | trades/yr | cost/yr @0.30% | net/yr |
|------|-----------|-----------|----------------|--------|
| H=1 | +1.752% | 2246 | 67.4% | +365% |
| H=2 | +1.102% | 1180 | 35.4% | +238% |
| H=3 | +0.766% | 796 | 23.9% | +167% |
| H=5 | +0.485% | 475 | 14.3% | +106% |

E=0: H=1 dominates. E=1 inference: H=2 likely best (+0.350%/day net vs H=1 +0.261%/day) — overnight gap avoidance saves more than alpha decay costs. Needs T+1-open simulation to confirm. K-band K=15 too tight for 393 stocks.
**Verdict: E=0 confirms F29. H=2 E=1 is open hypothesis → F37**

### H85: Longer Training Label Horizon (Blitz 2023)
**Fix:** `cross_sectional_wf.py` line 136 — barrier target now respects `--target-horizon`.

| Label | IC | avg_edge | Sharpe |
|-------|-----|----------|--------|
| 5d (H54) | +0.1515 | +25.52% | **9.17** |
| 10d | +0.1521 | +25.46% | 8.46 |
| 20d | +0.1520 | +25.36% | 8.86 |

IC nearly identical. Sharpe and edge slightly worse at longer horizons. 5d is optimal.
**Verdict: FAIL → F38. Closes the label-horizon axis.**

### Champion unchanged
**H54: +25.52% avg edge, Sharpe 9.17, 11/11 years**

---

## Session 25 Priority

1. **H77** — Dormant features: vol_regime, calendar, CCI, Williams %R (zero new data)
2. **H79** — VIX as training feature (use_macro=True, VIX only)
3. **H86** — XS fundamentals Approach A (52-ticker data, zero-filled for 341)
4. **H83** — Barrier amplitude (0.5%, 1.5%)
5. **H78 E=1** — Dedicated H=2 simulation with T+1-open entry prices
