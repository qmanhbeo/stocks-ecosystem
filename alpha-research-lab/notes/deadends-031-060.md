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