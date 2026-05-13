# Session 20 Log - Execution Reality Experiments (H61-H65)

## Context
Five experiments designed to close the gap between "good backtest" and "actual profit".
All use xs_barrier_all_probas_hose_full.parquet (393 HOSE stocks, 2015-2025).
Baseline: H56 nested WF — +25.98% avg edge, Sharpe 7.35, 9/9 years (zero contamination).

---

## H61: Liquidity Filter
**Script:** analysis/h61_liquidity_filter.py

| Universe | IC | Q5-Q1 | Nested WF Sharpe |
|---|---|---|---|
| All 393 | 0.152 | +21.27% | **7.35** |
| Top 200 | 0.114 | +16.02% | 2.70 |
| Top 150 | 0.096 | +13.45% | 3.20 |
| Top 100 | 0.081 | +11.32% | 2.89 |
| Top 50  | 0.071 | +9.71%  | 2.71 |

**Finding: Filtering for liquidity DESTROYS the edge.**
- Signal is highly concentrated in mid/small-cap stocks (tickers 51-393 by liquidity rank)
- Removing the bottom 50% of the universe cuts IC from 0.152 → 0.114
- VN30/large-caps carry very little of the predictive signal
- VND threshold approach fails for pre-2018 data (HOSE volumes were small) — thresholds of 1B+ VND/day filter to <4 tickers in early years

**Implication:** You cannot simply "trade only liquid stocks" — that kills the alpha. The strategy requires accessing mid/small caps, which requires managing execution costs carefully.

---

## H62: 5-Day Hold vs Daily Rebalancing
**Script:** analysis/h62_five_day_hold.py
All using E=1 (T+1 open entry), actual OHLC excess returns.

| Strategy | Gross/trade | Net/trade @0.3% | Trades/yr | Ann. net edge | Sharpe | Years+ |
|---|---|---|---|---|---|---|
| A: Daily H=1 (current) | +0.607% | +0.307% | 139.5 | +42.83% | **2.57** | 11/11 |
| B: Daily H=5 | +0.829% | +0.529% | 139.5 | +73.88% | 1.80 | 10/11 |
| C: Weekly H=5 | +1.141% | +0.841% | 34.7 | +29.17% | 1.62 | 10/10 |

**Key findings:**
- **Gross per-5d-position is 88% higher** than per-1d (+1.141% vs +0.607%) — signal accumulates over 5 days
- But daily H=1 has HIGHER annual net edge (+42.83%) because it trades 4× more
- **Sharpe is best for daily H=1 (2.57)** — 5d hold introduces more variance per year
- B (daily signal, 5d hold): looks great on paper (+73.88%/yr) but 2022 (-25.17%) and 2025 (-86.82%) are terrible — overlapping positions amplify bad streaks
- Weekly H=5 is the T+2-safe option: works for real trading but only 29% net/yr and Sharpe 1.62

**Practical conclusion:** Daily H=1 wins on risk-adjusted basis IF you can execute at low cost. Weekly H=5 is the conservative, T+2-safe alternative — 2× the gross per trade allows absorbing higher execution costs.

---

## H63: Cost Stress Test
**Script:** analysis/h63_cost_stress.py
Using E=1 H=1 actual OHLC excess returns.

**Strategy A: Daily H=1 (current approach)**
| RT cost | Gross/trade | Net/trade | Ann. net | Sharpe | Pos yrs |
|---|---|---|---|---|---|
| 0.00% | +0.539% | +0.539% | +84.69% | 2.57 | 11/11 |
| 0.30% | +0.539% | +0.239% | +42.83% | 1.30 | 11/11 |
| 0.50% | +0.539% | +0.039% | +14.92% | 0.45 | 7/11 |
| **0.70%** | +0.539% | **-0.161%** | **-12.99%** | **-0.39** | 2/11 ← **BREAKEVEN** |

**Strategy C: Weekly H=5 (T+2-safe)**
| RT cost | Gross/trade | Net/trade | Ann. net | Sharpe | Pos yrs |
|---|---|---|---|---|---|
| 0.30% | +1.101% | +0.801% | +24.97% | 1.12 | 10/11 |
| 0.70% | +1.101% | +0.401% | +12.20% | 0.55 | 7/11 |
| 1.00% | +1.101% | +0.101% | +2.63%  | 0.12 | 5/11 |
| **1.50%** | +1.101% | **-0.399%** | **-13.33%** | **-0.60** | 2/11 ← **BREAKEVEN** |

**Critical finding: 5-day hold doubles your cost tolerance (1.50% vs 0.70% RT)**
- Daily H=1: safe for stocks with ≤0.50% RT, breaks at 0.70%
- Weekly H=5: safe for stocks with ≤1.0% RT, breaks at 1.50%
- The strategy to maximize profit: sort stocks in your daily top-5 by liquidity; trade large caps with daily H=1, mid-caps with weekly H=5

---

## H64: VN30-Only Universe
**Script:** analysis/h64_vn30_universe.py
All 30 VN30 tickers found in the data (30/30).

| Metric | Full 393 | VN30 only |
|---|---|---|
| IC | 0.152 | **0.076** (half) |
| Q5-Q1 | +21.27% | +10.54% |
| Sig years | 11/11 | 11/11 |
| Top-5 Sharpe (H54 params) | 9.17 | 2.44 |
| Nested WF Sharpe | 7.35 | **1.34** |

**Finding: VN30 approach does NOT work.**
- Signal is halved in IC and completely collapses in portfolio Sharpe (7.35 → 1.34)
- The edge lives in mid/small caps, not the blue chips
- H64 confirms H61: restricting to liquid/large stocks kills the alpha

---

## H65: Score-Weighted Position Sizing
**Script:** analysis/h65_score_weighted.py
Using actual E=1 H=1 OHLC excess returns, same filters as H54.

| Scheme | Acc edge | Sharpe_acc | Gross/trade | Net/trade | Sharpe_ret | Years+ |
|---|---|---|---|---|---|---|
| Equal Weight (baseline) | +26.17% | 7.61 | +0.607% | +0.307% | 2.57 | 11/11 |
| Linear (proba-0.5) | +26.44% | 8.36 | +0.628% | +0.328% | 2.66 | 11/11 |
| **Square (proba-0.5)²** | **+26.73%** | **9.07** | **+0.651%** | **+0.351%** | **2.79** | **11/11** |
| Softmax(temp=0.1) | +26.67% | 9.14 | +0.648% | +0.348% | 2.78 | 11/11 |
| Softmax(temp=0.3) | +26.33% | 8.12 | +0.620% | +0.320% | 2.62 | 11/11 |
| Softmax(temp=1.0) | +26.22% | 7.76 | +0.611% | +0.311% | 2.58 | 11/11 |

Weight concentration (example top-5 probas [0.60, 0.58, 0.57, 0.56, 0.555]):
- Equal Weight: [0.200, 0.200, 0.200, 0.200, 0.200] HHI=0.200
- Square:       [0.358, 0.229, 0.175, 0.129, 0.108] HHI=0.240
- Softmax(0.1): [0.259, 0.212, 0.192, 0.173, 0.165] HHI=0.206

**Finding: Square weighting is the best no-parameter improvement.**
- +7% more gross return per trade (+0.044% absolute per trade)
- Sharpe improves 7.61 → 9.07 (+19%) — more consistent across years
- 11/11 years positive (same as baseline)
- Softmax(temp=0.1) is marginally better on Sharpe_acc but nearly identical
- **Recommended: implement Square weighting in h40_rank_portfolio.py**

---

## Master Conclusions

### The Core Tension
Signal is strongest in mid/small caps (IC 0.152 full vs 0.076 VN30-only), but those are exactly the stocks with highest execution costs. This is unavoidable — it's the nature of the signal.

### Practical Playbook for Going Live

**Tier 1 (implement now, no execution risk):**
- Use **Square (proba-0.5)² weighting** instead of equal-weight → free +7% return improvement
- This works regardless of which stocks you trade

**Tier 2 (based on stock liquidity):**
- For liquid stocks (VND vol > 5B/day, roughly top-50 by volume): **daily H=1** — RT cost ~0.20%, safe under 0.70% breakeven
- For mid-liquid stocks (VND vol 1-5B/day): **weekly H=5** — RT cost ~0.50%, safe under 1.50% breakeven
- For thin stocks (<1B VND/day): avoid until you have meaningful capital and market impact analysis

**Tier 3 (what NOT to do):**
- Don't restrict to VN30 — kills the signal (Sharpe 7.35 → 1.34)
- Don't use daily H=5 (B strategy) — volatile per-year (2022: -25%, 2025: -87%)
- Don't assume 0.30% RT for all stocks — thin stocks will cost 3-5× more
