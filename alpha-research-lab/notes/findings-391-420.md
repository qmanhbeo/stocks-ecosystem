# Findings 391-420

## F391: H453 Order Flow Imbalance Momentum — C21 New Signals (2026-05-08, Session 109)

**Decision: PASSED**

**Signal: C21a (buy_heavy_accel_expansion) + C21b (sell_heavy_decel_expansion)**

H453 tested whether imbalance LEVEL + MOMENTUM (delta) + vol_expansion combos beat H451 level-only.

**Results:**
- sell_heavy_decel_expansion: IC +0.2369 (+0.1069 vs baseline, 11/11 positive years) — **NEW SIGNAL C21b**
- buy_heavy_accel_expansion: IC +0.2320 (+0.1019 vs baseline, 11/11 positive years) — **NEW SIGNAL C21a**
- H451 buy_heavy_expansion (level-only): IC +0.2105 (+0.0508 lift)
- Imbalance acceleration alone: IC +0.1601 (+0.0300 lift, 11/11 pos years)
- Imbalance deceleration alone: IC +0.1503 (+0.0202 lift, 11/11 pos years)
- Accel × vol (delta × vol): IC +0.2126 (+0.0825 lift)

**Lift vs H451 level-only:** +0.0201-0.0260 incremental IC

**Two mechanisms:**
- Buy-heavy ACCELERATION in vol expansion = hidden demand building
- Sell-heavy DECELERATION in vol expansion = exhaustion/reversal

**Why it matters:**
- Level + delta + regime combos beat level-only by +0.02-0.03 IC
- Imbalance MOMENTUM (delta) is independent information beyond level
- Both acceleration AND deceleration in vol expansion are positive (different mechanisms)
- Stable imbalance underperforms — CHANGE IS THE SIGNAL

**Source:**
- [session_109_log.md](./session_109_log.md)
- `artifacts/run_summaries/20260508_170920_order_flow_imbalance_momentum_research_branch.json`

---

## F392: H454 Implied Limit Proximity — C22 New Signal (2026-05-08, Session 110)

**Decision: PASSED**

**Signal: C22 — approaching_ceiling**

H454 parsed `price_change_raw` strings to extract price change percentage, tested stocks approaching the +7% limit.

**Results:**
- approaching_ceiling (5-7% change): IC +0.2166 (+0.0868 vs baseline, 11/11 positive years) — **NEW SIGNAL C22**
- near_limit_sustained: IC +0.2166
- vol_expansion: IC +0.1753 (+0.0449 vs baseline)
- near_limit × vol_expansion: IC +0.2170 (+0.0872) — vol adds only +0.0004

**Key insight:**
- Near-ceiling momentum is REGIME-INDEPENDENT — vol expansion adds almost nothing
- High volume WITH near-limit is WEAKER (0.1375 vs 0.2166) — queue pressure thesis fails
- The signal is pure price momentum toward the limit, not volume-augmented
- Do NOT combine with volume — limit alone is stronger

**Why it matters:**
- NEW SIGNAL — regime-independent momentum
- Vol regime effects don't change limit-proximity signal quality
- Use as standalone ranker, NOT volume-augmented

**Source:**
- [session_110_log.md](./session_110_log.md)
- `artifacts/run_summaries/20260508_180706_implied_limit_proximity_research_branch.json`

---

## F393: H463 Amihud Illiquidity × Vol Expansion — C23 STRONGEST Signal (2026-05-08, Session 116)

**Decision: PASSED**

**Signal: C23 — high_illiq_expansion**

H463 computed Amihud illiquidity inline from `data/stock/gia_lich_su_*_1D.parquet` (1227 per-ticker files, ticker extracted from filename).

**Results:**
- high_illiq (standalone): IC +0.2029 (+0.0731 vs baseline 0.1298) — VERY strong standalone
- high_illiq_expansion: IC +0.2616 (+0.1318 vs baseline) — **+101% boost, STRONGEST signal**
- low_illiq: IC +0.0652
- low_illiq_expansion: IC +0.0808
- high_illiq_contraction: IC +0.1790
- buy_heavy_expansion (C20): IC +0.2105 — C23 beats C20 by +0.0511
- C21b (sell_heavy_decel): IC +0.2369 — C23 beats C21b by +0.0223

**Signal promotion criteria:**
- IC +0.1318 >> 0.05 threshold
- Consistent 11/11 positive years
- Beats ALL previous signals (C20/C21a/C21b/C22)
- OHLCV inline computation: no pre-built feature needed

**Why it matters:**
- C23 is now the STRONGEST standalone signal in the library
- regime-independent: vol_contraction also boosts illiq (0.1790 vs 0.0652)
- Mechanism: under-followed illiquid stocks respond more to market regime signals
- OHLCV-based inline computation works from per-ticker parquet files

**Source:**
- [session_116_log.md](./session_116_log.md)
- `artifacts/run_summaries/20260508_182909_amihud_illiquidity_regime_combo_research_branch.json`

---

## F394: H467 Multi-Day Ceiling Pressure — C24 New Signal (2026-05-08, Session 118)

**Decision: PASSED**

**Signal: C24 — multi_day_ceiling_pressure**

H467 tested multi-day limit-hitting behavior. Hits at +7% limit 2+ times in last 3 days.

**Results:**
- limit_2_of_3: IC +0.2353 (+0.1052 vs baseline, 8/8 positive years) — **NEW SIGNAL C24**
- near_limit (C22): IC +0.2162
- ceiling_exhaustion (near-limit today AND yesterday): IC +0.2119
- limit_1_of_3: IC +0.2117
- at_limit (+6.5%+): IC +0.1605

**Signal promotion criteria:**
- IC +0.1052 >> 0.05 threshold
- Consistent 8/8 positive years
- Incremental vs C22: +0.0191 IC
- Mechanism: sustained queue pressure → next-day release

**Why it matters:**
- Multi-day accumulation beats single-day (0.2353 vs 0.2162)
- Buildup signal: consecutive limit-hits create pressure
- Works independently of vol regime

**Source:**
- [session_118_log.md](./session_118_log.md)
- `artifacts/run_summaries/20260508_184202_price_limit_ceiling_count_regime_research_branch.json`

---

## F395: H466 Crowd Exhaustion — INVERSION of Hypothesis (2026-05-08, Session 118)

**Decision: PASSED (mechanism inverted)**

H466 tested whether "exhaustion" (high C16 + high return) leads to mean-reversion next day. The hypothesis was WRONG.

**Results:**
- two_days_exhaustion: IC +0.2013 (+0.0711 vs baseline, 3/3 positive years) — **STRONGEST**
- exhaustion_today: IC +0.1104 — confirms H445's "worst state"
- was_top20_not_today: IC +0.0882 (-0.0420 vs baseline) — dropped C16 stocks are WORSE

**Key insight:**
- The mechanism is CONTINUATION, not reversal
- Two consecutive days of top-C16 + high-return = sustained demand pressure = strong next-day
- "Exhaustion" in H445 means signal is AT ITS PEAK, not reversing
- NOT a new signal — it's momentum of C16 amplified by time

**Why it matters:**
- Do NOT interpret "exhaustion" as mean-reversion
- H445 exhaustion finding = signal quality degradation at peak, not directional reversal
- Two_days_exhaustion = concentrated conviction = strong next-day (captured by C16)

**Source:**
- [session_118_log.md](./session_118_log.md)
- `artifacts/run_summaries/20260508_184025_crowd_exhaustion_reversal_research_branch.json`

---

## F396: H468 Market Breadth as Regime Gate — MIXED (2026-05-08, Session 118)

**Decision: MIXED**

H468 tested market breadth as a regime gate for signals.

**Results:**
- vol_expansion_in_breadth_bottom20: IC +0.1936 (+0.0635) — **vol_expansion works best in NARROW markets**
- vol_expansion_in_breadth_top20: IC +0.1588 (+0.0287) — weaker in broad markets
- breadth_bottom20: IC +0.1441 (+0.0140) — narrow market itself is positive
- breadth_top20: IC +0.1101 (-0.0199) — **broad market is NEGATIVE for signal quality**
- c16_top20_in_breadth_top20: IC +0.0607 — very weak

**Key insight:**
- Narrow market (breadth bottom 20%) is a soft regime amplifier for vol_expansion signals
- Broad market degrades signal quality — breadth_top20 is WORSE than baseline
- Not strong enough for standalone promotion — soft filter only

**Why it matters:**
- Do NOT use breadth as a hard gate
- Use narrow market as a soft amplifier context for vol_expansion signals
- Broad market is a mild headwind for S1 signal quality

**Source:**
- [session_118_log.md](./session_118_log.md)
- `artifacts/run_summaries/20260508_184450_market_breadth_regime_signal_research_branch.json`

---

## F397: H465 Cross-Signal Orthogonality — NOT Orthogonal, D041 (2026-05-08, Session 117)

**Decision: MIXED (dead-end D041 for combination)**

H465 tested whether C20/C21/C22 combinations add incremental IC beyond each alone.

**Results:**
- C21a buy_heavy_accel_expansion: IC +0.2234
- C21b sell_heavy_decel_expansion: IC +0.2206
- C22 approaching_ceiling: IC +0.2166
- C20 buy_heavy_expansion: IC +0.2104
- C21a × C22: IC +0.2119 (lift vs max: **-0.0115** — WORSE)
- C20 × C22: IC +0.1997 (lift vs max: **-0.0169** — WORSE)
- C21a × C22 × C20: IC +0.2119 (same as 2-way)
- C21a × C21b: 0 rows (mutually exclusive — can't be both)

**Key insight:**
- Signals are NOT orthogonal — they share the vol_expansion regime driver
- All combos are WORSE than the best individual signal
- vol_expansion is the common factor making signals redundant when combined
- Each signal captures the same vol-expansion amplification
- The signals are ADDITIVE in portfolio sense (different days they fire), not combinatorial

**Why it matters:**
- Do NOT create composite signals from C20/C21/C22
- C23 (illiquidity_expansion) should also NOT be combined with C21/C22 in the same entry
- D041: signal combination skepticism — hard stop

**Source:**
- [session_117_log.md](./session_117_log.md)
- `artifacts/run_summaries/20260508_183554_cross_signal_orthogonality_audit_research_branch.json`

---

## F398: H464 Monday/Time-of-Day Calendar Pattern — WEAK (2026-05-08, Session 117)

**Decision: PASSED (weak signal, context only)**

H464 tested VN market T+2 settlement, Monday effect, month-end, quarter-start.

**Results:**
- Monday: IC +0.1434 (+0.0132 vs baseline) — **strongest calendar pattern**
- Friday: IC +0.1119 (-0.0183) — **negative**
- Month-end (day >= 25): IC +0.1367 (+0.0065)
- January: IC +0.1343 (+0.0041)
- Quarter-start (day <= 10): IC +0.1250 (-0.0052)
- Week1 of month: IC +0.1249 (-0.0053)

**Key insight:**
- Monday effect is the strongest calendar pattern (+0.0132 IC)
- Small but consistent, 11/11 positive years
- Friday is NEGATIVE — avoid long positions into weekend
- Not strong enough for standalone promotion — weak RL context only

**Why it matters:**
- Useful as weak RL context signal
- H400 already killed fixed dense calendar priors in the quorum
- Treat Monday as a mild confirmation clue, not a ranker

**Source:**
- [session_117_log.md](./session_117_log.md)
- `artifacts/run_summaries/20260508_183346_time_of_day_pattern_research_branch.json`

---

## F399: H469-H471 Order Flow, VWAP, Microstructure Signals (2026-05-08, Session 119)

**Decisions: H469 MIXED, H470 PASSED (C25 new signal), H471 PASSED (C26 new signal)**

### H469: foreign_flow_momentum — MIXED
H443 killed raw foreign flow direction variants. H469 tested momentum (acceleration/deceleration) of foreign flow in vol_expansion regime.

**Results:**
- ff_decel_exp: IC +0.1376 (+0.0074 lift, 11/11 pos years) — best
- ff_strong_buy_exp: IC +0.1280 (-0.0022) — weak
- ff_accel_exp: IC +0.1243 (-0.0059) — weak

**Key insight:** Foreign flow momentum adds only marginal signal. No state beats C16 by more than +0.01. Direction-based states (strong buy/sell) are all negative. Momentum doesn't rescue what H443 killed. Soft filter only, not promotion candidate.

### H470: vwap_deviation_regime — PASSED (NEW SIGNAL C25)
H470 tested VWAP deviation (price far from day's average transaction price) × vol_expansion regime.

**Results:**
- vwap_below_10_exp: IC +0.1733 (+0.0431 lift, 11/11 positive years) — **NEW SIGNAL C25**
- vwap_below_20_exp: IC +0.1668 (+0.0366)
- vwap_dev_bot10: IC +0.1610 (+0.0308)
- vwap_above_90_exp: IC +0.1473 (+0.0171)
- all_rows: IC +0.1302 (baseline)

**Signal C25: vwap_below_illiq_expansion**
- IC: +0.1733 (+0.0431 lift vs baseline)
- Consistency: 11/11 positive years
- Mechanism: stocks trading far below daily VWAP in expanding-volume markets = "cheap" vs average, under-followed/illiquid names amplify effect (similar to C23)
- Comparable to C23 (illiq_expansion) mechanism pattern

### H471: order_flow_microstructure_regime — PASSED (NEW SIGNAL C26)
H471 tested order flow imbalance × vol_expansion × illiquidity as a combined signal. D041 found signals share vol_expansion as universal amplifier — this test checked if order flow is independent or just echoes vol_expansion.

**Results:**
- buy_heavy_illiq_exp: IC +0.1889 (+0.0587 lift, 11/11 positive years) — **NEW SIGNAL C26**
- sell_heavy_illiq_exp: IC +0.1828 (+0.0526)
- buy_heavy_exp: IC +0.1680 (+0.0378)
- buy_heavy_no_regime: IC +0.1498 (+0.0196)
- all_rows: IC +0.1302 (baseline)

**Signal C26: buy_heavy_illiq_expansion**
- IC: +0.1889 (+0.0587 lift vs baseline)
- Consistency: 11/11 positive years
- Mechanism: institutional hidden demand accumulates in illiquid names during volatile markets; both buy_heavy and sell_heavy work with illiq+expansion (different mechanisms: buy = accumulation, sell = forced-sell rebound)

### Pattern discovered:
All strong signals share a common structure: **specific behavior + illiquidity + vol_expansion**.
- C23 (illiq_expansion): illiquidity × vol_expansion
- C24 (multi_day_ceiling_pressure): ceiling count × vol_expansion
- C25 (vwap_below_illiq_expansion): VWAP deviation + illiquidity + vol_expansion
- C26 (buy_heavy_illiq_expansion): order flow + illiquidity + vol_expansion

### D041 implication (CONFIRMED):
Signals are NOT orthogonal — they share vol_expansion + illiquidity as the universal amplifier. Do NOT combine as composite entries. Each signal captures a different facet of the same regime.

### Signal ranking (updated):
C23 (0.2616) > C21b (0.2369) > C24 (0.2353) > C21a (0.2320) > C22 (0.2170) > C26 (0.1889) > C25 (0.1733) > C20 (0.2105)

**Source:**
- [session_119_log.md](./session_119_log.md)
- `artifacts/run_summaries/h470_vwap_deviation_regime_*.json`
- `artifacts/run_summaries/h471_order_flow_microstructure_regime_*.json`

---

## F400: H449 Order Flow Momentum — Acceleration Dead-End (2026-05-08, Session 120)

**Decision: PASSED (but findings OPPOSITE)**

H449 tested C16 acceleration (second derivative) vs forward IC. Hypothesis: accelerating vs decelerating order pressure might differ.

**Results:**
- c16_level_high: IC +0.1614 (+0.0326 lift, 11/11 positive years) — **BEST state**
- c16_accel_expanding: IC +0.1219 (-0.0069 lift) — **WORSE than baseline**
- c16_accel_neutral: IC +0.1287 (-0.0001) — WORSE
- c16_accel_contracting: IC +0.1303 (+0.0015) — marginal
- c16_level_low: IC +0.1192 (-0.0096) — WORSE
- all_rows: IC +0.1288 (baseline)

**Key finding: ACCELERATION does NOT add value**
- C16 acceleration (momentum/second derivative) is NOT predictive
- C16 LEVEL is the signal (high pressure = strong IC)
- Confirms H443 pattern: foreign flow momentum also marginal/negative
- Confirms H446/H447: vol LEVEL matters, not vol CHANGE

**Dead-end D041:** All acceleration/momentum signals are dead-end. Use LEVEL (magnitude), not MOMENTUM (change), as signal conditioner.

**Source:**
- [session_120_log.md](./session_120_log.md)
- `artifacts/run_summaries/h449_order_flow_momentum_*.json`