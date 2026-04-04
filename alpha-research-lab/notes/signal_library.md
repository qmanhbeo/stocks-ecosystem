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

### C6 — Contrarian Intra-Sector Signal (H112)
**Status: CANDIDATE — passes standalone gate, 11/11 years positive**

- **Standalone IC:** +0.0299 (11/11 years positive) — highest consistency of all candidates
- **Correlation with S1:** +0.142 (< 0.30 threshold — qualifies)
- **Consistency:** 11/11 years IC positive (perfectly consistent)
- **Coverage:** 100% (dense signal — computed for all 394 tickers, all dates)

**What it captures:** `contrarian_intra_5d = xs_sector_mom_5d_rank × (1 − xs_intra_sector_rank)`.
Buys the LAGGARD within a HOT sector. When a sector is outperforming (high sector_mom_rank),
the stock within that sector that has underperformed its peers over 5d tends to outperform
next day. Intra-sector mean reversion dominates sector herding in Vietnamese equities.

**Economic mechanism:** T+2 settlement + ±7% price limits. Sector rotation flows force some
holdings into initial sector leaders, creating short-term dislocations for sector laggards.
The next day, pent-up capital rotates into the remaining laggards.

**H112 full results (Session 39):**
- `contrarian_intra_5d`: IC = +0.0299, 11/11 years, corr = +0.142 → PRIMARY
- `contrarian_intra_20d`: IC = +0.0345, 11/11 years, corr = +0.171 → slightly better IC
- `reverse_intra = 1 − xs_intra_sector_rank`: IC = +0.0466, 11/11 years, corr = +0.256 → highest IC but less independent

**Correlation note:** C6 and xs_sector_breadth_5d are correlated at +0.303 (at threshold). For RL state, use
either C6 or breadth but not both. C6 is strictly preferred (IC +0.030 vs +0.014, 11/11 vs 8/11).

**Artifact:** Computed on the fly from `data/features/xs_sector_rotation_daily.parquet`
(formula: `xs_sector_mom_5d_rank × (1 − xs_intra_sector_rank)`)

---

### C7 — Price Limit Momentum Signal (H115)
**Status: CANDIDATE — ceiling count passes, floor reversal borderline**

- **Standalone IC:** xs_ceiling_count_5d = +0.0121 (8/11 years positive)
- **Correlation with S1:** +0.064 (very low — highly independent)
- **Consistency:** 8/11 years IC positive
- **Coverage:** 100% (dense — all tickers, all dates, mostly zero count)

**What it captures:** `xs_ceiling_count_5d` = cross-sectional rank of how many times a
stock hit the +7% daily price ceiling in the past 5 days. Stocks hitting the ceiling
have pent-up demand that couldn't be satisfied (price was truncated at the limit). The next
day, buyers who couldn't fill at the ceiling return, creating continuation.

**Also passes:** `xs_floor_count_20d` (IC = +0.0104, 8/11 years, corr = +0.034) — floor
reversal signal over 20-day window.

**Economic mechanism:** Vietnamese ±7% limits create two effects: (1) Ceiling: forced queue
of buyers waiting for next day's open; (2) Floor: oversold bounce after forced selling exhausts.

**H115 full results (Session 39):**
| Feature | IC | Pos Years | Corr S1 | Gate |
|---------|-----|-----------|---------|------|
| xs_ceiling_count_5d | +0.0121 | 8/11 | +0.064 | PASS |
| xs_floor_count_20d | +0.0104 | 8/11 | +0.034 | PASS |
| xs_floor_count_5d | +0.0029 | 7/11 | +0.010 | fail |
| xs_limit_net_5d | +0.0070 | 7/11 | +0.026 | fail |

**Artifact:** `data/features/xs_price_limit_daily.parquet`
(columns: time, ticker, xs_ceiling_count_5d, xs_floor_count_5d, xs_ceiling_count_20d, xs_floor_count_20d, xs_limit_net_5d)

---

### C8 — Volume Activity Signal (H116)
**Status: CANDIDATE — multiple features pass, highly independent from S1**

- **Standalone IC:** xs_vol_zscore_5d = +0.0110 (10/11 years positive)
- **Correlation with S1:** +0.068 (very low — the S1 model's internal volume features are different)
- **Consistency:** 10/11 years IC positive
- **Coverage:** 100% (dense — computed for all tickers, all dates)

**What it captures:** `xs_vol_zscore_5d` = cross-sectional rank of how far above (or below)
a stock's 5-day average volume is relative to its own 60-day baseline. Stocks with
unusually high volume relative to their own history are being actively rotated into —
"discovered" capital allocation that carries into the next day.

**Note on S1 overlap:** S1 (xs_proba) uses volume features internally (H90 confirmed volume
improves the combined WF model). The very low corr = +0.068 confirms that the simple volume
zscore captures a DIFFERENT dimension of the volume signal than the XGBoost model's learned
volume encoding.

**H116 full results (Session 39):**
| Feature | IC | Pos Years | Corr S1 | Gate |
|---------|-----|-----------|---------|------|
| xs_vol_zscore_1d | +0.0353 | 11/11 | +0.192 | PASS (use with caution) |
| xs_vol_zscore_5d | +0.0110 | 10/11 | +0.068 | PASS |
| xs_value_zscore_5d | +0.0120 | 10/11 | +0.065 | PASS |
| xs_vol_surge_5d | +0.0074 | 9/11 | +0.055 | fail |

**Preferred feature:** `xs_vol_zscore_5d` (IC +0.011, corr +0.068) over `xs_vol_zscore_1d`
(IC +0.035, corr +0.192) — smoother signal with better independence from S1.

**Artifact:** `data/features/xs_volume_zscore_daily.parquet`
(columns: time, ticker, xs_vol_zscore_1d, xs_vol_zscore_5d, xs_value_zscore_5d, xs_vol_surge_5d)

---

### C9 — Short-Term 1-Day Return Reversal (H117)
**Status: CANDIDATE — strong reversal effect, 0/11 years of 1d momentum**

- **Standalone IC (negated):** +0.0284 (11/11 years IC positive after negation)
- **Correlation with S1:** −0.161 (negative — independent and complementary to 5d momentum)
- **Consistency:** 0/11 years for raw 1d lag rank → 11/11 after negation → perfectly consistent
- **Coverage:** 100% (dense — computed for all 394 tickers, all dates)

**What it captures:** `xs_reversal_1d = 1 − rank(1d excess return lagged 1 day)`. Buys
yesterday's underperformers relative to the cross-section. Vietnamese market shows systematic
1-day mean reversion — stocks that outperformed peers on day T tend to underperform on day T+1.

**Economic mechanism:** T+2 settlement + retail profit-taking. When a stock outperforms peers
on day T, retail traders who bought intraday sell to book profits on T+1 (limit orders refresh
at the open). This creates systematic short-term over-reaction at the daily horizon.

**Dual momentum structure confirmed:**
- 5-day momentum (S1): IC = +0.15 → medium-term continuation
- 1-day reversal (C9): IC = −0.028 (raw) → daily mean reversion
The RL agent can learn to balance both: prefer stocks with strong 5d momentum AND recent 1d
underperformance (the "reversal + momentum" sweet spot).

**Partial overlap with C6:** corr(C9, C6) = +0.199. Both are reversal signals, but C6 is
sector-conditioned (only fires in hot sectors) while C9 is unconditional. Use both.

**Artifact:** `data/features/xs_shortterm_reversal.parquet`
(columns: time, ticker, xs_reversal_1d, xs_reversal_2d, xs_ret_1d_abs_rank)

---

### C10 — Amihud Illiquidity Level (H121)
**Status: CANDIDATE — passes standalone gate, near-zero S1 correlation**

- **Standalone IC:** +0.0206 (10/11 years positive)
- **Correlation with S1:** +0.008 (near-zero → highly independent)
- **Consistency:** 10/11 years IC positive
- **Coverage:** 100% (dense — computed for all tickers, all dates)

**What it captures:** `xs_illiq_level_rank` = cross-sectional rank of 20d rolling average Amihud ILLIQ
= |daily_return| / (daily_trading_value in VND billions). Stocks with higher illiquidity (more price
impact per unit of capital) are under-followed and slower to incorporate information; when they begin
moving, continuation persists because the follow-on capital queue is long relative to float.

**Economic mechanism:** Classic Amihud (2002) illiquidity premium. In Vietnam's retail market,
small/illiquid stocks are not actively followed by institutions — price discovery is slower and
informed capital flows take multiple days to be absorbed.

**Spike and change signals fail:** Only the structural level (20d avg) is predictive. Today's
illiquidity spike vs own baseline (xs_illiq_spike_rank, IC=−0.001) and 5d rank change
(xs_illiq_change_5d, IC=−0.003) both fail the gate.

**Artifact:** Computed on the fly from OHLCV:
`illiq_raw = |pct_change(close, 1)| / (close × volume / 1e9)`, then 20d rolling mean + xs-rank.
No persistent file — build inline from `data/stock/gia_lich_su_*_1D.parquet`.

---

### C11 — 3-Month Continuation / Medium-Term Trend (H123)
**Status: CANDIDATE — passes standalone gate, orthogonal to S1**

- **Standalone IC:** +0.0101 (9/11 years positive)
- **Correlation with S1:** +0.008 (near-zero → highly independent)
- **Consistency:** 9/11 years IC positive
- **Coverage:** 100% (dense signal — computed for all 394 tickers, all dates)

**What it captures:** `xs_ret_60d_lag_rank` = cross-sectional rank of 60d excess return vs VNINDEX,
lagged by 1 day. H123 was framed as a reversal test, but the sign that survives is continuation,
not reversal.

**Economic mechanism:** 60d relative strength persists after the short-term reversal window has
faded. This is a slower, cleaner momentum axis than S1 and remains essentially independent of the
existing candidate set.

**Rejected orientation:** `xs_reversal_60d = 1 - xs_ret_60d_lag_rank` fails the gate
(IC = -0.0101, 2/11 years positive).

**Artifact:** Computed on the fly from OHLCV; no persistent file.

---

### C12 — Gap Absorption with Intraday Confirmation (H130)
**Status: CANDIDATE — strong microstructure state signal, orthogonal to current library**

- **Standalone IC:** +0.0284 (11/11 years positive)
- **Correlation with S1:** +0.131 (independent enough to qualify)
- **Consistency:** 11/11 years IC positive
- **Coverage:** 100% (dense signal — computed for all 394 tickers, all dates)

**What it captures:** `xs_gap_absorb_3 = rank(gap × 1[intraday > 0] × clv)`, where:
- `gap = open / close[t-1] - 1`
- `clv = (close - low) / (high - low)`

The signal fires when a stock gaps up and the market CONFIRMS that overnight information by
closing well and finishing the session green from the open. This is not just "gap momentum";
it is gap acceptance.

**Economic mechanism:** In Vietnam's T+2, retail-heavy market, overnight information often shows
up first in the opening auction. The key question is whether intraday trading absorbs that gap
or rejects it. When the stock gaps and still closes strong, demand was not just auction noise —
it persisted through the session and tends to carry into the next day.

**H130 full results (Session 43):**
- `xs_gap_absorb_1 = rank(gap × clv)`: IC = +0.0117, 11/11 years, corr S1 = +0.022, corr C4 = +0.298 → PASS but weaker
- `xs_gap_absorb_2 = rank(gap − intraday)`: IC = +0.0334, 10/11 years, corr S1 = +0.151, corr C4 = +0.453 → REJECTED AS REDUNDANT
- `xs_gap_absorb_3 = rank(gap × 1[intraday > 0] × clv)`: IC = +0.0284, 11/11 years, corr S1 = +0.131, corr C4 = +0.202 → PRIMARY
- `xs_gap_reject_1`: IC = +0.0073, 8/11 years → fail

**Preferred feature:** `xs_gap_absorb_3` over `xs_gap_absorb_1` because it is much stronger
while staying comfortably below the redundancy threshold.

**Artifact:** Computed on the fly from OHLCV; no persistent file.

---

### C13 — Compression Blow-Off Reversal (H133)
**Status: CANDIDATE — strong reversal state, distinct from current library**

- **Standalone IC:** +0.0351 (10/11 years positive)
- **Correlation with S1:** +0.191 (passes independence gate)
- **Consistency:** 10/11 years IC positive
- **Coverage:** 100% (dense signal — computed for all 394 tickers, all dates)

**What it captures:** `xs_compress_blowoff_2 = 1 - rank(compress_10_rank × expansion_rank × close_rank × vol_rank)`.
This is the exact sign-flipped interpretation of H128's failed breakout continuation setup.

**Economic mechanism:** In Vietnam, a stock that emerges from a compressed range with a large,
high-volume expansion bar is often not beginning a new trend; it is exhausting one. The combination
of prior compression, fresh range expansion, strong close, and high volume behaves like a blow-off
state that mean-reverts the next day.

**H133 full results (Session 44):**
- `xs_compress_blowoff_1`: IC = +0.0541, 11/11 years, corr S1 = +0.321 → fail on S1 overlap
- `xs_compress_blowoff_2`: IC = +0.0351, 10/11 years, corr S1 = +0.191, max candidate corr = +0.154 → PRIMARY
- `xs_compress_blowoff_3`: IC = +0.0540, 11/11 years, corr S1 = +0.340 → fail on S1 overlap

**Preferred feature:** `xs_compress_blowoff_2`. The higher-IC alternatives are too correlated with S1.

**Artifact:** Computed on the fly from OHLCV; no persistent file.

---

### C14 — Residual Close-Location Strength After Removing C8 (H134)
**Status: CANDIDATE — H127 survives after explicit de-duplication vs volume**

- **Standalone IC:** +0.0131 (11/11 years positive)
- **Correlation with S1:** +0.102
- **Consistency:** 11/11 years IC positive
- **Coverage:** 100% (dense signal — computed for all 394 tickers, all dates)

**What it captures:** `xs_clv_volconf_resid_rank` is the cross-sectional residual of the H127
volume-confirmed close-location signal after regressing it on `C8` (`xs_vol_zscore_5d`) each day.

**Economic mechanism:** H127 showed that "close near high + volume" is real, but most of that effect
was just C8. H134 isolates what remains after removing the explicit volume-activity axis. The residual
still predicts returns, which implies there is a genuine close-strength / intraday-control component
that volume alone does not explain.

**H134 full results (Session 44):**
- `xs_clv_volconf_resid_rank`: IC = +0.0131, 11/11 years, corr S1 = +0.102, max candidate corr = +0.099 → PASS
- inverted orientation: IC = −0.0131, 0/11 years → fail

**Artifact:** Computed on the fly from OHLCV plus the existing C8 series; no persistent file.

---

### I1 — Reduced-Shape Intraday Disagreement Atoms (H275)
**Status: CANDIDATE — observed-subset intraday state family, offline only**

- **Observed subset:** `243,763` rows from the `2023-2025` matrix
- **Observed share:** `94.34%` of audited `2023-2025` matrix rows
- **Breadth:** `394` tickers across `718` dates
- **Scope:** reduced-shape `1H` history only; not a dense full-history library promotion

**What passed:**
- `fade_tension_disagreement`
  - dev / validation / confirmation IC:
    - `+0.0323 / +0.0367 / +0.0202`
  - max dev correlation vs `S1`, `C4`, `C12`:
    - `0.0667`
- `intraday_shape_core_disagreement`
  - dev / validation / confirmation IC:
    - `+0.0330 / +0.0259 / +0.0160`
  - max dev correlation vs `S1`, `C4`, `C12`:
    - `0.0751`

**What they capture:** The surviving intraday information is not the raw reduced-shape axis.
It is the cross-sectional disagreement between reduced-shape intraday behavior and the existing
daily continuation / gap / close-location library. Concretely:
- `fade_tension_disagreement` = residual of daily `rank(first_hour_fade_proxy)` after removing
  `S1`, `C4`, and `C12`
- `intraday_shape_core_disagreement` = residual of the reduced-shape core
  (`fade + failed breakout + drive/fade`) after removing `S1`, `C4`, and `C12`

**Why only offline / observed-subset for now:**
- this is `2023-2025` only because the reduced-shape intraday source does not extend across the
  full historical library window
- the branch did **not** survive as a live gate in `H274`
- these atoms are therefore candidate RL state features, not activation or deployment rules

**Important constraint:** the raw reduced-shape atoms were predictive but failed the orthogonality
bar:
- `fade_tension_rank`: strong IC, but corr vs `S1` = `+0.319`
- `intraday_shape_core_rank`: strong IC, but corr vs `C4` = `+0.316`
- `failed_breakout_rank`: weaker IC, but corr vs `C4` = `+0.318`

So the disagreement residual is the promotable part, not the raw atom itself.

---

### ~~C3 — Cross-Sectional Dispersion Regime (H101)~~ REJECTED (Session 37)

**Status: REJECTED — regime-conditional IC analysis decisive (2026-03-27)**

- **WF integration test (Session 34):** Sharpe 15.34 (+0.26 vs H93) — marginal noise, not genuine
- **Standalone gate (Session 37, H106):** IC spread across dispersion terciles ≤ 2% relative
  (threshold: >10%). No monotone relationship between dispersion level and signal quality.
- **Day-level Spearman** vs S1 top-5 accuracy: p=0.124 for primary feature (xs_dispersion_z20)

See `notes/findings-061-090.md` (F67) for full analysis.

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
| VN30 rebalancing proximity (H114) | xs_vn30_rank_change_5d IC +0.0075 (10/11) | Rank level anti-predictive; change directionally consistent but below 0.01 gate |
| 52-week high proximity (H118) | xs_52w_high_prox IC +0.0065 (9/11) | Directionally correct but below IC > 0.01 gate |
| Low volatility anomaly (H119) | xs_low_vol_20d IC −0.011 (1/11) | Anti-predictive: Vietnam is HIGH-beta market (opposite of global anomaly) |
| Intraday reversal (H120) | xs_intraday_reversal IC +0.041 | IC strong but corr with C4 (oc_asym_5d) = +0.394 — captured by C4 already |
| Illiquidity spike/change (H121 sub-features) | xs_illiq_spike_rank IC −0.001; xs_illiq_change_5d IC −0.003 | Only structural level (20d avg) is predictive; intraday shocks and trend changes are noise |
| Bid-ask spread proxy (H122) | xs_spread_level_rank IC −0.0097; xs_spread_spike_rank IC −0.0301; xs_spread_change_5d IC −0.0035 | Corwin-Schultz H/L spread estimate is anti-predictive / noisy in this market |
| Earnings quality 394 tickers (H113) | best IC +0.006 (eps_yoy_rank); all others < 0.005 | Daily time-series application of quarterly data too coarse; all five features fail IC > 0.01 gate at full universe |
| Beta regime (H124) | `xs_low_beta_60d` passes standalone IC +0.013, but corr with C10 = +0.552 | Low-beta names are not orthogonal; beta collapses onto the illiquidity axis |
| Beta residual (H125) | `xs_low_beta_resid_60d` IC +0.0019, 6/11 years | Once beta is residualized vs illiquidity/volume, the signal disappears |
| Close-location persistence (H127) | `xs_clv_volconf_5d_rank` IC +0.0149, but corr with C8 = +0.903 | Strong standalone, but it is effectively the same axis as abnormal volume activity |
| Compression breakout continuation (H128) | best IC −0.035 (xs_compress_breakout_2) | Breakout-follow-through thesis is wrong in this market; the tested orientation is strongly anti-predictive |
| Sector breadth shock (H131) | best IC −0.003 (xs_breadth_shock_laggard) | Breadth changes add no standalone value beyond existing sector structures |
| Conditional liquidity release (H132) | best IC +0.007 (xs_liq_release_1) | Conditioning illiquidity changes on return/close state still does not clear the 0.01 gate |
| Longer-horizon continuation (H126) | 90d/120d ranks IC +0.011 but corr with C11 = +0.775 / +0.664 | Real signal, but it is just a longer-horizon restatement of the existing continuation axis |

---

## 🔲 Not Yet Tested

| Signal | Hypothesis | Data available | Priority |
|--------|-----------|----------------|---------|
| H98: LLM news sentiment | Higher quality than keyword approach | **PARKED** (runtime/throughput bottleneck) | Parked |
| H95: Foreign investor flow | Retail-dominated market: foreign = informed | NOT AVAILABLE historically (F59) | Blocked |
| H135: Gap-failure exhaustion | Combine H130 and H133 logic: failed gap acceptance after compression may be the strongest reversal state | Ready to test | High |
| H136: Sector-conditioned blow-off reversal | Test whether H133 strengthens inside hot sectors or recent ceiling clusters | Ready to test | High |
| H137: Residual long-horizon reversal | H126 continuation is redundant; test the sign-flipped 90d/120d residual after removing C11 | Ready to test | Medium |
| Order book imbalance | Bid/ask pressure predicts short-term price | Not available historically | Blocked |

H123, H124, H125, H126, H127, H128, H130, H131, H132, H133, and H134 are now closed and documented above.
Track new OHLCV-only search ideas in `notes/next_steps.md`.

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
