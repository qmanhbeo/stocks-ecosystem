# Signal Library — Learnable Alpha Signals for RL Training

This is the registry of signals confirmed to have predictive information for Vietnamese equities.
It is the **primary output** of this research lab.

**Goal:** Build a diverse set of orthogonal signals that an RL agent can learn to weight
dynamically. A signal does not need to be a complete trading strategy — it needs to be:

1. **Strong enough for promotion:** standalone IC > 0.05 for a real signal-library
   promotion; IC between 0.01 and 0.05 is weak candidate/context evidence.
2. **Independent:** rank correlation with existing library signals < 0.3
   (orthogonality = RL value).
3. **Consistent:** IC positive in >= 60% of years (not a random flip).
4. **Decision-time valid:** the feature/state must be observable before the
   execution decision, with no target-derived or future-derived regime labels.
5. **Not just a parent-signal slice:** filters or variations of S1, C16, or
   another existing parent must clear incremental lift and mechanism-matched
   controls versus that parent; absolute IC versus random is not enough.

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

**Execution rate finding:** `xs_ins_exec_rate_5d` is still weak or anti-predictive as a
standalone feature, but Session 132 `H306` showed it matters as a conditioner on the
**positive side** of `C5`. Two rewrites improved confirmation stability versus raw `C5`:
- `c5_scale_pos_exec_cap_dev_median`: scale positive `C5` by clipped `exec_rate / 0.20`
  using the dev-median threshold. Avg IC `+0.0379`, `11 / 11` positive years,
  confirmation pooled IC `+0.0119`.
- `c5_gate_pos_exec_gt_0`: zero positive `C5` rows when follow-through is absent.
  Avg IC `+0.0368`, `11 / 11` positive years, confirmation pooled IC `+0.0088`.

**Order-pressure finding:** Session 162 `H340` showed same-day posted buy-volume pressure is
an even stronger conditioner on the **positive side** of `C5` than exec-rate:
- `c5_scale_pos_buy_vol_ratio_cap_dev_median`: scale positive `C5` by clipped same-day
  buy-volume imbalance relative to the dev median support threshold. Avg IC `+0.0693`,
  `11 / 11` positive years, confirmation pooled IC `+0.0576`.
- `c5_gate_pos_buy_vol_ratio_gt_0`: zero positive `C5` rows when same-day posted
  buy-volume imbalance is non-positive. Avg IC `+0.0688`, `11 / 11` positive years,
  confirmation pooled IC `+0.0565`.
- `c5_gate_pos_dual_buy_pressure_gt_0`: require both same-day buy-volume and buy-count
  imbalance to stay positive. Avg IC `+0.0626`, `11 / 11` positive years,
  confirmation pooled IC `+0.0474`.
- `c5_gate_pos_buy_count_ratio_gt_0` failed confirmation (`-0.0212`), so count-only
  pressure is not the surviving mechanism.

**Stacking update:** Session 163 `H341` tested whether `H306` exec-rate adds
further value on top of the new `H340` buy-volume rewrite. It did not. The best
stacked row, `c5_scale_pos_exec_x_buy_vol_min_cap_dev_medians`, held `11 / 11`
positive years but still missed the `H340` baseline on avg IC retention
(`94.3%`) and on validation / confirmation pooled IC (`+0.0935 / +0.0548`
versus `+0.0980 / +0.0576`). The hard intersection gate also failed. Treat
`H340` as the preferred daily-state rewrite and keep `H306` only as a fallback
when order-pressure data is unavailable.

**Entry-book transfer update:** Session 192 `H353` tested whether H340 should
be promoted from a daily-state C5 rewrite into an entry-alpha prior. It should
not. The loose buy-volume gate had positive validation matched return lift
(`+0.0031`) but slightly negative confirmation return lift (`-0.0001`). The
strong buy-volume support state was positive in both validation and
confirmation (`+0.0001 / +0.0028` matched relative-return lift), but did not
beat raw positive `C5` in validation. Keep this as offline entry-book evidence
only.

**Foreign-flow interaction update:** Session 186 `H347` tested foreign-flow
agreement as a distinct non-price conditioner after standalone foreign-flow
paths failed. Foreign support improved raw `C5`, but did not beat the stronger
H340 rewrite:
- best row `c5_gate_pos_order_and_ff_net_5d_gt_0`: avg IC `+0.0572`,
  `11 / 11` positive years, validation / confirmation IC
  `+0.0942 / +0.0376`, S1 corr `-0.0258`
- raw `C5`: avg IC `+0.0374`, validation / confirmation IC
  `+0.0808 / +0.0028`
- H340 benchmark: avg IC `+0.0693`, validation / confirmation IC
  `+0.0980 / +0.0576`
Keep H347 as offline interaction evidence only. Do not replace H340 or tune
more foreign-net windows around `C5`.

**Insider-down update:** Session 265 `H387` tested whether positive C5 after
visible 1d/3d stock weakness plus high C16 forms a distinct rescue state. It
failed against the important controls: `insider_down_high_c16` beat ordinary
`insider_buy`, but its mean 5d lift was only `+0.00087` versus
`insider_high_c16` and `-0.00308` versus `stock_down_high_c16`, with negative
2025 lifts versus both. Do not add an insider-down overlay under the current
representation.

**Event-time update:** Session 279 `H398` reproduced the S272 positive-insider
event-time lead and rejected the current quiet pre-reaction form. `insider_tplus1`
reached avg C16 IC `+0.10498`, `11 / 11` positive years, and `+0.03000` lift
versus same-ticker non-event dates; `insider_t0` was also strong at `+0.10816`.
But `insider_tplus1_pre_reaction` lost to reacted T+1 rows by `-0.01811` avg
IC, while high buy-order-count T+1 insider rows were strongest (`+0.13776` avg
IC). Keep `insider_buy_lead` as real event-time evidence; do not promote the
no-news/no-high-count pre-reaction variant.

**Interpretation update:** weak bullish follow-through is a pollutant on raw `C5`, not a
new alpha family. The current preferred robustness form is the `H340`
same-day buy-volume rewrite, with the `H306` exec-rate rewrite as a weaker
secondary conditioner when needed.

**Artifact:** `data/features/xs_insider_quality_features.parquet`
(key column: xs_ins_relative_size_5d)

**Supersedes C2:** C5 is strictly better. Use `xs_ins_relative_size_5d` as the primary
insider signal going forward, with the `H340` positive-side buy-volume rewrite as the
preferred robustness variant when the branch wants a more selective daily-state form.

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

**Crowd-count update:** Session 280 `H399` found that high volume-z owns the
cleanest crowd-adjacent C16 pocket. `volume_z_high80` reached avg C16 IC
`+0.10258`, `8 / 8` positive years, and `+0.02739` lift versus all rows.
`high_count_volume_z_high80` was only marginally higher (`+0.10285`), so this
should be treated as C8/volume-state context rather than a new buy-count
primitive. In the same audit, `buy_count_rank` was anti-predictive
(`-0.01075`) and high buy count alone was only modest context.

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

### C15 — LLM News State Router (H290, H294)
**Status: OFFLINE EVIDENCE — state-gated news surface is real in the nonzero 2015-2017 window**

- **Standalone IC:** the pooled news surface is weak or negative, but the routed buckets are much stronger:
  - `llm_sentiment_30d` overall IC `-0.0121` (vs 5d return, H290)
  - `llm_sentiment_raw` overall IC `+0.047` (vs 1d barrier, H294) — 1/2 years positive (inconsistent)
  - `llm_sentiment_30d` in `novelty=follow`: IC `+0.1618`, daily hit rate `0.6296` (vs 5d return)
  - `llm_sentiment_5d` in `novelty=follow`: IC `+0.4796` (vs 5d return); `+0.4036` (vs 1d barrier) — extraordinary but 1 observable year only
  - **`llm_sentiment_raw` in `novelty=new`: IC `+0.078`, 2/2 years positive, 1331 rows (vs 1d barrier, H294)** — new; passes IC + available-year consistency gates
  - `llm_sentiment_raw` in `alignment=miss`: IC `+0.136`, 1/2 years (vs 1d barrier)
- **Correlation with S1:** `llm_sentiment_raw` corr with S1 `−0.043` (H294); `llm_sentiment_5d` corr with S1 `−0.0022` (H290)
- **Consistency:** `novelty/new` vs 1d barrier is 2/2 available years; full 6/8-year gate blocked by data constraint
- **Coverage:** 0.19% of (trading_day, ticker) pairs with nonzero LLM signal; below C1 (0.8%); active-book years zero-valued

**What it captures:** LLM news is not a single pooled sentiment factor. The same surface behaves very differently depending on state:
- `novelty/new` (dominant new information, not follow-up) is consistently predictive vs the 1d barrier
- `novelty/follow` (dominant follow-up context) is extraordinarily strong but too sparse to confirm with year consistency
- `alignment/miss` (expectation misses) shows a directional edge but is inconsistent across the 2 available years
- `novelty/flat` is anti-predictive (IC −0.285)

**Economic mechanism:** New, non-anticipated information moves prices more cleanly the next day in Vietnam's retail-heavy, T+2 market. Follow-up information in the right context triggers a larger concentrated response. Pooled sentiment gets overwhelmed by the noisy flat/beat cases.

**Why not live:** active-book years (2018-2025) have zero LLM cache coverage. Re-evaluate when extraction pipeline covers those years.

**Artifact:** `data/features/xs_llm_news_ticker_day.parquet`
  - routed on the 2016-2017 nonzero window
  - key feature: `llm_sentiment_raw` gated by `novelty/new` (llm_new_info_5d > llm_followup_info_5d)

---

### C16 — CafeF Posted Order-Volume Pressure (H356)
**Status: PUBLISHED FEATURE — scoped H359 contract, downstream opt-in only**

- **Standalone IC vs 1d barrier:** `+0.0738`
- **Consistency:** `11 / 11` years positive
- **Correlation with S1:** `+0.0342`
- **Coverage:** `98.04%` active rows on the 2015-2025 S1 panel
- **Split IC:** dev `+0.0799`, validation `+0.0593`, confirmation `+0.0713`
- **5d diagnostic IC:** `+0.0797`, also `11 / 11` positive years
- **Full-library residual IC (H357):** `+0.0687`, `11 / 11` positive years
- **Max current-library correlation:** `0.1877` with `C13`, below the
  redundancy bar
- **Frozen selector delta:** validation / confirmation top-5 edge
  `+0.0152 / +0.0554`
- **Executable portfolio delta (H358):** validation / confirmation relative
  return `+12.31% / +11.07%`, but validation cash drag `+0.0214` breached
  the `0.02` execution-health limit
- **Scoped sizing delta (H359):** `order_w0050_buyable` validation /
  confirmation relative return `+32.20% / +5.82%`; cash deltas
  `+0.0036 / -0.0067`
- **Published artifact (Session 200):** `data/features/xs_order_pressure_daily.parquet`
  with `1,315,778` rows, `402` tickers, `4,622` dates, max date
  `2025-12-31`, no duplicate ticker-days, and H359 blend weights of `0.0` or
  `0.05`
- **Published contract parity (H360):** reproduced the H359 winner with max
  absolute metric delta `9.10e-15`; portfolio and execution-health gates still
  passed

**What it captures:** `order_volume_ratio_rank` is the cross-sectional rank of
CafeF posted buy-vs-sell order-volume imbalance:
`(buy_order_volume - sell_order_volume) / (buy_order_volume + sell_order_volume)`.
It measures same-day demand pressure from the order-statistics page-2 daily
summary surface, available after the trading day and usable for a T-close
signal / T+1 open fill protocol.

**Why it matters:** H340 had already shown posted buy-volume pressure is a
strong conditioner on bullish insider conviction. H356 shows the same surface
has broad standalone value with dense coverage and low S1 overlap. This makes
CafeF order pressure one of the strongest current-data side-channel candidates
in the lab.

**Integration update:** H357 residualized `order_volume_ratio_rank` against the
current full library and tested it as one equal-weight addition to the frozen
label-level full-library selector. The residual signal stayed strong, and the
selector improved in validation and confirmation.

**Portfolio / tradability update:** H358 tested the same equal-weight addition
in the executable deterministic portfolio with the shared tradability artifact,
fees, T+1 open fills, and legal sell delay. The portfolio relevance was real:
validation / confirmation relative-return deltas were `+12.31% / +11.07%` and
IR deltas were `+0.15 / +0.47`. The pass was still classified `MIXED`, not
publishable, because validation average cash weight rose from `0.0238` to
`0.0452`, a `+0.0214` delta versus the predeclared `0.02` health limit.

**Sizing / state-scope update:** H359 then ran the one bounded continuation
allowed by H358. The winner, `order_w0050_buyable`, blends the full-library
score with `5%` order-pressure rank only where `can_buy_next_open` is true.
It passed both portfolio and execution-health gates: validation relative
return delta `+32.20%`, validation IR delta `+0.3735`, confirmation relative
return delta `+5.82%`, confirmation IR delta `+0.2738`, and validation /
confirmation cash deltas `+0.0036 / -0.0067`.

**Current constraint:** The scoped feature is now published and registered, but
it is not automatically consumed by RL or recommendations. Any downstream use
must explicitly apply `score = (1 - w) * base_score + w * order_volume_ratio_rank`,
where `w` is `order_pressure_h359_blend_weight`.

**Artifact:** source data currently lives at
`data/order_stats/cafef/order_stats_daily.parquet`. The published feature lives
at `data/features/xs_order_pressure_daily.parquet`. H356 saved research results under
`artifacts/run_summaries/latest_research_branch_order_pressure_standalone_gate.json`;
H357 saved integration results under
`artifacts/run_summaries/latest_research_branch_order_pressure_integration_audit.json`;
H358 saved executable portfolio results under
`artifacts/run_summaries/latest_research_branch_order_pressure_portfolio_tradability_audit.json`;
H359 saved sizing / state-scope results under
`artifacts/run_summaries/latest_research_branch_order_pressure_sizing_scope_audit.json`;
the publisher saved
`artifacts/run_summaries/latest_published_feature_order_pressure_daily.json`;
H360 saved the published contract audit under
`artifacts/run_summaries/latest_research_branch_order_pressure_published_contract_audit.json`.

---

### Q1 — Weak Signal Quorum Sleeve (H395)
**Status: STRONG COMPOSITE CANDIDATE — offline RL-state aggregate, not a new primitive**

- **Standalone IC vs 1d barrier:** `+0.05826`
- **Consistency:** `7 / 7` walk-forward test years positive (`2019-2025`)
- **Correlation with S1:** `+0.27541` (passes `<0.30`, but close)
- **Correlation with C16:** `-0.00685`
- **Lift versus random weak baskets:** `+0.02078`
- **Lift versus best individual component:** `+0.02745`
- **2025 confirmation IC:** `+0.06032`

**What it captures:** agreement among weak, mostly low-parent-correlation
candidate votes. H395 predeclared C4-C14, H364/news, official-delay,
observable VNI-down-2d, January-first-10, and Monday votes. For each test year,
it selected components using only prior years if train avg IC was at least
`+0.005`, positive-year share was at least `60%`, and train absolute
correlation to both S1 and C16 was below `0.30`. Test-year scoring used equal
weights only.

**Stable selected votes:** mostly C-library atoms (`C4`, `C6`, `C8-C14`) plus
`official_supported_delay`. `C5` and `C7` entered some folds. H364 positive
news was weak positive but did not pass the train selection gate; January and
Monday calendar votes were not useful.

**Why it matters:** H395 validates that IC `0.01-0.05` signals should not be
discarded. Weak votes can form a stronger RL state when they agree.

**Important constraint:** this is a composite of known candidate atoms, not a
new independent primitive signal. Do not double-count it as independent from
the C-library components until a residual / parent-echo audit passes.

**Residual audit update:** H396 confirmed the exact status. Q1 survives
same-date S1+C16 residualization with avg IC `+0.01669` and `7 / 7` positive
years, so it is not merely a market-parent echo. It does not survive
residualization against its C4-C14 ingredients (`+0.00187`), so it remains a
composite sleeve rather than a new primitive. The clean primitive residual
survivors from H396 were C13 (`+0.01839`), C10 (`+0.01278`), and C6
(`+0.01115`) after S1+C16 residualization.

**Artifact:** H395 saved the test scores and component selection audit under
`artifacts/run_summaries/20260505_171827_h395_weak_signal_quorum_sleeve_research_branch_weak_signal_quorum_sleeve.json`.
H396 saved the residual audit under
`artifacts/run_summaries/20260505_172353_h396_parent_echo_residual_harvester_research_branch_parent_echo_residual_harvester.json`.

---

### C17 — CafeF Order-Volume Ratio (H409)
**Status: DISCOVERED — candidate, orthogonality verified vs C16 and S1**

- **Standalone IC vs 1d barrier:** `+0.077`
- **Consistency:** `8 / 8` years positive
- **Correlation with S1:** `0.012` (very low - orthogonal!)
- **Correlation with C16:** `0.052` (very low - orthogonal!)
- **Coverage:** `98%+` rows on the S1 panel

**What it captures:** `order_volume_ratio` = 
`(buy_order_volume - sell_order_volume) / (buy_order_volume + sell_order_volume)`.
Same formula as C16 but from the raw order-statistics surface, not the H356 blend.

**Why it matters:** 
- H409 discovered this +0.077 IC standalone signal
- Very low correlations (0.012 vs S1, 0.052 vs C16) confirm it's ORTHOGONAL
- Can work as C16 alternative or add-on with additive (H410 showed additive improves S1)

**Source:** Session 290, F373, F374, F377.

---

### C17+S1 Additive — Best Candidate Ranker (H413-H419)
**Status: VERIFIED STANDARD — proven REAL, all tests passed**

- **Combined IC vs 1d barrier:** `+0.135` (vs S1 +0.118 = **+14% boost**)
- **Combined IC vs 10d barrier:** `+0.138` (vs S1 +0.119 = **+16% boost**)
- **Combined IC vs 20d barrier:** `+0.138` (vs S1 +0.119 = **+16% boost**)
- **Hold-out 2025 IC:** `+0.123` (proves NOT survivor bias)
- **Consistency:** `8 / 8` years positive on all horizons
- **Formula:** `0.10 × Volume_rank + 0.90 × S1_xs_proba`

**Verified properties:**
- H417 hold-out 2025: +0.014 lift = same as long-term (+0.017) → PROVES REAL
- H414: generalizes to ALL horizons (1d, 10d, 20d)
- H416: ROBUST in BOTH market states (VNI up +0.016, down +0.018)
- All weak signals fail to add: C16, Foreign, Insider

**What it captures:** 
- Best simple additive combination confirmed by 7 experiments (H410-H419)
- Weight insensitive (10-15% range optimal)
- Cross-products consistently FAIL, additive consistently WORKS

**Why it matters:**
- FIRST verified candidate ranker (hold-out proof)
- Works in ALL market conditions
- Adding more signals DOESN'T help (C16, Foreign, Insider all weak)

**Source:** Sessions 291-300, F374-F381, D023-D024.

---

### C18 — C16 Rank Delta (H431)
**Status: NEW SIGNAL — PASSED walk-forward validation**

- **Standalone IC:** +0.1290 (vs C16 level +0.0752 = **+72% boost**)
- **Lift vs baseline:** +0.0114 (8/8 positive years)
- **Validation (2023-2025):** Q5_incr +0.1310 vs level +0.0633

**What it captures:**
- C16 rank CHANGE (delta) captures flow acceleration, a different feature class from level
- Q5_incr (increasing rank) is the best bucket
- Both extremes beat the middle - flow momentum that level misses

**Formula:** `c16_rank_delta = c16_rank_today - c16_rank_yesterday`

**Why it matters:**
- NEW SIGNAL adds +0.0114 IC lift over baseline
- Use as a conditioner or additive component with Vol+S1
- Independent of C16 level (captures different information)

**Source:** Session 310, F384.

---

### C19 — Vol Expansion + Low Return Low Volume Combo (H448)
**Status: NEW SIGNAL — PASSED walk-forward validation**

- **Standalone IC:** +0.2069 (vs baseline +0.1298 = **+59% boost**)
- **Lift vs vol_expansion alone:** +0.0316 (11/11 positive years)
- **Lift vs low_return_low_vol alone:** +0.0025

**What it captures:**
- vol_expansion (5d vol change top 20%) × low_return_low_vol (return rank bottom 30% × volume rank bottom 30%)
- Captures the oversold-in-expanding-vol regime better than either component alone
- Both components are positive, COMBO adds incremental lift

**Formula:** `vol_expansion AND low_return_low_vol`

**Why it matters:**
- NEW SIGNAL - adds +0.0316 IC vs vol_expansion alone
- Use as conditioner: captures regime-specific contrarian edge

**Source:** Session 104, F393.

---

### C20 — Buy-Heavy Imbalance In Vol Expansion (H451)
**Status: NEW SIGNAL — PASSED walk-forward validation**

- **Standalone IC:** +0.1809 (vs baseline +0.1301 = **+39% boost**)
- **Lift vs vol_expansion alone:** +0.0053
- **Expansion vs Contraction (buy):** +0.0699 (11/11 positive years)

**What it captures:**
- buy_sell_volume_imbalance (top 20% = buy-heavy) × vol_expansion (top 20% 5d vol change)
- Buy-heavy imbalance works ONLY in vol expansion periods
- Sell-heavy is always negative - no regime benefit

**Formula:** `buy_heavy_imbalance AND vol_expansion`

**Why it matters:**
- NEW SIGNAL - regime-dependent imbalance is real
- Use as conditioner: buy-heavy only in vol expansion periods
- Source anchor for signal library promotion

**Source:** Session 107, F394.

---

### C21 — Level + Momentum + Vol Expansion Combos (H453)
**Status: NEW SIGNALS — PASSED walk-forward validation**

- **buy_heavy_accel_expansion IC:** +0.2320 (vs baseline +0.1301 = **+78% boost**)
- **sell_heavy_decel_expansion IC:** +0.2369 (vs baseline +0.1301 = **+82% boost**)
- **Lift vs H451 level-only:** +0.0201-0.0260 incremental IC
- **Consistency:** 11/11 positive years (both combos)

**What it captures:**
- `buy_heavy_accel_expansion`: buy-heavy imbalance LEVEL + ACCELERATING imbalance + vol_expansion
- `sell_heavy_decel_expansion`: sell-heavy imbalance LEVEL + DECELERATING imbalance + vol_expansion
- Two distinct mechanisms:
  - Buy-heavy acceleration in expansion = hidden demand building
  - Sell-heavy deceleration in expansion = exhaustion/reversal

**Formula:**
- `buy_heavy_accel_expansion`: imbalance_rank ≥ 0.8 AND imbalance_delta_rank ≥ 0.8 AND vol_change_rank ≥ 0.8
- `sell_heavy_decel_expansion`: imbalance_rank ≤ 0.2 AND imbalance_delta_rank ≤ 0.2 AND vol_change_rank ≥ 0.8

**Independent components:**
- `imbalance_accelerating` alone: IC +0.1601, +0.0300 lift (11/11 pos years)
- `imbalance_decelerating` alone: IC +0.1503, +0.0202 lift (11/11 pos years)
- `accel_expansion` (delta × vol): IC +0.2126, +0.0825 lift

**Why it matters:**
- NEW SIGNALS - level + momentum + regime combos beat level-only by +0.02-0.03 IC
- Imbalance momentum (delta) is an independent information dimension beyond level
- Both acceleration AND deceleration in vol expansion are positive signals (different mechanisms)
- Stable imbalance (no change) underperforms - change IS the signal

**Source:** Session 109, F391.

---

### C22 — Limit Proximity Momentum (H454)
**Status: NEW SIGNAL — PASSED walk-forward validation**

- **Standalone IC:** +0.2166 (vs baseline +0.1298 = **+67% boost**)
- **Lift vs vol_expansion alone:** +0.0415
- **Consistency:** 11/11 positive years

**What it captures:**
- Stocks APPROACHING the daily +7% price limit (+5% to +7%)
- Strong upward momentum toward the limit queue
- NOT vol-dependent: vol expansion adds only +0.0004 incremental IC

**Formula:** `pct_change >= 5.0 AND pct_change < 7.0`

**Why it matters:**
- NEW SIGNAL - regime-independent momentum signal
- Near-ceiling momentum is stronger than vol regime effects
- High volume WITH near-limit is WEAKER (0.1375 vs 0.2166) - queue pressure thesis fails
- Use as standalone ranker, NOT volume-augmented

**Source:** Session 110, F392.

---

### C23 — Amihud Illiquidity × Vol Expansion Combo (H463)
**Status: NEW SIGNAL — PASSED walk-forward validation**

- **Standalone IC:** +0.2029 (vs baseline +0.1298 = **+56% boost**)
- **Combo IC:** +0.2616 (vs baseline = **+101% boost**)
- **Lift vs vol_expansion alone:** +0.0862
- **Consistency:** 11/11 positive years

**What it captures:**
- amihud_20d_avg (computed inline from OHLCV: |return| / turnover_billions_VND, 20d rolling avg)
- rank in top 20% illiquidity (high_illiq) × vol_expansion (top 20% 5d vol change)
- Illiquid stocks (under-followed) amplify regime effects dramatically

**Formula:** `amihud_20d_avg_rank >= 0.80 AND vol_change_rank >= 0.80`

**Independent components:**
- high_illiq alone: IC +0.2029, +0.0731 lift
- vol_expansion alone: IC +0.1753 (from H460)
- high_illiq_expansion: IC +0.2616, +0.1318 lift

**Cross-checks:**
- beats C21 sell_heavy_decel (0.2393) by +0.0223
- beats C20 buy_heavy_expansion (0.2105) by +0.0511
- beats C22 approaching_ceiling (0.2170) by +0.0446
- high_illiq_buy_expansion (0.2396) < high_illiq_expansion (0.2616) — imbalance redundant with illiq

**Why it matters:**
- C23 is now the STRONGEST standalone signal in the library
- regime-independent: vol_contraction also boosts illiq (0.1790 vs 0.0652)
- OHLCV-based inline computation works; no pre-built feature needed
- Mechanism: under-followed illiquid stocks respond more to market regime signals

**Source:** Session 116, F393.

---

### C24 — Multi-Day Price Limit Ceiling Pressure (H467)
**Status: NEW SIGNAL — PASSED walk-forward validation**

- **Standalone IC:** +0.2353 (vs baseline +0.1302 = **+81% boost**)
- **Lift vs baseline:** +0.1052
- **Consistency:** 8/8 positive years

**What it captures:**
- stocks hitting the +7% price limit 2+ times in last 3 days (multi-day ceiling count)
- sustained queue pressure at daily ceiling creates next-day release
- multi-day beats single-day by +0.0191 IC (C22 single-day near_limit: 0.2162)

**Formula:** `ceiling_count_3d >= 2 AND vol_expansion`

**Independent components:**
- limit_2_of_3 alone: IC +0.2353, +0.1052 lift
- near_limit (C22) alone: IC +0.2162
- ceiling_exhaustion: IC +0.2119 (+0.0818)

**Why it matters:**
- multi-day sustained pressure is stronger than single-day
- C24 beats C22 single-day by +0.0191 IC
- mechanism: queue buildup → next-day release; works in vol_expansion regime
- independent of vol_expansion regime (works even when vol_expansion is low)

**Source:** Session 117, F396.

---

### C25 — VWAP Deviation Below Average + Vol Expansion (H470)
**Status: NEW SIGNAL — PASSED walk-forward validation**

- **Standalone IC:** +0.1733 (vs baseline +0.1302 = **+33% boost**)
- **Lift vs baseline:** +0.0431
- **Consistency:** 11/11 positive years

**What it captures:**
- stocks trading far below daily VWAP (bottom 10% of daily VWAP deviation) in vol expansion regime
- VWAP below = "cheap" vs day's average transaction price
- under-followed/illiquid stocks amplify this effect (similar to C23 mechanism)

**Formula:** `vwap_deviation_rank <= 0.10 AND vol_expansion_q80`

**Independent components:**
- vwap_below_10_exp: IC +0.1733, +0.0431 lift
- vwap_below_20_exp: IC +0.1668, +0.0366
- vwap_dev_bot10 (no regime): IC +0.1610, +0.0308

**Why it matters:**
- C25 captures a different dimension of "under-followed" than C23
- C23: illiquidity (turnover-based)
- C25: VWAP deviation (price-based)
- Both amplify in vol expansion regime

**Source:** Session 119, F399.

---

### C26 — Buy-Heavy Order Flow + Illiquidity + Vol Expansion (H471)
**Status: NEW SIGNAL — PASSED walk-forward validation**

- **Standalone IC:** +0.1889 (vs baseline +0.1302 = **+45% boost**)
- **Lift vs baseline:** +0.0587
- **Consistency:** 11/11 positive years

**What it captures:**
- buy-heavy order flow imbalance (buy volume > sell volume by 5%+) in illiquid stocks during vol expansion
- institutional hidden demand accumulates in illiquid names during volatile markets
- both buy_heavy and sell_heavy work with illiq+expansion (different mechanisms: buy = accumulation, sell = forced-sell rebound)

**Formula:** `buy_heavy (imbalance > 0.05) AND illiq_rank >= 0.70 AND vol_expansion_q80`

**Independent components:**
- buy_heavy_illiq_exp: IC +0.1889, +0.0587 lift
- sell_heavy_illiq_exp: IC +0.1828, +0.0526
- buy_heavy_exp (no illiq): IC +0.1680, +0.0378

**Why it matters:**
- D041 found signals share vol_expansion as universal amplifier
- C26 confirms: buy_heavy WITH illiq+expansion is stronger than buy_heavy alone
- institutional hidden demand in illiquid volatile markets is real edge
- Do NOT combine C23/C24/C25/C26 as composite — each captures different regime facet

**Source:** Session 119, F399.

---

### C27 — Implementation Pain as Positive Signal (H574)
**Status: NEW SIGNAL — PASSED walk-forward validation**

- **Standalone IC:** +0.1477 (vs liquid +0.1266 = **+17% boost**)
- **Lift vs baseline:** +0.0211
- **Consistency:** 10/10 positive years

**What it captures:**
- stocks that are blocked from buying OR selling (cannot execute at next open)
- implementation difficulty = hidden demand = alpha
- inverts the traditional tradability veto

**Formula:** `NOT can_buy_next_open OR NOT can_sell_next_open`

**Independent components:**
- blocked_either: IC +0.1477, +0.0211 lift
- blocked_sell: IC +0.1293, +0.0027 lift
- blocked_buy: IC +0.1062 (weak)

**Why it matters:**
- First finding that IMPLEMENTATION DIFFICULTY is POSITIVE, not a veto
- Hard-to-trade stocks capture hidden demand that others can't easily access
- Different mechanism from all existing signals (illiquidity/regime based)
- Do NOT combine with other filters - pain signal is standalone

**Source:** Session 368, F438.

---

### C16-Triple — CafeF Order Pressure + Triple Storm Conditions (S229)
**Status: DISCOVERED — candidate for publication**

- **Standalone IC vs 1d barrier:** `+0.158` (vs baseline +0.078 = **+104% boost**)
- **Walk-Forward IC:** `+0.145`, **9/9 years positive** (X231)
- **Holdout IC (2023-2025):** `+0.134` (+111% vs baseline)
- **Conditions:** liquid (>80% move) + market=down + divergence (price vs C16 direction disagree)

**What it captures:** Same as C16, but with Triple Storm filters applied:
- Liquid: 20-day rolling C16 std > 80th percentile
- Down market: daily win rate < 50% (contrarian regime)
- Divergence: yesterday return direction != C16 direction

**Mechanism:** Triple Storm is a universal signal amplifier that works on
anomaly/microstructure signals (C16, volume, reversal, skewness) but NOT
on position signals (foreign, sector).

**Reusable script:** `analysis/x232_triple_test.py`

**Source:** Sessions 229, 230, 231, 232.

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

See `notes/findings-00061-00090.md` (F67) for full analysis.

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

### C1b — PhoBERT Whole-Article Sentiment Family
**Status: CANDIDATE IMPLEMENTATION LANE — H364 combined local-news transform passed standalone gate; consumer integration pending**

- **Current implementation state:** full historical backfill completed on the
  tagged CafeF archive:
  - `342,135` unique tagged articles in
    `data/features/news/datasets/phobert_input_articles.parquet`
  - `660,255` article-ticker sentiment rows in
    `data/features/news/datasets/phobert_article_sentiment.parquet`
  - `1,436,996` dense ticker-day rows in
    `data/features/news/datasets/phobert_ticker_day_sentiment.parquet`
  - article label mix:
    - `POS 51.2%`
    - `NEU 27.8%`
    - `NEG 21.0%`
  - mean article confidence:
    - `0.817`
- **Role:** local whole-article Vietnamese sentiment family that should
  be richer than keyword lexicon scoring but still narrower than the full LLM
  semantic/event schema
- **Outputs:** additive `phobert_*` article probabilities, ticker-day
  aggregates, and rolling sentiment states under the canonical
  `data/features/news/` pipeline
- **Current alpha evidence:** H342 did not promote pooled PhoBERT sentiment as
  a standalone alpha signal. The best PhoBERT row,
  `phobert_sentiment_score_sum`, reached avg IC `+0.0082` over `2016-2025`
  and failed the gate, while sparse keyword `sentiment_cs_z` remained stronger
  but narrow. Treat PhoBERT sentiment as an implementation surface to combine
  with scope/source/forward-looking/event context, not as a solved standalone
  signal.
- **Conditioning update:** H343 found one useful BERT-only conditioned row,
  `h343_sentiment_x_official`, with avg IC `+0.0125`, `9 / 10` positive years,
  and S1 corr `-0.0498`. H344 fixed that winner and applied the stricter
  dev / validation / confirmation split: dev `+0.0143`, validation `+0.0146`,
  but 2025 confirmation `-0.0042`. This is offline evidence for source-gated
  sentiment, not a standalone promoted signal.
- **Ollama residual update:** H364 ran after the guarded Ollama event-family
  residual backfill completed and passed the combined local-news standalone
  audit. Best fixed feature:
  `h364_official_sentiment_x_earnings_guidance`, which multiplies sentiment,
  official/regulatory source probability, and Ollama earnings/guidance
  event-family agreement. It reached avg IC `+0.01766`, dev / validation /
  confirmation IC `+0.0173 / +0.0200 / +0.0156`, `10 / 10` positive years,
  S1 corr `-0.0104`, and `13.329%` coverage. Treat it as candidate local-news
  evidence pending one fixed portfolio/consumer integration audit, not a live
  branch change.
- **Consumer update:** H382 tested that fixed feature inside the entry-alpha
  candidate pool with TRUE walk-forward validation and random candidate-policy
  benchmarks. It passed only as a same-support active-news ranker: mean lift
  versus random-active `+0.00092`, `4 / 5` years above random-active mean, and
  2025 lift `+0.00296`. It failed broad random-all allocation with mean lift
  `-0.00367` and only `1 / 5` years above random-all mean. Do not promote H364
  as a broad portfolio allocator.
- **Flow/text interaction update:** H383 tested local-news states against C16
  order pressure with a primary 1d relative-return target. It passed as
  confirmation rather than disagreement: `active_news_strong_flow` reached WF
  relative IC `+0.10293`, `8 / 8` positive years, 2025 IC `+0.12163`, and lift
  `+0.04005` versus strong-flow; `positive_news_strong_flow` reached
  `+0.10854`. No-news and weak-flow disagreement states did not beat their
  baselines. H384 then failed the fixed consumer audit: both active/positive
  strong-flow states underperformed random same-support and random-all policy
  means. Treat H383 as offline interaction context, not a broad allocator.
- **Official-delay update:** H385 tested official/regulatory and
  forward-looking local-news rows with C16 or positive-insider support on 1d
  and 5d excess-return payoffs. It passed as delayed offline evidence:
  `official_supported` had 5d lift `+0.007408` versus unsupported official
  rows, and `official_forward_supported` had 5d lift `+0.007657` versus
  unsupported official/forward rows; both had `8 / 8` positive 5d-lift years.
  H386 then failed the fixed candidate-pool consumer audit: both states
  underperformed random same-support and random-all policy means. Treat H385
  as support-confirmed official-attention context, not a broad allocator.
- **Horizon-router update:** H397 retested the fixed H383/H385 states on
  buyable rows only, with `1d/2d/5d` future relative-return horizons and 15 bps
  per-row cost. It confirmed that active/positive-news strong-flow is a 1d C16
  ranker (`+0.02257` / `+0.02536` IC lift versus strong-flow), while official
  and official-forward supported attention are 5d payoff states (`+0.00650` /
  `+0.00662` net lift, `8 / 8` positive years). This does not override
  H384/H386's broad allocator failures; it says the states have narrower
  natural jobs.
- **Source-triangle update:** H392 tested a stricter C16+insider+local-news
  triangle. The required `c16_insider_any_news` core failed controls: mean 5d
  lift was `-0.007315` versus C16+insider-without-news and `-0.005205` versus
  C16+news-without-insider. Broader `three_plus_sensors` beat exactly-two
  sensors by `+0.005156`, but this is a non-insider news-triangle clue, not a
  C16+insider promotion. Source anchors: `F353`, `D010`.
- **Why this is different from H98:** the PhoBERT lane is local, GPU-friendly,
  and sentiment-focused; it does **not** claim to replace `event_type`,
  `rumor`, `source_authority`, `causal_impact_label`, or the rest of the
  hosted LLM schema
- **Promotion rule:** keep H364/H383/H385/H392 as offline local-news context and
  event-subset interaction/ranking or delay evidence. Do not promote these into
  a live or broad consumer-facing matrix contract without a materially stronger
  consumer audit.

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
| CafeF foreign-flow standalone paths (H327/H328/H333/H345) | best raw room-scarcity dev/validation IC +0.0117/+0.0074 but 2025 IC −0.0048; best residual loosen rank −0.0044/−0.0109/+0.0132; best accumulation change-point dev/validation IC only +0.0020/+0.0024 | Source acquired, but raw, conditioned, room-residual, and accumulation / ownership-change paths fail as standalone signals |
| Proprietary-flow conflict/agreement pilot (H348) | best proprietary buy-share row dev/validation/confirmation IC +0.0144/−0.0216/−0.0110 | Limited 2022+ CafeF proprietary-trading source is usable, but raw ranks and foreign/proprietary agreement-conflict states are unstable on the current next-day target |
| Sector ownership pressure (H351) | best sector participation row dev/validation/confirmation IC −0.0007/−0.0051/+0.0015 | Sector-level foreign pressure, participation, room/ownership, and sector-heat interactions fail; low sector-anchor correlation means this is not merely C6/breadth redundancy |
| Event-v2 / guarded-Ollama payoff and sparse-clock states (H352/H361/H389) | H352 best state q90 lift +0.0196/+0.0174 but q10 worsened; H361 fixed sparse-clock portfolio bonus validation/confirmation relative-return deltas −4.96%/−2.66%; H389 best guarded-Ollama `event_first20` lift only +0.00099 vs generic event and +0.00114 vs repeat event | Event timing remains offline evidence only; the event-v2 sparse-clock and guarded-Ollama first/repeat/transition reopening routes failed, so do not tune more event overlays under the current contract |
| Dividend-clock payoff / sparse-clock states (H354/H362) | H354 best `pre_ex_20d` mean lift +0.0007/+0.0002; H362 fixed sparse-clock portfolio bonus validation/confirmation relative-return deltas ~0.00%/+0.96% but failed the portfolio gate | Small pre-ex payoff hint remains offline calendar evidence only; do not tune more dividend windows or sparse-clock overlays under the current target |
| Legal public-holiday payoff / sparse-clock states (H363) | Best `all_holidays__post_5` top-book lift +0.00405/+0.01579 passed the payoff audit, but the fixed `+0.015` sparse portfolio bonus had validation/confirmation relative-return deltas `0.00%`/`0.00%` and failed the portfolio gate | Legal-holiday timing remains offline evidence only; do not tune more pre/post offsets, closure-length gates, bonus sizes, or veto variants under the current selector |
| Order-pressure smart-exit state (H355) | best two-phase utility delta vs H337 refit only about +0.00065/+0.00053 | CafeF order pressure is useful post-entry state evidence, but it does not solve H337/H339 smart-exit learning; do not integrate exit features or tune more linear step-hazard feature sets |
| Earnings quality 52 tickers (H109) | best IC +0.005 (roe_delta) | Insufficient universe; re-test at 394 tickers pending |
| VN30 rebalancing proximity (H114) | xs_vn30_rank_change_5d IC +0.0075 (10/11) | Rank level anti-predictive; change directionally consistent but below 0.01 gate |
| 52-week high proximity (H118) | xs_52w_high_prox IC +0.0065 (9/11) | Directionally correct but below the weak-candidate IC gate |
| Low volatility anomaly (H119) | xs_low_vol_20d IC −0.011 (1/11) | Anti-predictive: Vietnam is HIGH-beta market (opposite of global anomaly) |
| Intraday reversal (H120) | xs_intraday_reversal IC +0.041 | IC strong but corr with C4 (oc_asym_5d) = +0.394 — captured by C4 already |
| Illiquidity spike/change (H121 sub-features) | xs_illiq_spike_rank IC −0.001; xs_illiq_change_5d IC −0.003 | Only structural level (20d avg) is predictive; intraday shocks and trend changes are noise |
| Bid-ask spread proxy (H122) | xs_spread_level_rank IC −0.0097; xs_spread_spike_rank IC −0.0301; xs_spread_change_5d IC −0.0035 | Corwin-Schultz H/L spread estimate is anti-predictive / noisy in this market |
| Earnings quality 394 tickers (H113) | best IC +0.006 (eps_yoy_rank); all others < 0.005 | Daily time-series application of quarterly data too coarse; all five features fail the weak-candidate IC gate at full universe |
| Beta regime (H124) | `xs_low_beta_60d` passes standalone IC +0.013, but corr with C10 = +0.552 | Low-beta names are not orthogonal; beta collapses onto the illiquidity axis |
| Beta residual (H125) | `xs_low_beta_resid_60d` IC +0.0019, 6/11 years | Once beta is residualized vs illiquidity/volume, the signal disappears |
| Close-location persistence (H127) | `xs_clv_volconf_5d_rank` IC +0.0149, but corr with C8 = +0.903 | Strong standalone, but it is effectively the same axis as abnormal volume activity |
| Compression breakout continuation (H128) | best IC −0.035 (xs_compress_breakout_2) | Breakout-follow-through thesis is wrong in this market; the tested orientation is strongly anti-predictive |
| Gap-failure exhaustion (H283 / old H135 queue item) | best variant `xs_gap_failure_exhaustion_3` is predictive but maps back to C13 | Real construction, but not a new independent axis under the tested contract |
| Sector-conditioned blow-off reversal (H284 / old H136 queue item) | fixed sector / ceiling gates do not improve H133 | Parked; C13 remains the cleaner compression blow-off representation |
| Sector breadth shock (H131) | best IC −0.003 (xs_breadth_shock_laggard) | Breadth changes add no standalone value beyond existing sector structures |
| Conditional liquidity / tradability release (H132/H391) | H132 best IC +0.007; H391 `top5_release` / `top10_release` matched lifts `-0.03367` / `-0.02837` with negative 2025 lifts | Illiquidity-change and entry-panel blocked-buy release states do not clear; do not use `wait_release` as a buy boost under the current contract |
| Longer-horizon continuation (H126) | 90d/120d ranks IC +0.011 but corr with C11 = +0.775 / +0.664 | Real signal, but it is just a longer-horizon restatement of the existing continuation axis |
| Residual long-horizon reversal (H346 / old H137 queue item) | best residual continuation control IC +0.0072; 90d/120d residual reversal IC −0.0063/−0.0072 | After removing C11, the residual is too weak and the hypothesized reversal sign is wrong |

---

## 🔲 Not Yet Tested

| Signal | Hypothesis | Data available | Priority |
|--------|-----------|----------------|---------|
| H98: LLM news sentiment | Higher quality than keyword approach | **PARKED** (runtime/throughput bottleneck) | Parked |
| H95 follow-up: new data or target only | Standalone flow paths failed through H345; H347 foreign-insider agreement lost to H340; H348 proprietary-flow agreement/conflict failed; H351 sector ownership pressure failed | CafeF foreign-flow and proprietary-trading sources exist, but no current-data flow feature remains untested under this target | Parked |
| Order book imbalance | Bid/ask pressure predicts short-term price | Not available historically | Blocked |

### S244 New Signals (2026-05-03)

| Signal | IC | vs Random | Status | Use |
|--------|-----|---------|--------|------|
| insider_buy_lead | 0.1050 | +0.11 | REAL after S272 audit | C16 support context |
| consecutive_down_days | target-derived | n/a | INVALID from S244/S253 record | do not use |
| dividend_30d | 0.0526-0.0557 | +0.05 | weak after corrected window audit | context only |
| rank_time_acceleration | 0.0548 | +0.05 | weak, below C16 | context only |

S272 audit update:
- `actual` in `xs_barrier_vol_1d_hose_full.parquet` is a future binary barrier
  label. The old `consecutive_down` and target-derived market-down states used
  same-date `actual` as a regime input and are invalid as promotions.
- `insider_buy_lead` survives when mapped to the next trading day after the
  disclosure date; H398 reproduced this event-time lead and found reaction
  confirmation stronger than quiet pre-reaction. Source anchors: `F355`,
  `F362`, `D012`, `D014`.

### Calendar Signals (S242, S243)

| Signal | IC | vs Random | Status | Use |
|--------|-----|---------|--------|------|
| monday_jan_combo | 0.1054 | sparse | context / H390 PARKED | only 11 dates in S272; exact-state promotion parked |
| february_mid | 0.0858 | +0.09 | REAL | calendar |
| march_late | 0.0744 | baseline-like after S272 | context |
| monday | 0.0836 | +0.08 | REAL | calendar |
| october | 0.0738 | baseline-like after S272 | context |
| january_first_10 | 0.0823 / 0.0744 | mixed | day-of-year version modest; true first-10-trading-days baseline-like |

H390 mechanism update:
- Exact `monday_jan_combo` retained 1d residual C16-IC lift `+0.02745` after
  liquidity, breadth, news-volume, buyability, C16, and down-market controls,
  but it had only one active date per evaluated year, only `2 / 4` positive
  1d residual-lift years, and negative mean 5d residual lift (`-0.04055`).
  Do not promote it as an independent overlay under the current target.
- Diagnostic `january_first_10` was cleaner after residualization
  (`+0.03067` 1d residual lift, `5 / 5` positive years), but it was not a
  predeclared primary H390 state. Reopen only with a fixed broader
  January/weekday contract. Source anchors: `F351`, `D008`.

H400 quorum update:
- Do not add dense calendar residues as a fixed H395 weak vote. The
  non-calendar quorum retained avg IC `+0.05826`, but the calendar-added quorum
  fell to `+0.05605` and calendar lift was `-0.00221` with `0 / 7` positive
  lift years. Calendar-only IC was `-0.00827`. Source anchors: `F364`, `D016`.

### Market State Filters (S237, S238)

| Signal | IC | vs Random | Status | Use |
|--------|-----|---------|--------|------|
| vol_high | 0.0844 | +0.08 | modest / S272 survivor | volume context |
| tet | 0.097 | +0.10 | REAL | holiday filter |
| quarter_start | 0.098 | +0.10 | timing / H390 PARKED | raw timing filter; exact-state promotion parked |
| market_breadth A/D Q1 | 0.093 | +0.09 | breadth filter |

**Source:** [session_00244_log.md](./session_00244_log.md), [session_00243_log.md](./session_00243_log.md), [session_00242_log.md](./session_00242_log.md)

H123, H124, H125, H126, H127, H128, H130, H131, H132, H133, H134, H283, H284, and H346 are now closed and documented above.
Track new OHLCV-only search ideas in `notes/live_state.md`.

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

**Session 399 update (2026-05-18):**
- H614 persistence-decay boundary passes for the multi-signal branch:
  `composite_2plus_accum_20_30 IC=0.2542` vs
  `composite_2plus_accum_31plus IC=0.2407` (lift `+0.0135`, 11/11 positive
  years for both). Interpretation: accumulation is useful but bounded; the
  strongest persistence pocket is `20-30` accumulated active days (rolling 60d
  context), not unbounded accumulation.

**Session 404 update (2026-05-18):**
- H618 confirms timing-distribution structure inside multi-signal states:
  same-day multi-signal concentration (`signal_count >= 2`) is materially
  stronger than spread-across-days accumulation (`signal_count == 1` today with
  rolling 3d sum >= 2): `0.2445` vs `0.1821` (lift `+0.0624`, both `11/11`
  positive years). Prefer same-day concentration as the multi-signal regime
  state.

**Session 414 update (2026-05-18):**
- H628 confirms a concentration edge inside low-breadth multi-signal states:
  concentrated low-breadth (`conc_low`) beats distributed low-breadth
  (`dist_low`) by `+0.0209` IC (`0.2523` vs `0.2315`).
- Use concentration as a positive conditioner within low-breadth
  `composite_2plus` states under this contract.

---

## Notes on Evaluation

**Do not evaluate signals by whether they beat H54 (+25.52% edge).**
H54 is a complete portfolio strategy, not a comparison bar for individual signals.

**Correct evaluation for RL signal library:**

| Criterion | Threshold | Rationale |
|-----------|-----------|-----------|
| Strong standalone signal | IC > 0.05 | Real enough for signal-library promotion if all other gates pass |
| Weak candidate signal | 0.01 < IC <= 0.05 | Useful evidence, not a strong promotion by itself |
| Correlation with existing library | < 0.30 | Independent = adds RL state diversity |
| IC positive years | >= 60% | Consistency, not just noise |
| p-value / uncertainty | credible for sample size | Sparse states need stronger caveats and controls |
| Decision-time validity | observable pre-execution | No target-derived or future-derived states |

For filters, buckets, and rewrites of a parent signal, evaluate incremental
lift versus that parent and mechanism-matched controls. Example: a C16 subset
with IC `+0.07` is real market edge, but it is not a new signal if raw C16 is
already `+0.07` and the subset adds little lift.

**Why XGBoost "failure" ≠ RL failure:**
XGBoost cannot use sparse features effectively. A signal that adds 0 IC to the combined
supervised model may still be independently learnable by an RL agent that observes all
signals separately and learns to weight them contextually.
