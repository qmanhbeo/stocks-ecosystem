# Session 38 Log — 2026-03-28

## Objective
Generate creative hypotheses using underutilized existing data and Vietnamese market microstructure,
run 5 standalone experiments (H107–H111), update signal library.

## Experiments

### H107 — Overnight Gap Persistence
**Script:** `analysis/h107_overnight_standalone.py`
**Hypothesis:** Decomposing oc_asym into overnight vs intraday reveals a purer signal.
**Result:** FAIL

| Feature | IC | Pos Years | Corr S1 |
|---------|-----|-----------|---------|
| overnight_mom_5d | −0.0005 | 5/11 | −0.011 |
| intraday_mom_5d | −0.0343 | 1/11 | −0.235 |
| oc_asym_5d | +0.0225 | 11/11 | +0.147 |
| gap_abs_5d | +0.0078 | 9/11 | +0.003 |

**Finding (F72):** Signal is entirely in the contrast. oc_asym_5d = C4 candidate (passes gate).

---

### H108 — Insider Transaction Quality Score
**Scripts:** `data_tools/build_insider_quality_features.py`, `analysis/h108_insider_quality_standalone.py`
**Hypothesis:** Position-size-normalized and tier-weighted insider buys are more predictive than raw volume.
**Result:** PASS — xs_ins_relative_size_5d

| Feature | IC | Pos Years | Corr S1 | Coverage |
|---------|-----|-----------|---------|---------|
| xs_ins_relative_size_5d | +0.0374 | 10/11 | −0.008 | 3.39% |
| xs_ins_quality_buy_5d (tier-wtd) | +0.0248 | 9/11 | −0.007 | 3.60% |
| xs_ins_ceo_buy_5d | +0.0210 | 5/11 | −0.003 | 0.78% |
| xs_ins_exec_rate_5d | −0.0084 | 6/11 | +0.000 | 1.42% |
| insider_net_plan_5d (baseline) | +0.0256 | 9/11 | −0.007 | 3.57% |

**Finding (F73):** Relative size (% of holdings) is the informative dimension. Execution rate
is anti-predictive. C5 = xs_ins_relative_size_5d supersedes raw C2.

**New artifact:** `data/features/xs_insider_quality_features.parquet`

---

### H109 — Earnings Quality (52 tickers)
**Scripts:** `data_tools/build_earnings_quality_features.py`, `analysis/h109_earnings_quality_standalone.py`
**Hypothesis:** EPS acceleration and net margin trends capture earnings quality orthogonal to price.
**Result:** FAIL (insufficient universe)

| Feature | IC | Pos Years |
|---------|-----|-----------|
| xs_roe_delta_rank | +0.0049 | 8/11 |
| xs_eps_accel_rank | +0.0029 | 7/11 |
| xs_eps_yoy_rank | +0.0030 | 7/11 |
| xs_npm_trend_rank | −0.0033 | 1/11 |
| xs_debt_trend_rank | −0.0006 | 6/11 |

**Finding (F76):** Directionally consistent but IC < 0.01 at 52 tickers. xs_roe_delta_rank
(8/11 positive) is promising. Re-test at 394 tickers queued as H113.

**New artifact:** `data/features/xs_earnings_quality_daily.parquet` (52 tickers)

---

### H110 — VNM ETF Foreign Demand Proxy
**Scripts:** `data_tools/build_foreign_demand_features.py`, `analysis/h110_foreign_demand_standalone.py`
**Hypothesis:** VNM ETF premium × foreign affinity beta creates cross-sectional IC.
**Result:** FAIL

| Feature | IC | Pos Years |
|---------|-----|-----------|
| xs_fa_signal | −0.0014 | 6/11 |
| xs_fa_rank | −0.0029 | 4/11 |
| xs_foreign_affinity_120d | −0.0050 | 3/11 |
| xs_vnm_premium_1d | −0.0143 | 2/11 |

Conditional: high-premium days IC = −0.0108; low-premium days IC = +0.0089.

**Finding (F75):** VNM ETF premium is market-direction only. No cross-sectional differentiation.

**New artifact:** `data/features/xs_foreign_demand_daily.parquet` (not predictive; archive only)

---

### H111 — Sector Rotation with Intra-Sector Leadership
**Scripts:** `data_tools/build_sector_rotation_features.py`, `analysis/h111_sector_rotation_standalone.py`
**Hypothesis:** Best horse in hot race (sector_mom × intra_sector_rank) beats flat cross-section.
**Result:** PARTIAL PASS (sector_breadth passes; rotation composite fails)

| Feature | IC | Pos Years | Corr S1 |
|---------|-----|-----------|---------|
| xs_sector_rotation_signal | −0.0379 | 0/11 | −0.233 |
| xs_intra_sector_rank | −0.0466 | 0/11 | −0.256 |
| xs_sector_mom_5d_rank | −0.0015 | 5/11 | −0.053 |
| xs_sector_breadth_5d | +0.0143 | 8/11 | −0.004 |
| xs_sector_accel | +0.0079 | 8/11 | −0.030 |

**Finding (F74):** Intra-sector rank is strongly anti-predictive. Laggards beat leaders within
hot sectors (intra-sector mean reversion). Composite signal is dominated by this effect.
xs_sector_breadth_5d passes all gates: IC +0.0143, 8/11 years, corr = −0.004.
H112 queued: contrarian intra-sector (sector_mom × (1 − intra_sector_rank)).

**New artifact:** `data/features/xs_sector_rotation_daily.parquet`

---

## Signal Library After Session 38

| Signal | Feature | IC | Pos Years | Corr S1 | Status |
|--------|---------|-----|-----------|---------|--------|
| S1/H93 | xs_proba | +0.149 | 11/11 | — | CONFIRMED |
| C1 | sentiment_cs_z | +0.043 | 5/8 | +0.009 | Candidate |
| C4 | oc_asym_5d | +0.023 | 11/11 | +0.147 | NEW Candidate |
| C5 | xs_ins_relative_size_5d | +0.037 | 10/11 | −0.008 | NEW Candidate (supersedes C2) |
| — | xs_sector_breadth_5d | +0.014 | 8/11 | −0.004 | NEW Candidate |

## Session 39 Priority Queue

1. **H112** — Contrarian intra-sector signal. Data ready in `xs_sector_rotation_daily.parquet`.
   Quick test: sector_mom_5d_rank × (1 − xs_intra_sector_rank). Expected IC > 0.
2. **H113** — Earnings quality at 394 tickers. Run full fetch (~5 min), re-test xs_roe_delta_rank.
3. **H114** — VN30 rebalancing pressure. Derivable from existing daily value-traded data.
4. RL agent development using S1 + C4 + C5 (3 orthogonal signals with different coverage profiles).
