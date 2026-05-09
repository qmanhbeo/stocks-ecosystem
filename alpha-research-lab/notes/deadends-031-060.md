# Dead Ends 031-060

## D035: Semantic Novelty Saturation Hypothesis Fails (2026-05-08, Session 325)

Finding:
- Claim tested: news volume may be harmful when semantic novelty is exhausted,
  while high novelty plus muted price response may be delayed alpha.
- Evidence: `analysis/h445_semantic_novelty_saturation.py` tested news article counts
  (PhoBERT), created novelty proxies (first_in_5d_proxy, repeat_coverage), attention states
  (has_news, high_attention), response states (muted_response, strong_response), tested
  combinations (exhaustion, delayed_alpha, novel_delayed, novel_responded), 2015-2025.
- Result: NEGATIVE. All news states have NEGATIVE IC lift vs baseline. "no_news" (IC=0.1409)
  actually beats "has_news" (IC=0.1038) by +0.037. Exhaustion state (repeat coverage + high
  attention) is worst at -0.0474 lift. Delayed alpha (news + muted response) is worst overall
  at -0.0884 lift.
- The hypothesis tested whether novelty adds beyond count - the result shows BOTH novel and
  repeated news are negative.

Why it matters:
- Raw article counts from PhoBERT are NOT predictive as standalone features
- News ACTUALLY DEGRADES S1 signal quality
- The "exhaustion" mechanism is confirmed as negative, not positive
- Continue using source-type and sentiment features which H440/H383 found useful
- Do not reopen with raw count features

Source:
- [session_101_log.md](./session_101_log.md)
- `artifacts/run_summaries/20260508_174800_h445_semantic_novelty_saturation_research_branch.json`

---

## D036: Volume-Adjusted Price Momentum "Real Force" Hypothesis Fails (2026-05-08, Session 327)

Finding:
- Claim tested: price normalized by volume captures "expensive" vs "cheap" moves.
  Same return on higher volume = real force (real demand), same return on lower volume
  = fade (crowd blowoff). Test return/volume buckets for forward IC vs random baseline.
- Evidence: `analysis/h447_volume_adjusted_price_momentum.py` computed volume_z from 
  order_stats total volume, return/volume buckets (high/low return × high/low volume),
  return_per_volume ratio (expensive, cheap), tested 2015-2025.
- Result: OPPOSITE OF HYPOTHESIS. Original hypothesis: high return + high volume = "real force"
  (positive), high return + low volume = "fade" (negative). 
  - real_force (high_return_high_vol) IC=0.111 (-0.019 lift) UNDERPERFORMS
  - fade_move (high_return_low_vol) IC=0.143 (+0.013 lift) POSITIVE
  - low_return_low_vol IC=0.204 (+0.0746 lift) STRONGEST
  - low_return_high_vol IC=0.073 (-0.057 lift) WEAKEST
- This is a CONTRARIAN signal, not momentum. The volume-adjusted framework works but
  direction is inverted: "cheap moves" = mean reversion, not "real force" = sustained.

Why it matters:
- Original "real force" hypothesis is dead
- Use low_return_low_vol as contrarian conditioner if desired
- High return + high volume is NOT a positive signal - it underperforms

---

## D037: Vol Contraction Mean Reversion Exists But Wrong Direction For Long-Only (2026-05-08, Session 105)

Finding:
- Claim tested: H446 showed vol_contraction UNDERPERFORMS. But vol contraction + HIGH
  return might be the reversal: vol contracting after a rally indicates exhaustion.
- Evidence: `analysis/h449_vol_contraction_mean_reversion.py` computed vol_change (5d rolling 
  std of pct_change), vol_contraction (bottom 20% change), high_return (top 30%), tested 
  vol_contraction × high_return vs vol_expansion × high_return, 2015-2025.
- Result: PATTERN CONFIRMED but NEGATIVE for long-only. vol_contraction_exhaustion 
  IC=0.104 (-0.0255 lift) = mean reversion (negative IC), while vol_expansion_momentum 
  IC=0.167 (+0.0373) = positive momentum. Combo vs Momentum: -0.0628.

Why it matters:
- The regime-dependent behavior is REAL but in the WRONG direction for long-only
- Use vol_expansion_momentum side (positive), not vol_contraction_exhaustion
- Dead-end for direct long-only use of exhaustion pattern

Source:
- [session_105_log.md](./session_105_log.md)
- `artifacts/run_summaries/20260508_175412_vol_contraction_mean_reversion_research_branch.json`

---

## D038: Sector Momentum As Regime Gate Fails — Tiny Signal Differences (2026-05-08, Session 111)

**Finding:**
- Claim tested: cross-sectional market excess (sector_up vs sector_down) as regime gate should
  change signal behavior. S248-S252 failed as FILTERS, test as REGIME GATES.
- Evidence: `analysis/h455_sector_momentum_as_regime_not_filter.py` computed sector returns
  from order_stats, bucketed into sector_up/sector_down, tested C16/buy_heavy_expansion IC
  in each regime, 2015-2025.
- Result: Signal differences are TINY (-0.0017 to -0.0127). Signals work SIMILARLY across
  both regimes — no router benefit. High volume is always negative in both regimes.
  S248-S252 failed as FILTERS, this fails as REGIME GATES.

**Why it matters:**
- Do not use sector momentum as a regime router
- vol_expansion remains the only confirmed regime amplifier
- Reopen only with materially different sector representation or a sector-specific signal

**Source:**
- [session_111_log.md](./session_111_log.md)
- `artifacts/run_summaries/20260508_172929_sector_momentum_as_regime_not_filter_research_branch.json`

---

## D039: Spread As Hard Regime Gate Fails — Sparse Support (2026-05-08, Session 112)

**Finding:**
- Claim tested: spread (avg_buy_size / avg_sell_size ratio) as regime gate. Wide spread
  might amplify signals differently than tight spread.
- Evidence: `analysis/h456_spread_turnover_regime.py` computed spread, bucketed into
  tight/broad spread, tested buy_heavy_expansion in each regime, 2015-2025.
- Result: Wide spread AMPLIFIES buy_heavy_expansion significantly (+0.0948 vs baseline),
  but tight spread states are TOO SPARSE (356-1703 rows) for robust inference.
  Hard regime gate fails due to sparse support.

**Why it matters:**
- Do not use spread as a hard regime gate
- Use spread as a SOFT FILTER instead — the amplification effect in wide-spread is real
- Reopen only with materially different spread representation or more data

**Source:**
- [session_112_log.md](./session_112_log.md)
- `artifacts/run_summaries/20260508_173558_spread_turnover_regime_research_branch.json`

---

## D040: Rank Acceleration As Hidden Signal Fails — Anti-Predictive (2026-05-08, Session 115)

**Finding:**
- Claim tested: rank_change speed (how fast a ticker enters the candidate panel) might
  signal hidden information — suddenly appearing = different info than gradual entry.
- Evidence: `analysis/h462_activation_rate_hidden_signal.py` computed rank_change speed
  (delta of C16 rank), bucketed into accelerating/decelerating, tested with vol_expansion,
  2015-2025.
- Result: Rank acceleration is ANTI-PREDICTIVE alone (-0.0166 lift for accelerating,
  -0.0665 for decelerating). Adding rank acceleration to buy_heavy_expansion makes it
  MUCH WORSE (-0.0584). The "suddenly appearing = hidden info" hypothesis is NOT supported.

**Why it matters:**
- Do not use rank_change velocity features
- The "velocity of activation" direction doesn't capture useful information
- H431 rank_delta worked because it correlated with rank level, not as independent signal

**Source:**
- [session_115_log.md](./session_115_log.md)
- `artifacts/run_summaries/20260508_181614_activation_rate_hidden_signal_research_branch.json`

---

## D041: Signal Combination Fails — Vol Expansion Is Common Driver (2026-05-08, Session 117)

**Finding:**
- Claim tested: C20/C21/C22 signals are orthogonal and combos should add incremental IC.
- Evidence: `analysis/h465_cross_signal_orthogonality.py` tested C21a×C22, C20×C22,
  C21a×C22×C20, C21a×C21b combos, 2015-2025.
- Result: ALL combos are WORSE than the best individual signal.
  - C21a×C22: IC +0.2119 (-0.0115 vs max of 0.2234)
  - C20×C22: IC +0.1997 (-0.0169 vs max of 0.2104)
  - C21a×C22×C20: IC +0.2119 (same as 2-way)
  - C21a×C21b: 0 rows (mutually exclusive)

**Why it matters:**
- Signals are NOT orthogonal — vol_expansion is the common regime driver
- Do NOT create composite signals from C20/C21/C22
- The signals are ADDITIVE in portfolio sense (different days they fire), not combinatorial
- C23 (illiquidity_expansion) should also NOT be combined with C21/C22 in the same entry
- Treat signals as independent standalone conditions, not stackable

**Source:**
- [session_117_log.md](./session_117_log.md)
- `artifacts/run_summaries/20260508_183554_cross_signal_orthogonality_audit_research_branch.json`

---

## D041: Acceleration/Momentum Signals Are Dead-End (2026-05-08, Session 120)

**Finding:**
- Claim tested: C16 acceleration (second derivative) predicts forward IC. Accelerating vs decelerating order pressure might differ.
- Evidence: `analysis/h449_order_flow_momentum.py` tested c16_accel_expanding, c16_accel_contracting, c16_accel_neutral, c16_level_high, c16_level_low states, 2015-2025.
- Result: ACCELERATION states are NOT predictive.
  - c16_accel_expanding: IC +0.1219 (-0.0069 lift) — WORSE than baseline
  - c16_accel_neutral: IC +0.1287 (-0.0001) — WORSE
  - c16_accel_contracting: IC +0.1303 (+0.0015) — marginal
  - **c16_level_high: IC +0.1614 (+0.0326)** — BEST (but this is LEVEL, not acceleration)

**Why it matters:**
- CONFIRMS H443 pattern: foreign flow momentum also marginal/negative
- CONFIRMS H446/H447: vol LEVEL matters, not vol CHANGE
- The edge comes from LEVELS (high pressure, high volume), not MOMENTUM (changes)
- Use C16 level as regime conditioner, NOT its derivative
- This is dead-end D041 for ALL acceleration/momentum signals

**Source:**
- [session_120_log.md](./session_120_log.md)
- `artifacts/run_summaries/20260508_192635_h449_order_flow_momentum_research_branch.json`

---

## D042: Quality Delta as Prediction Fails — Marginal Signal (2026-05-09, Session 127)

**Finding:**
- Claim tested: quality CHANGE (delta S1 = current S1 - prior 5d S1) predicts forward IC. H437 tested quality LEVEL (entering ticker weakest at 0.066) — this tests if delta rescues it.
- Evidence: `analysis/h441_replacement_quality_delta.py` computed prior 5d S1 via shift, quality_delta = current - prior, bucketed into positive/negative delta, strong positive/negative, tested 2018-2025.
- Result: MIXED (weak).
  - strong_positive_delta (delta > 0.05): IC +0.1206 (+0.0012 lift, 8/8) — marginal best
  - all_rows baseline: IC +0.1194 — baseline
  - positive_delta (any improvement): IC +0.1169 (-0.0025) — BELOW baseline
  - negative_delta (declining): IC +0.0837 (-0.0357) — BELOW baseline
  - strong_negative_delta (delta < -0.05): IC +0.0784 (-0.0410) — BELOW

**Why it matters:**
- Quality delta is WEAKER than quality LEVEL (H437 entering=0.066)
- Strong positive delta only +0.0012 — far below promotion threshold (IC > 0.05)
- Positive delta actually underperforms baseline (-0.0025)
- Quality decline hurts more than improvement helps
- Dead-end D042: quality delta does not rescue quality level findings

**Source:**
- [session_127_log.md](./session_127_log.md)
- `artifacts/run_summaries/20260509_195148_replacement_quality_delta_quality_change.json`

---

## D043: Adaptive Signal Weighting via Rolling IC Fails (2026-05-09, Session 128)

**Finding:**
- Claim tested: weight C23-C26 by their recent 60d IC instead of equal weight. If IC-weighted outperforms, adaptive weighting adds value.
- Evidence: `analysis/h479_adaptive_signal_weights.py` computed signals C23 (high_illiq × vol_expansion), C24 (ceiling_count × vol_expansion), C25 (vwap_below × vol_expansion), C26 (buy_heavy × illiq × vol_expansion), computed rolling 60d IC per date, weighted by recent IC vs equal weight, tested 2015-2025.
- Result: FAILED.
  - IC-weighted composite: IC +0.1760 (+0.0465 lift vs baseline)
  - Equal weight composite: IC +0.1754 (+0.0458 lift vs baseline)
  - IC vs equal improvement: +0.0007 — **below +0.005 MIXED threshold**
  - Component ICs: C26 (0.2154), C23 (0.1858), C24 (0.1754), C25 (0.1754)

**Why it matters:**
- IC-weighted adds only +0.0007 IC over equal weight — marginal, not meaningful
- Equal weight composite captures the signal ensemble just as well
- Signals share vol_expansion as common amplifier, so relative predictive power stays stable over time
- Adaptive weighting via rolling IC does NOT outperform equal weight
- Dead-end D043: do not pursue dynamic IC-based weighting for C23-C26

**Source:**
- [session_128_log.md](./session_128_log.md)
- `artifacts/run_summaries/20260509_230557_adaptive_signal_weights_research_branch.json`

---

## D044: Sentiment Scope Filter Fails — S1 Robust Across Sentiment Regimes (2026-05-09, Session 131)

**Finding:**
- Claim tested: ultra_negative (bottom 5% prob_neg) identifies noise states where S1 quality fails. If filter helps, S1 WITHOUT ultra_negative > S1 WITH.
- Evidence: `analysis/h482_sentiment_scope_filter.py` loaded S1 + PhoBERT sentiment, computed ultra_negative rank (bottom 5%), compared S1 IC with/without ultra_negative, tested 2015-2025.
- Result: FAILED.
  - S1 WITH ultra_negative: IC 0.1006 (-0.0032 lift vs baseline)
  - S1 WITHOUT ultra_negative: IC 0.1040 (+0.0001 lift vs baseline)
  - Filter effect: +0.0034 — **below +0.01 PASS threshold**
  - S1 baseline (all with news): IC 0.1038

**Why it matters:**
- Filter effect is +0.0034, BELOW the +0.01 pass threshold
- Ultra_negative does NOT identify noise states where S1 quality fails
- S1 is ROBUST across sentiment regimes — quality is similar whether ticker has ultra-negative news or not
- The hypothesis that "sentiment extremes identify noise states" is NOT supported
- Dead-end D044: do NOT use ultra_negative as a signal quality filter

**Source:**
- [session_131_log.md](./session_131_log.md)
- `artifacts/run_summaries/h482_sentiment_scope_filter_summary.json`

---

## D045: Floor Pressure Symmetry Fails (2026-05-09, Session 131)

Finding:
- Claim tested: C24 tests CEILING (+7%), never tested FLOOR (-7%). Multi-day floor pressure = forced sell capitulation = reversal?
- Evidence: `analysis/h485_floor_pressure_symmetry.py` loaded S1 + order_stats, computed floor_count (hitting -7% limit 2+ times in last 3 days), floor_count × vol_expansion, compared to ceiling_2_of_3 (C24) analog, tested 2015-2025.
- Result: FAILED.
  - floor_2_of_3: IC 0.0818 (**-0.0483 lift** vs baseline 0.1301) — ANTI-PREDICTIVE
  - floor_2_expansion: IC 0.0575 (**-0.0726 lift**) — WORSE
  - ceiling_2_of_3 (C24): IC 0.2353 (+0.1052) — CONFIRMED

**Why it matters:**
- Floor pressure is NOT symmetric to ceiling pressure
- Multi-day floor pressure (hitting -7% limit 2+ times) predicts CONTINUED WEAKNESS, not reversal
- Ceiling pressure = queue buildup → next-day release (works)
- Floor pressure = continued weakness (does NOT work)
- Mechanism "capitulation at daily floor = reversal" is NOT supported
- Dead-end D045: do NOT test floor pressure as reversal signal

**Source:**
- [session_131_log.md](./session_131_log.md)
- `artifacts/run_summaries/20260509_232014_floor_pressure_symmetry_research_branch.json`

---

## D046: Lagged Signal Decay Fails (2026-05-09, Session 131)

Finding:
- Claim tested: C23 works at 1d, C24 multi-day works. Test if signal effectiveness DECAYS or IMPROVES at longer horizons (2d, 3d).
- Evidence: `analysis/h486_lagged_signal_decay.py` loaded S1 + computed C23 (high_illiq × vol_expansion), C24 (ceiling_2 × vol_expansion), tested 1d/2d/3d barrier labels via shift, 2015-2025.
- Result: FAILED.
  - C24: 1d IC=0.2291 → 2d IC=-0.0302 (**-0.2593 lift**) → goes NEGATIVE
  - C23: 1d IC=0.0844 → 2d IC=0.0323 (-0.0520 lift)
  - Best horizon: 1d for both signals

**Why it matters:**
- Signals do NOT improve at longer horizons
- C24 multi-day (multi-day buildup) still pays off at 1d, NOT delayed
- The "delayed release" hypothesis fails - the signal captures multi-day buildup but release is still T+1
- Dead-end D046: do NOT test C23/C24 at 2d/3d horizons

**Source:**
- [session_131_log.md](./session_131_log.md)
- `artifacts/run_summaries/20260509_232208_lagged_signal_decay_research_branch.json`

---

## D047: Breadth × Illiq × Vol Triple Combo Fails — Breadth Degrades Signals (2026-05-09, Session 132)

**Finding:**
- Claim tested: H481 found narrow > broad. Test illiq × vol_expansion × narrow_breadth triple combo. H481 tested breadth ALONE, not COMBO. Mechanism: regime interaction boost - narrow amplifies illiq effect.
- Evidence: `analysis/h490_breadth_illiq_regime_interaction.py` computed C23 (illiq × vol_expansion), market breadth from advancing/declining, tested triple combo, 2015-2025.
- Result: FAILED.
  - C23 (illiq × exp): IC 0.2616 (+0.1318) — baseline
  - **Triple (illiq × exp × narrow): IC 0.2436 (+0.1138)** — WORSE than C23 by -0.018
  - illiq × narrow (no vol): IC 0.1874 (+0.0576)
  - **vol × narrow: IC 0.0967 (-0.0331)** — ANTI-PREDICTIVE
  - narrow_breadth alone: IC 0.1267 (-0.0031) — nearly baseline
  - Triple too sparse: only 2,162 rows, 1/1 positive years

**Why it matters:**
- Breadth is NOT a useful regime gate for signals — it DEGRADES quality
- vol_expansion in narrow markets is ANTI-predictive (0.0967, -0.0331)
- H481 found breadth MONOTONIC as soft context, but hard intersection with signals makes them WORSE
- Do NOT use breadth as a hard filter for illiq/vol signals
- Dead-end D047: do NOT add breadth as a hard regime gate for C23/C24/C26 signals

**Source:**
- [session_132_log.md](./session_132_log.md)
- `artifacts/run_summaries/20260509_232738_breadth_illiq_regime_interaction_research_branch.json`

---

## D048: Stable Queue Volatility Fails — Too Sparse to Test (2026-05-09, Session 132)

**Finding:**
- Claim tested: Price limit friction (stable queue = low vol variance) might amplify signals differently than volatile queue. Test: ceiling_count × vol_stability vs ceiling_count × vol_volatility.
- Evidence: `analysis/h493_price_limit_friction_amplifier.py` computed ceiling 2-of-3, ticker-level vol std over 5d, stability threshold (bottom 20%), tested interaction, 2015-2025.
- Result: FAILED — TOO SPARSE.
  - stable_queue rows: only 21, sparse (1/5 positive years)
  - stable_queue × ceiling: only 21 rows total
  - Volatility definition too noisy — can't compute stable queue reliably

**Why it matters:**
- The price limit friction hypothesis is untestable with current data
- Volatility definition from pct_change_std is too noisy for stability detection
- Need different data source (order queue depth, trade-through rates) to test queue stability
- Dead-end D048: do NOT test queue stability without different data source

**Source:**
- [session_132_log.md](./session_132_log.md)
- `artifacts/run_summaries/20260509_233232_price_limit_friction_amplifier_research_branch.json`

---

## D049: Raw C17 (Non-ranked) Fails vs Ranked C16 (2026-05-09, Session 135)

**Finding:**
- Claim tested: C17 (raw order_volume_ratio without cross-sectional ranking) may preserve more signal than ranked C16 (like illiq alone worked better than combo). Test: raw vs ranked standalone.
- Evidence: `analysis/h498_c17_standalone.py` computed raw order_volume_ratio from order_stats, cross-sectional rank, tested high/top20 states vs baseline, 2015-2025.
- Result: FAILED.
  - Raw C17 top20%: IC 0.1623 (+0.0324)
  - Ranked C16 top20%: IC 0.1670 (+0.0371)
  - **C17 is WORSE than C16 by -0.0048 IC**
  - Combo (both): IC 0.1670 = same as C16 alone (no additional value)
  - Both high and low states work (symmetric signal)

**Why it matters:**
- Ranking does NOT strip away useful information — it actually helps slightly
- The hypothesis "raw preserves more signal" is NOT supported
- C16 (ranked) is the correct representation
- Dead-end D049: do NOT use raw C17 as standalone signal; ranking is correct

**Source:**
- [session_135_log.md](./session_135_log.md)
- `artifacts/run_summaries/20260509_235542_c17_standalone_research_branch.json`
