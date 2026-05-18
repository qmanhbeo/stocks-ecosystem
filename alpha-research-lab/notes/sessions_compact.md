# Sessions Compact

What this file is for: compact per-session recovery notes. Keep one unnumbered
one-liner or short paragraph per material session, newest first. Do not use
manual list numbering; prepend new entries at the top. Every entry must link
to its source session or state an explicit source anchor.

## Recent Sessions

- [Session 417](session_00417_log.md): Ran H644 formalized retests for six
  priority unresolved hypotheses. Outcome: `#99 PASSED` (confirmed),
  `#91 PASSED` (upgraded from data-gated), `#103 PASSED` (upgraded from
  data-gated), `#100 FAILED` (was data-gated), `BM17 FAILED` (was data-gated),
  and `BM07 MIXED` (marginal, sub-threshold). Source:
  [session_00417_log.md](./session_00417_log.md),
  [artifacts/run_summaries/20260518_214804_h644_formalized_retests_research_branch.json](../artifacts/run_summaries/20260518_214804_h644_formalized_retests_research_branch.json).

- [Session 416](session_00416_log.md): Ran H643 to first-pass close the
  remaining Bright-Mind wake/sleep and traffic backlog items in one proxy-audit
  batch. Outcome: `7 PASSED`, `1 MIXED`, `6 FAILED`, `3 DATA_GATED`. Strongest
  survivors were arousal-fatigue spread, wake pulse, cycle stability, router
  c23-only split, macro persistence, relaxation-gap, and headway-wide states.
  Source: [session_00416_log.md](./session_00416_log.md),
  [artifacts/run_summaries/20260518_212901_h643_brightmind_remaining_batch_research_branch.json](../artifacts/run_summaries/20260518_212901_h643_brightmind_remaining_batch_research_branch.json).

- [Session 415](session_00415_log.md): Ran H629 to close all remaining open
  numbered queue items (`85-91`, `96-103`) in one structured batch. Outcome:
  `6 PASSED`, `6 FAILED`, `3 DATA_GATED`; notable passes include 85, 86, 90,
  97, 99, and 101. Source: [session_00415_log.md](./session_00415_log.md),
  [artifacts/run_summaries/20260518_212651_h629_remaining_queue_85_103_batch_research_branch.json](../artifacts/run_summaries/20260518_212651_h629_remaining_queue_85_103_batch_research_branch.json).

- [Session 414](session_00414_log.md): Ran H628 signal concentration during
  low-breadth. PASSED (F461): concentrated low-breadth state
  (`conc_low IC=0.2523`) beat distributed low-breadth (`dist_low IC=0.2315`)
  by `+0.0209`, confirming a concentration edge inside sparse-crowd regimes.
  Source: [session_00414_log.md](./session_00414_log.md),
  [artifacts/run_summaries/20260518_182550_h628_signal_concentration_low_breadth_research_branch.json](../artifacts/run_summaries/20260518_182550_h628_signal_concentration_low_breadth_research_branch.json).

- [Session 413](session_00413_log.md): Ran H627 breadth-expansion exit rule as
  an event-study hold comparison (`adaptive >1.5x breadth` vs fixed 5-day
  hold). FAILED (D099): adaptive mean return `0.0084` vs fixed `0.0119`
  (lift `-0.0035`) with shorter holds (`2.32` vs `4.99` days). Source:
  [session_00413_log.md](./session_00413_log.md),
  [artifacts/run_summaries/20260518_182548_h627_breadth_expansion_exit_rule_research_branch.json](../artifacts/run_summaries/20260518_182548_h627_breadth_expansion_exit_rule_research_branch.json).

- [Session 412](session_00412_log.md): Ran H626 decay/exit-zone buckets on
  composite multi-signal persistence. FAILED (D098): front-loaded buckets are
  strong (`age_1_7 IC=0.2800`), but `age_31_plus` has zero support rows, so
  the intended `31+` decay boundary is not testable under current state
  construction. Source: [session_00412_log.md](./session_00412_log.md),
  [artifacts/run_summaries/20260518_182643_h626_signal_decay_exit_zone_research_branch.json](../artifacts/run_summaries/20260518_182643_h626_signal_decay_exit_zone_research_branch.json).

- [Session 411](session_00411_log.md): Ran H625 ticker self-reference breadth
  conditioning. MIXED (D097): self-history hot state
  (`composite_self_hist_hot IC=0.2475`) beats market-low state
  (`0.2406`) by `+0.0069`, but lift stays below +0.01 gate. Source:
  [session_00411_log.md](./session_00411_log.md),
  [artifacts/run_summaries/20260518_182642_h625_ticker_self_breadth_reference_research_branch.json](../artifacts/run_summaries/20260518_182642_h625_ticker_self_breadth_reference_research_branch.json).

- [Session 410](session_00410_log.md): Ran H624 calendar × breadth interaction.
  MIXED (D096): best weekday-conditioned low-breadth pocket
  (`low_breadth_other IC=0.2484`) only improves generic low-breadth state
  (`0.2406`) by `+0.0077`, below promotion threshold. Source:
  [session_00410_log.md](./session_00410_log.md),
  [artifacts/run_summaries/20260518_182545_h624_calendar_breadth_interaction_research_branch.json](../artifacts/run_summaries/20260518_182545_h624_calendar_breadth_interaction_research_branch.json).

- [Session 409](session_00409_log.md): Ran H623 conflict vs coherent
  multi-signal comparison. MIXED (D095): conflict (`0.2019`) is only
  `+0.0020` above coherent (`0.2000`), not actionable. Source:
  [session_00409_log.md](./session_00409_log.md),
  [artifacts/run_summaries/20260518_182544_h623_signal_conflict_edge_research_branch.json](../artifacts/run_summaries/20260518_182544_h623_signal_conflict_edge_research_branch.json).

- [Session 408](session_00408_log.md): Ran H622 magnitude-weighted multi-signal
  states. FAILED (D094): best magnitude state (`composite_mag_q50`) ties
  baseline (`0.2456`), while stronger magnitude cuts degrade IC. Source:
  [session_00408_log.md](./session_00408_log.md),
  [artifacts/run_summaries/20260518_182530_h622_signal_magnitude_hidden_state_research_branch.json](../artifacts/run_summaries/20260518_182530_h622_signal_magnitude_hidden_state_research_branch.json).

- [Session 407](session_00407_log.md): Ran H621 cross-signal breadth-threshold
  discovery (`10/20/30` percentile gates per C23/C24/C25/C26). MIXED (D093):
  threshold preferences differ (C25 prefers 30, others 20), but mean lift over
  common 20% gate is only `+0.0061`. Source:
  [session_00407_log.md](./session_00407_log.md),
  [artifacts/run_summaries/20260518_182525_h621_cross_signal_breadth_threshold_discovery_research_branch.json](../artifacts/run_summaries/20260518_182525_h621_cross_signal_breadth_threshold_discovery_research_branch.json).

- [Session 406](session_00406_log.md): Ran H620 implementation pain × multi-signal triple to test blocked-state amplification on `composite_2plus` (`blocked_either` and `blocked_day_2_3`). FAILED (D092): `composite_2plus_blocked_either IC=0.1660` vs `composite_2plus IC=0.2445` (lift -0.0785); `blocked_day_2_3` intersection remains sparse (`239` rows, yearly IC invalid). Source: [session_00406_log.md](./session_00406_log.md), [artifacts/run_summaries/20260518_181432_h620_implementation_pain_multi_signal_triple_research_branch.json](../artifacts/run_summaries/20260518_181432_h620_implementation_pain_multi_signal_triple_research_branch.json).

- [Session 405](session_00405_log.md): Ran H619 post-breadth-spike recovery timing to test `composite_2plus × low_breadth × post_spike` vs `composite_2plus × low_breadth` baseline. FAILED (D091): post-spike IC=0.2581 vs baseline low-breadth IC=0.2694 (lift -0.0113). Recovery-window timing does not improve the existing low-breadth contract. Source: [session_00405_log.md](./session_00405_log.md), [artifacts/run_summaries/20260518_181213_h619_post_breadth_spike_recovery_timing_research_branch.json](../artifacts/run_summaries/20260518_181213_h619_post_breadth_spike_recovery_timing_research_branch.json).

- [Session 404](session_00404_log.md): Ran H618 signal-day distribution regime to test same-day multi-signal concentration (`2+` today) vs spread-across-days accumulation (`1` today with 3d sum>=2). PASSED (F460): same_day IC=0.2445 vs spread IC=0.1821, lift +0.0624, both 11/11 positive years. Confirms simultaneous multi-signal concentration is materially stronger than staggered accumulation. Source: [session_00404_log.md](./session_00404_log.md), [artifacts/run_summaries/20260518_180932_h618_signal_day_distribution_regime_research_branch.json](../artifacts/run_summaries/20260518_180932_h618_signal_day_distribution_regime_research_branch.json).

- [Session 403](session_00403_log.md): Ran H617 breadth-scale signal strength regression to test continuous breadth scaling vs binary low-breadth gate on `composite_2plus`. MIXED (D090): quintile profile is directionally lower from Q1 to Q5, but continuous scaling collapses IC (`0.0878` vs binary gate `0.2694`, lift `-0.1816`). Breadth remains a discrete filter mechanism, not a continuous multiplier. Source: [session_00403_log.md](./session_00403_log.md), [artifacts/run_summaries/20260518_180725_h617_breadth_scale_signal_strength_research_branch.json](../artifacts/run_summaries/20260518_180725_h617_breadth_scale_signal_strength_research_branch.json).

- [Session 402](session_00402_log.md): Ran H616 multi-signal temporal coherence to test directional coherence vs mixed-direction states inside `composite_2plus`. MIXED (D089): coherent IC=0.1957 vs mixed IC=0.1955 (lift +0.0002, non-actionable). Directional coherence does not add incremental value under current state construction. Source: [session_00402_log.md](./session_00402_log.md), [artifacts/run_summaries/20260518_180504_h616_multi_signal_temporal_coherence_research_branch.json](../artifacts/run_summaries/20260518_180504_h616_multi_signal_temporal_coherence_research_branch.json).

- [Session 401](session_00401_log.md): Ran H615 signal concentration × breadth interaction on `composite_2plus` with explicit 4-way states (low/high breadth × low/high concentration). MIXED (D088): best low-breadth state IC=0.2745 vs best high-breadth state IC=0.2485 (+0.0260), but support is too sparse for promotion (best-high years=2, confirmation rows=3). Source: [session_00401_log.md](./session_00401_log.md), [artifacts/run_summaries/20260518_164406_h615_signal_concentration_breadth_interaction_research_branch.json](../artifacts/run_summaries/20260518_164406_h615_signal_concentration_breadth_interaction_research_branch.json).

- [Session 400](session_00400_log.md): Ran H614 persistence decay boundary with rolling-60d accumulation buckets on `composite_2plus`. PASSED (F459): `accum_20_30 IC=0.2542` vs `accum_31plus IC=0.2407`, lift +0.0135 (11/11 positive years both). Confirms bounded persistence sweet spot rather than monotonic “more is better.” Source: [session_00400_log.md](./session_00400_log.md), [artifacts/run_summaries/20260518_163916_h614_persistence_decay_boundary_research_branch.json](../artifacts/run_summaries/20260518_163916_h614_persistence_decay_boundary_research_branch.json).

- [Session 399](session_00399_log.md): Ran H613 cross-sectional dispersion regime to test `composite_2plus` on low- vs high-dispersion dates. MIXED (D087): low-disp combo IC=0.2539 vs high-disp combo IC=0.2372 (+0.0167), but support is sparse/non-robust (low years=5, high confirmation rows=29). Directional hint only; not promotion-worthy. Source: [session_00399_log.md](./session_00399_log.md), [artifacts/run_summaries/20260518_163631_h613_cross_sectional_dispersion_regime_research_branch.json](../artifacts/run_summaries/20260518_163631_h613_cross_sectional_dispersion_regime_research_branch.json).

- [Session 398](session_00398_log.md): Ran H612 market regime position multiplier to test breadth-based score scaling (`low=1.5x`, `high=0.5x`, mid=1.0x) vs baseline S1 score. FAILED (D086): scaled IC=0.0769 vs baseline IC=0.1298 (lift -0.0529). Confirms breadth works as discrete gating/filtering, not global multiplicative sizing. Source: [session_00398_log.md](./session_00398_log.md), [artifacts/run_summaries/20260518_163315_h612_market_regime_position_multiplier_research_branch.json](../artifacts/run_summaries/20260518_163315_h612_market_regime_position_multiplier_research_branch.json).

- [Session 397](session_00397_log.md): Ran H611 implementation pain as position sizing to test blocked-name score multiplier (`1.5x`) vs baseline S1 score. FAILED (D085): sized IC=0.1292 vs baseline IC=0.1302 (lift -0.0010). Blocked state helps as a filter/signal context (F438), not as direct score-size multiplier. Source: [session_00397_log.md](./session_00397_log.md), [artifacts/run_summaries/20260518_163041_h611_implementation_pain_position_sizing_research_branch.json](../artifacts/run_summaries/20260518_163041_h611_implementation_pain_position_sizing_research_branch.json).

- [Session 396](session_00396_log.md): Ran H610 regime transition timing alpha to test `composite_2plus × transition_to_low_breadth` vs `composite_2plus × sustained_low_breadth`. FAILED (D084): transition IC=0.2793 vs sustained IC=0.2797 (lift -0.0004, effectively tied). Transition timing adds no incremental value over static/sustained low-breadth regime. Source: [session_00396_log.md](./session_00396_log.md), [artifacts/run_summaries/20260518_162807_h610_regime_transition_timing_alpha_research_branch.json](../artifacts/run_summaries/20260518_162807_h610_regime_transition_timing_alpha_research_branch.json).

- [Session 395](session_00395_log.md): Ran H609 triple-factor alpha portfolio to test `composite_2plus × cofire_q1_c23 × persist_q4` vs `composite_2plus` baseline. FAILED (D083): triple IC=0.2172 vs composite IC=0.2445 (lift -0.0273). Pairwise stacks also failed to beat composite. Source: [session_00395_log.md](./session_00395_log.md), [artifacts/run_summaries/20260518_162111_h609_triple_factor_alpha_portfolio_research_branch.json](../artifacts/run_summaries/20260518_162111_h609_triple_factor_alpha_portfolio_research_branch.json).

- [Session 394](session_00394_log.md): Ran H608 capacity-modulated multi-signal to test `composite_2plus × tight_capacity` vs `composite_2plus` baseline. FAILED: combo IC=0.2404 vs composite IC=0.2445 (lift -0.0041). Tight capacity remains strong standalone (0.1900) but does not amplify the multi-signal pocket. Source: [session_00394_log.md](./session_00394_log.md), [artifacts/run_summaries/20260517_193032_h608_capacity_modulated_multi_signal_research_branch.json](../artifacts/run_summaries/20260517_193032_h608_capacity_modulated_multi_signal_research_branch.json).

- [Session 393](session_00393_log.md): Ran H607 inverse multi-signal edge to test whether blocked single-signal names (`signal_1 AND blocked`) front-run multi-signal convergence. FAILED: `signal_1_blocked IC=0.1237` vs `signal_1 IC=0.1724` (lift `-0.0487`). Blocked state weakens, not strengthens, the single-signal pocket. Source: [session_00393_log.md](./session_00393_log.md), [artifacts/run_summaries/20260517_192829_h607_inverse_multi_signal_edge_research_branch.json](../artifacts/run_summaries/20260517_192829_h607_inverse_multi_signal_edge_research_branch.json).

- [Session 392](session_00392_log.md): Ran H606 breadth-adjusted multi-signal to test whether continuous inverse-breadth weighting can beat the binary low-breadth gate on `composite_2plus`. FAILED: binary gate IC=0.2823 (4,811 rows) vs base composite IC=0.2456, while weighted score collapses to IC=0.1615 on the same 29,542 rows (lift vs binary = -0.1208). Confirms H530 pattern: breadth works as discrete filter, not continuous multiplier. Source: [session_00392_log.md](./session_00392_log.md), [artifacts/run_summaries/20260517_192638_h606_breadth_adjusted_multi_signal_research_branch.json](../artifacts/run_summaries/20260517_192638_h606_breadth_adjusted_multi_signal_research_branch.json).

- [Session 391](session_00391_log.md): Ran H605 multi-signal × blocked triple to test whether `composite_2plus × blocked_day_2_3` adds lift over F445. FAILED (data-gated sparsity): combo has only 207 pooled rows and no valid yearly IC (`NaN`) under minimum-row gates. Individual components remain strong (`composite_2plus=0.2445`, `blocked_day_2_3=0.1743`), but intersection is not promotable. Source: [session_00391_log.md](./session_00391_log.md), [artifacts/run_summaries/20260517_192349_h605_multi_signal_blocked_triple_research_branch.json](../artifacts/run_summaries/20260517_192349_h605_multi_signal_blocked_triple_research_branch.json).

- [Session 390](session_00390_log.md): Ran H107 signal order as hidden state to test if which signal fires FIRST (C23→C24 vs C24→C23) indicates different hidden demand. FAILED (Dead-end D084): first_any IC=0.2360 vs composite=0.2445 = -0.0085 (NEGATIVE). Signal order does NOT add value - C23/C24/C25/C26 sequence doesn't matter. Synergy is in "2+ signals" logic, not specific order. Source: [session_00390_log.md](./session_00390_log.md), [artifacts/run_summaries/20260517_175713_h107_signal_order_hidden_state_research_branch.json](../artifacts/run_summaries/20260517_175713_h107_signal_order_hidden_state_research_branch.json).

- [Session 389](session_00389_log.md): Ran H121 tight capacity × multi-signal amplifier to test if tight + composite_2+ + low_breadth beats F447 (0.2651). MIXED: triple IC=0.2702 vs F447 baseline=0.2651, lift +0.0051 (below +0.01 threshold). Adding tight_capacity provides marginal value over composite_2+ × low_breadth. F447 remains stronger combination. Source: [session_00389_log.md](./session_00389_log.md), [artifacts/run_summaries/20260517_175521_h121_tight_capacity_multi_signal_research_branch.json](../artifacts/run_summaries/20260517_175521_h121_tight_capacity_multi_signal_research_branch.json).

- [Session 388](session_00388_log.md): Ran H106 signal pair synergy matrix to test which specific signal pairs (C23+C24 vs C23+C25 etc) have strongest synergy. FAILED (Dead-end D083): No specific pair beats composite_2+ (0.2445). Best pair c23_c26 = 0.2396 (-0.0049). Synergy is in "2+ signals" logic, not specific composition. Source: [session_00388_log.md](./session_00388_log.md), [artifacts/run_summaries/20260517_175026_signal_pair_synergy_matrix_research_branch.json](../artifacts/run_summaries/20260517_175026_signal_pair_synergy_matrix_research_branch.json).

- [Session 387](session_00387_log.md): Ran H105 multi-signal × persistence stacking to test if F445 (composite_2+ = 0.2445) + F441/F442 (persistence/accumulation) amplify further. MIXED (marginal): composite_2+ × accumulation_q4 IC=0.2506 (+0.0061 vs composite_2+), below +0.01 threshold. Persistence Q4 actually HURTS multi-signal (-0.0021). Accumulation provides marginal improvement but not promotion-worthy. Dead-end D082. Source: [session_00387_log.md](./session_00387_log.md), [artifacts/run_summaries/20260517_174832_multi_signal_persistence_stacking_research_branch.json](../artifacts/run_summaries/20260517_174832_multi_signal_persistence_stacking_research_branch.json).

- [Session 386](session_00386_log.md): Ran H104 multi-signal × low-breadth amplification to test if F445 (composite_2+ = 0.2445) + H529 (low_breadth) amplify further. PASSED (Finding F447): composite_2+ × low_breadth IC=0.2651 vs composite_2+ alone=0.2445, lift +0.0206 (> +0.01 threshold), 10/11 positive years. Orthogonal amplifiers stack! New ideas 113-118 added to queue. Source: [session_00386_log.md](./session_00386_log.md), [artifacts/run_summaries/20260517_174457_h604_multi_signal_breadth_amplification_research_branch.json](../artifacts/run_summaries/20260517_174457_h604_multi_signal_breadth_amplification_research_branch.json).

- [Session 385](session_00385_log.md): Ran H96 zero-cofire edge test to see if "zero" competitors (completely isolated) beats "few" (Q1). FAILED (data constraint): C16 proxy too sparse (isolated=32 rows, few=66 rows). Original F440 used actual C23/C24/C25/C26 signals. Source: [session_00385_log.md](./session_00385_log.md).

- [Session 383](session_00383_log.md): Ran H94 blocked-state transition timing to test if first-day blocked vs 2-3d vs 4+ days matters. PASSED (Finding F444): blocked_day_2_3 IC=0.1734 (+0.0208 vs blocked_either). OPPOSITE of hypothesis - continuing blocked is STRONGER than first-day blocked. Same mechanism as H534: duration works as filter. Source: [session_00383_log.md](./session_00383_log.md).

- [Session 382](session_00382_log.md): Ran H93 cofire-persistence interaction test to see if isolated signals (F440: Q1 cofire) combined with sustained signals (F441: Q4 persistence) creates stronger alpha. PASSED (Finding F443): Cofire Q1 + Persist Q4 IC=0.1794 (+0.0110 lift vs baseline), 11/11 positive years. Isolated+sustained combo adds value over either amplifier alone. Source: [session_00382_log.md](./session_00382_log.md).

- [Session 381](session_00381_log.md): Ran H592 signal accumulation intensity test to see if cumulative days in active state (last 30d) predicts stronger alpha. PASSED (Finding F442): Q4 (20+ days) IC=0.2006 vs Q1 (0-7 days) IC=0.1137 = +0.0869 lift. Q4 vs baseline +0.0704. Both consecutive (F441) and non-consecutive (H592) persistence work - sustained hidden demand = stronger signal. Source: [session_00381_log.md](./session_00381_log.md), [artifacts/run_summaries/20260517_172553_signal_accumulation_intensity_research_branch.json](../artifacts/run_summaries/20260517_172553_signal_accumulation_intensity_research_branch.json).

- [Session 380](session_00380_log.md): Ran H84 active-set persistence test to see if sustained presence in active state (high persistence) predicts stronger signal than transient entry. PASSED (Finding F441): Q4 (sustained 7-9d) IC=0.1825 (+0.0227 vs active), Q1 (transient 0-2d) IC=0.1346 (-0.0252). Q4 vs Q1 = +0.0386 lift, 11/11 positive years. Consistent with H534 - longer time in active state = stronger hidden demand. Source: [session_00380_log.md](./session_00380_log.md).

- [Session 379](session_00379_log.md): Ran H82 co-fire degree test to see if isolated signals (few competitors) are stronger than crowded (many competitors). PASSED (Finding F440): signal+isolated (Q1) IC=0.2064 (+0.0500 lift vs signal), signal+crowded (Q4) IC=0.1259 (-0.0305). Isolated vs crowded = +0.0805 lift, 11/11 positive years. New regime signal - cofire isolation captures competitive crowding at signal-detection level. Source: [session_00379_log.md](./session_00379_log.md).

- [Session 378](session_00378_log.md): Ran H81 market breadth trend test to see if 3-day cumulative breadth trajectory captures de-congestion vs re-congestion. MIXED/FAILED: expanding (more active) IC=0.1629 > contracting IC=0.1554 (+0.0084), but both below +0.01 threshold. Hypothesis that contracting = stronger is falsified - direction adds no actionable value. Dead-end D081. Source: [session_00378_log.md](./session_00378_log.md).

- [Session 377](session_00377_log.md): Ran H80 capacity-breadth OR test to see if OR of tight+low_breadth AND active+low_breadth captures additional alpha beyond each component. FAILED: OR IC=0.1993 is IDENTICAL to tight+low (0.1993) and WORSE than active+low (0.2026). Set overlap: 99.98% of active+low stocks are already in tight+low - they are the same mechanism, not independent amplifiers. Dead-end D080. Source: [session_00377_log.md](./session_00377_log.md).

- [Session 376](session_00376_log.md): Ran H586 blocked duration sweet spot test to see if persistently blocked (8d+) beats newly blocked (1d) like H534 for active state. FAILED (sparse): duration_8pl = 0 rows, blocked stocks are too transient to stay blocked. But duration_2_3d IC=0.1635 vs 1d IC=0.1516 = +0.0119 (> +0.01!), though only 1/1 positive years (sparse). C27 queue exhausted. All 8 tests done: 2 finds (F438, F439), 6 dead-ends. Dead-end D079. Source: [session_00376_log.md](./session_00376_log.md), [20260517_165545_blocked_duration_sweet_spot_research_branch.json](../artifacts/run_summaries/20260517_165545_blocked_duration_sweet_spot_research_branch.json).

- [Session 375](session_00375_log.md): Ran H585 C27 × market activity interaction test to see if blocked stocks work differently in high vs low market activity regimes. FAILED (OPPOSITE): C27 × high_activity IC=0.0860 vs C27 × low_activity IC=0.1345 = -0.0485. NEW INSIGHT: blocked × high_breadth = 0.2029 (STRONGEST) but blocked × high_activity = 0.0860 (WORST). Breadth and activity are OPPOSITE signals for C27! C27 wants many signals active (high breadth) + low per-signal intensity. Dead-end D078. Source: [session_00375_log.md](./session_00375_log.md), [20260517_164909_c27_market_activity_interaction_research_branch.json](../artifacts/run_summaries/20260517_164909_c27_market_activity_interaction_research_branch.json).

- [Session 374](session_00374_log.md): Ran H583 liquid in bad breadth as contrarian test to see if liquid stocks (tradable, ignored by crowd) are contrarian in high-breadth regime. FAILED (OPPOSITE): liquid × high_breadth IC=0.1029 (-0.0236 vs liquid alone). blocked × high_breadth = 0.2029 (+0.0934 lift vs high_breadth) — C27 is STRONGEST in crowded markets! Liquid is NOT a contrarian play. Dead-end D077. Source: [session_00374_log.md](./session_00374_log.md), [20260517_164307_liquid_contrarian_high_breadth_research_branch.json](../artifacts/run_summaries/20260517_164307_liquid_contrarian_high_breadth_research_branch.json).

- [Session 373](session_00373_log.md): Ran H584 C27 as signal router test to see if being blocked changes how S1 performs on C23/C24. PASSED (negative finding): C24 × blocked IC=0.0891 vs C24 × non-blocked IC=0.1566 = -0.0675! C27 DESTROYS C24 signal quality. C23 × blocked is marginally better (+0.0033). Finding F439: C27 should be a NEGATIVE filter for C24 (ceiling stocks need selling pressure, blocked kills momentum). blocked_c23 remains positive. Source: [session_00373_log.md](./session_00373_log.md), [20260517_163734_c27_signal_router_research_branch.json](../artifacts/run_summaries/20260517_163734_c27_signal_router_research_branch.json).

- [Session 372](session_00372_log.md): Ran H582 C27 × signal composite test to see if blocked amplifies the C23/C24/C25 composite. PASSED but mechanistically circular: blocked×composite (+0.0198 vs composite) because composite is too broad (97% of all rows ≈ baseline). Composite itself has no alpha — the lift comes purely from C27. Finding: C27 is a standalone signal, not a combo amplifier. Dead-end D076. Source: [session_00372_log.md](./session_00372_log.md), [20260517_163527_c27_signal_composite_research_branch.json](../artifacts/run_summaries/20260517_163527_c27_signal_composite_research_branch.json).

- [Session 371](session_00371_log.md): Ran H581 C27 × breadth amplifier test to see if low_breadth amplifies blocked stocks (like it amplifies tight_capacity). FAILED (OPPOSITE + sparse): C27 × low_breadth IC=0.0960 (-0.0517 vs raw C27!) and too sparse (1,023 rows). C27 in HIGH breadth is slightly better (0.1500 vs raw 0.1477). Low breadth HURTS C27. Dead-end D075. Source: [session_00371_log.md](./session_00371_log.md), [20260517_162913_c27_breadth_amplifier_research_branch.json](../artifacts/run_summaries/20260517_162913_c27_breadth_amplifier_research_branch.json).

- [Session 370](session_00370_log.md): Ran H580 C27 × capacity amplifier test to see if blocked × tight_capacity combines two hidden-demand mechanisms. MIXED (marginal + too sparse): blocked×tight IC=0.1688 (+0.021 vs raw C27, +0.004 vs tight alone) but only 2,356 rows, 1/1 positive years (dev only). tight_capacity is the dominant signal, C27 is redundant when tight is present. Not promotion-worthy. Source: [session_00370_log.md](./session_00370_log.md), [20260517_162721_c27_capacity_amplifier_research_branch.json](../artifacts/run_summaries/20260517_162721_c27_capacity_amplifier_research_branch.json).

- [Session 369](session_00369_log.md): Ran H575 foreign flow regime as C27 conditioner test to see if blocked stocks work differently in foreign-up vs foreign-down regimes. FAILED (OPPOSITE): C27 × foreign-down IC=0.2243 (+0.0766 vs raw C27) but C27 × foreign-up IC=0.1146 (-0.0331 vs raw C27). Foreign selling STRENGTHENS C27, not foreign buying. C27 lift in foreign-down = +0.1069 vs foreign-up = -0.0203. Speculative mechanism: blocked stocks fill the void when foreigners sell. Dead-end D074. Source: [session_00369_log.md](./session_00369_log.md), [20260517_162326_foreign_flow_regime_c27_conditioner_research_branch.json](../artifacts/run_summaries/20260517_162326_foreign_flow_regime_c27_conditioner_research_branch.json).

- [Session 368](session_00368_log.md): Ran H574 implementation pain as positive signal test to see if "painful to trade" = hidden demand = alpha (invert tradability veto). PASSED: blocked_either (can't buy OR can't sell) IC = 0.1477 vs liquid IC = 0.1266 = +0.0211 lift (> +0.01 threshold). Implementation difficulty is a POSITIVE signal - stocks that are hard to trade capture hidden demand. Finding F438. Source: [session_00368_log.md](./session_00368_log.md), [20260517_161109_implementation_pain_positive_research_branch.json](../artifacts/run_summaries/20260517_161109_implementation_pain_positive_research_branch.json).

- [Session 367](session_00367_log.md): Ran H573 capacity-breadth-signal triple amplifier test to see if tight × low_breadth × C23 signal creates stronger alpha than the pair alone. FAILED: triple (0.1394) vs tight+low_breadth (0.1966) = -0.0571. Adding C23 signal HURTS - triple is too sparse (2,903 rows) and degrades quality. Finding: tight+low_breadth is optimal, adding more filters degrades. Dead-end D073. Source: [session_00367_log.md](./session_00367_log.md), [20260517_160617_capacity_breadth_signal_triple_research_branch.json](../artifacts/run_summaries/20260517_160617_capacity_breadth_signal_triple_research_branch.json).

- [Session 366](session_00366_log.md): Ran H567 quiet-to-active transition probability test to see if catching stocks ABOUT to activate captures pre-crowd alpha. FAILED: transition (0.1465) vs steady quiet (0.1625) = -0.0160. Transition is WORSE than steady quiet - stable quiet is stronger than transitioning. Source: [session_00366_log.md](./session_00366_log.md), [20260517_155811_quiet_to_active_transition_prob_research_branch.json](../artifacts/run_summaries/20260517_155811_quiet_to_active_transition_prob_research_branch.json).

- [Session 365](session_00365_log.md): Ran H566 time-since-active hidden state test to see if time since last active state modulates signal regardless of current state. FAILED: best TSA (0d) = 0.1574 vs current active = 0.1648 = -0.0074. Current state wins over history. Source: [session_00365_log.md](./session_00365_log.md), [20260517_155638_time_since_active_hidden_state_research_branch.json](../artifacts/run_summaries/20260517_155638_time_since_active_hidden_state_research_branch.json).

- [Session 364](session_00364_log.md): Ran H565 capacity-breadth direction combo test to see if tight_capacity × low_breadth amplifies both signals. PASSED: combo (0.2062) vs tight alone (0.1648) = +0.0414, vs low_breadth (0.1073) = +0.0989. Both components needed - strong amplification! Finding F437. Source: [session_00364_log.md](./session_00364_log.md), [20260517_155450_capacity_breadth_direction_combo_research_branch.json](../artifacts/run_summaries/20260517_155450_capacity_breadth_direction_combo_research_branch.json).

- [Session 363](session_00363_log.md): Ran H564 breadth quintile gate test to see if quintiles capture different alpha regimes vs binary bottom 20%. FAILED: Q1 (0.1053) vs binary (0.1073) = -0.0020. Q2 is strongest (0.1435), not Q1. Quintiles don't beat binary. Source: [session_00363_log.md](./session_00363_log.md), [20260517_155334_breadth_quintile_gate_research_branch.json](../artifacts/run_summaries/20260517_155334_breadth_quintile_gate_research_branch.json).

- [Session 362](session_00362_log.md): Ran H563 opposite-day breadth entry test to see if first day of low_breadth regime is stronger than sustained. FAILED: first_day (0.0977) vs sustained (0.1442) = -0.0464 (OPPOSITE). Onset is WORSE than steady state - sustained low_breadth is the signal. Source: [session_00362_log.md](./session_00362_log.md), [20260517_155217_opposite_day_breadth_entry_research_branch.json](../artifacts/run_summaries/20260517_155217_opposite_day_breadth_entry_research_branch.json).

- [Session 361](session_00361_log.md): Ran H562 breadth velocity (change rate) test to see if rate of breadth change captures hidden regime. FAILED: contracting (0.1310) vs expanding (0.1297) = only +0.0013 lift (below +0.01 threshold). Velocity effect is noise - change rate adds nothing beyond absolute level. Source: [session_00361_log.md](./session_00361_log.md), [20260517_154848_breadth_velocity_research_branch.json](../artifacts/run_summaries/20260517_154848_breadth_velocity_research_branch.json).

- [Session 360](session_00360_log.md): Ran H561 breadth regime hierarchy cascade test to see if priority cascade (C25优先→C24×breadth→C23) beats composite. FAILED: cascade (0.1907) < composite (0.1977) by -0.0070. Cascade logic flawed - C24×own_breadth (0.124) is weaker than C23 alone (0.189). C25 alone confirmed strongest (0.209). Source: [session_00360_log.md](./session_00360_log.md), [20260517_154656_breadth_regime_cascade_research_branch.json](../artifacts/run_summaries/20260517_154656_breadth_regime_cascade_research_branch.json).

- [Session 359](session_00359_log.md): Ran H560 signal mass entropy regime test to see if Shannon entropy of S1 distribution per date is a hidden regime detector. FAILED (OPPOSITE): high_entropy (0.1067) < low_entropy (0.1447) by -0.0380. Entropy adds nothing on low_breadth (0.1477 vs 0.1475). Concentrated beats dispersed - opposite of hypothesis. Source: [session_00359_log.md](./session_00359_log.md), [20260517_154126_signal_mass_entropy_regime_research_branch.json../artifacts/run_summaries/20260517_154126_signal_mass_entropy_regime_research_branch.json).

- [Session 357](session_00357_log.md): Ran H549 signal ignorance as alpha test to see if composite of weak-signal regimes (high_breadth, ultra_negative, floor_pressure) forms an ignore signal. MIXED: high_breadth dates have worse IC (0.1149 vs 0.1277 baseline), but effect is weak (+0.0029 < +0.01 threshold). Without ignore regime IC=0.1306. Confirms H525 finding but not actionable. Ultra_negative/floor_pressure data unavailable. Source: [session_00357_log.md](./session_00357_log.md), [20260517_153449_signal_ignorance_alpha.json](../artifacts/run_summaries/20260517_153449_signal_ignorance_alpha.json).

- [Session 356](session_00356_log.md): Ran H548 quiet-state duration sweet spot test to see if quiet state (C16>=0.75) has opposite duration pattern to active state. FAILED: Decay pattern EXISTS (duration_1d_quiet 0.1193 > duration_8pl_quiet 0.0749, +0.0444), confirming opposite to active state. BUT quiet_state is ANTI-PREDICTIVE overall (IC=0.0859 vs baseline 0.1302, -0.0443). Decay exists but quiet is not a signal. Source: [session_00356_log.md](./session_00356_log.md), [20260517_152844_quiet_state_duration_sweet_spot_research_branch.json](../artifacts/run_summaries/20260517_152844_quiet_state_duration_sweet_spot_research_branch.json).

- [Session 355](session_00355_log.md): Ran H547 breadth-concentration interaction test to see if signal concentration (top-5 share of S1 mass) adds value on top of breadth filter. MIXED (OPPOSITE): distributed (low concentration) IC=0.2604 (+0.1306) BEATS concentrated (high concentration) IC=0.1955 (+0.0658) by +0.0648! Concentration effect goes the WRONG way - spread-out signal mass is stronger than concentrated. Confirms H543 composite×low_breadth=0.2364. Source: [session_00355_log.md](./session_00355_log.md), [20260517_152634_breadth_concentration_interaction_research_branch.json](../artifacts/run_summaries/20260517_152634_breadth_concentration_interaction_research_branch.json).

- [Session 354](session_00354_log.md): Ran H546 capacity direction as signal weight test to see if capacity_expanding can be used as continuous weight modifier. MIXED: weighting fails (0.1833 vs binary 0.1853), similar to H544. OPPOSITE finding: tight_contracting (0.1853) > tight_expanding (0.1828), opposite of H538. Binary tight capacity remains strong (+0.055 lift). Source: [session_00354_log.md](./session_00354_log.md), [20260517_152031_capacity_direction_as_signal_weight_research_branch.json](../artifacts/run_summaries/20260517_152031_capacity_direction_as_signal_weight_research_branch.json).

- [Session 353](session_00353_log.md): Ran H545 breadth-adaptive exit test to see if exit timing (fresh vs sustained) differs by breadth regime. FAILED (data-gated): sustained exit states + breadth filtering too sparse (0 positive years). Low breadth (0.2712) > high breadth (0.2525) confirms H525, but exit timing comparison impossible due to data limits. Source: [session_00353_log.md](./session_00353_log.md), [20260517_151919_breadth_adaptive_exit_rules_research_branch.json ../artifacts/run_summaries/20260517_151919_breadth_adaptive_exit_rules_research_branch.json).

- [Session 352](session_00352_log.md): Ran H544 duration-weighted signal test to see if log(1+consecutive_days_in_active) can be used as continuous weight modifier for S1. FAILED: weighted IC=0.0972 is MUCH WORSE than binary filter (duration_8pl IC=0.1832, difference -0.086). Duration works as FILTER (selecting stocks), not as continuous WEIGHT (multiplying S1). H534's "longer = stronger" finding applies to selection only, not weighting. Source: [session_00352_log.md](./session_00352_log.md), [20260517_151544_duration_weighted_signal_strength_research_branch.json](../artifacts/run_summaries/20260517_151544_duration_weighted_signal_strength_research_branch.json).

- [Session 351](session_00351_log.md): Ran H543 breadth-weighted composite test to see if C23/C24/C25/C26 COMPOSITE works better than raw S1 with breadth weighting. PASSED: composite × low_breadth IC=0.2364 (+0.1066 vs baseline) is STRONGEST, beats composite alone (0.1988, +0.0690) by +0.0376. The composite signal (OR of any C23/C24/C25/C26 firing) with binary low_breadth filter outperforms H530's failed S1 weighting approach. Binary low_breadth on raw S1 alone is weak (0.1299, +0.0001). Source: [session_00351_log.md](./session_00351_log.md), [20260517_151351_breadth_weighted_composite_research_branch.json](../artifacts/run_summaries/20260517_151351_breadth_weighted_composite_research_branch.json).

- [Session 350](session_00350_log.md): Ran H542 breadth transition momentum test to see if direction of breadth change (contracting vs steady low) adds value. MIXED: contracting_to_low IC=0.1467 (+0.0165 vs baseline) beats baseline but is essentially TIED with steady_low (IC=0.1463, +0.0004). Transition adds almost nothing over static low breadth - confirms H525 finding that low breadth is the regime marker, not the path to it. Source: [session_00350_log.md](./session_00350_log.md), [20260517_150617_breadth_transition_momentum_research_branch.json](../artifacts/run_summaries/20260517_150617_breadth_transition_momentum_research_branch.json).

- [Session 349](session_00349_log.md): Ran H541 capacity-volume-breadth triple test. FAILED (data-gated): Volume data loading insufficient (only 100 stock files). The triple intersection couldn't be computed. Source: [session_00349_log.md](./session_00349_log.md).

- [Session 348](session_00348_log.md): Ran H538 capacity expansion regime test to see if contracting capacity (fewer orders over time) beats static tight_capacity. MIXED - OPPOSITE FINDING: tight_expanding (more orders over time, IC=0.1697) beats tight_contracting (IC=0.1553) by +0.0144. More orders arriving into tight names indicates stronger signal, not fewer orders. Source: [session_00348_log.md](./session_00348_log.md), [20260517_150424_capacity_expansion_regime_research_branch.json](../artifacts/run_summaries/20260517_150424_capacity_expansion_regime_research_branch.json).

- [Session 347](session_00347_log.md): Ran H535 triple-intersection alpha test combining tight_capacity + low_breadth + active (C16<=0.2). MIXED: triple_intersection IC=0.1956 (+0.0653 vs baseline) is STRONG but IDENTICAL to active_low_breadth (same 19,886 rows). tight_capacity adds nothing beyond active+low_breadth - redundant component. Source: [session_00347_log.md](./session_00347_log.md), [20260517_150242_triple_intersection_alpha_research_branch.json](../artifacts/run_summaries/20260517_150242_triple_intersection_alpha_research_branch.json).

- [Session 346](session_00346_log.md): Ran H534 active state duration sweet spot test to see if time-since-entry into active state predicts IC differently. PASSED: duration_8pl (8+ days in active state) IC=0.1832 beats baseline (0.1302) by +0.0530 lift (> +0.01 threshold). KEY FINDING: Longer duration in active state predicts STRONGER signal, NOT decay! This contradicts H526/D046 decay findings - sustained presence in C16<=0.2 indicates persistent hidden demand, not signal exhaustion. Duration_4_7d (0.1812, +0.0510) and duration_2_3d (0.1722, +0.0420) also strong. Source: [session_00346_log.md](./session_00346_log.md), [20260517_150058_active_state_duration_sweet_spot_research_branch.json](../artifacts/run_summaries/20260517_150058_active_state_duration_sweet_spot_research_branch.json).

- [Session 345](session_00345_log.md): Ran H532 breadth-triggered entry decay detection to test if signal rebounds after high-breadth spikes. MIXED: post-spike alone (IC=0.1170) still below baseline (-0.0107), lift vs high-breadth only +0.0084 (< +0.01 threshold). NEW FINDING: lowbreadth_post_spike combo = IC=0.1982 (+0.0706 vs baseline), even stronger than H531! Low breadth remains the key driver. Source: [session_00345_log.md](./session_00345_log.md).

- [Session 344](session_00344_log.md): Ran H531 breadth-capacity intersection test combining tight_capacity (H474) + low_breadth (H529). PASSED: intersection IC=0.1979 beats best single (tight_capacity 0.1878) by +0.0100 lift exactly at threshold. Lift vs baseline +0.0702 (+55%). Controls confirm both components needed: loose capacity destroys signal even on low-breadth dates. 7/7 positive years. Source: [session_00344_log.md](./session_00344_log.md), [20260517_144733_breadth_capacity_intersection_research_branch.json](../artifacts/run_summaries/20260517_144733_breadth_capacity_intersection_research_branch.json).

- [Session 343](session_00343_log.md): Ran H530 breadth-weighted position sizing test to see if continuous 1/breadth weighting beats binary filter. FAILED: weighted_score (S1 × inv_breadth) IC=0.1057 is WORSE than baseline (-0.0220). weighted_rank (rank of weighted score) IC=0.1407 (+0.0130) beats baseline but not > binary filter (0.1428). Binary low_breadth filter remains the better implementation. Source: [session_00343_log.md](./session_00343_log.md), [20260517_144255_breadth_weighted_position_sizing_research_branch.json](../artifacts/run_summaries/20260517_144255_breadth_weighted_position_sizing_research_branch.json).

- [Session 342](session_00342_log.md): Ran H529 anti-breadth entry signal test to see if explicitly selecting low-breadth dates as entry timing adds value. PASSED: S1 on low_breadth_dates IC=0.1542 beats baseline (0.1277) by +0.0266 lift (> +0.01 threshold). High breadth dates IC=0.1085 (-0.0191) worse than baseline. Active+low_breadth still strongest (0.2013, +26% vs active alone). Anti-breadth entry timing is a pure regime amplifier even without C16 active state. Source: [session_00342_log.md](./session_00342_log.md), [20260517_144053_anti_breadth_entry_research_branch.json](../artifacts/run_summaries/20260517_144053_anti_breadth_entry_research_branch.json).

- [Session 341](session_00341_log.md): Ran H528 quiet-state × low-breadth intersection test. MIXED for quiet: intersection IC=0.1644 beats min (0.1542) but not > max+0.01 (needs 0.1652). SIGNIFICANT finding: active + low_breadth IC=0.2013 beats active alone (0.1597) by +0.0416 (+26% boost). Low-breadth dates amplify active-state signal quality. Source: [session_00341_log.md](./session_00341_log.md), [20260517_143514_quiet_low_breadth_intersection_research_branch.json](../artifacts/run_summaries/20260517_143514_quiet_low_breadth_intersection_research_branch.json).

- [Session 340](session_00340_log.md): Ran H527 quiet-state inverse alpha test to see if quiet stocks in active markets (high C23 coverage) are contrarian. FAILED: quiet_in_high_breadth IC=0.1248 vs quiet_in_low_breadth IC=0.1225, lift only +0.0022 (below 0.01 threshold). No contrarian effect. Confirms state_quiet is still strong (IC=0.1205, 11/11 pos yrs). Also confirms H525: high breadth = weaker signal (active in high breadth 0.1642 vs low 0.1759). Source: [session_00340_log.md](./session_00340_log.md), [20260517_142721_quiet_state_inverse_alpha_research_branch.json](../artifacts/run_summaries/20260517_142721_quiet_state_inverse_alpha_research_branch.json).

- [Session 339](session_00339_log.md): Ran H526 exit timing discovery to test if holding-duration (time-since-entry into C23) or exit conditions predict different IC. FAILED: fresh_entry IC=0.1693 vs sustained IC=0.1712, difference only -0.002 (essentially NO difference). Both beat baseline (+0.042 lift). Exit (first day out of C23) is weaker (IC=0.1386) but not enough to matter. Conclusion: holding duration doesn't matter - signal works equally well at entry and as sustained position. Source: [session_00339_log.md](./session_00339_log.md), [20260517_142504_exit_timing_discovery_research_branch.json](../artifacts/run_summaries/20260517_142504_exit_timing_discovery_research_branch.json).

- [Session 338](session_00338_log.md): Ran H525 cross-sectional breadth as regime signal test with date-level active-stock density. FAILED (opposite of hypothesis): High breadth dates have WORSE IC (0.1149 vs baseline 0.1277), while LOW breadth has BETTER IC (0.1454, +0.0177 lift). When many stocks activate together it's a crowded regime with weaker signal. Quintiles uniform at 0.1454 suggesting binary distinction. Source: [session_00338_log.md](./session_00338_log.md), [20260517_141225_cross_sectional_breadth_research_branch.json](../artifacts/run_summaries/20260517_141225_cross_sectional_breadth_research_branch.json).

- [Session 337](session_00337_log.md): Ran H524 state combination alpha test with union (OR) and intersection (AND) logic combos of latent states. FAILED: combo states do NOT capture info beyond individual states. Best combo (`intersect_router_buyable` IC=0.1796) is only +0.0002 lift over best individual (`state_router` IC=0.1795). Union combos actually hurt (dilute signal). Key discovery: `state_quiet` is STRONG (IC=0.1552, 11/11 pos yrs), not neutral as previously assumed. Source: [session_00337_log.md](./session_00337_log.md), [20260517_141104_state_combo_alpha_research_branch.json](../artifacts/run_summaries/20260517_141104_state_combo_alpha_research_branch.json).

- [Session 336](session_00336_log.md): Ran H523 cross-sectional relative state encoding test with market/sector percentile features. FAILED: relative encoding (best `relative_active_market_top20` IC=0.2176) is -0.0082 below absolute best (`state_router` IC=0.2258). Participation pressure captured by specific mechanism (low C16), not relative ranking. Cross states too sparse. Source: [session_00336_log.md](./session_00336_log.md), [20260517_140345_cross_sectional_relative_state_research_branch.json](../artifacts/run_summaries/20260517_140345_cross_sectional_relative_state_research_branch.json).

- [Session 335](session_00335_log.md): Ran H522 transition dynamics alpha test with transition features (just_transitioned, transition_to_X flags, days_in_state). FAILED: best transition (`transition_to_router` IC=0.2246) is essentially identical to static state (`state_router` IC=0.2258), lift -0.0012. Duration features also don't help (long duration is anti-predictive, 5/11 positive years). Conclusion: transitions are NOT the alpha - static states ARE the signal. H507's coherent flow pattern is structural, not predictive incremental. Source: [session_00335_log.md](./session_00335_log.md), [20260517_140052_transition_dynamics_alpha_research_branch.json](../artifacts/run_summaries/20260517_140052_transition_dynamics_alpha_research_branch.json).

- [Session 334](session_00334_log.md): Ran H521 balanced carry-amplified search with weak carry features (simple lags: lag2_order_volume_ratio_rank, lag2_buy_sell_imbalance_norm, order_pressure_sustain). MIXED (5/7 gates): even weak features improve carry (+25%: 0.136 vs base 0.109) but still degrade amplified (-38%: 0.034 vs base 0.055). Conclusion: carry and amplified are structurally in tension in observable manifold - this is a latent property, not feature engineering. Branch conclusion: carry-amplified conflict documented. Source: [session_00334_log.md](./session_00334_log.md), [20260517_135555_balanced_carry_amplified_search_research_branch.json](../artifacts/run_summaries/20260517_135555_balanced_carry_amplified_search_research_branch.json).

- [Session 333](session_00333_log.md): Ran H519 carry-axis representation refinement with carry-focused temporal features (flow_persist, imbalance_persist, order_pressure_sustain). MIXED (5/7 gates): carry Jaccard improved significantly (`0.146` vs H518 `0.090`, +62%), but amplified Jaccard degraded (`0.031` vs H518 `0.151`, -80%). Trade-off is intrinsic to carry-focused features. Next: find minimal carry feature set or document carry/amplified conflict. Source: [session_00333_log.md](./session_00333_log.md), [20260517_135318_carry_axis_refinement_research_branch.json](../artifacts/run_summaries/20260517_135318_carry_axis_refinement_research_branch.json).

- [Session 332](session_00332_log.md): Ran H518 carry-axis bottleneck audit on the H515 guarded variant. PASSED (diagnostic): carry remains the weakest overlap axis (`jaccard 0.090`) versus onset (`0.208`) and amplified (`0.151`), but carry best-cluster IC is stable (`11/11` positive years). Conclusion: carry issue is representation-overlap bottleneck, not phase instability. Source: [session_00332_log.md](./session_00332_log.md), [20260517_134504_carry_axis_bottleneck_audit_research_branch.json](../artifacts/run_summaries/20260517_134504_carry_axis_bottleneck_audit_research_branch.json).

- [Session 331](session_00331_log.md): Ran H517 active-k selection contract audit. PASSED: guarded rule (`amp>=0.06`, `mean_disentangle>=0.10`, `lift_gap>=0.01`, `strong_clusters>=2`, silhouette tie-break) leaves H512 unchanged (`k=4`) but corrects H514 from silhouette `k=3` (`amp 0.032`) to guarded `k=5` (`amp 0.151`) while preserving lift/strength gates. Decision: SUPPORTS guarded selection contract. Source: [session_00331_log.md](./session_00331_log.md), [20260517_134248_active_k_selection_contract_audit_research_branch.json](../artifacts/run_summaries/20260517_134248_active_k_selection_contract_audit_research_branch.json).

- [Session 330](session_00330_log.md): Ran H516 robustness audit on H515 forced-`k=5` amplified-refinement variant. PASSED: two strong non-sparse clusters remain, both phase-positive out of dev, and dominant share `0.655` stays below one-pocket guardrail `0.80`. Confirms amplified-axis gain is structurally robust, not a sparse artifact. Source: [session_00330_log.md](./session_00330_log.md), [20260517_133945_h512_phase_stability_audit_research_branch.json](../artifacts/run_summaries/20260517_133945_h512_phase_stability_audit_research_branch.json).

- [Session 329](session_00329_log.md): Ran H515 forced active-`k=5` follow-through on H514 refined features. PASSED: quiet/C24 preservation holds (`0.963`/`0.966`), active-vs-random gap remains positive (`+0.0479`), and amplified-axis separation improves sharply (`max Jaccard 0.151` vs H512 `0.060`). Source: [session_00329_log.md](./session_00329_log.md), [20260517_133818_amplified_axis_refinement_research_branch.json](../artifacts/run_summaries/20260517_133818_amplified_axis_refinement_research_branch.json).

- [Session 328](session_00328_log.md): Ran H514 feature-augmented amplified-axis refinement with dev-silhouette active-k selection. MIXED: onset separation improved, but selected `k=3` degraded amplified-axis overlap (`0.032`), missing the main objective. This isolated selection-vs-representation as the immediate follow-through question. Source: [session_00328_log.md](./session_00328_log.md), [20260517_133731_amplified_axis_refinement_research_branch.json](../artifacts/run_summaries/20260517_133731_amplified_axis_refinement_research_branch.json).

- [Session 327](session_00327_log.md): Ran H513 H512 phase/year stability audit. PASSED: two strong non-sparse active clusters survive (`avg IC 0.2067` and `0.1873`), both remain positive in validation and confirmation, and dominant cluster share is `0.576` (well below one-pocket guardrail `0.80`). Verdict: supports H512 robustness, not a single sparse-pocket artifact. Source: [session_00327_log.md](./session_00327_log.md), [20260517_132509_h512_phase_stability_audit_research_branch.json](../artifacts/run_summaries/20260517_132509_h512_phase_stability_audit_research_branch.json).

- [Session 326](session_00326_log.md): Ran H512 C24-preserving active-manifold refinement (forced global `k=4`, then dev-silhouette active `k=4`). PASSED: quiet recovery `0.9634`, C24 recovery restored `0.9660`, active-vs-random lift gap `+0.0604`, mean onset/amplified/carry max-Jaccard `0.1048`, and 2 strong non-sparse active clusters. This resolves H511's negative result as a representation-selection issue and reopens the structural queue under strict dev-only discipline. Source: [session_00326_log.md](./session_00326_log.md), [20260517_132235_active_manifold_disentangling_research_branch.json](../artifacts/run_summaries/20260517_132235_active_manifold_disentangling_research_branch.json).

- [Session 325](session_00325_log.md): Ran H511 active-manifold disentangling with strict dev-only `k` selection on H509 artifacts. FAILED: quiet recovery stayed strong (`0.99797`), and active clusters beat random (`+0.04266` lift gap), but C24 recovery dropped (`0.5911` symbolic-in-cluster) and onset/amplification/carry disentangling stayed weak (mean max-Jaccard `0.0592`, only one strong non-sparse active cluster). Source: [session_00325_log.md](./session_00325_log.md), [20260517_131855_active_manifold_disentangling_research_branch.json](../artifacts/run_summaries/20260517_131855_active_manifold_disentangling_research_branch.json).

- [Session 324](session_00324_log.md): H510 Bull Participation State Audit. NEGATIVE FINDING: Used H509 clustered panel (k=6) to compare failure bull years (2017, 2025) vs success contrast (2021, 2022). C23 active state is HIGHER in failure years (4.55%) than success years (3.97%). 2017 IC (0.149) is STRONGER than 2021 (0.123) or 2022 (0.082). Latent state ecology does NOT explain heuristic-trader cash drag; problem is execution/portfolio construction in heuristic-trader. Source: [session_00324_log.md](./session_00324_log.md).

- [Session 139](session_00139_log.md): Ran skeptical interpretation audit on H509 artifacts only (no new experiments). Clarified that H509 robustly recovers quiet-vs-active structure and a convincing C24-like queue-friction channel, while onset/amplification/carry remain entangled; also flagged that `k=6` selection is informative but not uniquely proven because k-choice used full-period IC diagnostics. Source: [session_00139_log.md](./session_00139_log.md).

- [Session 139](session_00139_log.md): Ran H509 latent-state discovery (unsupervised emission clustering, dev-fit/frozen assign, `k=4/5/6`). SUPPORTS latent ontology with caveat: strong quiet-vs-active separation, stable phase centroids, and clear beat vs random partition (`k=6` lift gap `+0.0746`), plus meaningful C24-like rediscovery; onset/amplification/carry remain diffuse rather than clean one-to-one latent matches. Source: [session_00139_log.md](./session_00139_log.md).

- [Session 139](session_00139_log.md): Ran H508 router-equivalence / residual-ablation. STRUCTURE_PASS: freshness/cofire/low-C16 are nested C23 projections (all three have zero residual rows outside C23 by construction), while C24 remains distinctly strong outside C23 (`C24 | not C23`: IC=0.2559 on 8,329 rows). Compression result: one dominant C23-family primitive + router/timing layers + distinct C24 emission. Source: [session_00139_log.md](./session_00139_log.md).

- [Session 139](session_00139_log.md): Ran H507 latent-state switching structural audit (2015-2025 only). SUPPORTS latent-state view: non-quiet emissions (onset/amplified/router/carry) all show materially higher IC than baseline with 11/11 positive years; transitions are coherent (`onset/amplified/router -> carry -> quiet`) and global self-transition probability is high (`0.8692`). Caveat: strongest states remain sparse (router coverage 1.57%, amplified 2.08%). Next best action: H508 router-equivalence ablation. Source: [session_00139_log.md](./session_00139_log.md).

- [Session 138](session_00138_log.md): Batch 17 BU5 sector_vol_regime. MIXED: sector×C23 IC=0.2223 (+0.0919) marginally beats C23 alone (+0.0873) by +0.0046, but sector_c23 is VERY sparse (2853 rows, only 2/11 positive years), validation NaN. Sector vol regime not robust. Source: [session_00138_log.md](./session_00138_log.md).

- [Session 137](session_00137_log.md): Batch 17 BU4 cross_signal_day_complementarity. PASSED but MIXED insight: always_C23 IC=0.2176 (+0.0874 lift) is STRONGEST; any_signal (union) IC=0.1753 (+0.0451) is weaker; cofire_2 IC=0.2069 (+0.0767) confirms F412 regime strength. Signal routing does NOT beat always-C23. Source: [session_00137_log.md](./session_00137_log.md).

- [Session 136](session_00136_log.md): Batch 17 BU3 multi_day_c23_accumulation. MIXED: 2d consecutive (IC=0.2014, +0.0712) marginally beats single_day (0.2007, +0.0705) by +0.0007, but 3d degrades (0.1925, +0.0623). More accumulation after 2d hurts. Consistent with D046 signal decay. Source: [session_00136_log.md](./session_00136_log.md).

- [Session 135](session_00135_log.md): Batch 17 BU2 c17_standalone. FAILED: raw C17 IC=0.1623 vs ranked C16 IC=0.1670 (-0.0048). Raw is WORSE than ranked — blending does NOT strip info. Both high/low symmetric. Dead-end D049. Source: [session_00135_log.md](./session_00135_log.md).

- [Session 134](session_00134_log.md): Batch 17 BU1 market_wide_vol_regime. MIXED: market_vol×C23 IC=0.2006 (+0.0708, 11/11) vs ticker_vol×C23 IC=0.2616 (+0.1318). Market-level vol expansion is REAL but WEAKER than ticker-level by +0.061. Key finding: regime amplification works at STOCK level, not market level. Source: [session_00134_log.md](./session_00134_log.md).

- [Session 132](session_00132_log.md): Batch 16 COMPLETE (BR1-BR10). 3 PASSED: BR1 cofire_2 IC=0.2463 (+0.1165), BR3 illiq alone IC=0.1793 (+0.0495), BR10 c16_low×C23 IC=0.2838 (+0.1540) BEST this session. 5 MIXED: BR2 vol degree monotonic, BR5 market sentiment diff tiny, BR6 spread×vol +0.0239, BR8 illiq+vwap+exp 0.2795, BR9 signal decay confirmed. 2 FAILED: BR4 breadth combo WORSE than C23 (D047), BR7 stable queue too sparse (D048). Source: [session_00132_log.md](./session_00132_log.md).

- [Session 131](session_00131_log.md): Ran H486 `lagged_signal_decay` (BJ queue) to test if C23/C24 work at 2d/3d horizons. FAILED: C24 1d=0.2291 → 2d=-0.0302 (-0.2593 lift!), C23 1d=0.0844 → 2d=0.0323 (-0.0520). Signals DECAY massively at longer horizons, best at 1d. Dead-end D046. Finding F411. Source: [session_00131_log.md](./session_00131_log.md).

- [Session 131](session_00131_log.md): Ran H485 `floor_pressure_symmetry` (BG queue) to test if floor pressure (hitting -7% limit 2+ times) mirrors ceiling (C24). FAILED: floor_2_of_3 IC=0.0818 (-0.0483 lift vs baseline), floor_2_expansion IC=0.0575 (-0.0726). Floor pressure is anti-predictive, NOT symmetric to ceiling. C24 (ceiling_2_of_3 IC=0.2353) confirmed. Dead-end D045. Finding F410. Source: [session_00131_log.md](./session_00131_log.md).

- [Session 131](session_00131_log.md): Ran H482 `sentiment_scope_filter` to test if ultra_negative filters S1 quality. FAILED: filter effect +0.0034 is below +0.01 threshold. Ultra_negative does NOT identify noise states - S1 is robust across sentiment regimes. Finding F409: sentiment extremes do not filter signal quality. Source: [session_00131_log.md](./session_00131_log.md).

- [Session 130](session_00130_log.md): Ran H481 `breadth_threshold_finder` to find exact breadth cutoff where signal switches. PASSED: NO discrete switch - pattern is MONOTONIC. Best narrow threshold 5% = +0.0200 IC lift. Narrow markets consistently positive across all thresholds, broad markets consistently negative. Finding F408: use narrow market (bottom 10-20%) as soft regime amplifier. Source: [session_00130_log.md](./session_00130_log.md).

- [Session 129](session_00129_log.md): Ran H480 `extreme_negative_sentiment` to test extreme negative PhoBERT for capitulation-reversal. PASSED: ultra_negative (bottom 5% prob_neg) = IC 0.1068 (+0.0100 lift, 8/8). Extreme negative at bottom 10% is marginal (+0.0004). Finding F407: ultra_negative is new signal state capturing capitulation-reversal mechanism. Source: [session_00129_log.md](./session_00129_log.md).

- [Session 128](session_00128_log.md): Ran H479 `adaptive_signal_weights` to test IC-weighted C23-C26 vs equal weight. FAILED: IC-weighted (0.1760) vs equal weight (0.1754) = only +0.0007 improvement, below +0.005 threshold. Equal weight composite works just as well. Dead-end D043 - adaptive weighting via rolling IC does NOT outperform equal weight. Finding F406: signals share vol_expansion as common amplifier, so relative predictive power stays stable. Source: [session_00128_log.md](./session_00128_log.md).

- [Session 127](session_00127_log.md): Ran H441 `replacement_quality_delta` to test if quality CHANGE (delta S1) predicts forward IC. MIXED (weak): strong_positive_delta (delta > 0.05) = IC 0.1206 (+0.0012 lift, 8/8) — marginal; positive_delta = IC 0.1169 (-0.0025, BELOW baseline); negative_delta = IC 0.0837 (-0.0357 BELOW). Quality change is weaker than quality LEVEL (H437 entering=0.066). Dead-end D042 - quality delta does not rescue quality level. Not promotion-worthy. Source: [session_00127_log.md](./session_00127_log.md).

- [Session 126](session_00126_log.md): Investigated OpenCode slash-command / skill / compaction behavior end-to-end for the evergreen loop. Confirmed that `/bright-mind`, `/experimentor`, and `/manh-memory-system` are real installed OpenCode skills and load correctly in `opencode run` from positional args, stdin, and continued sessions because the build agent interprets the user text. Confirmed that `/compact` is different: stdin `/compact` is stored as literal text, while real interactive compaction is stored as a dedicated `compaction` message part. Patched the loop to use one fresh OpenCode session per cycle, explicit `--session <id>` reuse within the cycle, and a durable `evergreen-research-loop/state/cycle_handoff.md` file instead of fake `/compact`. Set the safe operator defaults to `MAX_CYCLES=1` and `SESSION_BATCH_SIZE=1` so no-arg loop runs stay bounded. Source: [session_00126_log.md](./session_00126_log.md).

- [Session 125](session_00125_log.md): Ran H478 `zero_liquidity_anomaly` (AR queue). MIXED: Zero volume states have 0 rows (no order data exists when volume = 0, hypothesis untestable). BUT low_volume_high_c16 PASSES: IC 0.176 (+0.056 lift, 8/8 pos years) — independent confirmation of H474 tight_capacity mechanism. Finding F404: sparse order flow = hidden demand. Source: [session_00125_log.md](./session_00125_log.md).

- [Session 124](session_00124_log.md): Ran H477 `ap_residual_signal_discovery` (AP queue). MIXED: S1 residual after removing vol_expansion correlation = IC +0.0013 (7/11 positive years, 63.6%). Marginal but real — residual IC is positive, confirming S1 is not purely vol_expansion-driven. But IC is only 0.0013, not strong enough for promotion. All-rows residual = -0.001 (4/11), noise on average. Finding F403: S1 has a tiny independent component beyond vol_expansion, but the effect is fragile. Do not promote as signal; raw S1 remains primary. Source: [session_00124_log.md](./session_00124_log.md).

- [Session 123](session_00123_log.md): Ran H474 `capacity_as_signal_not_veto` (AN queue). PASSED: tight_capacity (Q1: lowest order count) = IC 0.184 (+0.065 lift, 8/8 pos years). loose_capacity = IC 0.074 (-0.046, anti-predictive). Mechanism: sparse order flow = hidden demand / under-followed alpha, not tradability. tight_expansion sparse (2/8 years). NEW capacity signal — fundamentally different from H391 binary release. Use as positive filter for low-activity names, not as veto. Source: [session_00123_log.md](./session_00123_log.md).

- [Session 122](session_00122_log.md): Ran H473 `news_velocity_as_signal` (AM queue). FAILED: high_velocity (Q5) = IC 0.088 (-0.032 lift) = ANTI-predictive. burst_has_news = IC 0.082 (-0.037). Fast-arriving news = crowd-following, not hidden alpha. mid_velocity only +0.008. Low_velocity too sparse (0 news). News velocity adds no value beyond presence. Dead-end. Source: [session_00122_log.md](./session_00122_log.md).

- [Session 121](session_00121_log.md): Ran H472 `liquidity_adjusted_return` (AL queue). FAILED: high LAR (Q5) = IC 0.087 (-0.032 lift) = ANTI-predictive. return_5d_pos_illiq = IC 0.163 (+0.044) = illiquid momentum (C23-style), not flow quality. return_5d_pos_liq = IC 0.052 (-0.067) = liquid crowd blowoff (confirms D036). The ratio collapses two correlated effects into one confusing metric that loses to raw components. Dead-end for LAR ratio. Source: [session_00121_log.md](./session_00121_log.md).

- [Session 120](session_00120_log.md): Ran H449 `order_flow_momentum` to test C16 acceleration (2nd diff) vs forward IC. PASSED but with OPPOSITE insight: c16_level_high IC=0.1614 (+0.0326 lift, 11/11) — BEST. BUT c16_accel_expanding IC=0.1219 (-0.0069), c16_accel_contracting IC=0.1303 (+0.0015) BOTH WORSE than baseline. ACCELERATION does NOT add value - the edge comes from LEVELS (high pressure), not MOMENTUM (changes in pressure). Confirms H443 pattern: both foreign flow momentum and C16 momentum are NEGATIVE. Confirms H446/H447 patterns: vol LEVEL matters, not change. Use C16 level as regime conditioner, not its derivative. Dead-end D041 for acceleration signals. Source: [session_00120_log.md](./session_00120_log.md).

- [Session 119](session_00119_log.md): Ran H469 `foreign_flow_momentum`. MIXED: ff_decel_exp IC=0.1376 (+0.0074, 11/11) — marginal, not promotion. Ran H470 `vwap_deviation_regime`. PASSED: NEW SIGNAL C25! vwap_below_10_exp IC=0.1733 (+0.0431 lift, 11/11). Mechanism: VWAP far below average + vol expansion in illiquid stocks. C25 is strong signal. Ran H471 `order_flow_microstructure_regime`. PASSED: NEW SIGNAL C26! buy_heavy_illiq_exp IC=0.1889 (+0.0587 lift, 11/11). Buy-heavy order flow + illiquidity + vol expansion = institutional hidden demand. Pattern confirmed: ALL strong signals share structure: behavior + illiquidity + vol_expansion. Do NOT combine C23/C24/C25/C26 as composite entries. Source: [session_00119_log.md](./session_00119_log.md).

- [Session 116](session_00116_log.md): Ran H463 `amihud_illiquidity_regime_combo`. PASSED: NEW SIGNAL C23! high_illiq_expansion IC=0.2616 (+0.1318 lift vs baseline 0.1298). STRONGEST signal found — +101% boost over baseline. OHLCV computed inline from 1227 per-ticker files (ticker extracted from filename). Source: [session_00116_log.md](./session_00116_log.md).

- [Session 115](session_00115_log.md): Ran H462 `activation_rate_hidden_signal` to test rank_change speed × vol_expansion. FAILED: rank_accelerating ANTI-predictive (-0.0166 lift). rank_accel_buy_expansion WORSE than buy_heavy_expansion (-0.0584). "Suddenly appearing = hidden info" hypothesis NOT supported. Dead-end D040. Source: [session_00115_log.md](./session_00115_log.md).

- [Session 114](session_00114_log.md): Ran H461 `momentum_regime_combo` to test if momentum improves C21 combos. MIXED: momentum doesn't improve C21 (-0.0017 to -0.0047). C21 signals are complete as-is. Source: [session_00114_log.md](./session_00114_log.md).

- [Session 113](session_00113_log.md): Ran H460 `volume_regime_dependency_of_signals`. PASSED: ALL signals work best in vol_expansion. Rankings: C21 sell_heavy_decel (0.2393) > C21 buy_heavy_accel (0.2338) > C22 approaching_ceiling (0.2170) > C20 buy_heavy_expansion (0.2105). Vol contraction NO-GO. Source: [session_00113_log.md](./session_00113_log.md).

- [Session 112](session_00112_log.md): Ran H456 `spread_turnover_regime`. MIXED: Wide spread amplifies signals (+0.0948), but tight side sparse. Dead-end D039. Source: [session_00112_log.md](./session_00112_log.md).

- [Session 111](session_00111_log.md): Ran H455 `sector_momentum_as_regime_not_filter`. FAILED: sector differences tiny, no router benefit. Dead-end D038. Source: [session_00111_log.md](./session_00111_log.md).

- [Session 110](session_00110_log.md): Ran H454 `implied_limit_proximity`. PASSED: NEW SIGNAL C22! approaching_ceiling IC=0.2170 (+0.0872 lift). Source: [session_00110_log.md](./session_00110_log.md).

- [Session 107](session_00107_log.md): Ran H451 `buy_sell_imbalance_in_stress` to test buy_sell_volume_imbalance × vol_regime. PASSED: buy_heavy_expansion IC=0.1809 (+0.0508 lift, 11/11 pos years) is STRONGEST! NEW SIGNAL - buy-heavy imbalance works ONLY in vol expansion (+0.0699 vs contraction). Sell-heavy always negative. Source: [session_00107_log.md](./session_00107_log.md).

- [Session 106](session_00106_log.md): Ran H450 `volume_acceleration_signal` to test vol_delta × return vs volume LEVEL × return. MIXED: Accel helps high return (+0.0474 vs level), but low_vol (+0.0522) still dominates overall. Source: [session_00106_log.md](./session_00106_log.md).

- [Session 105](session_00105_log.md): Ran H449 `vol_contraction_mean_reversion` to test vol_contraction × high_return vs vol_expansion × high_return. MIXED: Pattern confirmed real (combo vs momentum -0.0628), but vol_contraction_exhaustion has NEGATIVE IC (-0.0255) = mean reversion, not a positive long-only signal. vol_expansion_momentum (+0.0373) is the useful side. Dead-end D037 for direct long-only use. Source: [session_00105_log.md](./session_00105_log.md).

- [Session 104](session_00104_log.md): Ran H448 `vol_expansion_contrarian_combo` to test vol_expansion (H446) × low_return_low_vol (H447) combo. PASSED: COMBO IC=0.2069 (+0.0771 lift, 11/11 pos years) is STRONGEST! Beats vol_expansion alone by +0.0316, beats low_return_low_vol alone by +0.0025. Captures oversold-in-expanding-vol regime better than either component alone. New signal - use as conditioner. Source: [session_00104_log.md](./session_00104_log.md).

- [Session 103](session_00103_log.md): Ran H447 `volume_adjusted_price_momentum` to test return/volume buckets for forward IC. MIXED (OPPOSITE of hypothesis): low_return_low_vol IC=0.2045 (+0.0746 lift, 11/11 pos years) is STRONGEST - this is CONTRARIAN not momentum. high_return_high_vol (real_force) IC=0.1109 (-0.019 lift) UNDERPERFORMS. Hypothesis inverted: cheap moves work, real force doesn't. Dead-end D036. Source: [session_00103_log.md](./session_00103_log.md).

- [Session 326](session_00102_log.md): Ran H446 `volatility_regime_transition` to test vol 5d change (expansion vs contraction) vs forward IC. PASSED: vol_expansion (top 20% 5d vol change) has IC=0.1750 vs baseline 0.1301 (+0.0449 lift, 11/11 pos years). vol_contraction (bottom 20%) IC=0.1216 (-0.0085 lift). Volatility REGIME TRANSITION is a real signal - when vol is expanding, S1 quality improves significantly. Use as regime conditioner. Source: [session_00102_log.md](./session_00102_log.md).

- [Session 325](session_00101_log.md): Ran H445 `semantic_novelty_saturation` to test news novelty vs repetition. FAILED (NEGATIVE): All news states NEGATIVE IC lift. no_news (IC=0.1409) beats has_news (IC=0.1038) by +0.037. Exhaustion state worst (IC=0.0861, -0.0474 lift). News counts NOT predictive - degrade S1 quality. Dead-end D035. Source: [session_00101_log.md](./session_00101_log.md).

- [Session 324](session_00100_log.md): Ran H444 `signal_ignorance_weight` to test whether S1/C16 have regimes where they hurt. PASSED (offline evidence): Found strong ignorance opportunity - worst regime "low_ic_low_temp" has IC=-0.0034 (negative!) vs baseline 0.1335, lift -0.1369. High IC + high temp regime has IC=0.2606 (+0.1271 lift). Caveat: regime buckets use same-period IC (lookahead), not a deployable rule - shows POTENTIAL only. Use as diagnostic or requires lagged regime prediction for deployable version. Source: [session_00100_log.md](./session_00100_log.md).

- [Session 323](session_00323_log.md): Ran H443 `prop_foreign_predator_prey` to test predator-prey interaction between foreign and proprietary flows. FAILED: All predator-prey states (ff_sell_pt_buy_absorption IC=0.0621, ff_buy_pt_sell_distribution IC=0.0959, prop_follow_ff IC=0.0842) are BELOW baseline IC=0.1335. Raw foreign flow (ff_buy IC=0.1188, ff_sell IC=0.1004) also underperforms baseline. Hypothesis not supported - flow direction alone is not predictive. Dead-end D034. Source anchor: [session_00323_log.md](./session_00323_log.md).

- [Session 321](session_00321_log.md): Ran H442 `ticker_rank_acceleration` to test second derivative of C16 rank
  (acceleration = delta of delta) vs H431 first derivative. FAILED: Accel Up vs Down lift only +0.0009,
  near zero. C16 rank LEVEL dominates (IC=0.158 vs accel 0.120). Both accel_up/down+flow equal (~0.147).
  H431 worked because it's correlated with rank level, not as independent signal. Second derivative is noise.
  Dead-end D033. Source anchor: [session_00321_log.md](./session_00321_log.md).

- [Session 320](session_00320_log.md): Ran H441 `cross_ticker_correlation_shock` to test whether date-level
  cross-sectional correlation regime (high vs low) predicts forward IC. FAILED: High vs Low corr date
  lift only +0.0033, below 0.01 threshold. Secondary: C16 flow prefers high-corr dates (0.167 vs 0.144),
  first-news prefers low-corr dates (0.153 vs 0.130). Shock mechanism weak. Dead-end D032. Source anchor:
  [session_00320_log.md](./session_00320_log.md).

- [Session 319](session_00319_log.md): Ran H440 `news_novelty_first_repeat` to test whether first-in-N-days
  novelty (vs repeat coverage vs high-frequency) predicts forward IC. PASSED: First-in-5d IC=0.123
  beats repeat IC=0.091 (+0.032 lift, 8/8 pos years, 23266 rows). First+strong-flow IC=0.161 vs
  repeat+flow IC=0.140. Novelty is the key dimension, not just presence. Aligns with H383
  active-news confirmation and adds the NOVELTY dimension. Use as news-state conditioner. Source
  anchor: [session_00319_log.md](./session_00319_log.md).

- [Session 318](session_00318_log.md): Ran H439 `volatility_regime_transition` to test whether vol_z 5d change
  (expansion vs contraction) predicts forward IC differently than static vol. MIXED:
  High vol states are MUCH stronger (IC=0.17-0.20 vs 0.09-0.10 low vol). High vol+contracting
  IC=0.195 is strongest, but this is vol LEVEL effect, not transition effect. Transition
  component is weak (+0.009 expanding vs contracting overall). Aligns with H411 and H434:
  vol level matters, transition is secondary. Not promoted as new signal. Source anchor:
  [session_00318_log.md](./session_00318_log.md).

- [Session 317](session_00317_log.md): Ran H438 `news_consensus_divergence` to test whether news source
  disagreement vs consensus predicts forward IC. MIXED: Consensus IC=0.102 beats divergence IC=0.093
  (-0.0086 lift), opposite of hypothesis. Both positive but neither beats all-rows (0.120). Aligns
  with H382: source TYPE matters but consensus vs divergence does not create alpha. Neither
  promoted. Source anchor: [session_00317_log.md](./session_00317_log.md).

- [Session 316](session_00316_log.md): Ran H437 `replacement_quality_revival` to test whether
  quality (S1 IC) of entering tickers vs exiting tickers predicts forward alpha.
  FAILED: Exiting tickers IC=0.126 (STRONGEST), stable IC=0.079, entering IC=0.066
  (WEAKEST). Entering vs exiting lift = -0.060. Opposite of hypothesis. Aligns with
  H388 finding that fresh reappearances are not strong. Dead-end D031. Source anchor:
  [session_00316_log.md](./session_00316_log.md).

- [Session 315](session_00315_log.md): Ran H436 `signal_ignorance_weight` to test whether
  composite regime features predict signal degradation with cash/veto action.
  FAILED badly: Top-10 S1 in degrade-state still IC=0.10 (STRONGER than all-rows
  IC=0.12), while ignoring signal drops to IC=0.053. Composite degrade indicators
  do NOT capture signal degradation. S1/C16 are robust across regime conditions.
  Dead-end D030. Source anchor: [session_00315_log.md](./session_00315_log.md).

- [Session 314](session_00314_log.md): Ran H435 `candidate_rank_actual_gap` to test whether
  prediction error (ranker predicted vs actual) predicts forward returns.
  FAILED: small gaps have HIGH IC (0.28-0.64), large gaps have NEGATIVE IC
  (-0.79 to -0.83). When ranker is surprised it's NOISE, not alpha. Confirms H413
  ranker is well-calibrated. Dead-end D028. Source anchor:
  [session_00314_log.md](./session_00314_log.md).

- [Session 313](session_00313_log.md): Ran H434 `signal_strength_gating` to test
  whether signal strength (S1 rank × C18 rank product) predicts forward returns.
  PASSED: High strength (Q5) IC 0.0940 vs low strength (Q1) IC 0.0829 = +0.0111 lift.
  Works strongest in stress years (2020 +0.0553, 2021 +0.0710). Not a ranker
  replacement but useful as dynamic position sizing signal. Offline evidence only.
  Source anchor: [session_00313_log.md](./session_00313_log.md).

- [Session 312](session_00312_log.md): Ran H433 `state_transition_not_event` to test
  event-count delta (change) vs level as predictor. Computed daily event count
  from order_pressure_h359_active, computed delta, bucketed into quintiles.
  MIXED: D2 (moderate decreasing delta) best (+0.0088 lift), but pattern
  inconsistent. Event-count level negative IC (-0.0065), delta provides some
  value but not strong enough to promote. Source anchor:
  [session_00312_log.md](./session_00312_log.md).

- [Session 311](session_00311_log.md): Ran H432 `volume_price_divergence` to test
  return vs volume-z divergence as predictor. Computed return and volume-z
  quintiles, tested divergence states (real_force, fade, hidden_support, crowded).
  FAILED: all states have negative lift vs baseline. real_force = +0.0921 (-0.0261),
  fade = +0.0892 (-0.0289). Hypothesis not supported. Source anchor:
  [session_00311_log.md](./session_00311_log.md).

- [Session 310](session_00310_log.md): Ran H431 `cross_sectional_rank_delta` to test
  C16 rank change (delta) vs level as predictor. Computed rank delta from
  order_volume_ratio_rank, bucketed into quintiles, tested forward IC.
  PASSED: Q5_incr (increasing rank) has best IC +0.1290 (+0.0114 lift), 8/8
  pos years. C16 level = +0.0752, delta boosts to +0.1290. Validation confirms
  Q5_incr +0.1310 vs level +0.0633. New signal - use as conditioner. Source
  anchor: [session_00310_log.md](./session_00310_log.md).

- [Session 309](session_00309_log.md): Ran H430 `candidate_temperature_entropy` to test
  whether entropy of top-10 candidate scores predicts forward IC. Bucketed dates
  by full_top10_score_entropy quintiles. MIXED: Q2 best in dev (+0.0105), but
  validation shows high-entropy better (+0.0143). Pattern inconsistent - not a
  clean predictor. Source anchor: [session_00309_log.md](./session_00309_log.md).

- [Session 308](session_00308_log.md): Ran H429 `signal_half_life_router` to test
  whether pre-declared half-life classes (S1 slope, volume state) win only on
  their natural horizon vs random horizon controls. Bucketed tickers by S1 slope
  (momentum vs reversion) and volume state (high vs low), tested IC at 1d/2d/5d/10d.
  FAILED: All classes degrade at longer horizons, no horizon-specific advantage.
  1d baseline always best. Dead-end D027. Source anchor: [session_00308_log.md](./session_00308_log.md).

- [Session 307](session_00307_log.md): Ran H428 tests: (1) `ranker_error_taxonomy`
  - S1 rank degradation FAILED: Top S1 tickers IMPROVE next-day (+0.0263 IC), no
  decay found. (2) `bid_ask_midbook_imbalance` FAILED: higher imbalance has
  WORSE C16 IC (Q5-Q1 lift -0.0385 dev). Both below promotion threshold.
  Dead-ends D026, D027. Source anchor: [session_00307_log.md](./session_00307_log.md).

- [Session 306](session_00306_log.md): Ran H427 `volume_attention_budget` as
  date-level concentration test. Computed volume Herfindahl from order_stats,
  bucketed dates into concentration quintiles, tested S1 IC across regimes.
  PASSED: Q3 (mid-concentration) has mean IC 0.1389 vs baseline 0.1264,
  lift +0.0125, 8/8 positive years. Both extreme concentration and extreme
  distribution hurt signal quality. Offline evidence, needs candidate-count
  policy follow-through. Source anchor: Session 306.

- [Session 305](session_00305_log.md): Attempted to activate item 8
  `selector_hysteresis_field` from 2026-05-08 ideation queue. The branch
  needs panel-to-panel ticker transition tracking (prior appearances, incumbent rank
  distance, rank gaps). SKIPPED as data-gated: computing transition
  features requires iterating millions of ticker-date pairs without a
  reusable script. Simpler next candidate is item 3
  `volume_attention_budget` which uses date-level aggregation. Source
  anchor: Session 305.

- [Session 304](session_00304_log.md): Ran H426 `forced_seller_detector` with a
  reusable walk-forward entry-candidate script and random baselines only. H426
  FAILED: `forced_seller_core_buyable` had tiny same-support lift
  (`+0.00023`) but only `1 / 5` positive WF years and random-all lift
  `-0.00205`; floor and large-down variants also failed, and literal release
  had only `7` rows. The next-day C16 clause was not used because it is not
  decision-time valid under the current T close -> T+1 open entry-label
  contract. Source anchors: `D025`, Session 304.

- [Session 303](session_00303_log.md): Continued safe-first artifact hardening.
  Added lockbox-window-aware C10-C14 RL component caches with manifest
  fingerprints, exact old-inline parity checks, component-only reuse mode, and
  a lightweight artifact integrity CLI. Migrated H413 onto the additive harness
  with legacy summary fields preserved, and batched activation-meta derived
  columns to remove fragmentation warnings. Source anchor: Session 303.

- [Session 299](session_00299_log.md): Ran H418
  `foreign_additive` with reusable script
  `analysis/h418_foreign_additive.py`. Tested adding foreign flow to H413.
  H418 FAILED: foreign has +0.004 IC, adding HURTS (-0.006).
  Same pattern as C16 - too weak to contribute.
  Source anchors: `D023`.

- [Session 298](session_00298_log.md): Ran H417
  `holdout_2025` with reusable script
  `analysis/h417_holdout_2025.py`. Tested on completely held-out 2025.
  H417 PASSED: +0.014 lift on 2025 = same as long-term (+0.017).
  PROVES NOT survivor bias - pattern is REAL.
  Source anchors: `F381`.

- [Session 297](session_00297_log.md): Ran H416
  `market_state_gated` with reusable script
  `analysis/h416_market_state_gated.py`. Tested additive in VNI-up/down.
  H416 PASSED: works in BOTH market states (+0.016 to +0.018 lift).
  ROBUST pattern confirmed.
  Source anchors: `F380`.

- [Session 296](session_00296_log.md): Ran H415
  `weight_optimization` with reusable script
  `analysis/h415_weight_optimization.py`. Grid search Vol/S1 weights.
  H415 MIXED: 15V+85S = +0.136 IC, marginal +0.001 over H413.
  Optimum in 10-15% volume range. Keep H413 as standard.
  Source anchors: `F379`.

- [Session 295](session_00295_log.md): Ran H414
  `alternative_target_additive` with reusable script
  `analysis/h414_alternative_target_additive.py`. Tested Vol+S1 on 1d/10d/20d barriers.
  H414 PASSED: additive works on ALL horizons (+0.017 to +0.019 lift).
  This confirms generalizable pattern, not target-specific.
  Source anchors: `F378`.

- [Session 294](session_00294_log.md): Ran H413
  `triple_signal_additive` with reusable script
  `analysis/h413_triple_signal_additive.py`. Tested three-signal additive combos.
  H413 PASSED: 0.1×Vol + 0.9×S1 = +0.135 IC, beats H410 (+0.126) by +0.009.
  Lower volume weight (10% vs 25%) is key. New standard: 0.1V+0.9S.
  Source anchors: `F377`.

- [Session 293](session_00293_log.md): Ran H412
  `volume_c16_additive` with reusable script
  `analysis/h412_volume_c16_additive.py`. Tested Volume+C16 additive.
  H412 FAILED: additive doesn't beat Volume alone (+0.073 vs +0.075).
  C16 too weak to rescue. Source anchors: `F376`.

- [Session 292](session_00292_log.md): Ran H411
  `volume_triple_storm` with reusable script
  `analysis/h411_volume_triple_storm.py`. Tested Triple Storm on Volume.
  H411 FAILED: Volume+Triple = +0.038, WORSE than Volume alone (+0.075).
  Triple Storm is C16-specific, not universal amplifier.
  Source anchors: `F375`, `D022`.

- [Session 291](session_00291_log.md): Ran H410
  `volume_s1_additive` with reusable script
  `analysis/h410_volume_s1_additive.py`. Tested Volume+S1 additive combos.
  H410 PASSED: 0.25×Vol + 0.75×S1 = +0.12649 IC, beats both standalones!
  Adds +0.009 IC lift over S1 - additive beats cross-product.
  Source anchors: `F374`.

- [Session 290](session_00290_log.md): Ran H409
  `volume_c16_cross_product` with reusable script
  `analysis/h409_volume_c16_cross_product.py`. Tested Vol×C16 cross-product.
  H409 was MIXED: cross +0.017 but Volume alone +0.077 is NEW SIGNAL!
  CRITICAL: `order_volume_ratio` standalone is +0.077 IC, 8/8 pos years.
  Source anchors: `F373`.

- [Session 289](session_00289_log.md): Ran H408
  `s1_c16_cross_product` with reusable script
  `analysis/h408_s1_c16_cross_product.py`. Tested S1×C16 cross-product.
  H408 was MIXED: cross +0.108 but S1 alone +0.118 (worse).
  Source anchors: `F372`.

- [Session 288](session_00288_log.md): Ran H407
  `phase_lead` (simplified) with reusable script
  `analysis/h407_hilbert_phase_lead.py`. Tested lagged C16 × price cross-product.
  H407 PASSED: phase lag added +0.022 IC with 7/8 positive years.
  Source anchors: `F371`.

- [Session 282](session_00282_log.md): Ran H401
  `anti_signal_annihilation_veto` with reusable script
  `analysis/h401_anti_signal_annihilation_veto.py`. Fixed top-5 buyable
  candidate rows, no `2026+`, cycle relative-return labels, long-only cash
  vetoes with denominator `K=5`, and random same-breadth veto controls. H401
  was MIXED: strict `support_count_zero` had tiny lift versus no-veto
  (`+0.000167`, `6 / 7` positive years) and random mean (`+0.000152`), but did
  not beat random p95. Broader disagreement masks were negative versus no-veto.
  Source anchors: `F365`, `D017`.

- [Session 281](session_00281_log.md): Ran H400
  `calendar_as_weak_prior_not_clock` with reusable script
  `analysis/h400_calendar_as_weak_prior_not_clock.py`. Rebuilt the H395
  train-before-test quorum with calendar votes removed, then added one fixed
  calendar prior averaging January-first-10, Monday, month-end, and T+2 weekday
  residues. H400 FAILED: non-calendar quorum avg IC was `+0.05826`, calendar
  quorum avg IC fell to `+0.05605`, and calendar lift was `-0.00221` with
  `0 / 7` positive lift years. Calendar-only IC was `-0.00827`. Source
  anchors: `F364`, `D016`.

- [Session 280](session_00280_log.md): Ran H399
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

- [Session 279](session_00279_log.md): Ran H398
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

- [Session 278](session_00278_log.md): Ran H397
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

- [Session 277](session_00277_log.md): Ran H396
  `parent_echo_residual_harvester` with reusable script
  `analysis/h396_parent_echo_residual_harvester.py`. No `2026+`; test years
  `2019-2025`; same-date cross-sectional residualization of H395 and C4-C14
  votes against S1/C16, plus H395 residualization against all C-vote
  ingredients. H396 PASSED as a clarification: H395 survives S1/C16
  residualization (`+0.01669`, `7 / 7` positive years), but fails
  residualization against C votes (`+0.00187`), so it is a strong composite
  RL state, not a new primitive. C13/C10/C6 are the clean S1/C16 residual
  primitive survivors. Source anchor: `F360`.

- [Session 276](session_00276_log.md): Ran H395
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

- [Session 275](session_00275_log.md): Ran H394
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

- [Session 274](session_00274_log.md): Added the reusable lightweight
  research-branch scaffold: `src/experiment_contract.py` plus runnable copy
  template `analysis/_template_research_branch.py`. The contract provides
  role-safe S1 loading that renames raw `actual` to target-only
  `s1_barrier_hit_1d`, default `2026+` blocking, target/state overlap checks,
  yearly and phase IC helpers, and standard run-summary/artifact writes.
  Updated `README_for_AGENTS.md` and `README.md` so future agents start from
  the scaffold for state/signal/context audits. Source anchor: `F357`.

- [Session 273](session_00273_log.md): Clarified the signal-library promotion
  rule in `README.md`, `notes/signal_library.md`, and compact findings. Strong
  standalone promotion now explicitly means IC `> 0.05` plus decision-time
  observability, non-leakage, independence from existing library signals,
  positive-year consistency, and enough coverage. IC `0.01-0.05` is weak
  candidate/context evidence. Parent-signal filters must show incremental lift
  versus the parent and matched controls; absolute IC `> 0.05` alone is not a
  new independent promotion. Source anchor: `F356`.

- [Session 272](session_00272_log.md): Audited the S24x-S25x "strong" signal
  promotions with reusable script `analysis/audit_s24x_s25x_signal_claims.py`.
  The audit found that `actual` is a binary future 1d barrier label, so the
  S244/S246/S247/S253 market-down and consecutive-down states were partly
  target-derived. Leaky target-market-down ICs reproduced high
  (`+0.0925` / `+0.0951`), but observable VNI-down states dropped to
  `+0.0771` / `+0.0806` versus C16 baseline `+0.0738`; stock-down states were
  weaker than C16. `insider_lead_next_trading_day` survived (`+0.1050`,
  `11 / 11` positive years), while high buy-order-count volume context was
  modest (`+0.0844`). Source anchors: `F355`, `D012`.

- [Session 271](session_00271_log.md): Ran H393 `nihilist_reversal` with
  reusable script `analysis/h393_nihilist_reversal.py`. TRUE walk-forward
  `2018-2025`, no `2026+`, fixed high-C16, stock-down, VNI-down, and
  no-bullish-news definitions. H393 was MIXED: `nihilist_reversal` had mean
  5d payoff `+0.010170` but failed `stock_down_high_c16` by `-0.002027`, had
  only `+0.000169` lift versus parent `stock_market_down_high_c16`, and 2025
  payoff was `-0.000982`. `stock_down_high_c16` remains the cleaner state.
  Source anchors: `F354`, `D011`.

- [Session 270](session_00270_log.md): Ran H392 `source_triangle_sparse` with
  reusable script `analysis/h392_source_triangle_sparse.py`. TRUE
  walk-forward `2018-2025`, no `2026+`, fixed C16, C5 insider, source-news,
  and forward-text sensors. H392 was MIXED: the required
  `c16_insider_any_news` core had positive mean 5d payoff `+0.003177` but lost
  to `c16_insider_no_news` by `-0.007315`, to
  `c16_any_news_no_insider` by `-0.005205`, and had 2025 lift
  `-0.003072` versus exactly-two sensors. Broader `three_plus_sensors` beat
  exactly-two by `+0.005156` with `8 / 8` positive lift years, but the edge is
  not the insider+C16 triangle. Source anchors: `F353`, `D010`.

- [Session 269](session_00269_log.md): Ran H391
  `tradability_release_pulse` with reusable script
  `analysis/h391_tradability_release_pulse.py`. TRUE walk-forward
  `2021-2025`, no `2026+`, fixed top-5/top-10 release states from
  `release_flag`, and same-year same-rank stable/non-release buyable matched
  controls. H391 FAILED: `top5_release` mean cycle relative return was
  `-0.032254` with matched-control lift `-0.033668`, only `1 / 5` positive
  matched-control years, and 2025 lift `-0.080106`; `top10_release` was also
  negative with matched-control lift `-0.028365` and 2025 lift `-0.066302`.
  Source anchors: `F352`, `D009`.

- [Session 268](session_00268_log.md): Ran H390
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

- [Session 267](session_00267_log.md): Ran H389
  `post_ollama_event_cascade` with reusable script
  `analysis/h389_post_ollama_event_cascade.py`. The first run exposed
  non-finite target rows, so the script was patched and rerun; canonical
  artifacts are timestamp `20260504_203158`. TRUE walk-forward `2018-2025`,
  no `2026+`, guarded-Ollama first/repeat/family-transition event states, and
  5d relative-return payoffs. H389 FAILED: best state `event_first20` had mean
  lifts only `+0.00099` versus generic event and `+0.00114` versus repeat
  event, below the `+0.002` gate; no family pocket cleared MIXED. Source
  anchors: `F350`, `D007`.

- [Session 266](session_00266_log.md): Ran H388
  `fresh_selection_pulse` with reusable script
  `analysis/h388_fresh_selection_pulse.py`. Computed prior top-5/top-10
  appearances using only earlier panel dates; TRUE walk-forward `2021-2025`,
  no `2026+`, buyable candidate rows, and cycle relative-return labels. H388
  FAILED: `top5_fresh20` beat incumbents but failed stale-repeat control
  (mean lift `-0.00016`, 2025 lift `-0.00269`); `top10_fresh20` also failed
  stale-repeat control (mean lift `-0.00068`, 2025 lift `-0.00098`). Source
  anchors: `F349`, `D006`.

- [Session 265](session_00265_log.md): Ran H387
  `insider_down_rescue` with reusable script
  `analysis/h387_insider_down_rescue.py`. TRUE walk-forward `2018-2025`, no
  `2026+`, fixed positive-C5, 1d/3d stock-down, and high-C16 states, with 5d
  relative-return payoffs versus insider-only, insider-C16, and stock-down-C16
  controls. H387 FAILED: `insider_down_high_c16` beat ordinary insider rows
  but failed the meaningful controls, with mean 5d lift `+0.00087` versus
  `insider_high_c16` and `-0.00308` versus `stock_down_high_c16`; 2025 lifts
  versus both were negative. Source anchors: `F348`, `D005`.

- [Session 264](session_00264_log.md): Ran H386
  `official_delay_consumer_router` with reusable script
  `analysis/h386_official_delay_consumer_router.py`. TRUE walk-forward
  `2021-2025`, no `2026+`, fixed H385 official/forward supported states,
  train-before-test `K` choice only, deterministic candidate-rank selection,
  and random same-support plus random-all policy benchmarks. H386 FAILED:
  `official_supported` mean lift was `-0.00035` versus random-state and
  `-0.00540` versus random-all; `official_forward_supported` mean lift was
  `-0.00057` versus random-state and `-0.00555` versus random-all. Source
  anchors: `F347`, `D004`.

- [Session 263](session_00263_log.md): Ran H385
  `official_attention_delay` with reusable script
  `analysis/h385_official_attention_delay.py`. TRUE walk-forward `2018-2025`,
  no `2026+`, fixed official/forward local-news states, C16 or insider support,
  and 1d/5d excess-return payoffs versus unsupported official/forward controls.
  H385 PASSED as delayed offline evidence: `official_supported` 5d lift
  `+0.007408`, `8 / 8` positive 5d-lift years, 2025 lift `+0.005566`;
  `official_forward_supported` 5d lift `+0.007657`, `8 / 8` positive years,
  2025 lift `+0.006799`. Source anchor: `F346`.

- [Session 262](session_00262_log.md): Ran H384
  `news_flow_confirmation_consumer` with reusable script
  `analysis/h384_news_flow_confirmation_consumer.py`. TRUE walk-forward
  `2021-2025`, no `2026+`, fixed H383 states, train-before-test `K` choice
  only, and random same-support plus random-all candidate-policy benchmarks.
  H384 FAILED: `active_news_strong_flow` mean lift was `-0.00026` versus
  random-state and `-0.00337` versus random-all; `positive_news_strong_flow`
  mean lift was `-0.00020` versus random-state and `-0.00191` versus
  random-all. Source anchors: `F345`, `D003`.

- [Session 261](session_00261_log.md): Ran H383 `news_flow_disagreement` with
  reusable script `analysis/h383_news_flow_disagreement.py`. TRUE walk-forward
  `2018-2025`, no `2026+`, fixed C16/news state definitions, primary target
  1d close-to-close relative return versus VNINDEX, and secondary S1 `actual`
  diagnostics. H383 PASSED as confirmation rather than disagreement:
  `active_news_strong_flow` rel IC `+0.10293`, `8 / 8` positive years, 2025
  `+0.12163`, and lift `+0.04005` versus strong-flow; `positive_news_strong_flow`
  was also strong at `+0.10854`. No-news and weak-flow disagreement states did
  not beat baselines. Source anchor: `F344`.

- [Session 260](session_00260_log.md): Ran H382
  `h364_local_news_consumer_integration` with reusable script
  `analysis/h382_h364_local_news_consumer_integration.py`. TRUE walk-forward
  `2021-2025`, no `2026+`, train-before-test `K` choice only, and random
  candidate-policy benchmarks because this is not a direct S1/C16 variation.
  Script verdict PASSED on the primary same-support random-active benchmark:
  mean lift `+0.00092`, `4 / 5` years above random-active mean, and 2025 lift
  `+0.00296`. Caveat: broad random-all benchmark failed, mean lift `-0.00367`
  and only `1 / 5` years above random-all mean. Source anchors: `F343`, `D002`.

- [Session 259](session_00259_log.md): Confirmed `ollama_guarded_backfill`
  complete, patched H364 to accept the authorized no-cutoff full Ollama
  backfill while filtering the audit to `2016-2025`, refreshed the combined
  local-news aggregate overlay, and ran H364. H364 PASSED: best fixed feature
  `h364_official_sentiment_x_earnings_guidance` had avg IC `+0.01766`,
  dev/validation/confirmation IC `+0.0173 / +0.0200 / +0.0156`, `10 / 10`
  positive years, S1 corr `-0.0104`, and `103,248` active rows. Source anchor:
  `F342`.

- [Session 258](session_00258_log.md): Ran H381 `silent_order_pressure` with
  reusable script `analysis/h381_silent_order_pressure.py`. TRUE walk-forward
  `2018-2025`, no `2026+`, fixed no-news states, and direct C16 variation
  benchmarks. The branch FAILED: `silent_5d` C16 IC `+0.0700` was below all-C16
  `+0.0752` and active-5d-news C16 `+0.0846`; down-market no-news controls
  failed too. Removed `silent_order_pressure` from the active queue. Source
  anchors: `F341`, `D001`.

- [Session 257](session_00257_log.md): Ran H380 `candidate_count_policy_router`
  as the narrowed PP5 continuation. Reusable script
  `analysis/h380_candidate_count_policy_router.py`, TRUE walk-forward
  `2021-2025`, no `2026+`, and random policy baselines only. Candidate-count
  router PASSED as offline policy evidence: mean cycle return `+0.00796` vs
  random K/cash `+0.00407`, lift `+0.00389`, `4 / 5` years above random
  K/cash mean, and 2025 lift `+0.00472`. Not live-promoted; 2021 failed and
  this remains policy state, not ticker alpha. Source anchor: `F340`.

- [Session 256](session_00256_log.md): Added
  [portfolio_policy_library.md](portfolio_policy_library.md) as the sibling
  registry to `signal_library.md` for K/exposure/hold/veto/release state.
  Captured current surfaces, action vocabulary, policy-state feature families,
  active frozen policy components, H379 offline evidence, queued policy
  hypotheses, and the future `portfolio_policy_state_daily` promotion path.
  No experiment was run and no live branch changed.

- [Session 255](session_00255_log.md): Ran H379
  `dynamic_candidate_thermodynamics` as the next queue item with reusable script
  `analysis/h379_dynamic_candidate_thermodynamics.py`. TRUE walk-forward
  `2021-2025`, no `2026+`, and random K-policy baselines only. The tiny
  date-level K/cash router PASSED as offline evidence: mean cycle return
  `+0.00665` vs random invested `+0.00508`, lift `+0.00157`, `4 / 5` years
  above random mean, 2025 lift `+0.00108`; not live-promoted because only
  `1 / 5` years beat random p95. Source anchor: `F339`.

- [Session 254](session_00254_log.md): Bright-mind eureka refresh and live-state
  queue cleanup. Reconstructed current beliefs, verified the active
  `ollama_guarded_backfill` status at `6298 / 7344` batches, collapsed the stale
  multi-thousand-line hypothesis dump into a concise 10-item queue, and ranked
  new falsifiable branches around no-news order pressure, text-flow
  disagreement, official-delay confirmation, dynamic breadth, insider-down
  rescue, selection freshness, and post-Ollama event cascades.

- [Session 253](session_00253_log.md): Superseded by S272. The original log
  claimed TRUE walk-forward validation passed for insider lead, consecutive
  down, and down-market C16, but S272 found the market/consecutive states were
  target-derived and the train/test protocol was not the advertised TRUE WF.
  Keep only the insider-lead survivor. Source anchors: `F355`, `D012`.

- [Sessions 248-252](session_00248_00252_log.md): Bright-mind eureka tests - **ALL 5 FAILED**.
  - S248 macro_c16_regime: FAILED (+0%) - no regime boost.
  - S249 gap_open_c16: FAILED (-4%) - no gap help.
  - S250 vol_shock: FAILED (data proxy insufficient).
  - S251 consecutive_down: FAILED (+0%) - no day-to-day compounding.
  - S252 c16_extreme: FAILED (-63%) - too sparse.
  - S272 later corrected the target-derived down-market/consecutive framing;
    keep only the non-leaky failed-filter conclusions here.

- [Sessions 245-247](session_00245_log.md): C16 contrarian tests. S245 failed;
  S246/S247 down-market/deep-down promotions are superseded by S272 because
  their market states were derived from same-date S1 `actual`, not observable
  returns. Observable VNI-down context is only modest. Source anchors: `F355`,
  `D012`.

- [Session 244](session_00244_log.md): S244 eureka tests - **5 signals tested**.
  - insider_buy_lead PASSED (+40% boost): IC=0.1113, still survives S272 at
    `+0.1050`.
  - c16_entropy FAILED (inconsistent year-to-year): WEAK - dead end.
  - disclosure_shock_reaction: NO DATA (empty source).
  - S272 invalidated the old `consecutive_down` promotion and downgraded
    dividend / rank-time acceleration to weak context. Source anchors: `F355`,
    `D012`.
- [Session 243](session_00243_log.md): Calendar + combo tests.
- [Session 243](session_00243_log.md): Calendar + combo tests.
  monday_jan_combo IC=0.1109 (+42% - STRONGEST!), feb_mid +10%, march_late +7%.
  yearend -16%, midyear -9% FAILED.
  x240_wf_ic_test.py reusable script updated.
- [Session 242](session_00242_log.md): January effect + volume regime confirmation.
  january_first_10 IC=0.0817 (+5% boost), vol_high IC=0.0941 (+21%).
  Reusable x240_wf_ic_test.py script updated.
- [Session 232](session_00232_log.md): Triple Storm Extensions — 6 PASSED, 3 FAILED.
  Universal: works on order/volume/reversal/skewness, NOT on position (foreign/sector).
  x232_triple_test.py reusable script.
  All signals 9/9 years positive. Triple Storm +92% in WF.
- [Session 230](session_00230_log.md): Triple Storm HOLDOUT — CONFIRMED.
- [Session 229](session_00229_log.md): triple_storm — **DISCOVERED** (+104%).
  Liquid + DOWN + divergence = IC +0.158 vs baseline +0.078.
- [Session 228](session_00228_log.md): c16_divergence — WEAK PASS (+39%).
  Price disagree with C16 = IC +0.108 vs baseline +0.078 (+39%). Divergence works.
- [Session 227](session_00227_log.md): c16_acceleration — FAILED.
  C16 level IC +0.078 vs ROC IC +0.056 (-28%). Level wins.
- [Sessions 224-226](session_00224_00226_log.md): New C16 branches.
  X224 sector-relative: FAILED (-15%). X225 persistence: FAILED (-17%).
  X226 market-state: PASSED - C16 +26% stronger in DOWN markets (+0.098 vs +0.056).
- [Session 223](session_00223_log.md): sector_convergence_contrarian — FAILED.
  Fragmented + high C16: IC +0.035 vs baseline +0.078 (-55%).
  Kill branch.
- [Session 222](session_00222_log.md): dynamic_liquidity_regime — WEAK PASS.
  High market regime: +0.081 vs Low: +0.074 (diff +0.007, ~8%)
  Not enough for regime switching, could use for sizing only.
- [Session 221](session_00221_log.md): liquid_braid_stack TEST — MIXED.
  X53 (liquid): +25% IC ✅. X54 (braid): +3%. Stack: -18% ❌.
  Stacking FILTERS HURTS. Use X53 alone, not both.
- [Session 220](session_00220_log.md): X51-X55 stochastic resonance batch - SUPER PASS.
  X53 (Liquid C16): C16 + high move >80%ile = IC +0.137 (+52% vs baseline +0.090).
  X54 (Braid): Low sector kurtosis = unanimous pressure = IC +0.080 vs +0.031 (+160%).
  Scripts: x51, x52, x53v2, x54, x55.
- [Session 219](session_00219_log.md): H365-H378 + X1-X5 batch — ALL FAILED except C16 baseline.
  Tested: H372 (vol→price), H373 (sector), H374 (early session), H375 (ROC), H377 (curvature), X1 (auction), X2 (exhaustion), X5 (lunar). C16 remains champion +0.077 to +0.084.
- [Session 218](session_00218_log.md): X72 volume regime — FAILED (c8 combo hurts C16).
- [Session 217](session_00217_log.md): X75 Benford Law — FAILED (IC +0.0023).
- [Session 216](session_00216_log.md): H366 order+ceiling — FAILED.
- [Session 215](session_00215_log.md): H367 order+gap — FAILED.
- [Session 214](session_00214_log.md): H365 C16 standalone — PASSED.
  C16 standalone beats full_library baseline on val IR 1.98 (vs 0.85), val ret +1.47%
  (vs +0.45%), clean execution health. PASSED as offline evidence.

- [Session 212](./session_00212_log.md): Recovered the evergreen loop while
  `ollama_guarded_backfill` was running, found the active run had reverted to
  an empty cutoff and the non-lockbox `146,872`-row input, stopped it before it
  reached the known post-2025 tail, verified the `120` newly appended score
  cache rows were all Dec 2023, and relaunched the checkpoint-safe
  `--max-published-at 2025-12-31T23:59:59+07:00` command. The corrected input
  manifest is back to `142,296` rows with `4,576` date-filtered articles, H364
  readiness now blocks until the final Ollama ticker-day dataset exists, and
  H364 was hardened to reject missing lockbox cutoffs.

- [Session 211](./session_00211_log.md): Resumed the guarded Ollama residual
  backfill at the user's request, but first found that the existing input cache
  included a `2026` tail. Added a cutoff-aware `--max-published-at` path,
  rebuilt the input cache to `142,296` rows with max timestamp
  `2025-12-31T20:40:05+07:00`, launched `ollama_guarded_backfill` in tmux with
  `2026+` excluded, then stopped it for the day at `3,638 / 7,115` checkpoint
  batches and `72,760 / 142,296` processed input rows. H364 is prepared as the
  fixed combined local-news audit to run after completion.

- [Session 210](./session_00210_log.md): Stopped the guarded Ollama residual
  backfill at the user's request. The tmux job session closed, no
  `build_ollama_guarded_features` process remained, `qwen2.5-coder:3b` was
  unloaded from Ollama, and the status file was marked `stopped_by_user` at
  `2281 / 7344` checkpoint batches with `45,620` processed input rows.

- [Session 209](./session_00209_log.md): Implemented and ran H363 Vietnam legal
  holiday timing. The calendar builder generated `436` 2015-2025 sparse
  pre/post trading-day rows across `53` VNINDEX-inferred closure clusters with
  no `2026+` leakage. Matched payoff found one passing state,
  `all_holidays__post_5`, but the single fixed `+0.015` sparse portfolio bonus
  produced `0.00% / 0.00%` validation/confirmation relative deltas and failed
  the portfolio gate, so legal-holiday timing stays offline evidence only.

- [Session 208](./session_00208_log.md): Resumed the guarded Ollama residual
  backfill in tmux from the Session 207 checkpoint, then completed two
  scheduled 5-minute watchdog checks. Latest status was healthy/running at
  `780 / 7344` checkpoint batches, `15,600` processed rows, with
  `qwen2.5-coder:3b` loaded at about `2.3GB` VRAM.

- [Session 207](./session_00207_log.md): Stopped the guarded Ollama residual
  backfill at the user's request, verified the tmux session and Ollama model
  runner were gone, updated `live_state.md`, then prepared the repository for
  commit and push.

- [Session 206](./session_00206_log.md): Added the session closeout checklist,
  `Last verified` marker, and strict compact source-anchor rule to the repo
  memory stack and `manh-memory-system`; also verified the guarded Ollama
  backfill is still running at `744 / 7344` checkpoint batches.

- [Session 205](./session_00205_log.md): Made the `live_state.md` contract
  explicit: current state, active constraints, immediate next actions,
  do-not-reopen conditions, and pointers. Tightened this repo's live-state file
  from a branch ledger into a short operational brain, and updated
  `manh-memory-system` to require immediate next actions inside `live_state.md`.

- [Session 204](./session_00204_log.md): Renamed the alpha-lab live-state note to
  `live_state.md`, updated repo pointers and historical note links, and
  upgraded `manh-memory-system` so fresh repos prefer `live_state.md` while
  grandfathering coherent legacy names.

- Memory note migration (2026-04-28): Added compact full-history findings and
  derived dead-end recovery views in
  [findings_compact.md](./findings_compact.md) and
  [deadends_compact.md](./deadends_compact.md), keeping chunked
  `findings-*.md` files as the append-only source of truth. Source anchor:
  [Session 206](./session_00206_log.md) reconciliation of the prior unsourced
  compact entry.

- [Session 203](./session_00203_log.md): Ran H362 as the dividend pre-ex sparse-clock portfolio reopening test. The fixed calendar bonus failed the portfolio gate, so dividend-clock timing remains offline evidence under the current selector contract.

- [Session 202](./session_00202_log.md): Ran H361 as the strict event-v2 sparse-clock portfolio reopening test. The fixed event bonus failed the portfolio gate, so event-v2 remains parked under the current target and executable selector contract.

- [Session 201](./session_00201_log.md): Ran H360 as a fixed published-contract parity audit. The published C16 artifact reproduced the H359 winner within floating-point noise and still passed portfolio plus execution-health gates.

- [Session 200](./session_00200_log.md): Published the scoped C16 order-pressure artifact at `data/features/xs_order_pressure_daily.parquet`, registered it in `shared-recommendation`, and updated producer/consumer docs while keeping RL and recommendation defaults unchanged.

- [Session 199](./session_00199_log.md): Ran H359 as the bounded C16 sizing / state-scope audit. The scoped 5% order-pressure blend on next-open-buyable rows passed both portfolio and execution-health gates, which led to the Session 200 publisher work.

- [Session 198](./session_00198_log.md): Resumed the stalled guarded Ollama residual backfill from stale `505 / 7344` checkpoint state and ran H358. Order pressure had strong executable portfolio relevance, but the equal-weight full-library addition was `MIXED` because validation cash drag narrowly breached the health limit.

- [Session 197](./session_00197_log.md): Ran H357 as the H356 integration audit. Order pressure survived full-library residualization and improved the frozen label-level selector; H358 completed the required portfolio/tradability review, and H359 / Session 200 later promoted the scoped contract.

- [Session 196](./session_00196_log.md): Ran H356 as a CPU-only standalone order-pressure gate while the Ollama residual backfill continued. CafeF posted order-volume pressure passed strongly as a broad candidate signal; H357-H359 and Session 200 are the current follow-up evidence.

- [Session 195](./session_00195_log.md): Resumed the guarded Ollama residual backfill in tmux after confirming the previous status heartbeat was stale. The job advanced from `12 / 7344` to `100 / 7344` batches on the later watchdog check and is now the single active heavy local-model job.

- [Session 194](./session_00194_log.md): Ran H355 as the order-pressure step-hazard audit. CafeF order pressure helped some smart-exit metrics, but the improvement over H337 was too small to solve the H337/H339 blocker.

- [Session 193](./session_00193_log.md): Ran H354 as the dividend-clock payoff audit. The 20-day pre-ex window has a small local payoff hint, but no dividend-clock state cleared the validation / confirmation payoff and risk gate.

- [Session 192](./session_00192_log.md): Ran H353 as the H340 entry-label transfer audit. H340 remains the preferred daily-state C5 rewrite, but it is not a clean entry-alpha prior: the loose gate lost confirmation return lift and the strong support state did not beat raw C5 in validation.

- [Session 191](./session_00191_log.md): Ran H352 as the event-v2 optionality payoff audit. Event states showed upside-tail hints, but the payoff distribution was not clean enough: downside tails worsened and confirmation mean lift was negative for the best state.

- [Session 190](./session_00190_log.md): Ran H351 as the sector ownership-pressure audit. Sector-level foreign pressure and ownership states failed; the current-data H95 flow branch is now closed under this target.

- [Session 189](./session_00189_log.md): Ran H350 as an official-disclosure source gate. The HNX universe is wired, but the current disclosure history is a two-ticker current sample with no pre-2026 rows, no transaction extracts, and no usable HOSE bridge.

- [Session 188](./session_00188_log.md): Ran H349 as the first high-value queue experiment. The H321 cascade state failed to transfer to the entry-alpha label contract: validation and confirmation matched return lifts were both negative.

- [Session 187](./session_00187_log.md): Ran H348 as a limited-source proprietary-flow conflict/agreement pilot. The best row cleared 2023 dev, then flipped negative in 2024 and 2025, so proprietary-flow rank variants should not continue on this target.

- [Session 186](./session_00186_log.md): Ran H347 as a CPU-only foreign-flow interaction pass. Foreign agreement improved raw `C5`, but did not beat the stronger H340 order-pressure rewrite. Keep it as offline interaction evidence only.

- [Session 185](./session_00185_log.md): Ran H346 to close the stale residual long-horizon reversal queue item. The sign-flipped residual after removing C11 failed; the continuation residual was directionally positive but below gate. Signal-library stale H135/H136/H137 rows were cleaned up.

- [Session 184](./session_00184_log.md): Ran H345 as a CPU-only CafeF foreign-flow continuation. Accumulation / ownership-change change-points failed the unchanged foreign-flow gate, so standalone H95 tuning should stop unless a distinct interaction contract is introduced.

- [Session 183](./session_00183_log.md): Ran H343/H344 as CPU-only existing-data audits. H343 showed official-conditioned PhoBERT sentiment clears the broad standalone gate, but H344 failed it as a standalone promoted signal under 2025 confirmation.

- [Session 182](./session_00182_log.md): Ran an evergreen artifact-only queue pass while the Ollama residual backfill continued as the active heavy job. H340/H341/H342 were treated as solved existing hypotheses rather than reopened.

- [Session 181](./session_00181_log.md): Added row-level Ollama score caching and checkpoint-cadence migration so `checkpoint_rows` changes no longer invalidate expensive scoring outputs.

- [Session 179](./session_00179_log.md): Optimized the local Ollama residual prompt under the hardware cap. The safe default is bottom-schema event-family-only JSON with `num_ctx=512` and first-300-word article truncation. A BERT-gated checkpointed backfill is running in `tmux` as `ollama_guarded_backfill`.

- [Session 178](./session_00178_log.md): Completed the repaired local PhoBERT `article_scope` and `source_type` train/publish sequence on CUDA with mid-epoch train checkpoints, resume-safe publish checkpoints, and artifact sanity checks confirming the published parquets use the new trained model ids.

- [Session 177](./session_00177_log.md): Repaired the semantic binary-head contract so `article_scope` and `source_type` no longer inherit the forward-looking date split and hard `0.5` threshold blindly. Binary-head training now calibrates a per-head decision threshold on validation, publish uses that saved threshold, and `article_scope` defaults to a stratified article-level split with positive class weighting enabled.

- [Session 176](./session_00176_log.md): Upgraded binary-head publish to the same shard-checkpoint/finalize contract already used by forward-looking publish, with a focused resume test covering the article-scope lane.

- [Session 175](./session_00175_log.md): Confirmed the real WSL runtime sees the RTX 3050 GPU outside the restricted sandbox, then hardened heavy PhoBERT train/publish paths to fail fast when `/dev/dxg` is hidden instead of silently falling back to CPU.

- [Session 174](./session_00174_log.md): Moved the offline PhoBERT runtime guard into repo code so the main local PhoBERT commands no longer rely on shell-level offline prefixes.

- [Session 173](./session_00173_log.md): Tightened the binary-head trainer so it mirrors the forward-looking lane's local-first runtime posture and epoch-level observability.

- [Session 172](./session_00172_log.md): Added repo-native PhoBERT `article_scope` and `source_type` head paths by reusing the forward-looking staged binary-head pattern.

- [Session 171](./session_00171_log.md): The news pipeline now defaults to a local-first contract: PhoBERT for sentiment and forward-looking, minimal Ollama residual semantics, and no hosted API dependency in the default local-news path.

- [Session 168](./session_00168_log.md): Targeted long-job scripts under `data_tools/` now expose canonical restart-safe job-status files and stricter durable resume boundaries.

- [Session 167](./session_00167_log.md): Repo-local planning assumptions are now explicitly constrained to `3GB VRAM / 10GB RAM` for safe local-ML work.

- [Session 166](./session_00166_log.md): The first real PhoBERT forward-looking canary forced two runtime repairs and established the current watchdog and stage-manifest flow.
