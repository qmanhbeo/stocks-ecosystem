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
