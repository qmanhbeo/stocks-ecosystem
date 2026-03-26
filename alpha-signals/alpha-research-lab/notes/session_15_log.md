# Session 15 Log — Dollar Returns + Signal Decay (2026-03-17)

## Objectives
Convert probability-accuracy signal to actual dollar returns (H45).
Test every turnover-reduction mechanism (H46, H47, H49).
Measure signal decay curve in dollar terms (H48).
Determine if H43 is profitable after realistic 0.30% round-trip transaction costs.

## System State (entering)
Best: H43 +13.75% accuracy edge, Sharpe 4.58. Dollar returns unknown. Daily turnover 69%.

## Experiments

### H45 — Actual Monetary Return per Trade (FOUNDATIONAL)

**Code:** `analysis/h45_actual_returns.py`
**Data:** 497 invested days × 5 stocks = 2,485 stock-days (2015-2025, H43 selections)

**Model hit rate:** P(actual outperform) = **60.0%** in top-5 selections. Confirmed real edge.

**Gross return by holding period:**

| Hold | avg_win | avg_loss | gross/trade | > 0.30% RT? |
|------|---------|----------|-------------|-------------|
| 1d | +1.784% | -1.653% | **+0.409%** | YES |
| 2d | +2.289% | -1.914% | **+0.608%** | YES |
| 3d | +2.546% | -1.898% | **+0.768%** | YES |
| 5d | +2.783% | -1.838% | **+0.935%** | YES |
| 10d | +3.203% | -1.878% | **+1.171%** | YES |

**ALL holding periods beat 0.30% RT cost.** Even 1-day trades are profitable.

**Corrected annual P&L framework:**
- Invested days/year: ~45 (VIX filter active)
- Gross per stock-day: +0.409%
- Annual gross excess vs VNINDEX: 45 × 0.409% = **~18.4%/yr**
- Annual cost: 45 invested days × 69% turnover × 0.30% RT / 5 stocks = **~9.3%/yr**
- **Net excess vs VNINDEX: ~9.1%/yr**

The prior H44 "cost" calculation (comparing accuracy-edge % to dollar-cost %) was a unit error.
H45 resolves this: the strategy is genuinely profitable after realistic costs.

### H46 — Persistence Filter (K consecutive days in top-N)

**Hypothesis:** Only enter/hold a stock if it ranks in top-N for K consecutive days. Reduces
false signals and turnover.

**Code:** `analysis/h46_persistence_filter.py`

| K | avg_edge | n_years | trades/yr | turnover |
|---|----------|---------|-----------|---------|
| 1 (baseline) | +13.75% | 11 | 45.2 | 85.4% |
| 2 | +20.71% | **2** | 6.0 | 93.3% |
| 3 | no data | 0 | — | — |

**Result: FAILED.** K=2 requires stocks to be in top-5 for 2 consecutive days. Only 2 qualifying
years total. The signal is transient — stocks rarely sustain top-5 ranking for 2+ days.
Persistence filter kills the strategy by eliminating almost all trades.

**Lesson:** The signal fires in 1-day bursts. Today's top-5 ≠ tomorrow's top-5.

### H47 — Probability Smoothing (Rolling Average Ranking)

**Hypothesis:** Smooth XS proba with a N-day rolling average before ranking. Reduces reactive
turnover from daily noise.

**Code:** `analysis/h47_proba_smoothing.py`

| Window | avg_edge | n_years | trades/yr | turnover |
|--------|----------|---------|-----------|---------|
| 1d (raw, baseline) | +13.75% | 11 | 45.2 | 85.4% |
| 3d smooth | +15.46% | 7 | 21.7 | 61.6% |
| 5d smooth | +12.35% | 3 | 20.3 | 47.2% |
| 7d smooth | +15.94% | 2 | 20.0 | 43.5% |

**Result: Not viable.** Smoothing halves turnover but also dramatically reduces qualifying years
(11 → 7 → 3 → 2) and trading frequency (45 → 22 days/yr). With only 2-7 years of data, results
are statistically meaningless.

**Interpretation:** Rolling averages rarely sustain ≥0.55 for multiple days. The signal fires
in concentrated bursts, then fades. Smoothing demands the burst be SUSTAINED, which it never is.

### H48 — Signal Decay Curve with Real Dollar Returns

**Code:** `analysis/h48_signal_decay.py`

Measures: if we select stocks TODAY using the current model, what is the cumulative edge at
each subsequent holding horizon (vs a naive investor who holds the VNINDEX)?

| Hold | top5_ret | naive | edge (top5 - naive) | Worth 0.30% RT? |
|------|----------|-------|---------------------|-----------------|
| 1d | +0.409% | +0.041% | **+0.368%** | YES |
| 2d | +0.605% | +0.107% | **+0.498%** | YES |
| 3d | +0.764% | +0.150% | **+0.613%** | YES |
| 5d | +0.927% | +0.217% | **+0.710%** | YES |
| 7d | +1.072% | +0.315% | **+0.758%** | YES |
| 10d | +1.160% | +0.449% | **+0.711%** | YES |
| 15d | +1.338% | +0.630% | **+0.708%** | YES |

**The signal does NOT die within 15 days in dollar terms.** Cumulative edge keeps growing.

**Per-day marginal decay:**
- Day 1: +0.368%/day
- Days 1-5 marginal: ~+0.085%/day
- Days 5-10 marginal: ~+0.020%/day
- Days 10-15 marginal: near-zero

**Reconciliation with H44 accuracy decay:**
- H44 measured: "if I use a 10-day-old ranking, how accurate is it?" → accuracy drops to 4%
- H48 measured: "if I select stocks TODAY, what's their cumulative return over 10 days?" → +0.711%
- These measure DIFFERENT things. H48 shows that fresh picks compound returns for 10+ days.
  H44 shows that stale rankings are not useful for NEW selections.

**Strategy comparison (daily rebalancing vs hold 10 days):**
- Daily rebalancing: 0.409% × 45 days - 9.3% cost = **~9.1% net/yr**
- 10-day hold: 0.711% × 4.5 periods - 1.35% cost = **~1.85% net/yr**
- Daily rebalancing wins ~5x over any hold-and-wait approach.

**2025 anomaly:** 5-day hold shows -0.771% edge in 2025 (signal reversal at medium term).
Monitor in 2026.

### H49 — Patient Rebalancing (Hold Until Rank > M)

**Code:** `analysis/h49_patient_rebalancing.py`

Instead of daily exit, hold a stock until it falls below rank M (wider than N).

| (N,M) | avg_edge | sharpe | trades/yr | turnover | sells/d |
|-------|----------|--------|-----------|---------|---------|
| (5,5) baseline | +11.96% | 3.79 | 182.4 | 39.0% | 1.67 |
| (5,7) | +11.74% | **4.76** | 187.8 | 36.0% | 1.57 |
| (5,10) | +10.93% | **4.69** | 195.1 | 32.2% | 1.42 |
| (5,15) | +10.00% | **4.74** | 204.4 | 27.1% | 1.21 |

**Important:** H49 baseline (5,5) ≠ H43 baseline. H49 holds positions through low-confidence
periods (invested 182 days/yr vs H43's 45 days/yr). The lower edge (11.96% vs 13.75%) is because
H49 includes "stale" holding days outside the VIX window.

**Result: Wider exit zone (M=7-15) improves Sharpe (3.79 → 4.74) but reduces edge.** H43 already
achieves Sharpe 4.58 with a strict quality filter. Patient rebalancing doesn't improve on H43's
"only trade when confident" approach.

## Session Conclusions

1. **The signal is real in dollar terms (H45).** +0.409% gross per stock per 1-day trade.
   All holding periods beat 0.30% RT cost. Net ~9.1%/yr excess vs VNINDEX.

2. **Turnover reduction doesn't help (H46, H47, H49).** Every mechanism either:
   - Kills the strategy (K=2 persistence, smoothing → <3 years of data), or
   - Sacrifices quality (patient rebalancing holds stale positions)

3. **The signal fires in 1-2 day bursts (H44+H47).** Stocks don't remain in top-5 for multiple
   consecutive days. Smoothing and persistence requirements eliminate the actual signal.

4. **Daily rebalancing wins 5x over any hold approach (H48).** Fresh rankings capture
   +0.368%/day on day 1; stale 10-day rankings are near-worthless for NEW trades.

5. **H43 is optimal as-is.** VIX[15,30] + top-5 daily + min_proba=0.55 + exit when filter fails.

6. **The one remaining issue:** VIX_MAX=30, MIN_PROBA=0.55, TOP_N=5 are the three hardcoded
   parameters that were selected by observing 2015-2025 results. The XS model itself is
   walk-forward clean. These three parameters are contaminated. Session 16 addresses this.

## Production System After This Session
**H43** (top-5 rank portfolio, VIX [15,30], min_proba=0.55, daily rebalancing):
- **+13.75% accuracy edge, Sharpe 4.58, 11/11 positive years**
- **+0.409% gross/trade, ~9.1%/yr net excess vs VNINDEX after costs**

```bash
conda run -n stocks python analysis/h40_rank_portfolio.py
# Uses: data/features/xs_barrier_all_probas.parquet
```

## Next Session Priority (Session 16)
**Eliminate parameter contamination.** In order:
1. **Option C** — Add VIX as training feature in `cross_sectional_wf.py`. Model learns
   regime internally. Test without external VIX filter. (Lowest effort, biggest contamination fixed)
2. **Option B** — Soft parameterless portfolio: softmax weights over all stocks (no TOP_N, no
   MIN_PROBA, no VIX filter). Zero free parameters. New script `analysis/h50_soft_portfolio.py`
3. **Option A** — Nested walk-forward parameter search: for test year T, grid-search on T-3 to T-1.
   Most rigorous. Implements fully clean Layer 2.

See `notes/next_steps.md` Session 16 section for full implementation details.
