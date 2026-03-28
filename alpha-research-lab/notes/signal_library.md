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

### C4 — Open/Close Asymmetry (H107)
**Status: CANDIDATE — passes standalone gate, confirmed orthogonal**

- **Standalone IC:** +0.0225 (vs 1-day barrier label, 11/11 years positive)
- **Correlation with S1:** +0.147 (< 0.30 threshold — qualifies)
- **Consistency:** 11/11 years IC positive (highly consistent)
- **Coverage:** 100% (dense signal — computed for all 394 tickers, all dates)

**What it captures:** `oc_asym_5d = overnight_mom_5d − intraday_mom_5d`. The signal lives
entirely in the CONTRAST between overnight and intraday momentum — not either component alone.
When a stock's overnight gains (pre-open auction) are not reversed during intraday trading,
the signal predicts next-day continuation. H107 (Session 38) confirmed the decomposition:
overnight_mom_5d alone has IC ≈ 0 and intraday_mom_5d is anti-predictive (IC = −0.034).

**Economic mechanism:** T+2 settlement + ±7% price limits. Overnight gaps reflect informed
auction activity using US-close/VNM-ETF information that cannot be traded until the 9:00 AM
opening. The gap-minus-intraday contrast isolates the informed signal from mean-reversion noise.

**Why not in supervised WF:** H100/H102 tested this in combined XGBoost — Sharpe collapsed from
15.08 to ~12 due to variance inflation. As a STANDALONE signal for RL state, it passes.

**Artifact:** `data/features/xs_open_close_asymmetry.parquet`
(columns: time, ticker, oc_asym_5d, overnight_mom_5d, intraday_mom_5d, oc_asym_20d, gap_abs_5d)

---

### C5 — Insider Relative Size Signal (H108)
**Status: CANDIDATE — UPGRADES C2, highest IC of all insider features**

- **Standalone IC:** +0.0374 (10/11 years positive) — +46% improvement over raw C2
- **Correlation with S1:** −0.008 (near-zero → genuinely independent)
- **Consistency:** 10/11 years IC positive (superior to raw C2's 9/11)
- **Coverage:** 3.39% of (trading_day, ticker) pairs

**What it captures:** `net_plan_vol / VolumeBeforeTransaction` — position-normalized insider
conviction. A CEO buying 10% of their holdings is far more informative than buying 0.01%,
even if the absolute share count is the same. Raw C2 counted absolute volume; C5 counts
the fractional commitment signal.

**Session 38 H108 findings (vs baseline C2 IC = +0.0255):**
- `xs_ins_relative_size_5d`: IC = +0.0374, 10/11 positive, corr = −0.008 → BEST
- `xs_ins_quality_buy_5d` (tier-weighted): IC = +0.0248, 9/11 → slightly below baseline
- `xs_ins_ceo_buy_5d` (CEO only): IC = +0.0210, 5/11 → inconsistent (too sparse at 0.78%)
- `xs_ins_exec_rate_5d` (execution rate): IC = −0.0084 → anti-predictive

**Execution rate finding:** When insiders execute LESS than announced (exec_rate < 1.0), it
is slightly bearish — consistent with "lost conviction after disclosure" hypothesis. Not
strong enough standalone but may be useful as a confirmation filter.

**Artifact:** `data/features/xs_insider_quality_features.parquet`
(key column: xs_ins_relative_size_5d)

**Supersedes C2:** C5 is strictly better. Use `xs_ins_relative_size_5d` as the primary
insider signal going forward.

---

### ~~C3 — Cross-Sectional Dispersion Regime (H101)~~ REJECTED (Session 37)

**Status: REJECTED — regime-conditional IC analysis decisive (2026-03-27)**

- **WF integration test (Session 34):** Sharpe 15.34 (+0.26 vs H93) — marginal noise, not genuine
- **Standalone gate (Session 37, H106):** IC spread across dispersion terciles ≤ 2% relative
  (threshold: >10%). No monotone relationship between dispersion level and signal quality.
- **Day-level Spearman** vs S1 top-5 accuracy: p=0.124 for primary feature (xs_dispersion_z20)

See `notes/findings.md` F67 for full analysis.

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
| Dispersion regime (C3/H101/H106) | Regime IC spread ≤ 2%, p=0.124 | No regime effect on H93 IC; H101 Sharpe gain (+0.26) is noise |
| Overnight gap decomposition (H107) | overnight_mom IC ≈ 0, intraday IC −0.034 | Signal in oc_asym CONTRAST, not components; oc_asym_5d → C4 |
| Insider tier-weighting (H108 quality) | CEO-only IC +0.021, exec-rate IC −0.008 | Position-size normalization wins; tier/quality weighting doesn't |
| Sector rotation composite (H111) | xs_sector_rotation_signal IC −0.038 | Intra-sector rank is anti-predictive (laggards beat leaders) |
| VNM ETF foreign affinity (H110) | xs_fa_signal IC −0.001 | ETF premium is market-direction signal only; no cross-sectional differentiation |
| Earnings quality 52 tickers (H109) | best IC +0.005 (roe_delta) | Insufficient universe; re-test at 394 tickers pending |

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
