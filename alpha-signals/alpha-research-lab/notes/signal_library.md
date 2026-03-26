# Signal Library — Learnable Alpha Signals for RL Training

This is the registry of signals confirmed to have predictive information for Vietnamese equities.
It is the **primary output** of this research lab.

**Goal:** Build a diverse set of orthogonal signals that an RL agent can learn to weight
dynamically. A signal does not need to be a complete trading strategy — it needs to be:

1. **Weakly predictive:** standalone IC > 0.01 (even IC = 0.03 is useful if independent)
2. **Independent:** rank correlation with other signals < 0.3 (orthogonality = RL value)
3. **Consistent:** IC positive in ≥ 60% of years (not a random flip)

A signal that "fails" to improve a combined XGBoost model may still be RL-valuable if it is
independent and directionally consistent — the supervised model can't use sparse signals,
but an RL agent that selectively attends to them can.

---

## ✅ Confirmed Signals

### S1 — Cross-Sectional Relative Momentum (H93)
**Status: CONFIRMED — primary signal**

- **Standalone IC:** +0.149 (p < 0.001, all years positive)
- **Correlation with other signals:** N/A (primary reference)
- **Consistency:** 11/11 years IC positive
- **Edge std:** 1.60% (lowest variance seen)
- **Sharpe:** 15.08

**What it captures:** Short-term (1–20 day) relative return vs VNINDEX. Stocks that have
outperformed the market recently tend to outperform tomorrow's open. Strongest at the
T+1 opening auction.

**Artifact:** `data/features/xs_barrier_vol_1d_hose_full.parquet`
(columns: time, ticker, xs_proba, actual)

**Config:** H93 = volume features + 1-day barrier label + XGBoost XS walk-forward

**Run:**
```bash
PYTHONIOENCODING=utf-8 /c/Users/manhn/miniconda3/envs/stocks/python.exe cross_sectional_wf.py \
  --use-volume-signals --barrier-pct 0.01 --target-horizon 1 \
  --save-all-probas data/features/xs_barrier_vol_1d_hose_full.parquet
```

---

## 🔶 Candidate Signals (weak, needs improvement)

### C3 — Cross-Sectional Dispersion Regime (H101)
**Status: CANDIDATE/PASS (risk-adjusted), dense**

- **WF integration test:** H93 + dispersion features
- **IC (factor test):** +0.1474 (vs H93 +0.1491; small decrease)
- **Top-5 avg edge:** +23.83% (vs H93 +24.15%; small decrease)
- **Top-5 Sharpe:** **15.34** (vs H93 15.08; +0.26)
- **Edge std:** **1.55%** (vs H93 1.60%; improved stability)
- **Coverage:** 100% date-level (dense, non-sparse)

**What it captures:** Market-wide cross-sectional return spread and breadth regime
(dispersion std/iqr/tail spread, breadth up/down, rolling z-score). This acts as a
context signal that stabilizes ranking behavior across regimes.

**Why it matters for RL:** Dense regime context is suitable for policy conditioning and
appears to slightly improve risk-adjusted performance.

### C1 — Keyword News Sentiment (H89)
**Status: CANDIDATE — orthogonal but inconsistent**

- **Standalone IC:** +0.043 (p = 0.07, marginally significant)
- **Correlation with S1:** 0.009 (nearly fully independent)
- **Consistency:** 5/8 years IC positive (2020: +0.18, 2019: +0.12, but 2025: −0.18)
- **Coverage:** 0.8% of (trading_day, ticker) pairs — very sparse

**What it captures:** Sentiment of Vietnamese financial news articles about a specific stock
on a given day. Articles mentioning positive terms (tăng trưởng, đột phá, lãi) vs negative
terms (giảm, lỗ, khó khăn). Ticker identification via parenthetical `(TICKER)` in titles.

**Why it matters for RL:** Almost zero correlation with the price signal. On days when a
stock has news, the sentiment is an independent data point. RL agent can learn to use it
on news days and ignore it otherwise.

**Why it's weak:** Keyword lexicon is coarse; signal fires on only 0.8% of (day, ticker) pairs;
year-to-year variance is too high (some years strongly negative).

**Artifact:** `data/features/xs_news_sentiment_daily.parquet`
(columns: time, ticker, sentiment_score, sentiment_cs_z, positive_ratio, article_count)

**Needed to promote to CONFIRMED:** Rolling 5d/30d aggregation to reduce sparsity (H96),
or LLM-based scoring for higher quality (H98).

---

### C2 — Insider Net Buy Signal (H97)
**Status: CANDIDATE — orthogonal, standalone IC positive, XGBoost can't use it**

- **Standalone IC (5d window):** +0.0255 (9/11 years positive)
- **Significant years:** 2019, 2020, 2023, 2024 (all p < 0.05)
- **Correlation with S1:** −0.027 (near-zero → genuinely independent)
- **Coverage:** 3.57% of (trading_day, ticker) pairs — sparse but 4× denser than C1

**What it captures:** When company insiders (officers, directors, related persons) publicly
disclose a planned net buy transaction, the stock tends to outperform peers in the next 5 days.
Signal date is `PublishedDate` (SSC disclosure filing date) — no look-ahead.

**Why it matters for RL:** Nearly uncorrelated with S1. When the insider signal fires, it adds
independent evidence. RL agent can learn to up-weight positions when both S1 and C2 are positive.

**Why it's weak in XGBoost:** 3.57% coverage means XGBoost trees can't reliably split on this
feature — high-sparsity features increase variance on non-event rows without compensating gains.
(Same mechanism as C1/news — F66.)

**Session 32 standalone test (event-day ranking):**
- Top-1 edge: -0.304%
- Top-3 edge: +0.049%
- Top-5 edge: +0.090%
- Top-5 positive years: 5/11

Interpretation: C2 is still useful as an orthogonal RL context signal, but not robust as a
naive standalone tradable portfolio.

**Data source:** CafeF GDCoDong API — free, no auth, all 394 HOSE tickers covered.
```
https://cafef.vn/du-lieu/Ajax/PageNew/DataHistory/GDCoDong.ashx?Symbol=FPT&...
```

**Artifacts:**
- `data/features/xs_insider_deals_raw.parquet` — 32k raw rows
- `data/features/xs_insider_features.parquet` — rolling 5d/30d feature matrix (826k rows)

---

## ❌ Rejected Signals (not learnable under tested conditions)

| Signal | IC | Reason |
|--------|----|--------|
| Raw OHLCV technical indicators (standalone) | ~0 | F2: no edge vs drift baseline |
| FPT-only OHLCV model | 0 standalone | F4: single-stock feature space exhausted |
| Old keyword news (F8) | −3.31% edge | Raw count-based, no semantic content |
| Sector-relative features (H80, H94) | neutral | Already captured by rel_ret lags |
| Sector sub-models (H92) | worse than pooled | Data scarcity beats sector specificity |
| Macro regime as filter (VIX thresholds) | reduces IC | F41: contaminated; clean version neutral |
| Dormant features (CCI, WillR, vol_regime, calendar) | neutral | H77: no IC lift |
| Rolling 5d/30d news sentiment (H96) | IC −0.0008 vs H93 | F63: 94.9% zeros, model ignores |
| Body-text enhanced news (H99) | IC −0.0128 vs H93 | F64: 6× coverage but noisier per-obs |
| Insider deal features (H97) | IC −0.0007 vs H93, Sharpe −4.31 | F66: 3.57% sparse, adds variance |
| Open/close asymmetry dense features (H100/H102) | edge up, Sharpe down sharply | Variance inflation dominates |
| Return skewness dense features (H103) | IC −0.0002 vs H93, Sharpe −4.45 | Standalone IC too weak (+0.0019) |
| Earnings calendar dense features (H104/H105) | IC flat/slightly down, Sharpe −3.3 to −3.4 | Standalone IC weak (~0.001 to 0.006) |

---

## 🔲 Not Yet Tested

| Signal | Hypothesis | Data available | Priority |
|--------|-----------|----------------|---------|
| H98: LLM news sentiment | Higher quality than keyword approach | **PARKED** (runtime/throughput bottleneck) | Parked |
| H95: Foreign investor flow | Retail-dominated market: foreign = informed | NOT AVAILABLE historically (F59) | Blocked |
| Earnings calendar events | Price behavior around reporting dates | Build from public HOSE calendar | Medium |
| Order book imbalance | Bid/ask pressure predicts short-term price | Not available historically | Blocked |

**Session 33 update (2026-03-26):**
- H98 infrastructure is implemented:
  - `data_tools/extract_llm_news_features.py`
  - `data_tools/build_llm_news_features.py`
  - WF flags: `--use-llm-news`, `--use-llm-market`
- Full H98 signal evaluation is still pending because local Ollama timed out in this runtime during smoke extraction.

**Session 34 update (2026-03-26):**
- **H98 set to PARKED** by directive due runtime throughput.
- **H100 (open/close asymmetry):** not robust (edge up, Sharpe down materially).
- **H101 (dispersion regime):** best dense branch so far; slight Sharpe improvement with lower variance.

**Session 35 standalone-gate update (2026-03-26):**
- H100 proxy (`oc_asym_5d`) standalone IC: +0.0273 (10/11 years), corr with S1 +0.147.
- H101 context (`xs_dispersion_z20` vs S1 daily top-5 edge): weak standalone relation (Spearman −0.0289, p=0.13).
- H103 proxy (`ret_skew_z20`) standalone IC: +0.0019 (6/11 years), corr with S1 −0.0035.

**Session 36 update (2026-03-26):**
- H104 earnings calendar (dense date-level) fails risk-adjusted bar (Sharpe 11.80 vs H93 15.08).
- H105 (H101 + earnings calendar) degrades the best dense branch (Sharpe 11.96 vs H101 15.34).
- Earnings calendar standalone ICs are weak (~+0.001 to +0.006), below RL standalone threshold.

---

## Notes on Evaluation

**Do not evaluate signals by whether they beat H54 (+25.52% edge).**
H54 is a complete portfolio strategy, not a comparison bar for individual signals.

**Correct evaluation for RL signal library:**

| Criterion | Threshold | Rationale |
|-----------|-----------|-----------|
| Standalone IC | > 0.01 | Any positive predictive content is learnable |
| Correlation with S1 | < 0.30 | Independent = adds RL state diversity |
| IC positive years | ≥ 60% | Consistency — not just noise |
| p-value (standalone) | < 0.10 | Weak bar — we're searching, not deploying |

**Why XGBoost "failure" ≠ RL failure:**
XGBoost cannot use sparse features effectively. A signal that adds 0 IC to the combined
supervised model may still be independently learnable by an RL agent that observes all
signals separately and learns to weight them contextually.
