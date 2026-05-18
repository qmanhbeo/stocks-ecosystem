# Dead Ends Compact

What this file is for: compact recovery notes for durable failed, parked,
closed, blocked, or explicitly non-promotable paths. The chunked source of
truth now starts at [deadends.md](./deadends.md); older entries before that
index are derived from chunked findings and session logs.


Do not add a path here just because one test was mixed. Add it when the durable
record says the current path should stop, stay parked, or reopen only under a
specified changed condition. Keep links to source `F` IDs so the original
evidence remains traceable. Every compact dead-end entry must include source
anchors: stable dead-end IDs, finding IDs, or source session links.

## Resolution: Triple-Factor Stack Fails To Beat Composite Baseline (D083)

- H609 triple_factor_alpha_portfolio is D083. The queue-109 triple
  (`composite_2plus × cofire_q1_c23 × persist_q4`) underperforms the base
  `composite_2plus` contract.
- `triple_factor_109 IC=0.2172` vs `composite_2plus IC=0.2445` (lift `-0.0273`).
- Pairwise stacks are also weaker than base (`composite_2plus_cofire_q1=0.2224`,
  `composite_2plus_persist_q4=0.2424`).
- Keep `composite_2plus` as local champion; do not reopen this exact triple
  unless state definitions change materially.
- Source: [session_00395_log.md](./session_00395_log.md).

## Resolution: Transition Timing Adds No Edge Over Sustained Low-Breadth (D084)

- H610 regime_transition_timing_alpha is D084. Transition day into low breadth
  does not beat sustained low-breadth days for `composite_2plus`.
- `composite_2plus_transition_low IC=0.2793` vs
  `composite_2plus_sustained_low IC=0.2797` (lift `-0.0004`).
- Keep breadth as a level/filter regime; do not treat transition timing itself
  as additive alpha under this contract.
- Source: [session_00396_log.md](./session_00396_log.md).

## Resolution: Blocked Score Multiplier Degrades Baseline Signal (D085)

- H611 implementation_pain_position_sizing is D085. Scaling blocked names by
  `1.5x` on score hurts rather than helps.
- Baseline IC `0.1302` vs blocked-sized IC `0.1292` (lift `-0.0010`).
- Keep blocked-state logic as filter/context features, not naive multiplicative
  score sizing.
- Source: [session_00397_log.md](./session_00397_log.md).

## Resolution: Breadth Score-Scaling Collapses Baseline Signal (D086)

- H612 market_regime_position_multiplier is D086. Breadth exposure multipliers
  (`low=1.5x`, `high=0.5x`) severely degrade IC.
- Baseline IC `0.1298` vs breadth-scaled IC `0.0769` (lift `-0.0529`).
- Keep breadth as a discrete regime filter, not a global score multiplier.
- Source: [session_00398_log.md](./session_00398_log.md).

## Resolution: Dispersion Regime Lift Is Directional But Not Robust (D087)

- H613 cross_sectional_dispersion_regime is D087. Low-dispersion composite
  outperforms high-dispersion composite (`+0.0167`) but fails robustness gates.
- Sparse support (`low years=5`, `high confirmation rows=29`) makes it
  non-promotable under current contract.
- Treat as directional hint only; reopen only with stronger out-of-sample
  support or denser state support.
- Source: [session_00399_log.md](./session_00399_log.md).

## Resolution: Concentration × Breadth Interaction Is Directional But Too Sparse (D088)

- H615 signal_concentration_breadth_interaction is D088. Best low-breadth
  interaction state beats best high-breadth state (`+0.0260` IC), but support
  is too sparse for promotion.
- Best-high regime has only `2` yearly points and `3` confirmation rows.
- Keep as directional evidence only; reopen with denser state support.
- Source: [session_00401_log.md](./session_00401_log.md).

## Resolution: Multi-Signal Coherence Tie Is Non-Actionable (D089)

- H616 multi_signal_temporal_coherence is D089. Coherent and mixed-direction
  `composite_2plus` states are effectively tied.
- Coherent IC `0.1957` vs mixed IC `0.1955` (lift `+0.0002`).
- No incremental edge under current direction semantics; keep parked.
- Source: [session_00402_log.md](./session_00402_log.md).

## Resolution: Continuous Breadth Scaling Fails Despite Quintile Gradient (D090)

- H617 breadth_scale_signal_strength is D090. Quintile map shows directional
  degradation from low to high breadth, but continuous score scaling fails
  catastrophically.
- Binary gate IC `0.2694` vs continuous-scaled IC `0.0878`
  (lift `-0.1816`).
- Keep breadth as a discrete gating axis; do not use naive continuous scaling.
- Source: [session_00403_log.md](./session_00403_log.md).

## Resolution: Post-Spike Recovery Timing Degrades Low-Breadth Baseline (D091)

- H619 post_breadth_spike_recovery_timing is D091. Adding post-spike recovery
  timing to `composite_2plus × low_breadth` hurts the baseline.
- Baseline IC `0.2694` vs post-spike combo IC `0.2581` (lift `-0.0113`).
- Keep low-breadth baseline without post-spike recovery gating.
- Source: [session_00405_log.md](./session_00405_log.md).

## Resolution: Implementation-Pain Multi-Signal Triple Underperforms Baseline (D092)

- H620 implementation_pain_multi_signal_triple is D092. Blocked-state overlays
  on `composite_2plus` underperform or remain sparse.
- `composite_2plus_blocked_either IC=0.1660` vs `composite_2plus IC=0.2445`
  (lift `-0.0785`), while `blocked_day_2_3` intersection stays data-gated.
- Keep blocked-state logic separate from multi-signal concentration contract.
- Source: [session_00406_log.md](./session_00406_log.md).

## Resolution: Per-Signal Breadth Threshold Drift Is Too Small To Promote (D093)

- H621 finds threshold heterogeneity (C25 prefers `30%`, others `20%`) but the
  mean lift over the common `20%` gate is only `+0.0061`.
- Keep the current common low-breadth gate; do not add per-signal threshold
  branching under this contract.
- Source: [session_00407_log.md](./session_00407_log.md).

## Resolution: Magnitude Overlay Is Redundant On Composite Count (D094)

- H622 shows magnitude-weighted states do not improve `composite_2plus`.
- Best magnitude state ties baseline (`0.2456`), tighter cuts degrade.
- Keep binary multi-signal count; park magnitude weighting.
- Source: [session_00408_log.md](./session_00408_log.md).

## Resolution: Conflict-vs-Coherent Split Is Non-Actionable (D095)

- H623 shows conflict is only marginally higher than coherent
  (`+0.0020` IC lift).
- No actionable routing edge from this split under current semantics.
- Source: [session_00409_log.md](./session_00409_log.md).

## Resolution: Calendar×Breadth Interaction Is Sub-Threshold (D096)

- H624 weekday-conditioned low-breadth states add only `+0.0077` over generic
  low-breadth baseline.
- Do not add calendar branching to the low-breadth multi-signal path.
- Source: [session_00410_log.md](./session_00410_log.md).

## Resolution: Ticker Self-Reference Lift Is Weak (D097)

- H625 self-history-hot context beats market-low breadth by `+0.0069`, below
  promotion threshold.
- Keep as weak context evidence only; not a promoted state rule.
- Source: [session_00411_log.md](./session_00411_log.md).

## Resolution: 31+ Decay Zone Unsupported (D098)

- H626 cannot validate a `31+` persistence bucket (`0` rows), so decay/flip
  beyond 30 cannot be promoted.
- Current structure is front-loaded (`1-7` strongest), not an actionable
  post-30 exit zone.
- Source: [session_00412_log.md](./session_00412_log.md).

## Resolution: Breadth-Expansion Adaptive Exit Harms Returns (D099)

- H627 adaptive breadth-expansion exit underperforms fixed 5-day hold:
  `0.0084` vs `0.0119` mean return (lift `-0.0035`).
- Keep fixed-hold baseline; do not promote breadth-expansion exit.
- Source: [session_00413_log.md](./session_00413_log.md).

## Resolution: Remaining Queue Backlog Produced New Negative/Data-Gated Paths (D100-D110)

- Session 415 closed numbered backlog items and rejected several branches:
  first-activation onset (D100), tight+blocked channel (D101), spread
  concentration proxy (D102), zero-cofire edge (D104), low-breadth per-signal
  extreme rule (D105), and persistent-low breadth superiority (D107).
- Session 415 also marked three items data-gated under first-pass support:
  vol-depth split (D103), accumulation×low-breadth (D106), and
  tight×high-accumulation interaction (D108).
- Session 416 backlog tests parked multiple wake/sleep and traffic ideas as
  failed (D109) or data-gated due macro/sector contract gaps (D110).
- Source: [session_00415_log.md](./session_00415_log.md),
  [session_00416_log.md](./session_00416_log.md).

## Resolution: Formalized Retests Closed Remaining High-Priority Ambiguities (D111-D112)

- Session 417 (`H644`) converted prior data-gated high-priority items into
  formal outcomes: queue `100` is now explicit FAIL (`D111`) and `BM17` is now
  explicit FAIL (`D112`).
- Historical data-gates `D103` and `D108` are superseded by Session 417 pass
  outcomes on queue `91` and queue `103`.
- Source: [session_00417_log.md](./session_00417_log.md).

## Resolution: Continuous Breadth Weighting Fails (D046)

- H530 breadth_weighted_position_sizing is D046. Continuous 1/breadth weighting does NOT beat binary filter.
- weighted_score (S1 × inv_breadth) IC=0.1057 is WORSE than baseline (-0.0220). Direct multiplication amplifies low-breadth signals too much, distorting rank.
- weighted_rank (rank of weighted score within date) IC=0.1407 (+0.0130) beats baseline but still slightly below binary filter (0.1428).
- Binary low_breadth filter remains the superior implementation. Do not reopen with continuous weighting.
- Source: [session_00343_log.md](./session_00343_log.md).

## Resolution: Quiet + Low-Breadth Intersection Is NOT Promotion-Worthy (D082)

- H528 quiet_low_breadth_intersection is D082 (partial). Quiet (rank >= 0.75) + low_breadth dates intersection IC=0.1644 beats min component (0.1542) but does NOT exceed max + 0.01 threshold (needs 0.1652). The intersection is NOT promotion-worthy as a signal filter.
- HOWEVER: Active (rank < 0.2) + low_breadth dates intersection shows SIGNIFICANT improvement: IC=0.2013 beats active alone (0.1597) by +0.0416 (+26% boost). This is a regime amplifier finding, not a dead end.
- Low-breadth dates act as a positive regime amplifier for active-state signals. Use as positive filter (select low-breadth dates), not negative (exclude high-breadth).
- Source: [session_00341_log.md](./session_00341_log.md).

## Resolution: LAR Ratio Is Anti-Predictive

- H472 liquidity_adjusted_return (AL queue) is killed. Return / Amihud illiquidity ratio
  is ANTI-predictive as a standalone ranker: high LAR (Q5) = IC 0.087 (-0.032 lift) vs
  baseline 0.119. The mechanism is inverted: "high return + low Amihud" (high LAR) = liquid
  crowd chase (negative), while "high return + high Amihud" (return_5d_pos_illiq) = illiquid
  momentum (IC 0.163, +0.044 lift) = C23-style effect, not independent flow quality. The ratio
  collapses two correlated effects into one confusing metric that loses to raw components.
  Do not reopen LAR ratio as standalone ranker. Use Amihud LEVEL (C23) as the signal, not
  the return/Amihud ratio. Source: [session_00121_log.md](./session_00121_log.md).

## Resolution: Quiet-State Inverse Alpha Has No Contrarian Effect

- H527 quiet_state_inverse_alpha (queue item 9) is killed. Quiet stocks in high-breadth dates (IC=0.1248) vs low-breadth dates (IC=0.1225) lift only +0.0022, below 0.01 threshold. Market activity level does NOT meaningfully modulate quiet-stock quality. Confirms state_quiet alone is still strong (IC=0.1205, 11/11 positive years). Do not reopen as contrarian filter. Source: [session_00340_log.md](./session_00340_log.md), D081.

## Resolution: Exit Timing Has No Alpha

- H526 exit_timing_discovery (queue item 8) is killed. Holding duration does NOT predict different IC:
  - Fresh entry (first day in C23): IC=0.1693 (11/11 positive years)
  - Sustained (day 2+ in C23): IC=0.1712 (11/11 positive years)
  - Fresh vs sustained lift: -0.002 (essentially NO difference)
  - Exit (first day out of C23): IC=0.1386 - weaker but not enough to matter
  - All timing states beat baseline (0.1277) by +0.042
  - Interpretation: Signal works equally well at entry and as sustained position. Holding duration is noise, not signal. Do not reopen exit-timing as alpha source. Source: [session_00339_log.md](./session_00339_log.md), D080.

## Resolution: Acceleration/Momentum Signals Are Dead-End

- H449 order_flow_momentum is D037 for acceleration signals. C16 ACCELERATION (second derivative) is NOT predictive — c16_accel_expanding IC=0.1219 (-0.0069 lift), c16_accel_neutral IC=0.1287 (-0.0001), c16_accel_contracting IC=0.1303 (+0.0015) ALL WORSE or equal to baseline. Confirms H443 pattern: foreign flow momentum also NEGATIVE (ff_accel_exp IC=0.1243). Confirms H446/H447: vol LEVEL matters, not vol CHANGE. The edge comes from LEVELS (high pressure, high volume), not MOMENTUM (changes in pressure/volume). Use C16 level as regime conditioner, not its derivative. Dead-end D037 for all acceleration/momentum signals. Source: [session_00120_log.md](./session_00120_log.md), D037.

- H428 bid_ask_midbook_imbalance is D022. Higher buy/sell volume imbalance was hypothesized to proxy hidden depth but instead correlates with WEAKER C16 signal (Q5 vs Q1 IC lift -0.0385 dev, -0.0116 val). Direct prediction vs S1 is weakly positive (IC +0.0194 dev, +0.0373 val) but below IC > 0.05 threshold. Interpretation: high imbalance indicates weakness, not hidden depth. Do not reopen as C16 conditioner or standalone signal. Source anchor: Session 307, D022.

## Resolution: Signal Combination Skepticism

- H508 router_equivalence_ablation closes standalone-primitive claims for
  freshness, cofire, and low-C16 router outside the C23 core regime. Residual
  tests found zero support rows for `fresh_not_c23`, `cofire_not_c23`, and
  `lowc16_not_c23` (nested by construction), while C23 retained positive
  residual IC after removing freshness. Treat these as router/timing layers on
  C23, not independent primitives. Reopen only if a materially different state
  definition yields non-nested support. Source: [session_00139_log.md](./session_00139_log.md).

- H465 cross_signal_orthogonality_audit is D036. Signals C20/C21/C22 are NOT orthogonal — all combos are WORSE than best individual. C21a×C22 IC=0.2119 (-0.0115 vs max), C20×C22 IC=0.1997 (-0.0169 vs max). vol_expansion is the common regime driver making signals redundant when combined. Do NOT create composite signals from C20/C21/C22. They are additive in portfolio sense (different days fire) not combinatorial. Source: [session_00117_log.md](./session_00117_log.md), D036.

- H449 vol_contraction_mean_reversion is dead-end for direct long-only use. Pattern confirmed real (vol_contraction + high_return = mean reversion with IC=-0.0255), but the direction is wrong for long-only: vol_expansion_momentum IC=+0.0373 is positive while vol_contraction_exhaustion is negative. Use vol_expansion_momentum side (positive), do not use exhaustion pattern as buy signal. Source: [session_00105_log.md](./session_00105_log.md), D032.

- H447 volume_adjusted_price_momentum "real force" hypothesis is killed. Original hypothesis: high return + high volume = "real force" (positive), high return + low volume = "fade" (negative). OPPOSITE found: high_return_high_vol (real_force) IC=0.111 (-0.019 lift) UNDERPERFORMS baseline. The volume-adjusted framework works but direction is inverted: low_return_low_vol (cheap moves/contrarian) is the STRONGEST state at IC=0.204 (+0.0746 lift). This is a CONTRARIAN signal, not momentum. Use low_return_low_vol as contrarian conditioner if desired, but do not use high_return_high_vol as "real force" - it's dead. Source: [session_00103_log.md](./session_00103_log.md), D031.

- H445 semantic_novelty_saturation is killed (NEGATIVE result). News article counts (PhoBERT) are NOT predictive - they DEGRADE S1 signal quality. All news states have NEGATIVE IC lift vs baseline. "no_news" (IC=0.1409) actually beats "has_news" (IC=0.1038) by +0.037. Exhaustion state (repeat coverage + high attention) is worst at -0.0474 lift. Raw article counts are not useful as standalone signals. Continue using source-type and sentiment features which H440/H383 found useful. Do not reopen with raw count features. Source: [session_00101_log.md](./session_00101_log.md), D030.

## Resolution: Sector Vol Regime Marginal

- H506 sector_vol_regime (BU5) is parked as MIXED. sector_c23 (sector >50% stocks in vol_expansion × C23) marginally beats always_c23 (IC 0.2223 vs 0.2176, +0.0046) BUT the state is extremely sparse (2,853 rows, only 2/11 positive years). Validation and confirmation phases have NaN due to insufficient data. The pattern is similar to cofire_2 (sector-level co-occurrence = stronger signal) but too sparse to be useful. D033 killed sector MOMENTUM; sector VOL regime is marginally better but not robust enough to act on. Park and do not reopen without different sampling or data. Source: [session_00138_log.md](./session_00138_log.md), F424.

## Resolution: Sentiment Filter Skepticism

- H482 sentiment_scope_filter is D040. Ultra_negative (bottom 5% prob_neg from H480) does NOT filter S1 quality. Filter effect is +0.0034 IC (below +0.01 pass threshold). S1 WITH ultra_negative: IC 0.1006, S1 WITHOUT ultra_negative: IC 0.1040. S1 is ROBUST across sentiment regimes - quality is similar whether ticker has ultra-negative news or not. The hypothesis that "sentiment extremes identify noise states" is NOT supported. Do NOT use ultra_negative as a signal quality gate. Source: [session_00131_log.md](./session_00131_log.md), D040.

- H443 prop_foreign_predator_prey is killed. Predator-prey interaction between foreign and proprietary flows does NOT add predictive value. All states (ff_sell_pt_buy_absorption IC=0.0621, ff_buy_pt_sell_distribution IC=0.0959, prop_follow_ff IC=0.0842) are BELOW baseline IC=0.1335. Raw foreign flow (ff_buy IC=0.1188, ff_sell IC=0.1004) also underperforms baseline. Flow direction alone is not predictive - S1 already captures any useful information from these flows. Do not reopen unless materially different data or representation. Source anchor: [session_00323_log.md](./session_00323_log.md), D029.

- S253 methodology resolution is superseded by S272. S272 found the S244/S246/S247/S253
  market-down and consecutive-down claims used same-date S1 `actual` to define
  regimes even though `actual` is a future binary barrier label. The leaky
  states reproduced high ICs, but observable VNI-down states were only modestly
  above C16 and observable stock-down states were weaker. Keep insider lead;
  do not use S253 to promote `consecutive_down`, target-derived
  `down_market_c16`, or `deep_down_c16`. Source anchors: `F355`, `D012`.

- Midbook imbalance promotion is killed under H428. Higher buy/sell volume
  imbalance was hypothesized to proxy hidden depth but instead correlates
  with WEAKER C16 signal (Q5 vs Q1 IC lift -0.0385 dev, -0.0116 val).
  Direct prediction vs S1 is weakly positive (IC +0.0194 dev, +0.0373 val)
  but below IC > 0.05 threshold. Interpretation: high imbalance indicates
  weakness, not hidden depth. Do not reopen as C16 conditioner or standalone
  signal. Source anchor: Session 307.

- S1 rank degradation hypothesis is killed under H428 (ranker_error_taxonomy).
  Top S1 quintile tickers do NOT decay in next-day IC - they actually IMPROVE
  by +0.0263 lift. This is the opposite of hypothesized mean-reversion. Q3 (mid)
  is the weakest pocket (-0.0230), not top. Do not use S1 rank as error-state
  indicator. Reopen only with materially different quality/continuation proxy.
  Source anchor: [session_00307_log.md](./session_00307_log.md), D023.

- Signal half-life routing hypothesis is killed under H429. Pre-declared half-life
  classes (S1 momentum vs reversion, vol_high vs vol_low) do NOT show horizon-specific
  advantage. All classes degrade at longer horizons - 1d baseline is always best.
  vol_low becomes negative at 5d+ horizons. Do not route signals to different
  horizons based on half-life characteristics. Reopen only with materially different
  horizon definition or target. Source anchor: [session_00308_log.md](./session_00308_log.md), D027.

- Volume-price divergence hypothesis is killed under H432. Return vs volume-z
  divergence states do NOT capture hidden pressure - all states have negative
  lift vs baseline (real_force -0.0261, fade -0.0289, hidden_support -0.0791,
  crowded -0.0705). Energy conservation hypothesis doesn't translate to alpha.
  Source anchor: [session_00311_log.md](./session_00311_log.md), D026.

## Current Hard Stops

- Forced-seller detector promotion is killed under H426's current daily
  entry-alpha consumer. Fixed buyable forced-seller states from price weakness,
  volume spike, sell-order pressure, rising/high avg sell size, floor pressure,
  and no active bad PhoBERT news did not beat random policies: the broad core
  had only `+0.000230` lift versus random-state, `1 / 5` positive WF years,
  and `-0.002047` lift versus random-all; floor and large-down variants also
  failed, while literal tradability release had only `7` rows. Reopen only
  with an honest delayed-entry protocol for a post-sell-pressure C16 turn or
  materially different intraday/queue/open-fill absorption data. Source
  anchors: `D021`, [session_00304_log.md](./session_00304_log.md).

- Broad anti-signal veto promotion is blocked under H401. Top-5 cash-veto
  masks based on loose side-channel disagreement reduced cycle relative return
  versus no-veto: `support_count_le1` `-0.000123`,
  `pretty_price_weak_flow` `-0.000026`, `news_hype_weak_flow` `-0.000075`,
  and `weak_flow_weak_sector` `-0.000225`. Only strict `support_count_zero`
  survived as a tiny clue (`+0.000167` vs no-veto), below promotion and random
  p95. Source anchors: `D017`, `F365`.

- Order fragmentation promotion is parked under H402. Fragmentation ratio
  (log order-count / log order-volume) added only marginal IC beyond C16
  (+0.00753) with poor year consistency (2/8 positive years). C16 itself
  was negative IC in this period, so the lift is marginal. Avg buy-minus-sell
  size is the strongest standalone proxy (+0.03033 IC) but needs high-C16
  conditioning or materially different queue/open-fill data. Source anchors:
  `D018`, `F366`.

- Haar wavelet cascade promotion is killed under H404. C16 wavelet energy at scales
  1/2/4/8 days added no signal beyond C16 level. Haar 2d IC was only
  -0.00447 with 3/8 positive years, Haar jump 2->4 was +0.00491,
  and Haar energy sum was +0.00501. This confirms prior C16 acceleration
  failures - scale derivatives are not the edge. Reopen only with materially
  different wavelet basis or non-C16 base series. Source anchors: `D019`, `F368`.

- Sector event lightcone is killed under H405. Both own-ticker and sector-peer
  event intensity added negative IC (own: -0.00481, sector: -0.00698, both 0/8 pos years).
  Confirms prior news/event feature failures. Reopen only with materially different
  sector or event representation. Source anchors: `D020`, `F369`.

- Conservation law residual is killed under H406. Expected from flow predicts forward
  at +0.00983 IC (3/3 pos years) but residual inversely predicts (-0.02861 IC, 0/3 pos years).
  The model captures flow in expected; residual is mean-reverting noise. Do not reopen as
  conservation-break alpha. Source anchors: `D021`, `F370`.

- Fixed calendar weak-prior voting is killed under the H400 representation.
  Removing calendar votes from H395 left the quorum at `+0.05826` avg IC, but
  adding one pooled January/weekday/month-end/T+2 prior lowered it to
  `+0.05605`; calendar lift was `-0.00221` with `0 / 7` positive lift years,
  and calendar-only IC was `-0.00827`. Reopen only with a different target or
  mechanism-matched consumer, not by reweighting the same dense prior. Source
  anchors: `D016`, `F364`.

- Standalone buy-order count is not a promoted signal. H399 found
  `buy_count_rank` anti-predictive (`-0.01075`, `3 / 8` positive years), and
  `high_buy_count` only a modest C16 conditioner (`+0.08463` avg IC, `+0.00944`
  lift versus all rows, `6 / 8` positive lift years). Do not treat
  high-count plus high volume-z as a new crowd primitive; high volume-z already
  owns the clean pocket. Reopen only for the high-average-buy-size plus
  H394-low-weather clue or with materially different fragmentation/queue/
  intraday data. Source anchors: `D015`, `F363`.

- Volume Triple Storm (H411): Triple Storm does NOT amplify Volume like it amplifies C16.
  Volume+Triple = +0.038 IC, WORSE than Volume alone (+0.075). Ablation shows
  none of the 3 conditions help. C16-specific, not universal amplifier.
  Do not reopen as Volume amplifier. Source anchors: `D018`.

- Volume+C16 additive (H412): additive fails, C16 is too weak (-0.0008 IC).
  Best additive = +0.073, WORSE than Volume alone (+0.075).
  C16 has near-zero IC - cannot be rescued by additive.
  H410 works with S1 (+0.126), not with C16.
  Source anchors: `F376`.

- Quiet insider pre-reaction is parked under the current same-day own-news and
  high-buy-order-count absence proxy. H398 reproduced `insider_tplus1` as real
  event-time evidence (`+0.10498` avg C16 IC, `11 / 11` positive years,
  `+0.03000` lift versus same-ticker non-event dates), but
  `insider_tplus1_pre_reaction` lost to reacted rows by `-0.01811` avg IC.
  High buy-order-count T+1 insider rows were strongest (`+0.13776` avg IC).
  Reopen only with materially different pre-reaction timing data such as
  intraday absorption, source timestamp sequencing, queue timing, or peer-news
  visibility. Source anchors: `D014`, `F362`.

- Broad oracle-shadow weather promotion is parked under the current observable
  aggregate contract. H394 weakly predicted future S1 barrier breadth (avg date
  IC `+0.05019`, `7 / 8` positive years), but the best honest predicted bucket
  lifted C16 only `+0.00342` versus all rows and `+0.00416` versus random
  dates, below gates, and degraded S1. Observable `VNI down 2d` was cleaner.
  Reopen only with materially different intraday/opening data, a different
  regime target, or a quorum/consumer design where weak weather is one vote.
  Source anchors: `D013`, `F358`.

- S24x/S25x target-derived market-down promotions are invalid. The corrected
  audit found `leaky_target_market_down` IC `+0.09248` and
  `leaky_target_market_down_2d` `+0.09510`, but observable VNI-down states
  were only `+0.07706` / `+0.08058` versus C16 `+0.07377`, and observable
  stock-down states were weaker than C16. Reopen only with fixed observable
  trailing market/stock/breadth states and proper controls. Source anchors:
  `D012`, `F355`.

- Same-day nihilist reversal is parked. H393 found high C16 after stock and
  market weakness with no bullish news was positive, but it failed the simpler
  `stock_down_high_c16` control by `-0.00203` mean 5d lift and had negative
  2025 payoff. Reopen only with a predeclared weak-active-news subset,
  intraday absorption after capitulation, or a delayed re-entry consumer.
  Source anchors: `D011`, `F354`.

- C16+insider+news source-triangle promotion is parked under the current
  representation. H392 found `c16_insider_any_news` had positive mean 5d
  payoff, but lost to C16+insider-without-news and C16+news-without-insider
  controls, and 2025 lift versus exactly-two sensors was negative. The broader
  `three_plus_sensors` clue should be reopened only as a predeclared
  non-insider C16+source+forward news pocket or with materially different
  insider-quality data. Source anchors: `D010`, `F353`.

- Entry-panel tradability release is killed under the current cycle-label
  target. H391 found top-5/top-10 rows that became buyable after a prior
  blocked-buy state were negative and weaker than same-rank stable/non-release
  buyable controls (`top5_release` matched lift `-0.03367`, 2025 lift
  `-0.08011`; `top10_release` matched lift `-0.02837`, 2025 lift `-0.06630`).
  Reopen only with order-book queue/open-fill data, intraday post-release
  absorption, or a fixed wait-for-reblock/sellability-normalization contract.
  Source anchors: `D009`, `F352`.

- Calendar mechanism promotion is parked under the current target. H390 found
  exact `monday_jan_combo` retained 1d residual C16-IC lift after mechanism
  controls, but the state was only one active date per evaluated year, had
  only `2 / 4` positive 1d residual-lift years, and had negative mean 5d
  residual lift; `quarter_start` and late quarter-month timing did not retain
  positive 1d residual lift. Reopen only with a broader predeclared
  January/weekday contract, a different execution/5d target, or a downstream
  mechanism-matched consumer. Source anchors: `D008`, `F351`.

- Guarded-Ollama event cascade does not reopen event timing. H389 found the
  best state, `event_first20`, had mean 5d lift only `+0.00099` versus generic
  event and `+0.00114` versus repeat event, below the reopening gate; transition
  and family pockets were weaker. Keep event timing parked unless the target,
  source timestamping, or downstream consumer changes. Source anchors: `D007`,
  `F350`.

- Long-dormancy fresh selection is killed under the current entry-alpha
  candidate-history representation. H388 found `top5_fresh20` beat incumbents
  but failed stale-repeat control (mean lift `-0.00016`, 2025 lift
  `-0.00269`), and `top10_fresh20` failed stale-repeat control too. Reopen only
  with a materially different short-repeat, rank-transition, or portfolio
  policy contract. Source anchors: `D006`, `F349`.

- Insider-down rescue is killed under the current C5/stock-down/high-C16
  representation. H387 found `insider_down_high_c16` beat ordinary insider
  rows but failed the meaningful high-C16 controls: mean 5d lift was only
  `+0.00087` versus `insider_high_c16` and `-0.00308` versus
  `stock_down_high_c16`, with negative 2025 lifts versus both. Reopen only
  with materially different insider event-quality or timing data. Source
  anchors: `D005`, `F348`.

- H385 official-delay consumer promotion is parked. H385 passed as offline
  delayed-payoff evidence, but H386 failed the fixed candidate-policy
  follow-through: `official_supported` mean lift was `-0.00035` versus
  random-state and `-0.00540` versus random-all; `official_forward_supported`
  mean lift was `-0.00057` versus random-state and `-0.00555` versus
  random-all. Use H385 as delayed official-attention context, not as a broad
  allocator. Source anchors: `D004`, `F346-F347`.

- H383 active/positive-news strong-flow consumer promotion is parked. H383
  passed as offline IC evidence, but H384 failed the fixed candidate-policy
  follow-through: `active_news_strong_flow` mean lift was `-0.00026` versus
  random-state and `-0.00337` versus random-all; `positive_news_strong_flow`
  mean lift was `-0.00020` versus random-state and `-0.00191` versus
  random-all. Use H383 as context, not as a broad allocator. Source anchors:
  `D003`, `F344-F345`.

- H364 broad candidate-pool consumer promotion is parked. H382 passed only the
  same-support active-news random benchmark (`+0.00092` mean lift,
  `4 / 5` years above random-active mean) but failed broad random-all
  allocation (`-0.00367` mean lift, `1 / 5` years above random-all mean).
  Use H364 as an event-subset ranker or interaction anchor, not as a broad
  portfolio allocator. Source anchors: `D002`, `F343`.

- Silent order pressure is killed under the current own-ticker PhoBERT
  article-count proxy. H381 found no-news C16 weaker than all-C16 and
  active-news C16: `silent_5d` WF IC `+0.0700` versus all-C16 `+0.0752` and
  active-5d-news C16 `+0.0846`. Reopen only with a materially different
  "not public yet" representation, such as Ollama event-family states,
  peer/co-mention narrative vacuum, source-type timing, or another non-count
  proxy. Source anchors: `D001`, `F341`.

- S244 weak/inconsistent signals:
  - c16_entropy: WEAK (inconsistent year-to-year) - dead end
  - disclosure_shock_reaction: NO DATA - blocked (empty source)
  Source: [session_00244_log.md](./session_00244_log.md)

- Event-v2 timing is parked under the current executable top-5 selector:
  H321 remains offline sparse evidence, but additive integration, entry-label
  transfer, payoff-shape promotion, and sparse-clock portfolio rescue all
  failed. Reopen only with new event data, a materially different target, or a
  downstream consumer contract that is not the current selector. Source anchors:
  `F241`, `F289`, `F292`, `F302`.

- Dividend-clock timing is parked: broad calendar model inputs failed, the
  pre-ex payoff hint was too small, and the fixed sparse-clock portfolio bonus
  failed validation. Reopen only with a different calendar target or downstream
  consumer contract. Source anchors: `F294`, `F303`.

- Legal public-holiday timing is parked under the current executable top-5
  selector: H363 found a clean `all_holidays__post_5` top-book payoff hint, but
  the required fixed sparse-clock portfolio bonus did not change validation or
  confirmation relative returns. Do not tune more holiday offsets, closure
  gates, bonus sizes, or veto variants unless the target or downstream consumer
  contract changes. Source anchors: `F304`.

- Standalone foreign/proprietary flow is parked on current data: raw CafeF
  foreign-flow ranks, room scarcity, residual discontinuities,
  accumulation/change-points, foreign-C5 agreement, proprietary agreement or
  conflict, and sector ownership pressure all failed promotion. Reopen only
  with a materially different data source, target, or interaction contract.
  Source anchors: `F247-F248`, `F253`, `F285`, `F287-F291`.

- Smart-exit ML is parked until richer post-entry state or a different model
  contract exists. The legal-exit oracle has upper-bound value, but simple
  hold/sell, entry-time horizon routing, replacement-aware and skip-aware
  variants, and order-pressure post-entry state did not learn enough of the
  rare continuation pockets. Source anchors: `F151-F154`, `F254-F259`, `F295`.

- Old OHLCV residual queue items H135/H136/H137 are closed under the current
  contract. Do not rerun gap/compression/long-horizon residual variants unless
  a new target, execution contract, or non-price state changes the meaning of
  C11/C13 residuals. Source anchors: `F206-F207`, `F286`.

## Signal And Feature Dead Ends

- Standard OHLCV technical analysis and extended raw OHLCV feature additions
  did not create edge in the early single-stock setup; later common variants
  such as proba momentum, VIX-as-feature, IC stability filters, sector-relative
  additions, and raw quarterly fundamentals did not improve the promoted XS
  model stack. Source anchors: `F2`, `F5`, `F23`, `F36`, `F40`, `F42-F43`, `F57`.

- C16 stacking filters (S221): Combining liquid + braid/sector filters OVERFILTERS,
  reducing sample below statistical validity. Stacking hurts: IC -18% vs baseline.
  Source anchors: Session 221.

- C16 sector-relative adjustment (S224): Subtract sector median to remove sector bias
  HURTS signal: -15% IC. Keep absolute C16. Source: Session 224.

- C16 persistence (S225): Yesterday's pressure confirming today's doesn't help.
  IC -17%. Source: Session 225.

- Rank time acceleration (S244): Rank velocity WORSE than rank level.
  IC 0.0576 vs baseline 0.0778 (-26%). All 8 years negative delta.
  Confirms: level > velocity pattern (same as C16 ROC failure S227).
  Source: session_00244_log.md

## Bright-Mind Failed Experiments (S248-S252)

- macro_c16_regime (S248): Macro VIX regime doesn't condition C16.
  IC +0.078 BULL vs +0.077 BEAR (+0%) - no boost.
  Source: F332

- gap_open_c16 (S249): Previous day's return direction doesn't help C16.
  IC +0.075 gap positive vs +0.079 none (-4%) - no boost.
  Source: F333

- vol_shock_c16 (S250): Volume shock proxy insufficient data.
  Could not compute meaningful volume signal.
  Source: F334

- consecutive_down_c16 (S251): Day 2/3 streak doesn't compound.
  IC +0.078 day1 = day2 = day3 (0%) - no compounding.
  Source: F335

- c16_extreme_down (S252): Very high C16 (>0.9) too sparse.
  IC +0.028 vs +0.078 baseline (-63%) - signal lost.
  Source: F336

- News keyword and simple pooled sentiment paths are not enough by themselves:
  keyword sentiment added no IC, rolling aggregation did not fix sparsity,
  body-text ticker extraction hurt quality, the keyword lexicon path was
  exhausted, and simple LLM/PhoBERT pooled sentiment did not clear standalone
  promotion. Source anchors: `F60`, `F63-F65`, `F204`, `F284`.

- Earnings quality, VN30 rebalancing proximity, Corwin-Schultz spread proxy,
  raw return skewness, and several dense calendar/earnings features failed
  standalone or risk-adjusted bars. Source anchors: `F70-F71`, `F76`, `F78`,
  `F83-F84`.

- Sector and ownership routing mostly failed after the core library was known:
  sector sub-models underperformed pooled models, sector conditioning did not
  rescue compression blow-off, sector-level foreign pressure failed, and
  H319/H320 style ownership/criticality routers did not beat simpler controls.
  Source anchors: `F61`, `F207`, `F238-F239`, `F291`.

## Portfolio And Execution Dead Ends

- Retail-scale deployability is not solved by simple construction changes:
  ADV floors and participation caps broke the long-only edge, soft
  tradability-aware scoring did not create a viable retail region, multi-day
  entry slicing did not rescue benchmark-relative economics, and variable
  breadth failed after liquidity gating. Source anchors: `F91`, `F97`, `F100-F101`,
  `F103-F106`, `F108-F109`, `F113`.

- Early ML-style construction selection did not survive honest walk-forward.
  Fixed simple constructions and later selector-efficacy activation were more
  credible than broad model-selection meta-rules. Source anchors: `F95-F96`, `F118`,
  `F120`.

- Complexity around the activation champion mostly failed: three-state sizing,
  walk-forward rule selection, compact meta-models, local guards, exposure
  sizing, basket-coherence guards, and sticky-plus-sector stacking did not beat
  the simpler champion branch. Source anchors: `F122`, `F125`, `F130-F133`, `F138`.

- The complex `blocked5<=q80 + sector_cap_3` historical winner is not the live
  branch because it failed expanding-train/next-year pseudo-live testing. Use
  the simpler sticky branch unless a new locked protocol changes the evidence.
  Source anchors: `F137-F139`.

## Selector, Entry, And Intraday Dead Ends

- The first post-freeze additive selector path closed: H151 failed, H152 atoms
  did not survive selector-level promotion, and later H203/H204 selector
  discovery exhausted the current ladder. Source anchors: `F141`, `F144`, `F147-F149`.

- Entry-alpha remains parked as a small-book offline branch. Small-book
  contracts, local confirmation/calibration, label sharpening, sparse catalysts,
  selector-relative rescue, report-window switchboards, contradiction overlays,
  and dynamic breadth did not create a live-compatible replacement. Source anchors:
  `F157-F168`.

- Generic continuation/exit timing rules failed before deterministic
  integration, and event/corporate surfaces did not create useful continuation
  or exit signals under the locked protocol. Source anchors: `F151-F155`, `F174`,
  `F177-F178`.

- Reduced-shape intraday produced useful narrow evidence but is not a universal
  branch. Top-k stress routing, event-conditioned disagreement, strict
  confirmation split, and current-account compatibility checks failed enough
  that the surviving evidence must stay sleeve-specific. Source anchors:
  `F185-F196`, `F199-F203`, `F209-F212`.

## Data-Availability Dead Ends And Blocks

- True historical queue/open-fill alpha remains source-blocked locally.
  Current open data supports daily side channels and reduced-shape intraday,
  not historical order-book depth or a universal queue artifact. Source anchors:
  `F244`, `F260-F261`.

- HNX official disclosures are wired but not yet a usable HOSE historical
  bridge. Do not run disclosure alpha IC until broader history or a HOSE/HSX
  official source exists. Source anchors: `F235`, `F290`.

- Public-investment and several news-surrogate routes recovered structure but
  did not create promoted routers: beneficiary routing, title-sequence novelty,
  hybrid novelty cascade, lexical event-family routing, and surrogate
  disagreement tail all missed their promotion contracts. Source anchors:
  `F242`, `F249-F252`.

- Local full-schema Ollama replacement is not the default path. The durable
  local-news architecture is PhoBERT-first plus a narrow event-family Ollama
  residual; broad generator fields remain optional diagnostics. Source anchors:
  `F274`, `F282-F283`.

- Signal ignorance / regime-gated cash-veto is killed under H436. Composite regime
  features (market breadth, C16 volatility, news state, calendar) do NOT predict
  signal degradation. Top-10 S1 buyers in composite degrade-state still achieve IC=0.10
  (STRONGER than all-rows IC=0.12), while ignoring signal in degrade-state drops to
  IC=0.053 (WORSE than always-buy top10 IC=0.086). Composite degrade indicators capture
  nothing useful; S1/C16 are robust across all tested regime conditions. Do not reopen
  as a regime-gated cash/veto signal unless materially different regime features are
  introduced. Source anchors: `D030`, [session_00315_log.md](./session_00315_log.md).

- Replacement quality revival is killed under H437. Entering tickers have WEAKER
  S1 IC (0.066) than exiting tickers (0.126), stable tickers (0.079), and all-rows
  (0.117). Enter vs exit lift is -0.060, opposite of hypothesis. Aligns with H388's
  finding that fresh reappearances are not strong and stale-repeat controls failed.
  Do not reopen as a replacement quality signal unless materially different quality
  metrics are introduced. Source anchors: `D031`, [session_00316_log.md](./session_00316_log.md).

- Cross-ticker correlation shock promotion is killed under H441. Date-level cross-sectional
  correlation regime (high vs low) predicted only +0.0033 IC lift, below the 0.01 threshold.
  Secondary finding: C16 flow works better in high-corr dates (0.167 vs 0.144) while first-news
  novelty prefers low-corr dates (0.153 vs 0.130), but the primary shock mechanism is weak.
  Do not reopen as a date-level correlation shock signal unless materially different correlation
  or shock representations are introduced. Source anchors: `D032`, [session_00320_log.md](./session_00320_log.md).

- Ticker rank acceleration promotion is killed under H442. Second derivative of C16 rank
  (acceleration = delta of delta) has near-zero IC lift (+0.0009) versus first derivative.
  C16 rank LEVEL dominates (IC=0.158 vs acceleration IC=0.120). Both accel_up+flow and
  accel_down+flow are equal (~0.147), showing acceleration direction doesn't matter. H431
  rank delta worked because it correlated with rank level, not as independent signal. Do not
  reopen as a rank acceleration signal. Source anchors: `D033`, [session_00321_log.md](./session_00321_log.md).

- Sector momentum as regime gate is killed under H455. Cross-sectional market excess (sector_up vs sector_down) as regime gate has tiny signal differences (-0.0017 to -0.0127). Signals work SIMILARLY across both regimes - no router benefit. High volume is always negative in both regimes. S248-S252 failed as FILTERS, this fails as REGIME GATES. Do not reopen as a sector-momentum regime router. Source anchor: `D033`, [session_00111_log.md](./session_00111_log.md).

- Spread as hard regime gate is killed under H456. Wide spread amplifies buy_heavy_expansion significantly (+0.0948), but tight spread states are TOO SPARSE (356-1703 rows) for robust inference. Hard regime gate fails due to sparse support. Use spread as SOFT FILTER instead of hard gate. Source anchor: `D034`, [session_00112_log.md](./session_00112_log.md).

- News velocity as signal is killed under H473. News VELOCITY (3d delta = 5d-1d article count) is ANTI-predictive: high_velocity Q5 = IC 0.088 (-0.032 lift vs baseline 0.120), burst_has_news = IC 0.082 (-0.037). Fast-arriving news = crowd-following, not breaking alpha. mid_velocity only +0.008 (weak). low_velocity too sparse (most tickers have 0 news). The third dimension beyond novelty (H440) and presence (H445) is noise. Do not reopen with news-count velocity or acceleration derivatives. Only structured features (source-type, forward-looking, official) survive. Source: [session_00122_log.md](./session_00122_log.md).

- Rank acceleration as hidden signal is killed under H462. Rank acceleration (rank_change speed) is ANTI-predictive alone (-0.0166 lift for accelerating, -0.0665 for decelerating). Adding rank acceleration to buy_heavy_expansion makes it MUCH WORSE (-0.0584). The "suddenly appearing = hidden info" hypothesis is NOT supported. Do not reopen with rank_change velocity features. Source anchor: `D035`, [session_00115_log.md](./session_00115_log.md).

## Resolution: Transition Dynamics Are NOT Alpha

- H522 transition_dynamics_alpha is D076. Transition events (time-in-state, transition_to_X flags) do NOT capture info beyond static state labels. Best transition (`transition_to_router` IC=0.2246) is essentially identical to static state (`state_router` IC=0.2258), lift -0.0012. Duration features also don't help: long duration (`days_in_state_q4`) is actually anti-predictive (only 5/11 positive years, IC 0.0864). The coherent flow pattern H507 found is STRUCTURAL, not predictive incremental. Static states ARE the signal, transitions are not. Do not reopen with transition event features. Source: [session_00335_log.md](./session_00335_log.md), D076.

## Resolution: Relative State Encoding Is NOT Alpha

- H523 cross_sectional_relative_state is D077. Relative encoding (percentile rank within market/sector) does NOT beat absolute binary labeling. Best relative (`relative_active_market_top20` IC=0.2176) is -0.0082 below absolute best (`state_router` IC=0.2258). Sector-relative is similar (IC 0.2152, -0.0106 below absolute). Cross states (high relative but low absolute) are too sparse to evaluate. Participation pressure is captured by the specific mechanism (low C16 router), not by relative ranking. Do not reopen with percentile-rank relative features. Source: [session_00336_log.md](./session_00336_log.md), D077.

## Resolution: State Combination Is NOT Alpha

- H524 state_combo_alpha is D078. Union (OR) and intersection (AND) logic combos of latent states do NOT capture information beyond individual states. Best union combo (`union_router_only` IC=0.1795) equals best individual (`state_router` IC=0.1795). Best intersection combo (`intersect_router_buyable` IC=0.1796) is only +0.0002 lift. Union combos actually hurt: adding more states dilutes the signal. The latent state structure from H507-H515 already captured signal organization; combinations add nothing. Key discovery: `state_quiet` is STRONG (IC=0.1552, 11/11 pos yrs), not neutral as previously assumed - this is an unexpected finding worth noting. Do not reopen with state combination features. Source: [session_00337_log.md](./session_00337_log.md), D078.

## Resolution: High Breadth Is Negative Regime Signal

- H525 cross_sectional_breadth is D079. Date-level active-stock density (breadth) has OPPOSITE effect of hypothesis: HIGH breadth dates have WORSE IC (0.1149) vs LOW breadth (0.1454), lift -0.0305. When many stocks activate together, it's a crowded regime with weaker signal quality. Low breadth (sparse activation) dates have BETTER signal (+0.0177 lift vs baseline 0.1277). Quintiles show uniform IC at 0.1454, suggesting binary distinction (high vs low) not gradations. Use as regime FILTER: avoid high-breadth dates. Source: [session_00338_log.md](./session_00338_log.md), D079.

## Resolution: Multi-Signal × Persistence Stacking Is Marginal (D069)

- H105 multi_signal_persistence_stacking is D069. F445 (composite_2+ = 0.2445) + F441/F442 (persistence/accumulation) does NOT amplify beyond threshold.
- Evidence: composite_2+ × accumulation_q4 IC = 0.2506 (+0.0061 vs composite_2+), below +0.01 threshold. composite_2+ × persist_q4 actually HURTS (-0.0021).
- The two persistence mechanisms (accumulation vs persistence ratio) have OPPOSITE effects when combined with multi-signal.
- Not promotion-worthy. Do not reopen with persistence filters on multi-signal.
- Source: [session_00387_log.md](./session_00387_log.md), `D069`.

## Resolution: Signal Pair Specificity Does NOT Matter (D070)

- H106 signal_pair_synergy_matrix is D070. No specific signal pair (C23+C24 vs C23+C25 etc) beats the generic "any 2+ signals" composite.
- Evidence: composite_2+ IC = 0.2445, best pair c23_c26 = 0.2396 (-0.0049), all pairs WORSE than generic composite.
- The synergy is in having multiple signals, NOT which specific signals combine.
- The specific pair composition doesn't matter - any 2+ signals together creates the alpha.
- Do not reopen with specific pair combinations; generic multi-signal logic is the mechanism.
- Source: [session_00388_log.md](./session_00388_log.md), `D070`.

## Resolution: Signal Order/Sequence Does NOT Matter (D071)

- H107 signal_order_hidden_state is D071. Which signal fires FIRST (C23→C24 vs C24→C23) does NOT indicate different hidden demand.
- Evidence: composite_2+ IC = 0.2445, first_any IC = 0.2360 (-0.0085), first_c23 IC = 0.2361 (-0.0084). All WORSE than generic composite.
- The synergy is in having 2+ signals together, NOT in which signal came first.
- Signal sequence/order is NOT a hidden state - the "count" logic works, not "sequence" logic.
- Do not reopen with signal order/sequence; multi-signal count is the mechanism.
- Source: [session_00390_log.md](./session_00390_log.md), `D071`.

## Resolution: Multi-Signal × Blocked Triple Is Data-Gated (D072)

- H605 multi_signal_blocked_triple is D072. Intersection `composite_2plus × blocked_day_2_3` is too sparse under protocol (`207` rows, yearly IC invalid/NaN).
- Components remain individually strong (`composite_2plus=0.2445`, `blocked_day_2_3=0.1743`), but triple is not promotable.
- Do not reopen this exact intersection without materially broader support.
- Source: [session_00391_log.md](./session_00391_log.md), `D072`.

## Resolution: Continuous Breadth Weighting Fails On Multi-Signal Too (D073)

- H606 breadth_adjusted_multi_signal is D073. Binary low-breadth gate dominates (`0.2823`) while inverse-breadth weighted score collapses (`0.1615`) on the same family.
- Confirms H530 pattern: breadth works as discrete filter, not continuous multiplier.
- Do not reopen inverse-breadth weighting on this family under current contract.
- Source: [session_00392_log.md](./session_00392_log.md), `D073`.

## Resolution: Blocked Single-Signal Pre-Convergence Thesis Fails (D074)

- H607 inverse_multi_signal_edge is D074. `signal_1_blocked` underperforms `signal_1` by `-0.0487` IC.
- Blocked state weakens the single-signal pocket, not front-runs convergence.
- Do not reopen this blocked-single pre-convergence thesis under current data.
- Source: [session_00393_log.md](./session_00393_log.md), `D074`.

## Resolution: Tight Capacity Does Not Amplify Multi-Signal Pocket (D075)

- H608 capacity_modulated_multi_signal is D075. `composite_2plus_tight` is below `composite_2plus` (`-0.0041` lift).
- Tight capacity stays strong standalone, but not additive with multi-signal co-occurrence.
- Keep these as separate conditioners; do not reopen this exact combo.
- Source: [session_00394_log.md](./session_00394_log.md), `D075`.

## Maintenance Rule

- When future findings close or park a branch, update the source
  `findings-*.md` chunk first. Add or adjust this compact file only when the
  result should prevent future rediscovery or materially changes a reopening
  condition.
