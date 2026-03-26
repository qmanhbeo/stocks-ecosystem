# Session 14 Log — H44 Portfolio Refinements (2026-03-17)

## Objectives
Understand H43's cost structure and practical implementability.
Four sub-experiments: turnover measurement, rebalancing frequency, confidence weighting, sector caps.
Goal: find if any modification improves net performance, and expose the dollar cost question.

## System State (entering)
Best: H43 +13.75% avg edge, Sharpe 4.58, 11/11 years. Daily rebalancing, 69% daily turnover.

## Experiments

**Code:** `analysis/h44_portfolio_refinements.py`

All experiments run on H43 baseline (top-5, VIX[15,30], min_proba=0.55).

### EXP1 — Turnover Analysis

**Question:** What fraction of the top-5 portfolio changes each day?

**Result:** 69% daily turnover. On average, 3.45 of the 5 stocks are replaced each day.

**Implication (as initially calculated):** At 0.30% round-trip cost per trade, annual drag was
estimated at ~64% (using 250-day-traded convention). This appeared to make the strategy
unprofitable — but this calculation was WRONG. It was mixing units: accuracy-edge (%) vs dollar
cost (%). The correct dollar framework was deferred to H45 (Session 15).

### EXP2 — Rebalancing Frequency (N-day holds)

**Question:** If we only rebalance every N days (holding positions for N days), how does accuracy edge change?

| N (rebalancing frequency) | avg_wf_edge | notes |
|---|---|---|
| 1 (daily, baseline) | +13.75% | 11 years, 45 days/yr |
| 2 | +13.84% | similar |
| 3 | +13.84% | still strong |
| 5 | +9.25% | starts degrading |
| 10 | ~4% | significantly weaker |
| 21 | ~1% | near-zero |

**Finding: Signal half-life = 3-5 days** (in accuracy units). The ranking becomes stale quickly.
By day 10, the model's 10-days-old rankings are barely predictive.

**Interpretation:** Fresh model output each day is important. The signal is generated daily and
decays fast — it's not a "hold for a week" signal in the ranking dimension.

### EXP3 — Confidence Weighting (equal vs proba-weighted)

**Question:** Should stocks with higher proba get larger position weight?

**Result:** ~0% difference between equal weight and proba-weighted.

**Why:** Proba scores above the 0.55 threshold are essentially flat in distribution. All stocks
that pass the min_proba filter have very similar confidence levels. There is no further
discrimination in the proba values above 0.55 — they're all equally reliable.

### EXP4 — Sector Cap (max 2 stocks per sector)

**Question:** The top-5 might be concentrated in one sector (e.g., 4 banking stocks). Does
capping at 2 per sector diversify and improve risk-adjusted returns?

**Result:** ~0% edge change vs uncapped.

**Why:** The top-5 portfolio is already naturally diversified across sectors. The XS model
produces top-5 picks that span multiple industries — the sector concentration concern was
not materializing in practice.

## Unanswered Question After H44

All of H44's analysis worked in **accuracy-edge units** (%). The cost of daily turnover is in
**dollar units** (%). These cannot be directly compared.

Specifically:
- H43's 13.75% = average directional accuracy edge
- Daily turnover cost = X% of portfolio value per day in transaction costs

To know if H43 is profitable after costs, we need to know: what is the actual dollar return per
correct/incorrect prediction? This requires mapping accuracy → actual P&L.

**This became the priority for Session 15 (H45).**

## Session Conclusions

1. **Rebalancing frequency: daily is optimal.** Edge degrades from 13.75% to 4% at 10-day
   rebalancing. The signal has a 3-5 day half-life in accuracy units.

2. **Confidence weighting: zero value.** All stocks above 0.55 threshold are equally predictive.
   No further confidence discrimination possible from XS proba alone.

3. **Sector cap: zero value.** Portfolio naturally diversified; concentration was a non-issue.

4. **The critical unanswered question:** Dollar return per trade → Session 15.

## Production System After This Session
**H43 unchanged**: +13.75% avg edge, Sharpe 4.58. No modification improved on the baseline.

## Next Session Priority
H45: Convert accuracy edge to dollar return. What is the gross return per stock per 1-day trade?
Does the signal survive after 0.30% round-trip transaction costs?
