# Dead Ends 001-030

## D001: Silent Order Pressure Fails Under Current PhoBERT Article-Count Proxy (2026-05-04, Session 258)

Dead end:
- Claim tested: C16 order pressure should be strongest before public narrative
  appears, proxied by `phobert_article_count_1d == 0` or
  `phobert_article_count_5d == 0`.
- Evidence: H381 used `analysis/h381_silent_order_pressure.py` with fixed
  no-news states, TRUE walk-forward test years `2018-2025`, `2016-2025` data
  only, no `2026+`, and direct C16 variation benchmarks.
- Result: `silent_5d` WF IC was `+0.0700`, below all-C16 `+0.0752` and active
  5d-news C16 `+0.0846`; `silent_1d` was also below all-C16 and active 1d-news
  C16. Down-market no-news controls failed the same way.

Do not reopen under current representation:
- Do not keep retesting "no own PhoBERT article count means cleaner C16" as a
  standalone split.
- The first-order effect is inverted: active-news C16 is stronger than no-news
  C16 in the current ticker-day count surface.

Reopening condition:
- Reopen only with a materially different "not public yet" representation, such
  as completed Ollama event-family states, peer/co-mention narrative-vacuum
  features, source-type timing, or another proxy that is not merely own-ticker
  PhoBERT article-count absence.

Source:
- [session_258_log.md](./session_258_log.md)
- `artifacts/run_summaries/20260504_130641_h381_silent_order_pressure_research_branch_silent_order_pressure.json`

## D002: H364 Broad Candidate-Pool Consumer Promotion Fails The Random-All Benchmark (2026-05-04, Session 260)

Dead end:
- Claim tested: the fixed H364 local-news feature can be promoted as a broad
  candidate-pool consumer allocator after passing standalone local-news IC.
- Evidence: H382 used
  `analysis/h382_h364_local_news_consumer_integration.py` with TRUE
  walk-forward test years `2021-2025`, `2019-2025` data only, no `2026+`, and
  random same-`K` candidate-policy benchmarks.
- Result: H364 beat random selection within the active H364 event-news subset,
  but failed broad random-all candidate allocation. Mean lift versus random-all
  was `-0.00367`, and only `1 / 5` years beat random-all mean.

Do not reopen under current representation:
- Do not add H364 as a broad candidate-pool allocator or live portfolio overlay
  from H364/H382 alone.
- Do not treat "official sentiment x earnings/guidance" as a complete
  portfolio policy; the active subset itself is not a superior broad allocation
  universe.

Reopening condition:
- Reopen only as a narrower event-subset ranker, an input to
  `news_flow_disagreement`, official-delay/source-triangle interactions, or a
  materially different consumer contract with a predeclared random benchmark.

Source:
- [session_260_log.md](./session_260_log.md)
- `artifacts/run_summaries/20260504_194152_h382_h364_local_news_consumer_integration_research_branch_h364_local_news_consumer_integration.json`

## D003: H383 Active/Positive-News Strong-Flow Consumer Promotion Fails (2026-05-04, Session 262)

Dead end:
- Claim tested: the H383 active-news and positive-news strong-flow states can
  be promoted from IC evidence into a buyable candidate-pool allocation policy.
- Evidence: H384 used `analysis/h384_news_flow_confirmation_consumer.py` with
  TRUE walk-forward test years `2021-2025`, `2019-2025` data only, no `2026+`,
  fixed state definitions, and random same-support plus random-all candidate
  policy benchmarks.
- Result: neither state beat random same-support or random-all cleanly.
  `active_news_strong_flow` mean lift was `-0.00026` versus random-state and
  `-0.00337` versus random-all. `positive_news_strong_flow` mean lift was
  `-0.00020` versus random-state and `-0.00191` versus random-all.

Do not reopen under current representation:
- Do not add H383 active/positive-news strong-flow states as broad candidate
  allocators, live overlays, matrix columns, or recommendation-contract rules
  from H383/H384 alone.
- Do not rerun the same fixed state/K policy just because 2025 was positive;
  the mean and year-consistency gates failed.

Reopening condition:
- Reopen only with a materially different consumer contract, for example a
  same-support event subset ranker, a delay-aware official/source interaction,
  or a predeclared policy that uses H383 as context rather than as the complete
  allocator.

Source:
- [session_262_log.md](./session_262_log.md)
- `artifacts/run_summaries/20260504_195935_h384_news_flow_confirmation_consumer_research_branch_news_flow_confirmation_consumer.json`

## D004: H385 Official-Delay Candidate-Pool Consumer Promotion Fails (2026-05-04, Session 264)

Dead end:
- Claim tested: the H385 support-confirmed official/forward delayed-payoff
  states can be promoted as buyable candidate-pool allocators.
- Evidence: H386 used `analysis/h386_official_delay_consumer_router.py` with
  TRUE walk-forward test years `2021-2025`, `2019-2025` data only, no `2026+`,
  fixed state definitions, and random same-support plus random-all candidate
  policy benchmarks.
- Result: neither state beat random same-support or random-all cleanly.
  `official_supported` mean lift was `-0.00035` versus random-state and
  `-0.00540` versus random-all. `official_forward_supported` mean lift was
  `-0.00057` versus random-state and `-0.00555` versus random-all.

Do not reopen under current representation:
- Do not add H385 official/forward supported states as broad candidate-pool
  allocators, live overlays, matrix columns, or recommendation-contract rules
  from H385/H386 alone.
- Do not rerun the same fixed state/K policy with candidate-rank selection; the
  mean, 2025, and year-consistency gates failed.

Reopening condition:
- Reopen only with a materially different consumer contract, for example a
  delay-matched event sleeve, a predeclared equal-weight state basket, or a
  holding/exit target that directly matches the H385 5d payoff mechanism.

Source:
- [session_264_log.md](./session_264_log.md)
- `artifacts/run_summaries/20260504_201315_h386_official_delay_consumer_router_research_branch_official_delay_consumer_router.json`

## D005: Insider-Down Rescue Fails Against High-C16 Controls (2026-05-04, Session 265)

Dead end:
- Claim tested: positive insider conviction after visible stock weakness and
  high C16 support is a distinct rescue state.
- Evidence: H387 used `analysis/h387_insider_down_rescue.py` with TRUE
  walk-forward years `2018-2025`, `2016-2025` data only, no `2026+`, fixed
  state definitions, 5d relative-return payoffs, and controls against
  ordinary insider, insider-plus-C16, and stock-down-plus-C16 rows.
- Result: `insider_down_high_c16` beat ordinary `insider_buy`, but failed the
  important controls. Mean 5d lift was only `+0.00087` versus
  `insider_high_c16` and `-0.00308` versus `stock_down_high_c16`; 2025 lifts
  versus those controls were negative. The deep-down variant also failed.

Do not reopen under current representation:
- Do not add an insider-after-stock-weakness overlay, live rule, matrix column,
  or recommendation-contract policy from H387.
- Do not rerun the same positive-C5 plus 1d/3d stock-down plus high-C16 state;
  the stock-down high-C16 control is stronger.

Reopening condition:
- Reopen only with a materially different insider representation or target,
  such as transaction-role quality, filing freshness, realized execution
  follow-through, or a consumer target that directly uses insider event timing.

Source:
- [session_265_log.md](./session_265_log.md)
- `artifacts/run_summaries/20260504_201913_h387_insider_down_rescue_research_branch_insider_down_rescue.json`

## D006: Long-Dormancy Fresh Selection Pulse Fails (2026-05-04, Session 266)

Dead end:
- Claim tested: top-5/top-10 candidates reappearing after at least `20`
  trading days out of the set deserve a fresh-selection boost.
- Evidence: H388 used `analysis/h388_fresh_selection_pulse.py` with prior-only
  candidate-history features, TRUE walk-forward years `2021-2025`,
  `2019-2025` data only, no `2026+`, buyable candidate rows, and cycle
  relative-return labels.
- Result: fresh20 rows did not beat stale-repeat controls. `top5_fresh20`
  mean lift versus `top5_stale_repeat` was `-0.00016` with 2025 lift
  `-0.00269`; `top10_fresh20` mean lift versus `top10_stale_repeat` was
  `-0.00068` with 2025 lift `-0.00098`.

Do not reopen under current representation:
- Do not add a long-dormancy fresh-selection boost, live overlay, matrix
  column, or recommendation policy from H388.
- Do not rerun the same `20+` trading-day reappearance state; the stronger
  control was short repeat, not fresh return.

Reopening condition:
- Reopen only with a materially different candidate-history contract, such as
  a predeclared short-repeat state, rank-transition state, or portfolio policy
  benchmark that explicitly compares churn, concentration, and turnover.

Source:
- [session_266_log.md](./session_266_log.md)
- `artifacts/run_summaries/20260504_202357_h388_fresh_selection_pulse_research_branch_fresh_selection_pulse.json`

## D007: Guarded-Ollama Event Cascade Fails To Reopen Event Timing (2026-05-04, Session 267)

Dead end:
- Claim tested: the completed guarded-Ollama event-family surface can revive
  event timing through first-event, repeat-event, or family-transition states.
- Evidence: H389 used `analysis/h389_post_ollama_event_cascade.py` with TRUE
  walk-forward years `2018-2025`, `2016-2025` data only, no `2026+`, fixed
  guarded-Ollama event states, and 5d relative-return payoffs.
- Result: no first/repeat/transition state beat generic event, cascade-control,
  and no-event rows cleanly. The best state, `event_first20`, had mean 5d lift
  only `+0.00099` versus generic event and `+0.00114` versus repeat event,
  below the `+0.002` gate.

Do not reopen under current representation:
- Do not add guarded-Ollama first/repeat/family-transition event states as live
  overlays, sparse clocks, matrix columns, or recommendation policies from
  H389.
- Do not retune event-family shares or quiet/repeat windows under the same 5d
  payoff target; the H389 representation did not improve enough on H321/H361.

Reopening condition:
- Reopen only with a materially different event target, timestamped source,
  event-neighbor propagation contract, or downstream consumer that is not the
  current event sparse-clock / 5d payoff setup.

Source:
- [session_267_log.md](./session_267_log.md)
- `artifacts/run_summaries/20260504_203158_h389_post_ollama_event_cascade_research_branch_post_ollama_event_cascade.json`

## D008: Calendar Mechanism Promotion Is Parked Under Current Target (2026-05-04, Session 268)

Dead end:
- Claim tested: old calendar edges (`monday_jan_combo`, `quarter_start`, and
  late quarter-month timing) retain independent C16 quality after residualizing
  liquidity, breadth, news volume, buyability, C16 availability, volume
  pressure, and trailing down-market controls.
- Evidence: H390 used `analysis/h390_calendar_liquidity_mechanism.py` with
  daily C16 IC versus 1d/5d relative returns and S1 `actual`, TRUE
  walk-forward years `2021-2025`, a saved daily range ending `2025-12-31`, and
  no `2026+`.
- Result: H390 was `MIXED`, not promotable. Exact `monday_jan_combo` retained
  mean 1d residual IC lift `+0.02745`, but had only one active date per
  evaluated year, only `2 / 4` positive 1d residual-lift years, and negative
  mean 5d residual lift `-0.04055`. `quarter_start` and
  `late_quarter_month` did not retain positive 1d residual lift.

Do not reopen under current representation:
- Do not add old exact calendar states as live overlays, sparse-clock rules,
  matrix columns, or recommendation policies from H390.
- Do not retune date windows around `monday_jan_combo`, `quarter_start`, or
  late quarter-month timing under the same daily-C16-IC / 5d payoff target.

Reopening condition:
- Reopen only with a materially different predeclared contract, such as a
  broader January-window or weekday mechanism test, a different execution/5d
  target, or a downstream consumer that explicitly benchmarks calendar context
  against mechanism-matched alternatives.

Source:
- [session_268_log.md](./session_268_log.md)
- `artifacts/run_summaries/20260504_204043_h390_calendar_liquidity_mechanism_research_branch_calendar_liquidity_mechanism.json`

## D009: Entry-Panel Tradability Release Pulse Fails (2026-05-04, Session 269)

Dead end:
- Claim tested: high-ranked candidates that become buyable after a prior
  blocked-buy state deserve a `wait_release` inclusion boost.
- Evidence: H391 used `analysis/h391_tradability_release_pulse.py` with
  `candidate_panel_daily.parquet`, `entry_labels_cycle5`, TRUE walk-forward
  years `2021-2025`, `2019-2025` data only, no `2026+`, fixed top-5/top-10
  release states, and same-year same-rank matched stable/non-release buyable
  controls.
- Result: release rows were negative and weaker than controls. `top5_release`
  mean cycle relative return was `-0.032254`, with matched-control lift
  `-0.033668`, only `1 / 5` positive matched-control years, and 2025 lift
  `-0.080106`. `top10_release` mean relative return was `-0.027022`, with
  matched-control lift `-0.028365`, only `1 / 5` positive years, and 2025 lift
  `-0.066302`. Top-5 and top-10 release can-sell rates were also below the
  `0.90` health gate or barely near it.

Do not reopen under current representation:
- Do not add a `wait_release` inclusion boost, live overlay, matrix column, or
  recommendation policy from the current entry-panel `release_flag`.
- Do not rerun the same `prev_can_buy_next_open == false` and
  `can_buy_next_open == true` top-ranked state under the cycle-label target;
  it failed broad, matched, 2025, and sellability checks.

Reopening condition:
- Reopen only with materially different evidence, such as order-book
  queue/open-fill data, intraday post-release absorption, or a fixed rule that
  waits for re-block risk and next-day sellability to normalize before entry.

Source:
- [session_269_log.md](./session_269_log.md)
- `artifacts/run_summaries/20260504_204826_h391_tradability_release_pulse_research_branch_tradability_release_pulse.json`

## D010: C16-Insider-News Triangle Core Fails Current Controls (2026-05-04, Session 270)

Dead end:
- Claim tested: high C16 plus positive insider plus local-news source/type
  agreement is a sparse high-conviction state.
- Evidence: H392 used `analysis/h392_source_triangle_sparse.py` with fixed
  C16, C5 insider, source-news, and forward-text sensors; TRUE walk-forward
  years `2018-2025`; `2016-2025` data only; no `2026+`; and controls against
  C16+insider without news, C16+news without insider, insider+news without C16,
  and exactly-two-sensor rows.
- Result: the required core did not clear controls. `c16_insider_any_news`
  had mean 5d payoff `+0.003177`, but mean 5d lift was `-0.007315` versus
  `c16_insider_no_news`, `-0.005205` versus `c16_any_news_no_insider`, and
  only `+0.000271` versus `exactly_two_sensors`; 2025 lift versus exactly-two
  was `-0.003072`. `c16_insider_source` failed the same core controls.

Do not reopen under current representation:
- Do not add a C16+insider+news sparse overlay, matrix column, or
  recommendation policy from H392.
- Do not rerun the same C16/C5/PhoBERT source-type triangle; the C16+insider
  without-news control is stronger.

Reopening condition:
- Reopen only with a narrower predeclared non-insider news triangle such as
  `c16_source_forward`, or with materially different insider-quality
  information that changes the C5 side of the test.

Source:
- [session_270_log.md](./session_270_log.md)
- `artifacts/run_summaries/20260504_205532_h392_source_triangle_sparse_research_branch_source_triangle_sparse.json`

## D011: Same-Day Nihilist Reversal Fails Stock-Down High-C16 Control (2026-05-04, Session 271)

Dead end:
- Claim tested: high C16 after both stock and market weakness, with weak or
  absent bullish local news, is a stronger hidden-support state than ordinary
  stock-down high-C16.
- Evidence: H393 used `analysis/h393_nihilist_reversal.py` with fixed stock
  weakness, VNI weakness, no-bullish-news, high-C16, and control states; TRUE
  walk-forward years `2018-2025`; `2016-2025` data only; no `2026+`; and 5d
  relative-return payoff.
- Result: `nihilist_reversal` was positive but not stronger than controls.
  Mean 5d payoff was `+0.010170`, but lift was `-0.002027` versus
  `stock_down_high_c16`, only `+0.000169` versus
  `stock_market_down_high_c16`, and 2025 payoff was `-0.000982`.
  `stock_down_high_c16` remained the stronger state with mean 5d payoff
  `+0.012197` and 2025 payoff `+0.002174`.

Do not reopen under current representation:
- Do not add same-day nihilist-reversal overlays, matrix columns, or
  recommendation policies from the current high-C16 plus stock/market-down
  plus no-bullish-news state.
- Do not retune the same no-bullish-news threshold around this target; it did
  not improve the stock-down high-C16 control.

Reopening condition:
- Reopen only with a predeclared weak-active-news subset, intraday absorption
  after capitulation, or a consumer rule that waits for re-entry after the
  no-bullish-news washout rather than same-day entry.

Source:
- [session_271_log.md](./session_271_log.md)
- `artifacts/run_summaries/20260504_210147_h393_nihilist_reversal_research_branch_nihilist_reversal.json`

## D012: S24x-S25x Target-Derived Market-Down Promotions Are Invalid (2026-05-05, Session 272)

Dead end:
- Claim audited: S244/S246/S247/S253 `consecutive_down`, `down_market_c16`,
  and `deep_down_c16` were newly strong real regime filters.
- Evidence: `analysis/audit_s24x_s25x_signal_claims.py` recomputed the claims
  and found the original scripts used same-date S1 `actual` to define market
  state. `actual` is a future binary barrier label, not a signed return.
  `analysis/s253_true_wf_validation.py` also did not implement the advertised
  train `T-2,T-1` -> test `T` protocol.
- Result: the leaky target-derived states reproduced high ICs
  (`market_down` `+0.092478`, `market_down_2d` `+0.095095`), but observable
  VNI-down states were only modestly above baseline (`+0.077064` and
  `+0.080584` versus C16 `+0.073765`), and observable stock-down states were
  weaker than C16 (`+0.061540` and `+0.067884`).

Do not reopen under current representation:
- Do not use S253 as methodology resolution for the S24x/S25x claims.
- Do not add `consecutive_down`, target-derived `down_market_c16`, or
  `deep_down_c16` to signal libraries, matrix contracts, or live/recommendation
  rules from those sessions.
- Do not define market regimes from the same-date S1 `actual` target.

Reopening condition:
- Reopen only with fixed observable state variables such as trailing VNINDEX
  returns, trailing stock returns, or predeclared market breadth, and benchmark
  the result against C16, stock-down high-C16, and 2025 confirmation.

Survivor from the audit:
- `insider_lead_next_trading_day` remains real support context and should not
  be killed by this dead end.

Source:
- [session_272_log.md](./session_272_log.md)
- `artifacts/run_summaries/20260505_161922_s24x_s25x_signal_claim_audit_audit_s24x_s25x_signal_claims.json`

## D013: Broad Oracle-Shadow Weather Promotion Fails Current Observable Contract (2026-05-05, Session 275)

Dead end:
- Claim tested: target-breadth weather, the future information accidentally
  used by invalid S24x market regimes, can be honestly predicted from
  pre-decision date aggregates strongly enough to bucket S1/C16 IC.
- Evidence: H394 used `analysis/h394_oracle_shadow_regime_distiller.py` with
  rolling train-before-test years `2018-2025`, no `2026+`, fixed
  train-quantile ridge-predicted weather buckets, and random same-date bucket
  controls. Target-breadth buckets were retained only as diagnostic leakage
  upper bounds.
- Result: the ridge model found only weak weather prediction: avg date IC
  `+0.05019`, `7 / 8` positive years, below the `+0.10` gate. The best honest
  bucket, `ridge_pred_low20`, lifted C16 by only `+0.00342` versus all rows and
  `+0.00416` versus random same-date buckets, below the required gates; it
  degraded S1 by `-0.00708`. Observable `VNI down 2d` was cleaner.

Do not reopen under current representation:
- Do not promote `ridge_pred_low20`, `ridge_pred_high80`, or broad predicted
  barrier-breadth weather as standalone regime states from H394.
- Do not rescue the old S24x market-down idea by substituting a broad
  date-level ridge weather model under the same end-of-day observable contract.

Reopening condition:
- Reopen only with a materially different fixed representation, such as
  intraday/opening absorption data, a different target-breadth definition, or a
  quorum/consumer design where weak weather is one predeclared vote rather
  than the promoted state.

Source:
- [session_275_log.md](./session_275_log.md)
- `artifacts/run_summaries/20260505_170942_h394_oracle_shadow_regime_distiller_research_branch_oracle_shadow_regime_distiller.json`

## D014: Quiet Insider Pre-Reaction Clock Fails Current News/Order-Count Proxy (2026-05-05, Session 279)

Dead end:
- Claim tested: the S272 positive-insider next-trading-day lead is strongest
  before news or order-count sensors visibly react.
- Evidence: H398 used `analysis/h398_insider_pre_reaction_clock.py` with no
  `2026+`, event-time T-1/T0/T+1 mapping, same-ticker non-event controls,
  C16 order-pressure rank, and fixed pre-reaction versus reacted T+1 insider
  states.
- Result: `insider_tplus1_pre_reaction` remained positive (`+0.09247` avg IC,
  `11 / 11` positive years), but it lost to `insider_tplus1_reacted` by
  `-0.01811` avg IC and by `-0.00771` hit-rate lift. High buy-order-count
  T+1 insider rows were stronger (`+0.13776` avg IC) than not-high order-count
  rows by `+0.04487` avg IC.

Do not reopen under current representation:
- Do not promote quiet/no-news/no-high-buy-count insider T+1 rows as the
  cleaner insider clock from H398.
- Do not use H398 to argue that visible order/news reaction pollutes insider
  events; the tested evidence points the other way.

Survivor from the audit:
- `insider_tplus1` / `insider_buy_lead` remains real event-time evidence and
  should not be killed by this dead end.
- Order-count reaction confirmation is the live clue for the next
  crowd-count branch.

Reopening condition:
- Reopen only with a materially different "pre-reaction" proxy, such as
  intraday absorption, source timestamp sequencing, order-book queue timing,
  or peer-news visibility rather than same-day own-news and high buy-order
  count absence.

Source:
- [session_279_log.md](./session_279_log.md)
- `artifacts/run_summaries/20260505_173706_h398_insider_pre_reaction_clock_research_branch_insider_pre_reaction_clock.json`

## D015: Standalone Buy-Order Count Promotion Fails Under H399 (2026-05-05, Session 280)

Dead end:
- Claim tested: high buy-order count or buy-count rank is a standalone
  crowd-ignition signal.
- Evidence: H399 used `analysis/h399_crowd_count_ignition.py` with no
  `2026+`, fixed `2018-2025` years, raw CafeF order stats, published C16,
  C8 volume-z controls, and H394 predicted-weather buckets.
- Result: `buy_count_rank` was anti-predictive as a standalone score
  (`-0.01075`, only `3 / 8` positive years). The `high_buy_count` state was
  only a modest C16 conditioner (`+0.08463` avg IC, `+0.00944` lift versus all
  rows, `6 / 8` positive lift years) and had slightly lower target hit rate
  than all rows (`-0.00214`).

Do not reopen under current representation:
- Do not promote buy-order count rank as an independent signal-library member.
- Do not treat high buy count alone as more than modest C16 context.
- Do not claim high-count plus high volume-z is a new crowd-count primitive;
  H399 shows high volume-z already owns almost all of that pocket.

Survivor from the audit:
- `count_high_size_weather_low20` remains a mixed branch clue: avg IC
  `+0.10083` and `+0.01620` average yearly lift versus high buy count, but
  only `5 / 8` positive lift years.
- `volume_z_high80` remains the cleaner volume-state context.

Reopening condition:
- Reopen only with a stability or consumer audit for the
  high-average-buy-size plus H394-low-weather interaction, or with materially
  different order-fragmentation/queue/intraday data.

Source:
- [session_280_log.md](./session_280_log.md)
- `artifacts/run_summaries/20260505_174329_h399_crowd_count_ignition_research_branch_crowd_count_ignition.json`

## D016: Fixed Calendar Weak-Prior Quorum Vote Fails (2026-05-05, Session 281)

Dead end:
- Claim tested: January/weekday/month-end/T+2 calendar residues can be pooled
  into one weak prior and added to the H395 weak-signal quorum.
- Evidence: H400 used `analysis/h400_calendar_as_weak_prior_not_clock.py`
  with train-before-test folds, no `2026+`, H395 base components excluding
  calendar votes, one fixed calendar weak-prior vote, and a random extra
  weak-vote control.
- Result: adding the calendar prior reduced the non-calendar quorum from
  `+0.05826` avg IC to `+0.05605`. Incremental lift was `-0.00221` with
  `0 / 7` positive lift years. Calendar-only IC was negative (`-0.00827`).

Do not reopen under current representation:
- Do not add `january_first_10`, `monday`, month-end, T+2 weekday residue, or
  their pooled average as a fixed weak vote inside H395.
- Do not use H390's sparse diagnostic calendar pockets to justify a dense
  generic calendar prior.

Survivor from the audit:
- The T+2 weekday residue was mildly positive (`+0.00646`, `6 / 10` positive
  years), but below the weak-candidate IC gate and not useful in the pooled
  prior.

Reopening condition:
- Reopen only with a different calendar target or a mechanism-matched consumer
  contract, not by reweighting the same dense fixed calendar prior.

Source:
- [session_281_log.md](./session_281_log.md)
- `artifacts/run_summaries/20260505_174904_h400_calendar_as_weak_prior_not_clock_research_branch_calendar_as_weak_prior_not_clock.json`

## D017: Broad Anti-Signal Veto Promotion Fails H401 (2026-05-05, Session 282)

Dead end:
- Claim tested: broad side-channel disagreement can be promoted as a top-5
  long-only cash veto.
- Evidence: H401 used `analysis/h401_anti_signal_annihilation_veto.py` with no
  `2026+`, fixed top-5 buyable candidate rows, cycle relative-return labels,
  fixed C16/insider/news/tradability/sector disagreement masks, and random
  same-breadth veto controls.
- Result: broad masks did not improve no-veto. `support_count_le1` averaged
  `-0.000123` versus no-veto, `pretty_price_weak_flow` `-0.000026`,
  `news_hype_weak_flow` `-0.000075`, and `weak_flow_weak_sector` `-0.000225`.

Do not reopen under current representation:
- Do not add a broad side-channel disagreement veto to the portfolio policy
  library or live selector.
- Do not tune the same C16/insider/news/tradability/sector support-count masks
  under the current top-5 cycle-return contract.

Survivor from the audit:
- `support_count_zero` is a weak clue only: `+0.000167` avg lift versus
  no-veto and `6 / 7` positive no-veto years, but too small for promotion and
  below random p95.

Reopening condition:
- Reopen only as a narrower strict no-support scale-down/veto audit, or with a
  materially different top-book target, intraday/queue evidence, or learned
  portfolio consumer.

Source:
- [session_282_log.md](./session_282_log.md)
- `artifacts/run_summaries/20260505_175823_h401_anti_signal_annihilation_veto_research_branch_anti_signal_annihilation_veto.json`

---

## D022: Volume Triple Storm Fails (2026-05-05, Session 292)

Dead end:
- Claim tested: Triple Storm conditions amplify Volume signal (like C16-Triple).
- Evidence: H411 used `analysis/h411_volume_triple_storm.py` with liquid + market-down + divergence.
- Result: Volume+Triple = +0.038 IC, WORSE than Volume alone (+0.075 IC).

Why it killed:
- Triple Storm is C16-specific, not a universal signal amplifier
- Ablation: none of liquid (+0.084), down (+0.077), divergence (+0.032) helped
- The mechanism that makes Triple Storm work on C16 is C16-specific

Do not reopen:
- Do not test Triple Storm on other signals expecting the same amplification
- Do not generalize C16-Triple as a universal amplifier recipe
- The C16-Triple result was a special case, not a generalizable pattern

Reopening condition:
- Reopen only with a materially different signal/condition/mechanism

Source:
- [session_292_log.md](./session_292_log.md)

---

## D023: Foreign Flow Addition Fails (2026-05-05, Session 299)

Dead end:
- Claim tested: foreign flow adds to Vol+S1 additive.
- Evidence: H418 used foreign data with H413 formula.
- Result: -0.006 IC drop vs H413. Foreign alone +0.004.

Why it killed:
- Foreign has near-zero IC alone (+0.004)
- Adding weak signal HURTS performance
- Same pattern as C16 - some signals are too weak to contribute

Do not reopen:
- Do not try adding more weak signals to H413
- Focus on strong signals only (S1, Volume)

Reopening condition:
- Only reopen with a STRONG new signal (>0.05 standalone IC)

Source:
- [session_299_log.md](./session_299_log.md)

---

## D024: Insider Addition Fails (2026-05-05, Session 300)

Dead end:
- Claim tested: insider adds to Vol+S1 additive.
- Evidence: H419 tested insider with H413 formula.
- Result: Insider alone is NEGATIVE (-0.002). Adding gives +0.0004 (noise).

Why it killed:
- Insider is now NEGATIVE - historically strong but no longer
- Adding weak signal gives negligible lift
- Pattern matches C16 and Foreign

Source:
- [session_300_log.md](./session_300_log.md)

---

## D025: Forced-Seller Detector Fails Under Current Entry-Alpha Consumer (2026-05-06, Session 304)

Dead end:
- Claim tested: daily forced-seller / margin-cascade states can select better
  buyable entry candidates using observable negative return, volume spike,
  sell-order pressure, rising or high average sell size, floor-limit proximity,
  and absence of active bad PhoBERT news.
- Evidence: H426 used `analysis/h426_forced_seller_detector.py` with the
  existing entry-alpha candidate panel and cycle labels, `2019-2025` only,
  walk-forward K selection from prior years, and random same-support plus
  random-all policy baselines.
- Result: no fixed state cleared both random gates. `forced_seller_core_buyable`
  had mean lift only `+0.000230` versus random-state, only `1 / 5` positive
  WF years, and mean lift `-0.002047` versus random-all. Large-down and floor
  variants also failed broad allocation; the literal tradability-release state
  had only `7` rows and no usable support.

Do not reopen under current representation:
- Do not retune the same daily thresholds around sell pressure, volume spike,
  floor pressure, and no-bad-news inside the current entry-label consumer.
- Do not treat the queue memo's "next-day C16 turns positive" clause as
  decision-time valid under the current T close -> T+1 open entry contract.

Survivor from the audit:
- None for the current daily candidate-policy allocator. The broad core state
  is at most a weak distress context, not a buy selector.

Reopening condition:
- Reopen only with a delayed-entry protocol that can honestly observe a
  post-sell-pressure C16/order-pressure turn before execution, or with
  materially different intraday / queue / opening-fill data that measures
  actual absorption and tradability release timing.

Source:
- [session_304_log.md](./session_304_log.md)
- `artifacts/run_summaries/20260506_141722_h426_forced_seller_detector_research_branch_forced_seller_detector.json`

## D026: Midbook Imbalance Fails As Hidden Depth Proxy (2026-05-08, Session 307)

Dead end:
- Claim tested: (buy_volume - sell_volume) / (buy + sell) proxies hidden depth
  and can improve C16 as a conditioner or stand alone as a signal.
- Evidence: H428 used `analysis/h428_midbook_imbalance_test.py` with order_stats
  buy/sell volume merged with C16 (order_volume_ratio) and S1 targets over
  dev `2015-2022`, val `2023-2024`, confirm `2025`; computed C16 IC by midbook
  bucket and direct prediction IC vs S1.
- Result: FAILED as C16 conditioner - higher midbook imbalance (Q5) had WORSE
  C16 IC than lower imbalance (Q1), with Q5-Q1 lift -0.0385 dev, -0.0116 val.
  Direct prediction was weakly positive (IC +0.0194 dev, +0.0373 val) but below
  IC > 0.05 promotion threshold.

Do not reopen under current representation:
- Do not treat high buy/sell volume imbalance as hidden depth or stealth
  accumulation - it correlates with WEAKER signal quality.
- Do not test as C16 conditioner without materially different data (e.g., true
  queue/depth history that captures actual order-book state).

Survivor from the audit:
- None for the current hypothesis. The opposite direction holds: high
  imbalance = weak signal quality.

Reopening condition:
- Reopen only with true historical queue/depth data that captures actual
  order-book state at different price levels, not just aggregated daily
  buy/sell volumes.

---

## D027: S1 Rank Degradation Hypothesis Fails (2026-05-08, Session 307)

Dead end:
- Claim tested: High S1-ranked tickers predictably degrade in next-day ranker
  quality (S1 mean reversion).
- Evidence: H428 used `analysis/h428_ranker_error_taxonomy.py` bucketed tickers
  by current S1 rank into quintiles, measured next-day ranker IC over
  `2018-2025`.
- Result: FAILED - Top S1 tickers do NOT decay; they IMPROVE in next-day IC.
  Q5_top: mean IC +0.1616 (+0.0263 lift), Q3 (mid): +0.1123 (-0.0230 lift).
  Validation confirmed: Top-S1 +0.1592 vs baseline +0.1318 (+0.0274).

Do not reopen under current representation:
- Do not use S1 rank as an error-state indicator.
- High-quality tickers remain high-quality next day (momentum, not mean-reversion).

Reopening condition:
- Reopen only with materially different quality/continuation proxy (e.g.,
  changes in analyst coverage, institutional ownership, or other fundamental
  quality signals).

---

## D028: Signal Half-Life Routing Fails (2026-05-08, Session 308)

Dead end:
- Claim tested: Alpha states should carry estimated decay half-life rather than
  one universal label. Different signals should win on their natural horizon.
- Evidence: H429 used `analysis/h429_signal_half_life_router.py` to test half-life
  classes (S1 slope momentum vs reversion, vol_high vs vol_low) across
  1d/2d/5d/10d horizons over `2018-2025`.
- Result: FAILED - All half-life classes perform WORSE at longer horizons. 1d
  baseline always best: s1_momentum best at 1d (-0.1134 lift), vol_low becomes
  negative at 5d+ (-0.0020).

Do not reopen under current representation:
- No evidence that S1 slope predicts horizon-specific performance.
- Signal decay is uniform across declared half-life classes.
- Do not route signals to different horizons based on half-life characteristics.

Reopening condition:
- Reopen only with materially different horizon definition or target (e.g.,
  different barrier percentages, different cost models, or alternative
  execution contracts).

---

## D029: Volume-Price Divergence Hypothesis Fails (2026-05-08, Session 311)

Dead end:
- Claim tested: Price vs volume response divergence defines edge. Large move on
  small volume = real force; large move on large volume = fade.
- Evidence: H432 used `analysis/h432_volume_price_divergence.py` to compute
  return and volume-z quintiles and test divergence states (real_force, fade,
  hidden_support, crowded) over `2018-2025`.
- Result: FAILED - All divergence states have negative lift vs baseline.
  real_force: +0.0921 (-0.0261), fade: +0.0892 (-0.0289), hidden_support: +0.0391,
  crowded: +0.0477.

Do not reopen under current representation:
- Return vs volume-z divergence does NOT capture hidden pressure.
- Both "real force" and "fade" are WORSE than baseline ranker.
- Energy conservation hypothesis doesn't translate to alpha.

Reopening condition:
- Reopen only with materially different volume data (e.g., intraday volume
  profile, order-flow fragmentation metrics) or alternative divergence measures.

Source:
- [session_307_log.md](./session_307_log.md)
- `artifacts/run_summaries/h428_midbook_imbalance_summary.json`

## D026: Volume-Price Divergence Fails Under Return vs Volume-Z Representation (2026-05-08, Session 311)

Dead end:
- Claim tested: price vs volume response divergence defines edge. Large move on small volume = real force; large move on large volume = fade.
- Evidence: H432 computed return and volume-z quintiles, tested divergence states (real_force, fade, hidden_support, crowded) over `2018-2025`. All states compared against H413 baseline.
- Result: H432 `FAILED`. All divergence states have negative lift vs baseline: real_force +0.0921 (-0.0261), fade +0.0892 (-0.0289), hidden_support +0.0391, crowded +0.0477.

Do not reopen under current representation:
- Do not test energy conservation / return vs volume-z divergence as a standalone split.
- The hypothesis does not translate to alpha in this market.

Reopening condition:
- Reopen only with materially different volume representation or price response metric.

Source:
- [session_311_log.md](./session_311_log.md)
- `artifacts/run_summaries/h432_volume_price_divergence_summary.json`

## D027: Signal Half-Life Routing Fails Under Pre-Declared Half-Life Classes (2026-05-08, Session 308)

Dead end:
- Claim tested: pre-declared half-life classes (S1 momentum vs reversion, vol_high vs vol_low) should win only on their natural horizon vs random horizon controls.
- Evidence: H429 bucketed tickers by S1 slope (momentum vs reversion) and volume state (high vs low), tested IC at 1d/2d/5d/10d horizons over `2018-2025`.
- Result: H429 `FAILED`. All classes degrade at longer horizons; 1d baseline always best. vol_low becomes negative at 5d+ horizons. No horizon-specific advantage found.

Do not reopen under current representation:
- Do not route signals to different horizons based on half-life characteristics.
- The horizon specialization hypothesis is not supported by data.

Reopening condition:
- Reopen only with materially different horizon definition, target, or market regime classification.

Source:
- [session_308_log.md](./session_308_log.md)
- `artifacts/run_summaries/h429_signal_half_life_router_summary.json`

## D028: Candidate Rank-Actual Gap Fails - Surprises Are Noise, Not Alpha (2026-05-08, Session 314)

Dead end:
- Claim tested: gap between predicted rank and actual realized rank predicts forward returns. Large gaps = surprising information = alpha.
- Evidence: H435 computed predicted rank (H413 blend) and actual rank (barrier label proxy), tested gap magnitude quintiles over `2018-2025`. Compared against H413 baseline.
- Result: H435 `FAILED` badly - OPPOSITE of hypothesis!
  - Small gaps (aligned prediction/actual): HIGH IC (0.28-0.64)
  - Large gaps (surprising prediction): NEGATIVE IC (-0.79 to -0.83)
  - Q5-Q1 gap lift: -0.0615 (badly negative)

Do not reopen under current representation:
- Candidate rank-actual gap does NOT predict forward returns.
- When the ranker is "surprised", it means the signal was NOISE, not alpha.
- Surprises indicate unpredictability, not hidden information.
- The H413 ranker is well-calibrated - disagreement with reality means unpredictable.

Reopening condition:
- Reopen only if you can prove that model "surprise" contains information about future model error correction.
- The current formulation uses the label proxy, which introduces look-ahead bias.

Source:
- [session_314_log.md](./session_314_log.md)
- `artifacts/run_summaries/20260508_152427_h435_candidate_rank_actual_gap_research_branch_candidate_rank_actual_gap.json`
