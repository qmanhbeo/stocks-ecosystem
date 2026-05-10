# Sessions Compact

What this file is for: compact per-session recovery notes. Keep one unnumbered
one-liner or short paragraph per material session, newest first. Do not use
manual list numbering; prepend new entries at the top. Every entry must link
to its source session or state an explicit source anchor.

## Recent Sessions

- [Session 139](session_139_log.md): Ran skeptical interpretation audit on H509 artifacts only (no new experiments). Clarified that H509 robustly recovers quiet-vs-active structure and a convincing C24-like queue-friction channel, while onset/amplification/carry remain entangled; also flagged that `k=6` selection is informative but not uniquely proven because k-choice used full-period IC diagnostics. Source: [session_139_log.md](./session_139_log.md).

- [Session 139](session_139_log.md): Ran H509 latent-state discovery (unsupervised emission clustering, dev-fit/frozen assign, `k=4/5/6`). SUPPORTS latent ontology with caveat: strong quiet-vs-active separation, stable phase centroids, and clear beat vs random partition (`k=6` lift gap `+0.0746`), plus meaningful C24-like rediscovery; onset/amplification/carry remain diffuse rather than clean one-to-one latent matches. Source: [session_139_log.md](./session_139_log.md).

- [Session 139](session_139_log.md): Ran H508 router-equivalence / residual-ablation. STRUCTURE_PASS: freshness/cofire/low-C16 are nested C23 projections (all three have zero residual rows outside C23 by construction), while C24 remains distinctly strong outside C23 (`C24 | not C23`: IC=0.2559 on 8,329 rows). Compression result: one dominant C23-family primitive + router/timing layers + distinct C24 emission. Source: [session_139_log.md](./session_139_log.md).

- [Session 139](session_139_log.md): Ran H507 latent-state switching structural audit (2015-2025 only). SUPPORTS latent-state view: non-quiet emissions (onset/amplified/router/carry) all show materially higher IC than baseline with 11/11 positive years; transitions are coherent (`onset/amplified/router -> carry -> quiet`) and global self-transition probability is high (`0.8692`). Caveat: strongest states remain sparse (router coverage 1.57%, amplified 2.08%). Next best action: H508 router-equivalence ablation. Source: [session_139_log.md](./session_139_log.md).

- [Session 138](session_138_log.md): Batch 17 BU5 sector_vol_regime. MIXED: sector×C23 IC=0.2223 (+0.0919) marginally beats C23 alone (+0.0873) by +0.0046, but sector_c23 is VERY sparse (2853 rows, only 2/11 positive years), validation NaN. Sector vol regime not robust. Source: [session_138_log.md](./session_138_log.md).

- [Session 137](session_137_log.md): Batch 17 BU4 cross_signal_day_complementarity. PASSED but MIXED insight: always_C23 IC=0.2176 (+0.0874 lift) is STRONGEST; any_signal (union) IC=0.1753 (+0.0451) is weaker; cofire_2 IC=0.2069 (+0.0767) confirms F412 regime strength. Signal routing does NOT beat always-C23. Source: [session_137_log.md](./session_137_log.md).

- [Session 136](session_136_log.md): Batch 17 BU3 multi_day_c23_accumulation. MIXED: 2d consecutive (IC=0.2014, +0.0712) marginally beats single_day (0.2007, +0.0705) by +0.0007, but 3d degrades (0.1925, +0.0623). More accumulation after 2d hurts. Consistent with D046 signal decay. Source: [session_136_log.md](./session_136_log.md).

- [Session 135](session_135_log.md): Batch 17 BU2 c17_standalone. FAILED: raw C17 IC=0.1623 vs ranked C16 IC=0.1670 (-0.0048). Raw is WORSE than ranked — blending does NOT strip info. Both high/low symmetric. Dead-end D049. Source: [session_135_log.md](./session_135_log.md).

- [Session 134](session_134_log.md): Batch 17 BU1 market_wide_vol_regime. MIXED: market_vol×C23 IC=0.2006 (+0.0708, 11/11) vs ticker_vol×C23 IC=0.2616 (+0.1318). Market-level vol expansion is REAL but WEAKER than ticker-level by +0.061. Key finding: regime amplification works at STOCK level, not market level. Source: [session_134_log.md](./session_134_log.md).

- [Session 132](session_132_log.md): Batch 16 COMPLETE (BR1-BR10). 3 PASSED: BR1 cofire_2 IC=0.2463 (+0.1165), BR3 illiq alone IC=0.1793 (+0.0495), BR10 c16_low×C23 IC=0.2838 (+0.1540) BEST this session. 5 MIXED: BR2 vol degree monotonic, BR5 market sentiment diff tiny, BR6 spread×vol +0.0239, BR8 illiq+vwap+exp 0.2795, BR9 signal decay confirmed. 2 FAILED: BR4 breadth combo WORSE than C23 (D047), BR7 stable queue too sparse (D048). Source: [session_132_log.md](./session_132_log.md).

- [Session 131](session_131_log.md): Ran H486 `lagged_signal_decay` (BJ queue) to test if C23/C24 work at 2d/3d horizons. FAILED: C24 1d=0.2291 → 2d=-0.0302 (-0.2593 lift!), C23 1d=0.0844 → 2d=0.0323 (-0.0520). Signals DECAY massively at longer horizons, best at 1d. Dead-end D046. Finding F411. Source: [session_131_log.md](./session_131_log.md).

- [Session 131](session_131_log.md): Ran H485 `floor_pressure_symmetry` (BG queue) to test if floor pressure (hitting -7% limit 2+ times) mirrors ceiling (C24). FAILED: floor_2_of_3 IC=0.0818 (-0.0483 lift vs baseline), floor_2_expansion IC=0.0575 (-0.0726). Floor pressure is anti-predictive, NOT symmetric to ceiling. C24 (ceiling_2_of_3 IC=0.2353) confirmed. Dead-end D045. Finding F410. Source: [session_131_log.md](./session_131_log.md).

- [Session 131](session_131_log.md): Ran H482 `sentiment_scope_filter` to test if ultra_negative filters S1 quality. FAILED: filter effect +0.0034 is below +0.01 threshold. Ultra_negative does NOT identify noise states - S1 is robust across sentiment regimes. Finding F409: sentiment extremes do not filter signal quality. Source: [session_131_log.md](./session_131_log.md).

- [Session 130](session_130_log.md): Ran H481 `breadth_threshold_finder` to find exact breadth cutoff where signal switches. PASSED: NO discrete switch - pattern is MONOTONIC. Best narrow threshold 5% = +0.0200 IC lift. Narrow markets consistently positive across all thresholds, broad markets consistently negative. Finding F408: use narrow market (bottom 10-20%) as soft regime amplifier. Source: [session_130_log.md](./session_130_log.md).

- [Session 129](session_129_log.md): Ran H480 `extreme_negative_sentiment` to test extreme negative PhoBERT for capitulation-reversal. PASSED: ultra_negative (bottom 5% prob_neg) = IC 0.1068 (+0.0100 lift, 8/8). Extreme negative at bottom 10% is marginal (+0.0004). Finding F407: ultra_negative is new signal state capturing capitulation-reversal mechanism. Source: [session_129_log.md](./session_129_log.md).

- [Session 128](session_128_log.md): Ran H479 `adaptive_signal_weights` to test IC-weighted C23-C26 vs equal weight. FAILED: IC-weighted (0.1760) vs equal weight (0.1754) = only +0.0007 improvement, below +0.005 threshold. Equal weight composite works just as well. Dead-end D043 - adaptive weighting via rolling IC does NOT outperform equal weight. Finding F406: signals share vol_expansion as common amplifier, so relative predictive power stays stable. Source: [session_128_log.md](./session_128_log.md).

- [Session 127](session_127_log.md): Ran H441 `replacement_quality_delta` to test if quality CHANGE (delta S1) predicts forward IC. MIXED (weak): strong_positive_delta (delta > 0.05) = IC 0.1206 (+0.0012 lift, 8/8) — marginal; positive_delta = IC 0.1169 (-0.0025, BELOW baseline); negative_delta = IC 0.0837 (-0.0357 BELOW). Quality change is weaker than quality LEVEL (H437 entering=0.066). Dead-end D042 - quality delta does not rescue quality level. Not promotion-worthy. Source: [session_127_log.md](./session_127_log.md).

- [Session 126](session_126_log.md): Investigated OpenCode slash-command / skill / compaction behavior end-to-end for the evergreen loop. Confirmed that `/bright-mind`, `/experimentor`, and `/manh-memory-system` are real installed OpenCode skills and load correctly in `opencode run` from positional args, stdin, and continued sessions because the build agent interprets the user text. Confirmed that `/compact` is different: stdin `/compact` is stored as literal text, while real interactive compaction is stored as a dedicated `compaction` message part. Patched the loop to use one fresh OpenCode session per cycle, explicit `--session <id>` reuse within the cycle, and a durable `evergreen-research-loop/state/cycle_handoff.md` file instead of fake `/compact`. Set the safe operator defaults to `MAX_CYCLES=1` and `SESSION_BATCH_SIZE=1` so no-arg loop runs stay bounded. Source: [session_126_log.md](./session_126_log.md).

- [Session 125](session_125_log.md): Ran H478 `zero_liquidity_anomaly` (AR queue). MIXED: Zero volume states have 0 rows (no order data exists when volume = 0, hypothesis untestable). BUT low_volume_high_c16 PASSES: IC 0.176 (+0.056 lift, 8/8 pos years) — independent confirmation of H474 tight_capacity mechanism. Finding F404: sparse order flow = hidden demand. Source: [session_125_log.md](./session_125_log.md).

- [Session 124](session_124_log.md): Ran H477 `ap_residual_signal_discovery` (AP queue). MIXED: S1 residual after removing vol_expansion correlation = IC +0.0013 (7/11 positive years, 63.6%). Marginal but real — residual IC is positive, confirming S1 is not purely vol_expansion-driven. But IC is only 0.0013, not strong enough for promotion. All-rows residual = -0.001 (4/11), noise on average. Finding F403: S1 has a tiny independent component beyond vol_expansion, but the effect is fragile. Do not promote as signal; raw S1 remains primary. Source: [session_124_log.md](./session_124_log.md).

- [Session 123](session_123_log.md): Ran H474 `capacity_as_signal_not_veto` (AN queue). PASSED: tight_capacity (Q1: lowest order count) = IC 0.184 (+0.065 lift, 8/8 pos years). loose_capacity = IC 0.074 (-0.046, anti-predictive). Mechanism: sparse order flow = hidden demand / under-followed alpha, not tradability. tight_expansion sparse (2/8 years). NEW capacity signal — fundamentally different from H391 binary release. Use as positive filter for low-activity names, not as veto. Source: [session_123_log.md](./session_123_log.md).

- [Session 122](session_122_log.md): Ran H473 `news_velocity_as_signal` (AM queue). FAILED: high_velocity (Q5) = IC 0.088 (-0.032 lift) = ANTI-predictive. burst_has_news = IC 0.082 (-0.037). Fast-arriving news = crowd-following, not hidden alpha. mid_velocity only +0.008. Low_velocity too sparse (0 news). News velocity adds no value beyond presence. Dead-end. Source: [session_122_log.md](./session_122_log.md).

- [Session 121](session_121_log.md): Ran H472 `liquidity_adjusted_return` (AL queue). FAILED: high LAR (Q5) = IC 0.087 (-0.032 lift) = ANTI-predictive. return_5d_pos_illiq = IC 0.163 (+0.044) = illiquid momentum (C23-style), not flow quality. return_5d_pos_liq = IC 0.052 (-0.067) = liquid crowd blowoff (confirms D036). The ratio collapses two correlated effects into one confusing metric that loses to raw components. Dead-end for LAR ratio. Source: [session_121_log.md](./session_121_log.md).

- [Session 120](session_120_log.md): Ran H449 `order_flow_momentum` to test C16 acceleration (2nd diff) vs forward IC. PASSED but with OPPOSITE insight: c16_level_high IC=0.1614 (+0.0326 lift, 11/11) — BEST. BUT c16_accel_expanding IC=0.1219 (-0.0069), c16_accel_contracting IC=0.1303 (+0.0015) BOTH WORSE than baseline. ACCELERATION does NOT add value - the edge comes from LEVELS (high pressure), not MOMENTUM (changes in pressure). Confirms H443 pattern: both foreign flow momentum and C16 momentum are NEGATIVE. Confirms H446/H447 patterns: vol LEVEL matters, not change. Use C16 level as regime conditioner, not its derivative. Dead-end D041 for acceleration signals. Source: [session_120_log.md](./session_120_log.md).

- [Session 119](session_119_log.md): Ran H469 `foreign_flow_momentum`. MIXED: ff_decel_exp IC=0.1376 (+0.0074, 11/11) — marginal, not promotion. Ran H470 `vwap_deviation_regime`. PASSED: NEW SIGNAL C25! vwap_below_10_exp IC=0.1733 (+0.0431 lift, 11/11). Mechanism: VWAP far below average + vol expansion in illiquid stocks. C25 is strong signal. Ran H471 `order_flow_microstructure_regime`. PASSED: NEW SIGNAL C26! buy_heavy_illiq_exp IC=0.1889 (+0.0587 lift, 11/11). Buy-heavy order flow + illiquidity + vol expansion = institutional hidden demand. Pattern confirmed: ALL strong signals share structure: behavior + illiquidity + vol_expansion. Do NOT combine C23/C24/C25/C26 as composite entries. Source: [session_119_log.md](./session_119_log.md).

- [Session 116](session_116_log.md): Ran H463 `amihud_illiquidity_regime_combo`. PASSED: NEW SIGNAL C23! high_illiq_expansion IC=0.2616 (+0.1318 lift vs baseline 0.1298). STRONGEST signal found — +101% boost over baseline. OHLCV computed inline from 1227 per-ticker files (ticker extracted from filename). Source: [session_116_log.md](./session_116_log.md).

- [Session 115](session_115_log.md): Ran H462 `activation_rate_hidden_signal` to test rank_change speed × vol_expansion. FAILED: rank_accelerating ANTI-predictive (-0.0166 lift). rank_accel_buy_expansion WORSE than buy_heavy_expansion (-0.0584). "Suddenly appearing = hidden info" hypothesis NOT supported. Dead-end D040. Source: [session_115_log.md](./session_115_log.md).

- [Session 114](session_114_log.md): Ran H461 `momentum_regime_combo` to test if momentum improves C21 combos. MIXED: momentum doesn't improve C21 (-0.0017 to -0.0047). C21 signals are complete as-is. Source: [session_114_log.md](./session_114_log.md).

- [Session 113](session_113_log.md): Ran H460 `volume_regime_dependency_of_signals`. PASSED: ALL signals work best in vol_expansion. Rankings: C21 sell_heavy_decel (0.2393) > C21 buy_heavy_accel (0.2338) > C22 approaching_ceiling (0.2170) > C20 buy_heavy_expansion (0.2105). Vol contraction NO-GO. Source: [session_113_log.md](./session_113_log.md).

- [Session 112](session_112_log.md): Ran H456 `spread_turnover_regime`. MIXED: Wide spread amplifies signals (+0.0948), but tight side sparse. Dead-end D039. Source: [session_112_log.md](./session_112_log.md).

- [Session 111](session_111_log.md): Ran H455 `sector_momentum_as_regime_not_filter`. FAILED: sector differences tiny, no router benefit. Dead-end D038. Source: [session_111_log.md](./session_111_log.md).

- [Session 110](session_110_log.md): Ran H454 `implied_limit_proximity`. PASSED: NEW SIGNAL C22! approaching_ceiling IC=0.2170 (+0.0872 lift). Source: [session_110_log.md](./session_110_log.md).

- [Session 107](session_107_log.md): Ran H451 `buy_sell_imbalance_in_stress` to test buy_sell_volume_imbalance × vol_regime. PASSED: buy_heavy_expansion IC=0.1809 (+0.0508 lift, 11/11 pos years) is STRONGEST! NEW SIGNAL - buy-heavy imbalance works ONLY in vol expansion (+0.0699 vs contraction). Sell-heavy always negative. Source: [session_107_log.md](./session_107_log.md).

- [Session 106](session_106_log.md): Ran H450 `volume_acceleration_signal` to test vol_delta × return vs volume LEVEL × return. MIXED: Accel helps high return (+0.0474 vs level), but low_vol (+0.0522) still dominates overall. Source: [session_106_log.md](./session_106_log.md).

- [Session 105](session_105_log.md): Ran H449 `vol_contraction_mean_reversion` to test vol_contraction × high_return vs vol_expansion × high_return. MIXED: Pattern confirmed real (combo vs momentum -0.0628), but vol_contraction_exhaustion has NEGATIVE IC (-0.0255) = mean reversion, not a positive long-only signal. vol_expansion_momentum (+0.0373) is the useful side. Dead-end D037 for direct long-only use. Source: [session_105_log.md](./session_105_log.md).

- [Session 104](session_104_log.md): Ran H448 `vol_expansion_contrarian_combo` to test vol_expansion (H446) × low_return_low_vol (H447) combo. PASSED: COMBO IC=0.2069 (+0.0771 lift, 11/11 pos years) is STRONGEST! Beats vol_expansion alone by +0.0316, beats low_return_low_vol alone by +0.0025. Captures oversold-in-expanding-vol regime better than either component alone. New signal - use as conditioner. Source: [session_104_log.md](./session_104_log.md).

- [Session 103](session_103_log.md): Ran H447 `volume_adjusted_price_momentum` to test return/volume buckets for forward IC. MIXED (OPPOSITE of hypothesis): low_return_low_vol IC=0.2045 (+0.0746 lift, 11/11 pos years) is STRONGEST - this is CONTRARIAN not momentum. high_return_high_vol (real_force) IC=0.1109 (-0.019 lift) UNDERPERFORMS. Hypothesis inverted: cheap moves work, real force doesn't. Dead-end D036. Source: [session_103_log.md](./session_103_log.md).

- [Session 326](session_102_log.md): Ran H446 `volatility_regime_transition` to test vol 5d change (expansion vs contraction) vs forward IC. PASSED: vol_expansion (top 20% 5d vol change) has IC=0.1750 vs baseline 0.1301 (+0.0449 lift, 11/11 pos years). vol_contraction (bottom 20%) IC=0.1216 (-0.0085 lift). Volatility REGIME TRANSITION is a real signal - when vol is expanding, S1 quality improves significantly. Use as regime conditioner. Source: [session_102_log.md](./session_102_log.md).

- [Session 325](session_101_log.md): Ran H445 `semantic_novelty_saturation` to test news novelty vs repetition. FAILED (NEGATIVE): All news states NEGATIVE IC lift. no_news (IC=0.1409) beats has_news (IC=0.1038) by +0.037. Exhaustion state worst (IC=0.0861, -0.0474 lift). News counts NOT predictive - degrade S1 quality. Dead-end D035. Source: [session_101_log.md](./session_101_log.md).

- [Session 324](session_100_log.md): Ran H444 `signal_ignorance_weight` to test whether S1/C16 have regimes where they hurt. PASSED (offline evidence): Found strong ignorance opportunity - worst regime "low_ic_low_temp" has IC=-0.0034 (negative!) vs baseline 0.1335, lift -0.1369. High IC + high temp regime has IC=0.2606 (+0.1271 lift). Caveat: regime buckets use same-period IC (lookahead), not a deployable rule - shows POTENTIAL only. Use as diagnostic or requires lagged regime prediction for deployable version. Source: [session_100_log.md](./session_100_log.md).

- [Session 323](session_323_log.md): Ran H443 `prop_foreign_predator_prey` to test predator-prey interaction between foreign and proprietary flows. FAILED: All predator-prey states (ff_sell_pt_buy_absorption IC=0.0621, ff_buy_pt_sell_distribution IC=0.0959, prop_follow_ff IC=0.0842) are BELOW baseline IC=0.1335. Raw foreign flow (ff_buy IC=0.1188, ff_sell IC=0.1004) also underperforms baseline. Hypothesis not supported - flow direction alone is not predictive. Dead-end D034. Source anchor: [session_323_log.md](./session_323_log.md).

- [Session 321](session_321_log.md): Ran H442 `ticker_rank_acceleration` to test second derivative of C16 rank
  (acceleration = delta of delta) vs H431 first derivative. FAILED: Accel Up vs Down lift only +0.0009,
  near zero. C16 rank LEVEL dominates (IC=0.158 vs accel 0.120). Both accel_up/down+flow equal (~0.147).
  H431 worked because it's correlated with rank level, not as independent signal. Second derivative is noise.
  Dead-end D033. Source anchor: [session_321_log.md](./session_321_log.md).

- [Session 320](session_320_log.md): Ran H441 `cross_ticker_correlation_shock` to test whether date-level
  cross-sectional correlation regime (high vs low) predicts forward IC. FAILED: High vs Low corr date
  lift only +0.0033, below 0.01 threshold. Secondary: C16 flow prefers high-corr dates (0.167 vs 0.144),
  first-news prefers low-corr dates (0.153 vs 0.130). Shock mechanism weak. Dead-end D032. Source anchor:
  [session_320_log.md](./session_320_log.md).

- [Session 319](session_319_log.md): Ran H440 `news_novelty_first_repeat` to test whether first-in-N-days
  novelty (vs repeat coverage vs high-frequency) predicts forward IC. PASSED: First-in-5d IC=0.123
  beats repeat IC=0.091 (+0.032 lift, 8/8 pos years, 23266 rows). First+strong-flow IC=0.161 vs
  repeat+flow IC=0.140. Novelty is the key dimension, not just presence. Aligns with H383
  active-news confirmation and adds the NOVELTY dimension. Use as news-state conditioner. Source
  anchor: [session_319_log.md](./session_319_log.md).

- [Session 318](session_318_log.md): Ran H439 `volatility_regime_transition` to test whether vol_z 5d change
  (expansion vs contraction) predicts forward IC differently than static vol. MIXED:
  High vol states are MUCH stronger (IC=0.17-0.20 vs 0.09-0.10 low vol). High vol+contracting
  IC=0.195 is strongest, but this is vol LEVEL effect, not transition effect. Transition
  component is weak (+0.009 expanding vs contracting overall). Aligns with H411 and H434:
  vol level matters, transition is secondary. Not promoted as new signal. Source anchor:
  [session_318_log.md](./session_318_log.md).

- [Session 317](session_317_log.md): Ran H438 `news_consensus_divergence` to test whether news source
  disagreement vs consensus predicts forward IC. MIXED: Consensus IC=0.102 beats divergence IC=0.093
  (-0.0086 lift), opposite of hypothesis. Both positive but neither beats all-rows (0.120). Aligns
  with H382: source TYPE matters but consensus vs divergence does not create alpha. Neither
  promoted. Source anchor: [session_317_log.md](./session_317_log.md).

- [Session 316](session_316_log.md): Ran H437 `replacement_quality_revival` to test whether
  quality (S1 IC) of entering tickers vs exiting tickers predicts forward alpha.
  FAILED: Exiting tickers IC=0.126 (STRONGEST), stable IC=0.079, entering IC=0.066
  (WEAKEST). Entering vs exiting lift = -0.060. Opposite of hypothesis. Aligns with
  H388 finding that fresh reappearances are not strong. Dead-end D031. Source anchor:
  [session_316_log.md](./session_316_log.md).

- [Session 315](session_315_log.md): Ran H436 `signal_ignorance_weight` to test whether
  composite regime features predict signal degradation with cash/veto action.
  FAILED badly: Top-10 S1 in degrade-state still IC=0.10 (STRONGER than all-rows
  IC=0.12), while ignoring signal drops to IC=0.053. Composite degrade indicators
  do NOT capture signal degradation. S1/C16 are robust across regime conditions.
  Dead-end D030. Source anchor: [session_315_log.md](./session_315_log.md).

- [Session 314](session_314_log.md): Ran H435 `candidate_rank_actual_gap` to test whether
  prediction error (ranker predicted vs actual) predicts forward returns.
  FAILED: small gaps have HIGH IC (0.28-0.64), large gaps have NEGATIVE IC
  (-0.79 to -0.83). When ranker is surprised it's NOISE, not alpha. Confirms H413
  ranker is well-calibrated. Dead-end D028. Source anchor:
  [session_314_log.md](./session_314_log.md).

- [Session 313](session_313_log.md): Ran H434 `signal_strength_gating` to test
  whether signal strength (S1 rank × C18 rank product) predicts forward returns.
  PASSED: High strength (Q5) IC 0.0940 vs low strength (Q1) IC 0.0829 = +0.0111 lift.
  Works strongest in stress years (2020 +0.0553, 2021 +0.0710). Not a ranker
  replacement but useful as dynamic position sizing signal. Offline evidence only.
  Source anchor: [session_313_log.md](./session_313_log.md).

- [Session 312](session_312_log.md): Ran H433 `state_transition_not_event` to test
  event-count delta (change) vs level as predictor. Computed daily event count
  from order_pressure_h359_active, computed delta, bucketed into quintiles.
  MIXED: D2 (moderate decreasing delta) best (+0.0088 lift), but pattern
  inconsistent. Event-count level negative IC (-0.0065), delta provides some
  value but not strong enough to promote. Source anchor:
  [session_312_log.md](./session_312_log.md).

- [Session 311](session_311_log.md): Ran H432 `volume_price_divergence` to test
  return vs volume-z divergence as predictor. Computed return and volume-z
  quintiles, tested divergence states (real_force, fade, hidden_support, crowded).
  FAILED: all states have negative lift vs baseline. real_force = +0.0921 (-0.0261),
  fade = +0.0892 (-0.0289). Hypothesis not supported. Source anchor:
  [session_311_log.md](./session_311_log.md).

- [Session 310](session_310_log.md): Ran H431 `cross_sectional_rank_delta` to test
  C16 rank change (delta) vs level as predictor. Computed rank delta from
  order_volume_ratio_rank, bucketed into quintiles, tested forward IC.
  PASSED: Q5_incr (increasing rank) has best IC +0.1290 (+0.0114 lift), 8/8
  pos years. C16 level = +0.0752, delta boosts to +0.1290. Validation confirms
  Q5_incr +0.1310 vs level +0.0633. New signal - use as conditioner. Source
  anchor: [session_310_log.md](./session_310_log.md).

- [Session 309](session_309_log.md): Ran H430 `candidate_temperature_entropy` to test
  whether entropy of top-10 candidate scores predicts forward IC. Bucketed dates
  by full_top10_score_entropy quintiles. MIXED: Q2 best in dev (+0.0105), but
  validation shows high-entropy better (+0.0143). Pattern inconsistent - not a
  clean predictor. Source anchor: [session_309_log.md](./session_309_log.md).

- [Session 308](session_308_log.md): Ran H429 `signal_half_life_router` to test
  whether pre-declared half-life classes (S1 slope, volume state) win only on
  their natural horizon vs random horizon controls. Bucketed tickers by S1 slope
  (momentum vs reversion) and volume state (high vs low), tested IC at 1d/2d/5d/10d.
  FAILED: All classes degrade at longer horizons, no horizon-specific advantage.
  1d baseline always best. Dead-end D027. Source anchor: [session_308_log.md](./session_308_log.md).

- [Session 307](session_307_log.md): Ran H428 tests: (1) `ranker_error_taxonomy`
  - S1 rank degradation FAILED: Top S1 tickers IMPROVE next-day (+0.0263 IC), no
  decay found. (2) `bid_ask_midbook_imbalance` FAILED: higher imbalance has
  WORSE C16 IC (Q5-Q1 lift -0.0385 dev). Both below promotion threshold.
  Dead-ends D026, D027. Source anchor: [session_307_log.md](./session_307_log.md).

- [Session 306](session_306_log.md): Ran H427 `volume_attention_budget` as
  date-level concentration test. Computed volume Herfindahl from order_stats,
  bucketed dates into concentration quintiles, tested S1 IC across regimes.
  PASSED: Q3 (mid-concentration) has mean IC 0.1389 vs baseline 0.1264,
  lift +0.0125, 8/8 positive years. Both extreme concentration and extreme
  distribution hurt signal quality. Offline evidence, needs candidate-count
  policy follow-through. Source anchor: Session 306.

- [Session 305](session_305_log.md): Attempted to activate item 8
  `selector_hysteresis_field` from 2026-05-08 ideation queue. The branch
  needs panel-to-panel ticker transition tracking (prior appearances, incumbent rank
  distance, rank gaps). SKIPPED as data-gated: computing transition
  features requires iterating millions of ticker-date pairs without a
  reusable script. Simpler next candidate is item 3
  `volume_attention_budget` which uses date-level aggregation. Source
  anchor: Session 305.

- [Session 304](session_304_log.md): Ran H426 `forced_seller_detector` with a
  reusable walk-forward entry-candidate script and random baselines only. H426
  FAILED: `forced_seller_core_buyable` had tiny same-support lift
  (`+0.00023`) but only `1 / 5` positive WF years and random-all lift
  `-0.00205`; floor and large-down variants also failed, and literal release
  had only `7` rows. The next-day C16 clause was not used because it is not
  decision-time valid under the current T close -> T+1 open entry-label
  contract. Source anchors: `D025`, Session 304.

- [Session 303](session_303_log.md): Continued safe-first artifact hardening.
  Added lockbox-window-aware C10-C14 RL component caches with manifest
  fingerprints, exact old-inline parity checks, component-only reuse mode, and
  a lightweight artifact integrity CLI. Migrated H413 onto the additive harness
  with legacy summary fields preserved, and batched activation-meta derived
  columns to remove fragmentation warnings. Source anchor: Session 303.

- [Session 299](session_299_log.md): Ran H418
  `foreign_additive` with reusable script
  `analysis/h418_foreign_additive.py`. Tested adding foreign flow to H413.
  H418 FAILED: foreign has +0.004 IC, adding HURTS (-0.006).
  Same pattern as C16 - too weak to contribute.
  Source anchors: `D023`.

- [Session 298](session_298_log.md): Ran H417
  `holdout_2025` with reusable script
  `analysis/h417_holdout_2025.py`. Tested on completely held-out 2025.
  H417 PASSED: +0.014 lift on 2025 = same as long-term (+0.017).
  PROVES NOT survivor bias - pattern is REAL.
  Source anchors: `F381`.

- [Session 297](session_297_log.md): Ran H416
  `market_state_gated` with reusable script
  `analysis/h416_market_state_gated.py`. Tested additive in VNI-up/down.
  H416 PASSED: works in BOTH market states (+0.016 to +0.018 lift).
  ROBUST pattern confirmed.
  Source anchors: `F380`.

- [Session 296](session_296_log.md): Ran H415
  `weight_optimization` with reusable script
  `analysis/h415_weight_optimization.py`. Grid search Vol/S1 weights.
  H415 MIXED: 15V+85S = +0.136 IC, marginal +0.001 over H413.
  Optimum in 10-15% volume range. Keep H413 as standard.
  Source anchors: `F379`.

- [Session 295](session_295_log.md): Ran H414
  `alternative_target_additive` with reusable script
  `analysis/h414_alternative_target_additive.py`. Tested Vol+S1 on 1d/10d/20d barriers.
  H414 PASSED: additive works on ALL horizons (+0.017 to +0.019 lift).
  This confirms generalizable pattern, not target-specific.
  Source anchors: `F378`.

- [Session 294](session_294_log.md): Ran H413
  `triple_signal_additive` with reusable script
  `analysis/h413_triple_signal_additive.py`. Tested three-signal additive combos.
  H413 PASSED: 0.1×Vol + 0.9×S1 = +0.135 IC, beats H410 (+0.126) by +0.009.
  Lower volume weight (10% vs 25%) is key. New standard: 0.1V+0.9S.
  Source anchors: `F377`.

- [Session 293](session_293_log.md): Ran H412
  `volume_c16_additive` with reusable script
  `analysis/h412_volume_c16_additive.py`. Tested Volume+C16 additive.
  H412 FAILED: additive doesn't beat Volume alone (+0.073 vs +0.075).
  C16 too weak to rescue. Source anchors: `F376`.

- [Session 292](session_292_log.md): Ran H411
  `volume_triple_storm` with reusable script
  `analysis/h411_volume_triple_storm.py`. Tested Triple Storm on Volume.
  H411 FAILED: Volume+Triple = +0.038, WORSE than Volume alone (+0.075).
  Triple Storm is C16-specific, not universal amplifier.
  Source anchors: `F375`, `D022`.

- [Session 291](session_291_log.md): Ran H410
  `volume_s1_additive` with reusable script
  `analysis/h410_volume_s1_additive.py`. Tested Volume+S1 additive combos.
  H410 PASSED: 0.25×Vol + 0.75×S1 = +0.12649 IC, beats both standalones!
  Adds +0.009 IC lift over S1 - additive beats cross-product.
  Source anchors: `F374`.

- [Session 290](session_290_log.md): Ran H409
  `volume_c16_cross_product` with reusable script
  `analysis/h409_volume_c16_cross_product.py`. Tested Vol×C16 cross-product.
  H409 was MIXED: cross +0.017 but Volume alone +0.077 is NEW SIGNAL!
  CRITICAL: `order_volume_ratio` standalone is +0.077 IC, 8/8 pos years.
  Source anchors: `F373`.

- [Session 289](session_289_log.md): Ran H408
  `s1_c16_cross_product` with reusable script
  `analysis/h408_s1_c16_cross_product.py`. Tested S1×C16 cross-product.
  H408 was MIXED: cross +0.108 but S1 alone +0.118 (worse).
  Source anchors: `F372`.

- [Session 288](session_288_log.md): Ran H407
  `phase_lead` (simplified) with reusable script
  `analysis/h407_hilbert_phase_lead.py`. Tested lagged C16 × price cross-product.
  H407 PASSED: phase lag added +0.022 IC with 7/8 positive years.
  Source anchors: `F371`.

- [Session 282](session_282_log.md): Ran H401
  `anti_signal_annihilation_veto` with reusable script
  `analysis/h401_anti_signal_annihilation_veto.py`. Fixed top-5 buyable
  candidate rows, no `2026+`, cycle relative-return labels, long-only cash
  vetoes with denominator `K=5`, and random same-breadth veto controls. H401
  was MIXED: strict `support_count_zero` had tiny lift versus no-veto
  (`+0.000167`, `6 / 7` positive years) and random mean (`+0.000152`), but did
  not beat random p95. Broader disagreement masks were negative versus no-veto.
  Source anchors: `F365`, `D017`.

- [Session 281](session_281_log.md): Ran H400
  `calendar_as_weak_prior_not_clock` with reusable script
  `analysis/h400_calendar_as_weak_prior_not_clock.py`. Rebuilt the H395
  train-before-test quorum with calendar votes removed, then added one fixed
  calendar prior averaging January-first-10, Monday, month-end, and T+2 weekday
  residues. H400 FAILED: non-calendar quorum avg IC was `+0.05826`, calendar
  quorum avg IC fell to `+0.05605`, and calendar lift was `-0.00221` with
  `0 / 7` positive lift years. Calendar-only IC was `-0.00827`. Source
  anchors: `F364`, `D016`.

- [Session 280](session_280_log.md): Ran H399
  `crowd_count_ignition` with reusable script
  `analysis/h399_crowd_count_ignition.py`. Fixed `2018-2025` audit, no
  `2026+`, published C16, raw CafeF order stats, C8 volume-z from the RL
  matrix, and H394 predicted-weather buckets. H399 was MIXED: high buy count
  alone is only modest C16 context (`+0.08463` avg IC, `+0.00944` lift versus
  all rows), while `buy_count_rank` is anti-predictive as a standalone score
  (`-0.01075`). `volume_z_high80` owns the clean pocket (`+0.10258`, `8 / 8`);
  `count_high_size_weather_low20` is the best crowd clue (`+0.10083`, `+0.01620`
  lift versus high count) but only `5 / 8` lift years. Source anchors:
  `F363`, `D015`.

- [Session 279](session_279_log.md): Ran H398
  `insider_pre_reaction_clock` with reusable script
  `analysis/h398_insider_pre_reaction_clock.py`. Positive insider events from
  `RealBuyVolume - RealSellVolume > 0`, S272-style T-1/T0/T+1 event mapping,
  same-ticker non-event controls, no `2026+`, and test years `2015-2025`.
  H398 was MIXED: `insider_tplus1` reproduced the S272 lead with avg C16 IC
  `+0.10498`, `11 / 11` positive years, and `+0.03000` lift versus
  same-ticker non-event dates, but the quiet pre-reaction form failed because
  reacted T+1 rows beat pre-reaction by `+0.01811` avg IC. High buy-order-count
  T+1 insider rows were strongest (`+0.13776` avg IC). Source anchors:
  `F362`, `D014`.

- [Session 278](session_278_log.md): Ran H397
  `barrier_pop_vs_hold_router` with reusable script
  `analysis/h397_barrier_pop_vs_hold_router.py`. Fixed H364/H383/H385/C16/
  insider states, buyable rows only, no `2026+`, 15 bps per-row cost, and
  `1d/2d/5d` future relative-return horizons. H397 PASSED: active-news
  strong-flow and positive-news strong-flow are 1d C16 rankers
  (`+0.02257` / `+0.02536` IC lift versus strong-flow), while official and
  official-forward supported states are 5d payoff/hold states (`+0.00650` /
  `+0.00662` net lift, `8 / 8` positive years). H364 positive was too sparse;
  the C5 rank-within-insider form failed and does not kill S272 insider lead.
  Source anchor: `F361`.

- [Session 277](session_277_log.md): Ran H396
  `parent_echo_residual_harvester` with reusable script
  `analysis/h396_parent_echo_residual_harvester.py`. No `2026+`; test years
  `2019-2025`; same-date cross-sectional residualization of H395 and C4-C14
  votes against S1/C16, plus H395 residualization against all C-vote
  ingredients. H396 PASSED as a clarification: H395 survives S1/C16
  residualization (`+0.01669`, `7 / 7` positive years), but fails
  residualization against C votes (`+0.00187`), so it is a strong composite
  RL state, not a new primitive. C13/C10/C6 are the clean S1/C16 residual
  primitive survivors. Source anchor: `F360`.

- [Session 276](session_276_log.md): Ran H395
  `weak_signal_quorum_sleeve` with reusable script
  `analysis/h395_weak_signal_quorum_sleeve.py`. TRUE rolling train-before-test
  folds, test years `2019-2025`, no `2026+`, predeclared weak votes from
  C4-C14, H364/news, official-delay, observable VNI-down-2d, and calendar
  context, train-only low-corr/positive-IC component selection, and equal
  weights in test. H395 PASSED as a strong composite RL-state candidate:
  quorum avg IC `+0.05826`, `7 / 7` positive years, S1 corr `+0.27541`, C16
  corr `-0.00685`, lift `+0.02078` versus random weak baskets and `+0.02745`
  versus the best component. Not a new independent primitive. Source anchor:
  `F359`.

- [Session 275](session_275_log.md): Ran H394
  `oracle_shadow_regime_distiller` with reusable script
  `analysis/h394_oracle_shadow_regime_distiller.py`. TRUE rolling
  train-before-test date-regime model, test years `2018-2025`, no `2026+`,
  from observable S1/C16/order/news/market/tradability aggregates into future
  S1 barrier-breadth weather. H394 was MIXED: ridge weather weakly predicted
  breadth (avg date IC `+0.05019`, `7 / 8` positive years) but failed the
  promotion gates; best honest bucket `ridge_pred_low20` lifted C16 only
  `+0.00342` versus all rows and `+0.00416` versus random dates, and degraded
  S1. Observable `VNI down 2d` remained cleaner context. Source anchors:
  `F358`, `D013`.

- [Session 274](session_274_log.md): Added the reusable lightweight
  research-branch scaffold: `src/experiment_contract.py` plus runnable copy
  template `analysis/_template_research_branch.py`. The contract provides
  role-safe S1 loading that renames raw `actual` to target-only
  `s1_barrier_hit_1d`, default `2026+` blocking, target/state overlap checks,
  yearly and phase IC helpers, and standard run-summary/artifact writes.
  Updated `README_for_AGENTS.md` and `README.md` so future agents start from
  the scaffold for state/signal/context audits. Source anchor: `F357`.

- [Session 273](session_273_log.md): Clarified the signal-library promotion
  rule in `README.md`, `notes/signal_library.md`, and compact findings. Strong
  standalone promotion now explicitly means IC `> 0.05` plus decision-time
  observability, non-leakage, independence from existing library signals,
  positive-year consistency, and enough coverage. IC `0.01-0.05` is weak
  candidate/context evidence. Parent-signal filters must show incremental lift
  versus the parent and matched controls; absolute IC `> 0.05` alone is not a
  new independent promotion. Source anchor: `F356`.

- [Session 272](session_272_log.md): Audited the S24x-S25x "strong" signal
  promotions with reusable script `analysis/audit_s24x_s25x_signal_claims.py`.
  The audit found that `actual` is a binary future 1d barrier label, so the
  S244/S246/S247/S253 market-down and consecutive-down states were partly
  target-derived. Leaky target-market-down ICs reproduced high
  (`+0.0925` / `+0.0951`), but observable VNI-down states dropped to
  `+0.0771` / `+0.0806` versus C16 baseline `+0.0738`; stock-down states were
  weaker than C16. `insider_lead_next_trading_day` survived (`+0.1050`,
  `11 / 11` positive years), while high buy-order-count volume context was
  modest (`+0.0844`). Source anchors: `F355`, `D012`.

- [Session 271](session_271_log.md): Ran H393 `nihilist_reversal` with
  reusable script `analysis/h393_nihilist_reversal.py`. TRUE walk-forward
  `2018-2025`, no `2026+`, fixed high-C16, stock-down, VNI-down, and
  no-bullish-news definitions. H393 was MIXED: `nihilist_reversal` had mean
  5d payoff `+0.010170` but failed `stock_down_high_c16` by `-0.002027`, had
  only `+0.000169` lift versus parent `stock_market_down_high_c16`, and 2025
  payoff was `-0.000982`. `stock_down_high_c16` remains the cleaner state.
  Source anchors: `F354`, `D011`.

- [Session 270](session_270_log.md): Ran H392 `source_triangle_sparse` with
  reusable script `analysis/h392_source_triangle_sparse.py`. TRUE
  walk-forward `2018-2025`, no `2026+`, fixed C16, C5 insider, source-news,
  and forward-text sensors. H392 was MIXED: the required
  `c16_insider_any_news` core had positive mean 5d payoff `+0.003177` but lost
  to `c16_insider_no_news` by `-0.007315`, to
  `c16_any_news_no_insider` by `-0.005205`, and had 2025 lift
  `-0.003072` versus exactly-two sensors. Broader `three_plus_sensors` beat
  exactly-two by `+0.005156` with `8 / 8` positive lift years, but the edge is
  not the insider+C16 triangle. Source anchors: `F353`, `D010`.

- [Session 269](session_269_log.md): Ran H391
  `tradability_release_pulse` with reusable script
  `analysis/h391_tradability_release_pulse.py`. TRUE walk-forward
  `2021-2025`, no `2026+`, fixed top-5/top-10 release states from
  `release_flag`, and same-year same-rank stable/non-release buyable matched
  controls. H391 FAILED: `top5_release` mean cycle relative return was
  `-0.032254` with matched-control lift `-0.033668`, only `1 / 5` positive
  matched-control years, and 2025 lift `-0.080106`; `top10_release` was also
  negative with matched-control lift `-0.028365` and 2025 lift `-0.066302`.
  Source anchors: `F352`, `D009`.

- [Session 268](session_268_log.md): Ran H390
  `calendar_as_liquidity_mechanism` with reusable script
  `analysis/h390_calendar_liquidity_mechanism.py`. Converted C16 into daily
  IC, residualized walk-forward on liquidity, breadth, news-volume, buyability,
  C16 availability, volume-pressure, and trailing down-market controls, and
  avoided `2026+` (`2019-01-02` through `2025-12-31` daily panel; test years
  `2021-2025`). H390 was MIXED: exact `monday_jan_combo` retained 1d residual
  IC lift `+0.02745`, but it was only one active date per evaluated year, only
  `2 / 4` positive 1d residual-lift years, and 5d residual lift was negative
  (`-0.04055`). `quarter_start` and `late_quarter_month` did not retain clean
  1d residual lift. Source anchors: `F351`, `D008`.

- [Session 267](session_267_log.md): Ran H389
  `post_ollama_event_cascade` with reusable script
  `analysis/h389_post_ollama_event_cascade.py`. The first run exposed
  non-finite target rows, so the script was patched and rerun; canonical
  artifacts are timestamp `20260504_203158`. TRUE walk-forward `2018-2025`,
  no `2026+`, guarded-Ollama first/repeat/family-transition event states, and
  5d relative-return payoffs. H389 FAILED: best state `event_first20` had mean
  lifts only `+0.00099` versus generic event and `+0.00114` versus repeat
  event, below the `+0.002` gate; no family pocket cleared MIXED. Source
  anchors: `F350`, `D007`.

- [Session 266](session_266_log.md): Ran H388
  `fresh_selection_pulse` with reusable script
  `analysis/h388_fresh_selection_pulse.py`. Computed prior top-5/top-10
  appearances using only earlier panel dates; TRUE walk-forward `2021-2025`,
  no `2026+`, buyable candidate rows, and cycle relative-return labels. H388
  FAILED: `top5_fresh20` beat incumbents but failed stale-repeat control
  (mean lift `-0.00016`, 2025 lift `-0.00269`); `top10_fresh20` also failed
  stale-repeat control (mean lift `-0.00068`, 2025 lift `-0.00098`). Source
  anchors: `F349`, `D006`.

- [Session 265](session_265_log.md): Ran H387
  `insider_down_rescue` with reusable script
  `analysis/h387_insider_down_rescue.py`. TRUE walk-forward `2018-2025`, no
  `2026+`, fixed positive-C5, 1d/3d stock-down, and high-C16 states, with 5d
  relative-return payoffs versus insider-only, insider-C16, and stock-down-C16
  controls. H387 FAILED: `insider_down_high_c16` beat ordinary insider rows
  but failed the meaningful controls, with mean 5d lift `+0.00087` versus
  `insider_high_c16` and `-0.00308` versus `stock_down_high_c16`; 2025 lifts
  versus both were negative. Source anchors: `F348`, `D005`.

- [Session 264](session_264_log.md): Ran H386
  `official_delay_consumer_router` with reusable script
  `analysis/h386_official_delay_consumer_router.py`. TRUE walk-forward
  `2021-2025`, no `2026+`, fixed H385 official/forward supported states,
  train-before-test `K` choice only, deterministic candidate-rank selection,
  and random same-support plus random-all policy benchmarks. H386 FAILED:
  `official_supported` mean lift was `-0.00035` versus random-state and
  `-0.00540` versus random-all; `official_forward_supported` mean lift was
  `-0.00057` versus random-state and `-0.00555` versus random-all. Source
  anchors: `F347`, `D004`.

- [Session 263](session_263_log.md): Ran H385
  `official_attention_delay` with reusable script
  `analysis/h385_official_attention_delay.py`. TRUE walk-forward `2018-2025`,
  no `2026+`, fixed official/forward local-news states, C16 or insider support,
  and 1d/5d excess-return payoffs versus unsupported official/forward controls.
  H385 PASSED as delayed offline evidence: `official_supported` 5d lift
  `+0.007408`, `8 / 8` positive 5d-lift years, 2025 lift `+0.005566`;
  `official_forward_supported` 5d lift `+0.007657`, `8 / 8` positive years,
  2025 lift `+0.006799`. Source anchor: `F346`.

- [Session 262](session_262_log.md): Ran H384
  `news_flow_confirmation_consumer` with reusable script
  `analysis/h384_news_flow_confirmation_consumer.py`. TRUE walk-forward
  `2021-2025`, no `2026+`, fixed H383 states, train-before-test `K` choice
  only, and random same-support plus random-all candidate-policy benchmarks.
  H384 FAILED: `active_news_strong_flow` mean lift was `-0.00026` versus
  random-state and `-0.00337` versus random-all; `positive_news_strong_flow`
  mean lift was `-0.00020` versus random-state and `-0.00191` versus
  random-all. Source anchors: `F345`, `D003`.

- [Session 261](session_261_log.md): Ran H383 `news_flow_disagreement` with
  reusable script `analysis/h383_news_flow_disagreement.py`. TRUE walk-forward
  `2018-2025`, no `2026+`, fixed C16/news state definitions, primary target
  1d close-to-close relative return versus VNINDEX, and secondary S1 `actual`
  diagnostics. H383 PASSED as confirmation rather than disagreement:
  `active_news_strong_flow` rel IC `+0.10293`, `8 / 8` positive years, 2025
  `+0.12163`, and lift `+0.04005` versus strong-flow; `positive_news_strong_flow`
  was also strong at `+0.10854`. No-news and weak-flow disagreement states did
  not beat baselines. Source anchor: `F344`.

- [Session 260](session_260_log.md): Ran H382
  `h364_local_news_consumer_integration` with reusable script
  `analysis/h382_h364_local_news_consumer_integration.py`. TRUE walk-forward
  `2021-2025`, no `2026+`, train-before-test `K` choice only, and random
  candidate-policy benchmarks because this is not a direct S1/C16 variation.
  Script verdict PASSED on the primary same-support random-active benchmark:
  mean lift `+0.00092`, `4 / 5` years above random-active mean, and 2025 lift
  `+0.00296`. Caveat: broad random-all benchmark failed, mean lift `-0.00367`
  and only `1 / 5` years above random-all mean. Source anchors: `F343`, `D002`.

- [Session 259](session_259_log.md): Confirmed `ollama_guarded_backfill`
  complete, patched H364 to accept the authorized no-cutoff full Ollama
  backfill while filtering the audit to `2016-2025`, refreshed the combined
  local-news aggregate overlay, and ran H364. H364 PASSED: best fixed feature
  `h364_official_sentiment_x_earnings_guidance` had avg IC `+0.01766`,
  dev/validation/confirmation IC `+0.0173 / +0.0200 / +0.0156`, `10 / 10`
  positive years, S1 corr `-0.0104`, and `103,248` active rows. Source anchor:
  `F342`.

- [Session 258](session_258_log.md): Ran H381 `silent_order_pressure` with
  reusable script `analysis/h381_silent_order_pressure.py`. TRUE walk-forward
  `2018-2025`, no `2026+`, fixed no-news states, and direct C16 variation
  benchmarks. The branch FAILED: `silent_5d` C16 IC `+0.0700` was below all-C16
  `+0.0752` and active-5d-news C16 `+0.0846`; down-market no-news controls
  failed too. Removed `silent_order_pressure` from the active queue. Source
  anchors: `F341`, `D001`.

- [Session 257](session_257_log.md): Ran H380 `candidate_count_policy_router`
  as the narrowed PP5 continuation. Reusable script
  `analysis/h380_candidate_count_policy_router.py`, TRUE walk-forward
  `2021-2025`, no `2026+`, and random policy baselines only. Candidate-count
  router PASSED as offline policy evidence: mean cycle return `+0.00796` vs
  random K/cash `+0.00407`, lift `+0.00389`, `4 / 5` years above random
  K/cash mean, and 2025 lift `+0.00472`. Not live-promoted; 2021 failed and
  this remains policy state, not ticker alpha. Source anchor: `F340`.

- [Session 256](session_256_log.md): Added
  [portfolio_policy_library.md](portfolio_policy_library.md) as the sibling
  registry to `signal_library.md` for K/exposure/hold/veto/release state.
  Captured current surfaces, action vocabulary, policy-state feature families,
  active frozen policy components, H379 offline evidence, queued policy
  hypotheses, and the future `portfolio_policy_state_daily` promotion path.
  No experiment was run and no live branch changed.

- [Session 255](session_255_log.md): Ran H379
  `dynamic_candidate_thermodynamics` as the next queue item with reusable script
  `analysis/h379_dynamic_candidate_thermodynamics.py`. TRUE walk-forward
  `2021-2025`, no `2026+`, and random K-policy baselines only. The tiny
  date-level K/cash router PASSED as offline evidence: mean cycle return
  `+0.00665` vs random invested `+0.00508`, lift `+0.00157`, `4 / 5` years
  above random mean, 2025 lift `+0.00108`; not live-promoted because only
  `1 / 5` years beat random p95. Source anchor: `F339`.

- [Session 254](session_254_log.md): Bright-mind eureka refresh and live-state
  queue cleanup. Reconstructed current beliefs, verified the active
  `ollama_guarded_backfill` status at `6298 / 7344` batches, collapsed the stale
  multi-thousand-line hypothesis dump into a concise 10-item queue, and ranked
  new falsifiable branches around no-news order pressure, text-flow
  disagreement, official-delay confirmation, dynamic breadth, insider-down
  rescue, selection freshness, and post-Ollama event cascades.

- [Session 253](session_253_log.md): Superseded by S272. The original log
  claimed TRUE walk-forward validation passed for insider lead, consecutive
  down, and down-market C16, but S272 found the market/consecutive states were
  target-derived and the train/test protocol was not the advertised TRUE WF.
  Keep only the insider-lead survivor. Source anchors: `F355`, `D012`.

- [Sessions 248-252](session_248_252_log.md): Bright-mind eureka tests - **ALL 5 FAILED**.
  - S248 macro_c16_regime: FAILED (+0%) - no regime boost.
  - S249 gap_open_c16: FAILED (-4%) - no gap help.
  - S250 vol_shock: FAILED (data proxy insufficient).
  - S251 consecutive_down: FAILED (+0%) - no day-to-day compounding.
  - S252 c16_extreme: FAILED (-63%) - too sparse.
  - S272 later corrected the target-derived down-market/consecutive framing;
    keep only the non-leaky failed-filter conclusions here.

- [Sessions 245-247](session_245_log.md): C16 contrarian tests. S245 failed;
  S246/S247 down-market/deep-down promotions are superseded by S272 because
  their market states were derived from same-date S1 `actual`, not observable
  returns. Observable VNI-down context is only modest. Source anchors: `F355`,
  `D012`.

- [Session 244](session_244_log.md): S244 eureka tests - **5 signals tested**.
  - insider_buy_lead PASSED (+40% boost): IC=0.1113, still survives S272 at
    `+0.1050`.
  - c16_entropy FAILED (inconsistent year-to-year): WEAK - dead end.
  - disclosure_shock_reaction: NO DATA (empty source).
  - S272 invalidated the old `consecutive_down` promotion and downgraded
    dividend / rank-time acceleration to weak context. Source anchors: `F355`,
    `D012`.
- [Session 243](session_243_log.md): Calendar + combo tests.
- [Session 243](session_243_log.md): Calendar + combo tests.
  monday_jan_combo IC=0.1109 (+42% - STRONGEST!), feb_mid +10%, march_late +7%.
  yearend -16%, midyear -9% FAILED.
  x240_wf_ic_test.py reusable script updated.
- [Session 242](session_242_log.md): January effect + volume regime confirmation.
  january_first_10 IC=0.0817 (+5% boost), vol_high IC=0.0941 (+21%).
  Reusable x240_wf_ic_test.py script updated.
- [Session 232](session_232_log.md): Triple Storm Extensions — 6 PASSED, 3 FAILED.
  Universal: works on order/volume/reversal/skewness, NOT on position (foreign/sector).
  x232_triple_test.py reusable script.
  All signals 9/9 years positive. Triple Storm +92% in WF.
- [Session 230](session_230_log.md): Triple Storm HOLDOUT — CONFIRMED.
- [Session 229](session_229_log.md): triple_storm — **DISCOVERED** (+104%).
  Liquid + DOWN + divergence = IC +0.158 vs baseline +0.078.
- [Session 228](session_228_log.md): c16_divergence — WEAK PASS (+39%).
  Price disagree with C16 = IC +0.108 vs baseline +0.078 (+39%). Divergence works.
- [Session 227](session_227_log.md): c16_acceleration — FAILED.
  C16 level IC +0.078 vs ROC IC +0.056 (-28%). Level wins.
- [Sessions 224-226](session_224_226_log.md): New C16 branches.
  X224 sector-relative: FAILED (-15%). X225 persistence: FAILED (-17%).
  X226 market-state: PASSED - C16 +26% stronger in DOWN markets (+0.098 vs +0.056).
- [Session 223](session_223_log.md): sector_convergence_contrarian — FAILED.
  Fragmented + high C16: IC +0.035 vs baseline +0.078 (-55%).
  Kill branch.
- [Session 222](session_222_log.md): dynamic_liquidity_regime — WEAK PASS.
  High market regime: +0.081 vs Low: +0.074 (diff +0.007, ~8%)
  Not enough for regime switching, could use for sizing only.
- [Session 221](session_221_log.md): liquid_braid_stack TEST — MIXED.
  X53 (liquid): +25% IC ✅. X54 (braid): +3%. Stack: -18% ❌.
  Stacking FILTERS HURTS. Use X53 alone, not both.
- [Session 220](session_220_log.md): X51-X55 stochastic resonance batch - SUPER PASS.
  X53 (Liquid C16): C16 + high move >80%ile = IC +0.137 (+52% vs baseline +0.090).
  X54 (Braid): Low sector kurtosis = unanimous pressure = IC +0.080 vs +0.031 (+160%).
  Scripts: x51, x52, x53v2, x54, x55.
- [Session 219](session_219_log.md): H365-H378 + X1-X5 batch — ALL FAILED except C16 baseline.
  Tested: H372 (vol→price), H373 (sector), H374 (early session), H375 (ROC), H377 (curvature), X1 (auction), X2 (exhaustion), X5 (lunar). C16 remains champion +0.077 to +0.084.
- [Session 218](session_218_log.md): X72 volume regime — FAILED (c8 combo hurts C16).
- [Session 217](session_217_log.md): X75 Benford Law — FAILED (IC +0.0023).
- [Session 216](session_216_log.md): H366 order+ceiling — FAILED.
- [Session 215](session_215_log.md): H367 order+gap — FAILED.
- [Session 214](session_214_log.md): H365 C16 standalone — PASSED.
  C16 standalone beats full_library baseline on val IR 1.98 (vs 0.85), val ret +1.47%
  (vs +0.45%), clean execution health. PASSED as offline evidence.

- [Session 212](./session_212_log.md): Recovered the evergreen loop while
  `ollama_guarded_backfill` was running, found the active run had reverted to
  an empty cutoff and the non-lockbox `146,872`-row input, stopped it before it
  reached the known post-2025 tail, verified the `120` newly appended score
  cache rows were all Dec 2023, and relaunched the checkpoint-safe
  `--max-published-at 2025-12-31T23:59:59+07:00` command. The corrected input
  manifest is back to `142,296` rows with `4,576` date-filtered articles, H364
  readiness now blocks until the final Ollama ticker-day dataset exists, and
  H364 was hardened to reject missing lockbox cutoffs.

- [Session 211](./session_211_log.md): Resumed the guarded Ollama residual
  backfill at the user's request, but first found that the existing input cache
  included a `2026` tail. Added a cutoff-aware `--max-published-at` path,
  rebuilt the input cache to `142,296` rows with max timestamp
  `2025-12-31T20:40:05+07:00`, launched `ollama_guarded_backfill` in tmux with
  `2026+` excluded, then stopped it for the day at `3,638 / 7,115` checkpoint
  batches and `72,760 / 142,296` processed input rows. H364 is prepared as the
  fixed combined local-news audit to run after completion.

- [Session 210](./session_210_log.md): Stopped the guarded Ollama residual
  backfill at the user's request. The tmux job session closed, no
  `build_ollama_guarded_features` process remained, `qwen2.5-coder:3b` was
  unloaded from Ollama, and the status file was marked `stopped_by_user` at
  `2281 / 7344` checkpoint batches with `45,620` processed input rows.

- [Session 209](./session_209_log.md): Implemented and ran H363 Vietnam legal
  holiday timing. The calendar builder generated `436` 2015-2025 sparse
  pre/post trading-day rows across `53` VNINDEX-inferred closure clusters with
  no `2026+` leakage. Matched payoff found one passing state,
  `all_holidays__post_5`, but the single fixed `+0.015` sparse portfolio bonus
  produced `0.00% / 0.00%` validation/confirmation relative deltas and failed
  the portfolio gate, so legal-holiday timing stays offline evidence only.

- [Session 208](./session_208_log.md): Resumed the guarded Ollama residual
  backfill in tmux from the Session 207 checkpoint, then completed two
  scheduled 5-minute watchdog checks. Latest status was healthy/running at
  `780 / 7344` checkpoint batches, `15,600` processed rows, with
  `qwen2.5-coder:3b` loaded at about `2.3GB` VRAM.

- [Session 207](./session_207_log.md): Stopped the guarded Ollama residual
  backfill at the user's request, verified the tmux session and Ollama model
  runner were gone, updated `live_state.md`, then prepared the repository for
  commit and push.

- [Session 206](./session_206_log.md): Added the session closeout checklist,
  `Last verified` marker, and strict compact source-anchor rule to the repo
  memory stack and `manh-memory-system`; also verified the guarded Ollama
  backfill is still running at `744 / 7344` checkpoint batches.

- [Session 205](./session_205_log.md): Made the `live_state.md` contract
  explicit: current state, active constraints, immediate next actions,
  do-not-reopen conditions, and pointers. Tightened this repo's live-state file
  from a branch ledger into a short operational brain, and updated
  `manh-memory-system` to require immediate next actions inside `live_state.md`.

- [Session 204](./session_204_log.md): Renamed the alpha-lab live-state note to
  `live_state.md`, updated repo pointers and historical note links, and
  upgraded `manh-memory-system` so fresh repos prefer `live_state.md` while
  grandfathering coherent legacy names.

- Memory note migration (2026-04-28): Added compact full-history findings and
  derived dead-end recovery views in
  [findings_compact.md](./findings_compact.md) and
  [deadends_compact.md](./deadends_compact.md), keeping chunked
  `findings-*.md` files as the append-only source of truth. Source anchor:
  [Session 206](./session_206_log.md) reconciliation of the prior unsourced
  compact entry.

- [Session 203](./session_203_log.md): Ran H362 as the dividend pre-ex sparse-clock portfolio reopening test. The fixed calendar bonus failed the portfolio gate, so dividend-clock timing remains offline evidence under the current selector contract.

- [Session 202](./session_202_log.md): Ran H361 as the strict event-v2 sparse-clock portfolio reopening test. The fixed event bonus failed the portfolio gate, so event-v2 remains parked under the current target and executable selector contract.

- [Session 201](./session_201_log.md): Ran H360 as a fixed published-contract parity audit. The published C16 artifact reproduced the H359 winner within floating-point noise and still passed portfolio plus execution-health gates.

- [Session 200](./session_200_log.md): Published the scoped C16 order-pressure artifact at `data/features/xs_order_pressure_daily.parquet`, registered it in `shared-recommendation`, and updated producer/consumer docs while keeping RL and recommendation defaults unchanged.

- [Session 199](./session_199_log.md): Ran H359 as the bounded C16 sizing / state-scope audit. The scoped 5% order-pressure blend on next-open-buyable rows passed both portfolio and execution-health gates, which led to the Session 200 publisher work.

- [Session 198](./session_198_log.md): Resumed the stalled guarded Ollama residual backfill from stale `505 / 7344` checkpoint state and ran H358. Order pressure had strong executable portfolio relevance, but the equal-weight full-library addition was `MIXED` because validation cash drag narrowly breached the health limit.

- [Session 197](./session_197_log.md): Ran H357 as the H356 integration audit. Order pressure survived full-library residualization and improved the frozen label-level selector; H358 completed the required portfolio/tradability review, and H359 / Session 200 later promoted the scoped contract.

- [Session 196](./session_196_log.md): Ran H356 as a CPU-only standalone order-pressure gate while the Ollama residual backfill continued. CafeF posted order-volume pressure passed strongly as a broad candidate signal; H357-H359 and Session 200 are the current follow-up evidence.

- [Session 195](./session_195_log.md): Resumed the guarded Ollama residual backfill in tmux after confirming the previous status heartbeat was stale. The job advanced from `12 / 7344` to `100 / 7344` batches on the later watchdog check and is now the single active heavy local-model job.

- [Session 194](./session_194_log.md): Ran H355 as the order-pressure step-hazard audit. CafeF order pressure helped some smart-exit metrics, but the improvement over H337 was too small to solve the H337/H339 blocker.

- [Session 193](./session_193_log.md): Ran H354 as the dividend-clock payoff audit. The 20-day pre-ex window has a small local payoff hint, but no dividend-clock state cleared the validation / confirmation payoff and risk gate.

- [Session 192](./session_192_log.md): Ran H353 as the H340 entry-label transfer audit. H340 remains the preferred daily-state C5 rewrite, but it is not a clean entry-alpha prior: the loose gate lost confirmation return lift and the strong support state did not beat raw C5 in validation.

- [Session 191](./session_191_log.md): Ran H352 as the event-v2 optionality payoff audit. Event states showed upside-tail hints, but the payoff distribution was not clean enough: downside tails worsened and confirmation mean lift was negative for the best state.

- [Session 190](./session_190_log.md): Ran H351 as the sector ownership-pressure audit. Sector-level foreign pressure and ownership states failed; the current-data H95 flow branch is now closed under this target.

- [Session 189](./session_189_log.md): Ran H350 as an official-disclosure source gate. The HNX universe is wired, but the current disclosure history is a two-ticker current sample with no pre-2026 rows, no transaction extracts, and no usable HOSE bridge.

- [Session 188](./session_188_log.md): Ran H349 as the first high-value queue experiment. The H321 cascade state failed to transfer to the entry-alpha label contract: validation and confirmation matched return lifts were both negative.

- [Session 187](./session_187_log.md): Ran H348 as a limited-source proprietary-flow conflict/agreement pilot. The best row cleared 2023 dev, then flipped negative in 2024 and 2025, so proprietary-flow rank variants should not continue on this target.

- [Session 186](./session_186_log.md): Ran H347 as a CPU-only foreign-flow interaction pass. Foreign agreement improved raw `C5`, but did not beat the stronger H340 order-pressure rewrite. Keep it as offline interaction evidence only.

- [Session 185](./session_185_log.md): Ran H346 to close the stale residual long-horizon reversal queue item. The sign-flipped residual after removing C11 failed; the continuation residual was directionally positive but below gate. Signal-library stale H135/H136/H137 rows were cleaned up.

- [Session 184](./session_184_log.md): Ran H345 as a CPU-only CafeF foreign-flow continuation. Accumulation / ownership-change change-points failed the unchanged foreign-flow gate, so standalone H95 tuning should stop unless a distinct interaction contract is introduced.

- [Session 183](./session_183_log.md): Ran H343/H344 as CPU-only existing-data audits. H343 showed official-conditioned PhoBERT sentiment clears the broad standalone gate, but H344 failed it as a standalone promoted signal under 2025 confirmation.

- [Session 182](./session_182_log.md): Ran an evergreen artifact-only queue pass while the Ollama residual backfill continued as the active heavy job. H340/H341/H342 were treated as solved existing hypotheses rather than reopened.

- [Session 181](./session_181_log.md): Added row-level Ollama score caching and checkpoint-cadence migration so `checkpoint_rows` changes no longer invalidate expensive scoring outputs.

- [Session 179](./session_179_log.md): Optimized the local Ollama residual prompt under the hardware cap. The safe default is bottom-schema event-family-only JSON with `num_ctx=512` and first-300-word article truncation. A BERT-gated checkpointed backfill is running in `tmux` as `ollama_guarded_backfill`.

- [Session 178](./session_178_log.md): Completed the repaired local PhoBERT `article_scope` and `source_type` train/publish sequence on CUDA with mid-epoch train checkpoints, resume-safe publish checkpoints, and artifact sanity checks confirming the published parquets use the new trained model ids.

- [Session 177](./session_177_log.md): Repaired the semantic binary-head contract so `article_scope` and `source_type` no longer inherit the forward-looking date split and hard `0.5` threshold blindly. Binary-head training now calibrates a per-head decision threshold on validation, publish uses that saved threshold, and `article_scope` defaults to a stratified article-level split with positive class weighting enabled.

- [Session 176](./session_176_log.md): Upgraded binary-head publish to the same shard-checkpoint/finalize contract already used by forward-looking publish, with a focused resume test covering the article-scope lane.

- [Session 175](./session_175_log.md): Confirmed the real WSL runtime sees the RTX 3050 GPU outside the restricted sandbox, then hardened heavy PhoBERT train/publish paths to fail fast when `/dev/dxg` is hidden instead of silently falling back to CPU.

- [Session 174](./session_174_log.md): Moved the offline PhoBERT runtime guard into repo code so the main local PhoBERT commands no longer rely on shell-level offline prefixes.

- [Session 173](./session_173_log.md): Tightened the binary-head trainer so it mirrors the forward-looking lane's local-first runtime posture and epoch-level observability.

- [Session 172](./session_172_log.md): Added repo-native PhoBERT `article_scope` and `source_type` head paths by reusing the forward-looking staged binary-head pattern.

- [Session 171](./session_171_log.md): The news pipeline now defaults to a local-first contract: PhoBERT for sentiment and forward-looking, minimal Ollama residual semantics, and no hosted API dependency in the default local-news path.

- [Session 168](./session_168_log.md): Targeted long-job scripts under `data_tools/` now expose canonical restart-safe job-status files and stricter durable resume boundaries.

- [Session 167](./session_167_log.md): Repo-local planning assumptions are now explicitly constrained to `3GB VRAM / 10GB RAM` for safe local-ML work.

- [Session 166](./session_166_log.md): The first real PhoBERT forward-looking canary forced two runtime repairs and established the current watchdog and stage-manifest flow.
