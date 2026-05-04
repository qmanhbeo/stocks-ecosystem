# Live State

What this file is for: current working state, active constraints or blockers,
and immediate next actions. Keep it operational and short. Put session detail
in session logs, durable conclusions in findings chunks, failed or parked paths
in dead-end chunks, and cheap recovery context in the compact files.

Latest full session detail: [session_259_log.md](./session_259_log.md)
Last verified: [Session 259](./session_259_log.md), 2026-05-04
(Ollama residual complete; combined local-news aggregate refreshed; H364 passed).

Compact recovery:
- [sessions_compact.md](./sessions_compact.md)
- [findings_compact.md](./findings_compact.md)
- [deadends_compact.md](./deadends_compact.md)

Source durable memory:
- [findings.md](./findings.md)
- [findings-301-330.md](./findings-301-330.md)
- [findings-331-360.md](./findings-331-360.md)
- [deadends.md](./deadends.md)
- [deadends-001-030.md](./deadends-001-030.md)
- [signal_library.md](./signal_library.md)
- [portfolio_policy_library.md](./portfolio_policy_library.md)

---

## Current State

- The active live branch remains frozen:
  `full_library + k5_r5_eq + h175__rel2_gt0 + sticky_bonus_0p015`.
- The active research focus is local-first news infrastructure and bounded
  follow-through, not live-branch retuning.
- The local news stack is real: PhoBERT owns sentiment, forward-looking,
  `article_scope`, and `source_type`; Ollama is the guarded residual
  event-family lane.
- `ollama_guarded_backfill` is complete: `7344 / 7344` checkpoint batches,
  `146,872` gated input articles, and `1,406,206` ticker-day rows in
  `data/features/news/datasets/ollama_guarded_ticker_day_features.parquet`.
  Session 259 refreshed the combined local-news aggregate overlay, writing
  `1,436,996` rows to `data/features/news/datasets/news_daily_features.parquet`.
- H364 passed the combined local-news standalone audit. Best fixed feature:
  `h364_official_sentiment_x_earnings_guidance`; avg IC `+0.01766`,
  dev/validation/confirmation IC `+0.0173 / +0.0200 / +0.0156`, `10 / 10`
  positive years, S1 corr `-0.0104`, active rows `103,248`. This is candidate
  local-news evidence, not a live branch change. Source anchor: `F342`.
- C16 order pressure is a published shared feature contract at
  `data/features/xs_order_pressure_daily.parquet`, but downstream use is
  opt-in only. Do not run more C16 sizing/search unless a consumer asks for a
  matrix/export integration.
- H379/H380 dynamic breadth passed as offline policy evidence. H380 narrowed
  the branch to candidate-count-only routing and beat random K/cash policies
  with mean cycle lift `+0.00389`, `4 / 5` years above random K/cash mean, and
  positive 2025 confirmation; this is not a live promotion. The policy-state
  registry is [portfolio_policy_library.md](./portfolio_policy_library.md).
- H381 killed `silent_order_pressure` under current own-ticker PhoBERT
  article-count absence. No-news C16 was weaker than all-C16 and active-news
  C16 (`silent_5d` IC `+0.0700`, all-C16 `+0.0752`, active-5d-news `+0.0846`).
  Continue through local-news interaction states, not simple no-news stealth.
- Event-v2, dividend-clock, legal-holiday timing, foreign/proprietary/sector-flow,
  old OHLCV queue, smart-exit linear tweaks, and BERT-only sentiment are parked
  or failed under the current target/consumer contracts. Use the compact
  dead-end view before reopening any of them.

## Confirmed Recent Signals

- `insider_buy_lead`: TRUE WF IC `0.1093`; prior insider buy on T-1 boosts C16
  quality. Source anchors: `F313`, `F337`.
- `consecutive_down`: TRUE WF IC `0.1047`; down-day state is independently real.
  Source anchors: `F314`, `F337`.
- `down_market_c16`: TRUE WF IC `0.0992`; C16 is a contrarian down-market signal.
  Source anchors: `F330`, `F337`.
- `dividend_30d`: IC `0.0934` but noisy; keep as event context, not a promoted
  sparse-clock portfolio rule. Source anchor: `F315`.
- `rank_time_acceleration`: IC `0.0576`; weak state feature only.
- `h364_official_sentiment_x_earnings_guidance`: avg IC `0.01766`, `10 / 10`
  positive years, S1 corr `-0.0104`; candidate local-news signal pending fixed
  consumer integration. Source anchor: `F342`.
- C16 filter lesson: market-down, liquidity, and price/C16 divergence matter;
  macro regime, gap direction, same-signal persistence, sector-relative C16,
  streak compounding, and C16 extreme tails are already failed or overfit.

## Hypothesis Queue

Ranked by upside, novelty, current-data feasibility, and honesty of first test.
Do not assign `H` numbers until one branch is activated.

Activated next branch before returning to the ranked queue:
`h364_consumer_integration` - one fixed portfolio/consumer audit for
`h364_official_sentiment_x_earnings_guidance`; no `2026+` fitting.

1. `news_flow_disagreement`: public text and posted orders disagree before the
   best reversals and traps.
   Smallest honest test: bucket `order_volume_ratio_rank` against PhoBERT
   sentiment, `forward_looking`, `article_scope`, and `source_type`; compare
   next-day relative-return IC for bullish-flow/negative-news, bullish-flow/no-news,
   positive-news/weak-flow, and active-news/strong-flow confirmation states.
   Why not killed: H381 killed no-news absence but inverted toward active-news
   confirmation; C16 divergence worked for price-vs-flow; simple sentiment
   failed only as a pooled standalone lane.

2. `official_attention_delay`: official/regulatory or forward-looking articles
   need flow confirmation and may pay after a delay, not on the headline day.
   Smallest honest test: TRUE WF IC and 1d/5d payoff by high
   `phobert_source_type_official_or_regulatory_prob_*` plus C16/insider support
   versus official-only rows. Why not killed: official-conditioned PhoBERT was
   only offline evidence and standalone promotion failed; this tests a different
   interaction target.

3. `insider_down_rescue`: insider buys after visible weakness are different
   from ordinary insider buys.
   Smallest honest test: intersect prior insider buy, 1-3 day stock drawdown,
   and C16 rank; require sample-size and TRUE WF checks against insider-only
   and down-only controls. Why not killed: insider lead and consecutive-down
   passed separately; C16 streak compounding failed, but not insider-vs-weakness
   cross-source confirmation.

4. `fresh_selection_pulse`: a ticker's first reappearance in the top candidate
   set after dormancy carries more edge than repeated membership.
   Smallest honest test: compute days since ticker last appeared in top-5/top-10
   candidate pool from `entry_alpha/candidate_panel_daily.parquet`; compare
   matched cycle returns for first-return, stale-repeat, and incumbent states.
   Why not killed: sticky retention was a portfolio rule; freshness of selection
   history was not tested as a separate alpha state.

5. `post_ollama_event_cascade`: the narrow Ollama event-family residual can
   revive event timing only if it changes the event representation.
   Smallest honest test: after the guarded backfill finishes, build first-event,
   repeat-event, and event-family transition states, then compare against the
   old H321/H361 CafeF event-v2 sparse-clock controls. Why not killed: event-v2
   is parked under old mappings; this branch requires new event-family data.

6. `calendar_as_liquidity_mechanism`: calendar edges are proxies for settlement,
   attention, and breadth states, not magic dates.
   Smallest honest test: retest `monday_jan_combo`, quarter-start, and
   late-month effects after matching or residualizing volume regime, market
   breadth, news volume, buyable breadth, and C16 down-market state. Why not
   killed: calendar filters passed, but the mechanism has not been decomposed.

7. `tradability_release_pulse`: a high-ranked name becoming buyable after a
   blocked or limit-constrained state has a short executable continuation edge.
   Smallest honest test: use `release_flag`, `prev_can_buy_next_open`,
   `can_buy_next_open`, price-limit features, and candidate rank from the entry
   panel; compare next-cycle matched return and blocked-buy health. Why not
   killed: generic blocked-buy complexity failed as a live overlay, but release
   after constraint is a different stock-level entry event.

8. `source_triangle_sparse`: insider, order pressure, and local-news source
    type may form a sparse high-conviction state even when any two-way route is
    too noisy.
    Smallest honest test: require at least two of prior insider buy, high C16,
    official/stock-scope news, and forward-looking text; measure IC and matched
    returns with strict minimum support. Why not killed: foreign/proprietary and
    broad news routes failed; the confirmed pieces here are insider, C16, and
    local source/type heads.

## Hidden-Flow Branch Memo

Core thesis: Vietnam equities are less a pure price-prediction problem than a
hidden-flow, attention-delay, and tradability-release problem. The strongest
current evidence points to constraint plus delay: information appears in C16,
insider activity, order-volume imbalance, source/type news, and candidate state;
price adjusts late because of T+2, limits, liquidity gaps, retail attention,
opening mechanics, and buyability constraints. Search for disagreement between
price, orders, insiders, news, tradability, calendar, and candidate temperature.

Operational reframing:
- `S1` is the price-memory sensor.
- `C16` is the order-pressure sensor.
- `insider` is the conviction sensor.
- `PhoBERT/Ollama` are narrative and attention sensors.
- `1H bars` are intraday absorption sensors.
- `tradability` is the execution-boundary sensor.
- `calendar` is the settlement and attention clock.
- `candidate_panel` is the model-confidence and temperature sensor.

Ranked activation ladder:
1. `silent_accumulation_before_narrative`: high C16/order pressure, no 1d/5d
   stock news, mild price move, and non-extreme volume may be the cleanest
   hidden-demand state. First test: compare against raw C16, down-market C16,
   Triple Storm, high-C16/news-present, and high-C16/price-already-moved.
2. `dynamic_candidate_thermodynamics`: portfolio edge may come from choosing K,
   not another indicator. First test: score entropy, top-10 spread, rank gaps,
   buyable breadth, and activation uncertainty determine top-1/2/5/cash under
   TRUE rolling holdout.
3. `insider_down_rescue`: insider buying after visible weakness plus C16 support
   may be sparse but high-conviction. First test: matched sparse returns and
   top-book uplift versus insider-only, down-only, and C16-only controls.
4. `nihilist_reversal`: down stock, down market, weak/no bullish news, and high
   C16 may mark hidden support after public capitulation. First test: require it
   to beat consecutive-down and down-market C16 separately.
5. `tradability_release_pulse`: a high-ranked stock becoming buyable after a
   blocked/limit-constrained state may create a one-cycle door-open edge. First
   test: `prev_can_buy_next_open == false`, `can_buy_next_open == true`, rank,
   C16, and no immediate re-block.
6. `shadow_liquidity_gravity_well`: order counts and average order size should
   approximate missing book depth through fragmentation. First test:
   `log((buy_count + sell_count) / volume)`, avg-order-size imbalance, and
   price/fragmentation flux versus volume-spike and C16 controls.
7. `anti_signal_annihilation_veto`: high S1 should be vetoed when C16, insider,
   news, tradability, and sector context disagree. First test: long-only cash
   veto on top-book names, not shorting and not a dense rank feature.
8. `official_attention_delay_confirmed`: official/regulatory/source-type news
   may pay only after 1d/3d/5d delay and only with C16 or insider confirmation.
   First test: official-only versus official-plus-flow rows.
9. `fresh_selection_pulse`: a ticker newly noticed by the candidate panel after
   dormancy may be different from stale repeat membership. First test: first
   reappearance, stale repeat, incumbent, and never-before candidate buckets.
10. `capital_reynolds_number`: liquidity, breadth, volatility, C16, and friction
    should be unified into a flow-regime state. First test: low/medium/high `Re`
    buckets for C16 IC, Triple Storm IC, S1 degradation, and reversal dominance.
11. `haar_cascade_pressure`: hidden demand may become tradable when C16 energy
    migrates from short to medium horizons. First test: 1/2/4/8-day wavelet
    energy versus failed plain C16 acceleration controls.
12. `noether_flow_break`: order counts, order volumes, average order size,
    traded volume, and price should obey a pseudo-conservation law; alpha is the
    residual. First test: dev-fit expected price move, then test absorption,
    thin-book markup, and support residuals out of sample.
13. `causal_lightcone_news`: Ollama event-family shocks may propagate through
    sector, correlation, and co-mention neighbors. First test: neighbor event
    pressure versus ticker-only event states after Ollama aggregation.
14. `hilbert_phase_lead`: C16 phase leading price phase may be the continuous
    version of divergence. First test: price phase, C16 phase, phase gap buckets
    versus Triple Storm and price/C16 divergence controls.
15. `forced_seller_detector`: margin cascades may be visible without broker
    books through large negative return, volume spike, sell-volume pressure,
    rising avg sell size, limit/floor proximity, sector covariance, and no bad
    news. First test: reversal only when next-day C16 turns positive and
    tradability releases.

Extended source-memo branches:
16. `candidate_decision_boundary_curvature`: top-k instability may be encoded in
    the score curve around ranks 3-10. First test: score slope/curvature,
    rank-gap 5/6, and rank-gap 1/5 as concentration/diversification/cash gates.
17. `percolation_breadth_threshold`: alpha may change once positive-return or
    high-C16 tickers become one connected market cluster. First test: rolling
    correlation graph, active-node giant-component size, and C16/S1 IC by
    percolation bucket.
18. `ising_sector_frustration`: ticker-level flow fighting sector direction may
    be the right representation, unlike failed ordinary sector-relative C16.
    First test: ticker spin versus sector spin states, with special focus on
    sector-down/ticker-C16-up hidden support and sector-up/ticker-C16-down weak
    participation.
19. `volume_lot_grid_resonance`: retail crowding may cluster around round lots,
    round prices, and round traded values. First test: price/tick roundness,
    volume-lot roundness, traded-value roundness, and grid crowding as C16/S1
    conditioners.
20. `rational_anchor_reversion`: traders may anchor to simple fractions of a
    recent range. First test: distance to low-denominator Farey fractions of the
    60-day range and C16/S1/C9 payoff near versus away from anchors.
21. `prime_lag_memory_comb`: nonuniform memory may survive even though ordinary
    persistence failed. First test: prime-lag C16/return/volume combs at
    `2,3,5,7,11,13` against equal-count consecutive and random-lag controls.
22. `mobius_pressure_derivative`: a Mobius square-free filter may separate
    alternating non-redundant C16 pressure from stale persistence. First test:
    `sum(mu(k) * C16_lag_k)` for `k <= 13` versus ordinary C16 ROC/acceleration.
23. `crt_settlement_lattice`: T+2 settlement, weekday, attention, and rebalance
    cadences may alias into calendar residues. First test: predeclare residues
    modulo `2,3,5,8,13` and cross only with proven states such as high C16,
    down-market, consecutive-down, insider lead, and Triple Storm.
24. `fibonacci_time_crystal`: attention cycles may lock onto Fibonacci trading
    lags. First test: `5,8,13,21,34,55` return/C16/breadth combs against equal
    non-Fibonacci controls, weekday/month/quarter controls, and TRUE rolling
    holdout.
25. `ticker_soul_resonance`: ticker names should matter only through order
    pressure if superstition has any effect. First test: one fixed gematria map
    plus lunar-day distance; require C16 spikes and high-C16 payoff conditioning
    after weekday/month/lunar/calendar controls. Very low prior.
26. `capital_reynolds_number_detail`: this is the serious physics version of
    rank 10. First test: `Re = value_velocity * breadth / viscosity`, where
    viscosity comes from Amihud, range volatility, and tradability friction;
    compare laminar, transition, and turbulent regimes for C16, Triple Storm,
    S1 degradation, and reversal dominance.
27. `shadow_liquidity_fragmentation_well`: implementation detail for rank 6.
    First test: fragmentation, avg-buy-minus-avg-sell order size, and
    price/fragmentation flux; classify many-small-buy/no-move, few-large-buy/no-
    move, many-small-sell/no-fall, and few-large-sell/sharp-fall states.
28. `forced_seller_detector_detail`: implementation detail for rank 15. First
    test: large negative return, volume spike, sell-order pressure, rising avg
    sell size, limit/floor proximity, sector covariance, and no matching bad
    news; go long only if next-day C16 turns positive and tradability releases.
29. `retail_swarm_vs_institution_knife`: the same buy volume means different
    things depending on order count and average size. First test: retail-swarm
    versus institution-knife states crossed with price flat/up/down to separate
    fragile hype from stealth accumulation and informed support.
30. `queue_ghost_failed_ceiling`: ceiling pressure can mean either real demand
    or hidden supply. First test: near-ceiling count, ceiling-hit count,
    failed-ceiling count, post-ceiling buyability, and C16 support to separate
    release continuation from blowoff and floor-hit reversal.

Do not spend time on more raw C16 persistence, macro-regime C16, gap-direction
C16, ordinary sector-relative C16, standalone foreign-flow windows,
proprietary-flow rank/conflict variants, dense standalone news sentiment,
sparse calendar bonuses pasted onto the portfolio, or event-v2 overlays before
the Ollama event-family representation changes.

Meta-hypothesis: predict when prediction matters. Buy candidates only when
hidden demand is high, public attention is low or delayed, tradability has just
opened, the market is distressed but not collapsing, and candidate temperature
supports concentration.

## State-Transition Regime Machine Memo

Deeper thesis: the next edge is likely a regime machine, not another static
indicator. A valid branch should ask which hidden pressure is building, whether
the public story has caught up, whether the execution door is open, and which
market regime makes the pressure tradable. Everything below is current-data
testable unless marked post-Ollama or future-data. Overlaps with the
Hidden-Flow memo should share artifacts rather than becoming duplicate retunes.

Batch A, hidden buyer / hidden seller machines:
1. `state_invisible_buyer`: high C16, non-positive return, weak intraday close,
   moderate/high volume, and no positive news may mark quiet supply absorption.
   First test: beat raw C16, down-market C16, and C16 divergence.
2. `state_invisible_seller_veto`: high S1 plus pretty candle, high close
   location, high volume, and weak/negative C16 is a long-only veto state.
   First test: top-book cash veto versus normal buy.
3. `state_absorption_polarity_flip`: alpha may appear when price impact per unit
   C16 flips sign. First test: `return / C16_pressure` sign flips versus C16
   ROC/acceleration controls.
4. `state_silent_bid_3d`: three days of high C16 with no news and no price chase
   may be stealth accumulation. First test: require no-public-narrative and low
   price-response gates so this is not generic failed C16 persistence.
5. `state_failed_dump_support`: high sell-pressure with flat/up close in a down
   market may mean support. First test: sell-pressure failure states versus
   buy-pressure C16 states.

Batch B, attention / narrative machines:
6. `state_narrative_vacuum`: high C16 with no own-news, no 5d news, and no peer
   co-mention burst may be higher quality than high-C16 with attention. First
   test: compare own-news absence versus sector/peer-attention absence.
7. `state_narrative_lag`: C16 spikes may predict future article arrival. First
   test: today-only C16 predicts `t+1/t+2` news probability and returns without
   using future news for entry.
8. `state_news_lightcone_front_run`: peer news plus own-ticker C16 and no own
   news may front-run the target article. First test: peer news count/co-mention
   pressure versus own-ticker news baseline.
9. `state_hype_distribution`: bullish/forward-looking text plus weak C16, high
   volume, and positive return may be distribution. First test: veto high-S1
   candidates in this state.
10. `state_disbelief_accumulation`: negative text, high C16, stock drawdown, and
    down market may be the news version of Triple Storm. First test: beat
    negative-news-only and down-market-C16 controls.
11. `state_official_flow_confirmation`: official/regulatory text needs C16 or
    insider confirmation. First test: 1d/3d/5d payoffs for official-only versus
    official-plus-flow.
12. `state_source_type_conflict_matrix`: source types should be crossed with
    flow and price response, not pooled. First test: official/company/market/
    promotional source buckets by high/low C16 and positive/negative price.

Batch C, tradability / limit-boundary machines:
13. `state_door_opened`: candidate alpha may appear at the unbuyable-to-buyable
    transition. First test: previous blocked buyability, current buyability,
    top-10 rank, and C16 support.
14. `state_quiet_release`: tradability release should work best with low news
    attention and non-extreme volume. First test: door-opened state split by
    news count and volume crowding.
15. `state_panic_release`: floor/near-floor panic followed by buyability and
    improving C16 may be forced-seller release. First test: recent floor/bad
    tradability plus C16-rank-up in down/recovering markets.
16. `state_ceiling_queue_exhaustion`: repeated ceiling attempts with fading C16
    may be buyer-queue exhaustion. First test: ceiling count, declining C16,
    high volume, and close not at ceiling as continuation veto.
17. `state_floor_compression_spring`: recent floor hits plus high C16, range
    compression, and buyability may refine weak floor-reversal skeletons. First
    test: floor-count plus C16/range gates versus floor-count alone.
18. `state_boundary_entropy`: market-wide limit/blocked/zero-volume dispersion
    may determine whether signals degrade or become explosive. First test: S1,
    C16, and top-k performance by boundary-entropy bucket.

Batch D, candidate-panel / self-reflective alpha:
19. `state_first_sight`: first top-10 appearance after long dormancy may beat
    stale membership. First test: days since last top-10 `> 60` versus repeat
    and incumbent states.
20. `state_model_deja_vu`: nearest past candidate states may rhyme. First test:
    kNN over rounded score shape, sector mix, C16 distribution, tradability,
    breadth, and market state using dev-only memory for validation.
21. `state_candidate_crowd_cliff`: many similar scores near the cutoff imply
    uncertainty. First test: small rank 5-10 gap, high candidate count, and high
    buyable breadth as diversify/reduce-exposure gate.
22. `state_candidate_monarchy`: one dominant candidate may justify top-1
    concentration. First test: large score 1-2 and 1-5 gaps plus buyability.
23. `state_candidate_civil_war`: low overlap among top names by S1, C16,
    reversal, insider, sector, and tradability means portfolio uncertainty.
    First test: reduce K/exposure when cross-voice overlap is low.
24. `state_self_disagreement_alpha`: selector-high but one subvoice-low may be
    non-obvious alpha or trap. First test: specific disagreement buckets such as
    selector-high/C16-low, selector-high/news-low, and selector-high/tradability
    pain.

Batch E, sector / graph / propagation machines:
25. `state_sector_laggard_hidden_bid`: C6-style sector laggard plus high C16 and
    no news may improve the confirmed laggard skeleton. First test: beat C6
    alone.
26. `state_leader_exhaustion_laggard_transfer`: sector-leader blowoff with
    declining leader C16 may transfer flow to laggards. First test: leader
    return/volume/C16 exhaustion plus follower C16 rising.
27. `state_correlation_neighbor_echo`: correlated-neighbor news or C16 shocks may
    move target tickers 1-3 days later. First test: own-only, neighbor-only, and
    own-plus-neighbor signals.
28. `state_co_mention_contagion`: news co-mentions may define attention channels
    better than sector labels. First test: co-mention graph neighbor events;
    post-Ollama event-family aggregation is the preferred richer version.
29. `state_sector_winding_number`: sector leadership may rotate topologically,
    not just rank. First test: signed sector-rank rotation states and C16/S1 IC
    by winding state.
30. `state_mycelial_market_network`: weak-tie pressure from sector, co-mention,
    correlation, insider relation, and ownership style may predict no-signal
    tickers. First test: mycelial pressure on stocks with no own-ticker signal.

Batch F, 1H reduced-shape resurrection:
31. `state_first_hour_lie`: first-hour direction that disagrees with daily C16
    may reverse or reveal false strength. First test: first-hour positive with
    C16 negative and first-hour negative with C16 positive by market/liquidity.
32. `state_lunch_absorption_proxy`: early weakness and later recovery without
    news plus high C16 may proxy intraday absorption. First test: first-half
    negative, final-hour positive, close-location high, high C16.
33. `state_reduced_shape_triple_storm`: Triple Storm should be tested on 1H
    reduced-shape disagreement atoms. First test: liquid, market-down, and
    intraday-shape disagreement versus known Triple Storm.
34. `state_opening_auction_acceptance`: gap direction matters less than whether
    flow accepts or rejects the open. First test: gap-up/down crossed with
    intraday continuation/rejection, close location, and C16.

Batch G, flow identity machines:
35. `state_retail_swarm`: many small buy orders may be crowd attention. First
    test: high buy-count and low avg-buy-size split by market, news, C16, and
    price response.
36. `state_institution_knife`: fewer larger buy orders plus buy-volume pressure
    may be stealth sponsorship. First test: high avg-buy-size, moderate/low
    buy-count, high buy-volume pressure, price not up, no news.
37. `state_swarm_to_knife_transition`: hype may become real sponsorship when
    retail swarm shifts to institution knife. First test: `t-1` swarm to `t`
    knife transition.
38. `state_knife_to_swarm_exit`: large-order accumulation followed by swarm and
    news hype may be distribution. First test: earlier knife, current swarm,
    news spike, price up as exit/veto.
39. `state_avg_order_size_divergence`: buy pressure is stronger when average buy
    order size rises faster than sell order size. First test: z-scored avg-size
    divergence as C16 and insider conditioner.
40. `state_count_only_decoy`: buy-count imbalance without buy-volume imbalance
    may be retail noise. First test: count-only states versus buy-volume pressure
    controls.

Batch H, calendar as mechanism:
41. `state_salary_flow_window`: salary windows may proxy retail inflow regimes.
    First test: day-of-month `25-31` and `1-5` crossed only with high C16,
    retail swarm, volume z-score, and small/illiquid buckets.
42. `state_margin_reset_window`: forced selling may cluster near month-end after
    drawdowns. First test: month-end, 5d market drawdown, floor/sell-pressure
    proxy, then reversal only when C16 turns positive.
43. `state_monday_january_rerisking`: Monday-January may be re-risking rather
    than magic calendar. First test: decompose January, first 10 days, Monday,
    post-holiday, volume, breadth, and C16 down-market.
44. `state_pre_holiday_liquidity_vacuum`: pre-holiday thin liquidity may change
    C16 usefulness. First test: days to closure `<= 3`, low volume, and high
    illiquidity as conditioner only, not sparse calendar bonus.

Batch I, physics / complexity machines:
45. `state_capital_reynolds_2`: laminar, transition, and turbulent flow regimes
    may decide which alpha works. First test: `turnover_velocity * breadth /
    (Amihud + volatility + boundary pressure)`.
46. `state_market_viscosity_shock`: sudden liquidity thickening/thinning may
    change edge. First test: Amihud, high-low range, zero-volume share, and
    blocked-boundary share versus rolling 20d mean; split S1/C16 by bucket.
47. `state_lagrangian_cheap_motion`: large move with low liquidity-normalized
    action may continue; high action may blow off. First test: `sum(return^2 /
    traded_value_zscore)` states.
48. `state_entropy_collapse`: price/volume/flow uncertainty compression may
    precede large moves. First test: 20d discretized entropy collapse and C16
    direction as breakout direction.
49. `state_bifurcation_panic`: threshold crossings matter more than levels.
    First test: control parameter from C16 pressure, breadth slope, boundary
    entropy, and market drawdown; crossing-up/down outcome tests.
50. `state_percolation_ignition`: high-C16/positive-return nodes may ignite when
    connected into a giant component. First test: active-node component share
    versus candidate returns, C16 IC, and S1 IC.
51. `state_hurst_gate`: C16 should mean different things in persistent versus
    anti-persistent markets. First test: rolling Hurst of relative price or
    breadth; split C16, C9, S1, and Triple Storm.
52. `state_renormalization_survival`: real signals should survive coarse
    graining. First test: 1d/2d/4d/8d signal IC stability, sign consistency, and
    rank correlation.

Batch J, mathematical weirdness but honest:
53. `state_walsh_candidate_spectrum`: recent top-10 membership bitstrings may
    contain hidden modes. First test: Walsh-Hadamard coefficients over last 8
    rebalances against next-cycle returns.
54. `state_p_adic_liquidity_shells`: divisibility shells of ticks/lots/traded
    value may reveal roundness regimes. First test: `v_p` for `2,3,5,7` as
    C16/S1 conditioners.
55. `state_farey_anchor_reversion`: simple fractions of the 60d range may change
    behavior. First test: distance to `1/4,1/3,1/2,2/3,3/4,1` and C16/S1/C9
    performance.
56. `state_continued_fraction_narrative`: simple ratio trends may be more
    visible and crowded. First test: continued-fraction entropy of relative
    slope and C16/S1 by complexity bucket.
57. `state_mobius_memory_filter`: square-free lag filtering may isolate true
    alternating pressure. First test: Mobius C16 against ROC, consecutive lags,
    random lags, and prime-lag comb.
58. `state_riemann_zero_calendar_alias`: irregular harmonic phases are a
    low-prior calendar audit. First test: fixed first zeros only, no tuning, C16
    IC splits versus weekday/month controls.

Batch K, synthesis architectures:
59. `architecture_hidden_demand_state_machine`: classify ticker-days into no
    demand, visible momentum, stealth accumulation, absorption under stress,
    distribution into hype, forced-sell exhaustion, tradability release, and
    crowded blowoff. First test: next-day relative return, next-cycle portfolio
    return, and top-book success/failure.
60. `architecture_selector_policy`: learn the daily action, not just ticker
    returns: top1, top2, top5, top10, cash, sticky hold, or veto. First test:
    candidate entropy, score spread, buyable breadth, C16 dispersion, breadth,
    boundary entropy, and news attention.
61. `architecture_alpha_tribunal`: let independent voices judge each candidate:
    price, flow, insider, attention, execution, sector, and portfolio. First
    test: structural classes such as all-agree, price-high/flow-weak,
    flow-high/news-absent, insider-flow-weakness, and attention-high/flow-weak.
62. `architecture_long_only_antifragility`: optimize when to be long,
    concentrated, diversified, cash, or veto rather than pure IC. First test:
    objective includes return, drawdown penalty, cash drag, failed-fill penalty,
    and concentration regret.
63. `architecture_regime_alpha_zoo`: search for regimes, not universal signals:
    quiet accumulation, panic reversal, trend continuation, crowded hype,
    execution boundary, and sector rotation. First test: default frozen branch
    plus explicit state rules, each with matched controls.

North-star rule: price is late, story is later, order flow is earlier, and
execution decides whether early becomes tradable.

## Wild Hypothesis Queue

These are deliberately high-strangeness representation changes. They are not
claims of truth; each must be killed by the first cheap walk-forward test if it
does not beat the appropriate baseline. Do not assign `H` numbers until one
branch is activated.

1. `p_adic_liquidity_shells`: price ticks and volume lots may cluster in
   `2/3/5/7`-adic shells where retail crowding and price-limit mechanics create
   release states.
   Smallest honest test: compute p-adic valuations of rounded close, traded
   value, volume lots, and C16 rank; compare next-day IC inside each shell
   versus C16 baseline.

2. `farey_anchor_reversion`: stocks near low-denominator fractions of their
   rolling high/low range may behave like anchored rational grids, not smooth
   prices.
   Smallest honest test: flag closeness to Farey fractions with denominator
   `<= 8` over 20d/60d ranges; test whether C16, S1, or reversal IC changes
   only at those anchors.

3. `continued_fraction_trend_entropy`: relative price paths with unusually
   simple continued-fraction expansions may be crowded narratives that either
   continue hard or snap back.
   Smallest honest test: compute partial-quotient entropy on stock/VNINDEX
   relative price slopes; bucket IC and top-book returns by low versus high
   complexity.

4. `crt_settlement_lattice`: Vietnamese T+2 settlement, weekdays, and rebalance
   cadence may alias through a Chinese-remainder calendar lattice.
   Smallest honest test: predeclare residues modulo `2,3,5,8,13` trading days,
   cross them with C16/down-market state, and require TRUE rolling holdout.

5. `mobius_pressure_derivative`: C16 momentum failed as a plain derivative, but
   a Mobius square-free lag filter may isolate alternating accumulation from
   stale persistence.
   Smallest honest test: build `sum(mu(k) * C16_rank_lag_k)` for `k<=13` and
   compare to C16 level and simple C16 ROC under the same WF IC protocol.

6. `riemann_zero_phase_alias`: market attention may alias against irregular
   trading-time harmonics better than against ordinary Fourier peaks.
   Smallest honest test: use only the first fixed Riemann-zero phases as
   predeclared calendar features; test C16 IC splits against ordinary month and
   weekday controls.

7. `walsh_hadamard_candidate_spectrum`: top-k membership over recent rebalances
   is a binary signal; hidden selector modes may live in Walsh-Hadamard
   coefficients rather than raw ranks.
   Smallest honest test: encode each ticker's last 8 top-10 appearances as a
   bitstring, transform it, and test which fixed coefficients predict next
   cycle relative return.

8. `haar_cascade_pressure`: order pressure may matter when energy jumps across
   dyadic scales, not when its raw level is high.
   Smallest honest test: apply Haar wavelets to 1/2/4/8-day C16 rank histories;
   compare scale-jump states to C16 level, divergence, and down-market C16.

9. `hilbert_phase_lead`: C16 and price may form an oscillator where flow phase
   leading price phase predicts continuation, while price leading flow predicts
   exhaustion.
   Smallest honest test: Hilbert-transform rolling price-relative and C16
   series; test quadrants of phase lead/lag with strict no-2026 fitting.

10. `ising_sector_frustration`: sectors and tickers can be treated as spins;
    the best edge may appear when ticker pressure is frustrated against sector
    direction rather than aligned with it.
    Smallest honest test: define spin signs from sector return, ticker return,
    and C16 pressure; test frustration energy versus raw sector-relative C16,
    which already failed.

11. `percolation_breadth_threshold`: market breadth may have a critical
    threshold where stock moves become one connected cluster and activation
    alpha changes regime.
    Smallest honest test: build a rolling correlation graph, mark advancing or
    positive-C16 nodes, and test giant-component size as an activation-state
    conditioner.

12. `renormalization_fixed_point`: robust signals should survive coarse
    graining; fragile signals should change sign across 1/2/4/8-day scales.
    Smallest honest test: coarse-grain S1, C16, insider, and volume regimes
    across powers of two; test fixed-point stability versus next-day IC.

13. `noether_flow_break`: order-book summary variables may obey approximate
    conservation laws; alpha appears when buy/sell order counts, order volumes,
    and price movement violate the conservation residual.
    Smallest honest test: fit the conservation residual on dev years only, then
    test residual extremes as C16 conditioners in validation and confirmation.

14. `lagrangian_action_compression`: a stock moving a long way with little
    liquidity-normalized action may be under external force and continue.
    Smallest honest test: compute rolling action `sum(return^2 / value_zscore)`
    and test high-C16/low-action states against high-C16 alone.

15. `kalman_dark_flow`: hidden demand is the innovation left after price, C16,
    foreign flow, proprietary flow, insider buys, and news state fail to explain
    each other.
    Smallest honest test: dev-fit a lightweight Kalman or state-space residual;
    test residual sign and magnitude as a pure out-of-sample side-channel.

16. `topological_sector_winding`: sector leadership may rotate with winding
    number rather than with a single sector rank.
    Smallest honest test: fix a sector ordering, compute 5d winding of sector
    rank vectors, and test whether candidate returns differ in clockwise,
    counterclockwise, and no-wind states.

17. `decision_boundary_curvature`: the top-5 book may be unstable when scores
    near the selection boundary form a curved crowded surface.
    Smallest honest test: from candidate panels, compute score slope/curvature
    around ranks `3..10`; test whether high curvature predicts top-k failure or
    favors dynamic breadth.

18. `holographic_limit_boundary`: limit-up, limit-down, blocked-buy, and
    tradability-boundary tickers may encode more about tomorrow's whole market
    than the market average itself.
    Smallest honest test: build boundary entropy and boundary C16 pressure from
    execution/tradability flags; test next-day breadth and activation state.

19. `attention_black_hole`: heavy news attention with low price response and
    low order-pressure entropy may absorb information before a delayed move.
    Smallest honest test: combine news-count spikes, low realized return, and
    compressed C16 dispersion; test 1d/5d payoff against ordinary high-news
    days.

20. `anti_signal_annihilation`: rows where S1 is high but C16, insider, news,
    and tradability state all disagree may be long-only veto states rather than
    weak longs.
    Smallest honest test: predefine an anti-signal count and test cash/veto
    value on top-book candidates; no shorting and no 2026 tuning.

21. `euclid_lot_grid_resonance`: volume lots and price ticks may share simple
    gcd structures that reveal retail round-number crowding.
    Smallest honest test: compute gcd-like features on rounded price ticks,
    volume lots, and traded value; test only as a conditioner on C16/S1.

22. `prime_comb_memory`: ordinary C16 persistence failed, but a fixed prime-lag
    comb may capture nonuniform memory under settlement and limit constraints.
    Smallest honest test: aggregate lags `2,3,5,7,11,13` for return, volume,
    and C16 ranks; compare to same-length consecutive-lag controls.

23. `causal_lightcone_news`: event impact may propagate through sector and
    correlation neighbors with finite speed instead of staying on the tagged
    ticker.
    Smallest honest test: after local-news aggregation finishes, propagate
    first-event flags to nearest sector/correlation neighbors for 1-3 days and
    compare to ticker-only event-v2 controls.

24. `thermodynamic_candidate_free_energy`: candidate selection may be a
    temperature problem: score edge minus entropy cost determines whether the
    book should concentrate or diversify.
    Smallest honest test: compute daily candidate free energy from score spread,
    rank entropy, buyable breadth, and activation state; test fixed top-k
    policy by temperature bucket.

## Omega Hypothesis Queue

Omega ideas deliberately synthesize C16/Triple Storm with non-finance frames.
They are acceptable only as predeclared mathematical transforms over existing
data. Kill any branch that cannot beat the relevant baseline under walk-forward
or matched-holdout controls.

1. `omega_reynolds_capital_flow`: capital flow has laminar and turbulent
   regimes, and C16/Triple Storm only dominate when market Reynolds number is
   below the churn threshold.
   Smallest honest test: define `Re = value_velocity * breadth / viscosity`,
   where viscosity is Amihud/volatility/spread proxy; compare C16 and Triple
   Storm IC in laminar, transition, and turbulent buckets.

2. `omega_vortex_shedding_rotation`: sector rotation may shed periodic eddies
   after a leadership stock accelerates, creating repeatable follower pulses.
   Smallest honest test: compute sector-leader return/C16 acceleration and
   lagged follower response at 1-5 days; require out-of-sample lift over raw
   sector momentum and C16.

3. `omega_hurst_memory_gate`: C16 is a different signal in persistent markets
   than in anti-persistent markets.
   Smallest honest test: estimate rolling Hurst exponent for stock-relative
   price and market breadth; test C16/down-market C16 IC in `H<0.45`,
   `0.45<=H<=0.55`, and `H>0.55` states.

4. `omega_bifurcation_panic`: stable trends collapse when a control parameter
   crosses a bifurcation point: high C16, falling breadth, and rising blocked
   boundary entropy.
   Smallest honest test: predefine the control parameter from C16, breadth
   slope, and tradability-boundary entropy; test next-day gap/failure and
   top-book drawdown around threshold crossings.

5. `omega_stoic_indifference`: the strongest longs are stocks whose order
   pressure remains high while the crowd is indifferent: no news, low chatter,
   low return response.
   Smallest honest test: combine high C16 with low news count, low realized
   return, and low volume shock; compare against `silent_order_pressure` and
   Triple Storm controls.

6. `omega_nihilist_capitulation`: when all ordinary narratives are broken,
   forced selling creates a cleaner long-only reversal than optimistic news.
   Smallest honest test: define a nihilism state from negative recent returns,
   no positive news, weak sentiment, and high order pressure; test against
   consecutive-down and down-market C16 baselines.

7. `omega_yuga_market_cycle`: ancient cycle structure is only useful if it
   compresses known calendar edges into a better deterministic phase variable.
   Smallest honest test: map trading days into fixed 4-phase Yuga-style cycles
   with lengths derived from `4:3:2:1`; test C16 IC splits after controlling
   for month, weekday, and quarter-start.

8. `omega_nakshatra_attention_clock`: lunar mansions are a superstition proxy
   for retail timing only if they condition news and volume attention better
   than the failed generic lunar test.
   Smallest honest test: approximate lunar phase/nakshatra from date, cross
   only with news-volume spikes and C16 down-market state, and require lift over
   ordinary weekday/month controls.

9. `omega_quantum_observation_collapse`: major news spikes collapse a
   price-volume uncertainty wave; the post-collapse direction depends on
   whether C16 was already aligned before observation.
   Smallest honest test: define uncertainty as rolling price entropy times
   volume entropy; test event/news-spike rows where uncertainty drops sharply
   and pre-spike C16 is high versus low.

10. `omega_neural_link_reflex`: retail network reflexes show up as synchronized
    microbursts across related tickers before official narratives arrive.
    Smallest honest test: on 1H CafeF adjusted bars, detect same-hour volume
    bursts across sector/correlation neighbors; test whether ticker-day C16
    after the burst predicts next-day top-book return.

11. `omega_mycelial_information_transport`: information may propagate like a
    mycelial network through sector, shared-holder, and news-comention edges at
    a measurable biological speed.
    Smallest honest test: build a graph from sector plus news co-mentions; test
    whether first-event/C16 shocks improve neighbor returns at fixed 1-3 day
    propagation delays.

12. `omega_epigenetic_trauma_support`: crash memory is inherited; old 2022
    high-volume support/resistance zones remain reflexive sell or buy loci.
    Smallest honest test: mark distance to 2022 crash volume-at-price proxies
    from daily bars; test whether high C16 near those ghost levels reverses or
    fails differently from ordinary high C16.

13. `omega_omega_point_breadth`: market breadth may approach a finite-time
    singularity before large regime changes.
    Smallest honest test: fit dev-only reciprocal-time curves to breadth
    acceleration; test predeclared singularity-near states against activation
    and top-book drawdown outcomes.

14. `omega_quantum_annealed_book`: top-k selection may be a low-temperature
    annealing problem where small score gaps make the book unstable.
    Smallest honest test: compute candidate energy from negative score and
    temperature from rank entropy; compare fixed top-k outcomes by temperature
    bucket and test whether dynamic breadth helps only at high temperature.

15. `omega_simulation_glitch_repetition`: exact repeated state vectors may be
    glitches where the market replays a previous local path.
    Smallest honest test: hash rounded 5-day vectors of return, volume, C16,
    breadth, and news state; when a near-duplicate appears, test whether the
    next-day outcome repeats more than baseline.

## Omega Additions And Data Gates

These refine the latest speculative prompts into workspace-valid tests. Items
marked data-gated should not consume experiment time until the named source
exists.

1. `omega_hyperbolic_liquidity_vacuum`: order-book liquidity may be non-linear;
   apparent depth near the current price can vanish when the price path becomes
   fractal and C16 remains high.
   Smallest honest test: current-data proxy uses 1H CafeF adjusted path
   efficiency, daily order stats, and tradability/limit flags to detect
   high-C16 vacuum snap-backs. True test is data-gated on historical depth or
   matched 1-minute order-book snapshots; do not use adjusted 1H bars as proof
   of literal book curvature.

2. `omega_mycelial_herd_entanglement`: retail herding may synchronize across
   related tickers before public news, like a distributed information network.
   Smallest honest test: current-data proxy detects same-hour 1H volume bursts
   across sector/correlation/news-co-mention neighbors on zero-news days, then
   tests next-day C16/return lift. Direct Zalo/Telegram mutual-information test
   is data-gated until those feeds are legally and durably captured.

3. `omega_gematric_liquidity_wells`: ticker strings and lunar timing may proxy
   founder/retail superstition, but only if they beat strict calendar controls.
   Smallest honest test: predeclare one ASCII/ticker gematria mapping and one
   lunar-phase approximation; test ticker-gematria residue crossed with lunar
   phase and volume `mod 7` against weekday/month/quarter controls. Low prior
   because generic lunar already failed.

4. `omega_non_newtonian_capital_flow`: capital viscosity may change with
   stress; under high shear, liquidity solidifies and C16 stops behaving like a
   smooth flow signal.
   Smallest honest test: define shear from return/volume/news acceleration and
   viscosity from Amihud, range, blocked-boundary entropy, and value traded;
   compare C16/Triple Storm IC across low-shear, transition, and solidified
   states. This is the stress-dependent extension of
   `omega_reynolds_capital_flow`.

5. `omega_matching_engine_precision_ghost`: raw trade prints that violate tick
   size or precision rules could reveal API/matching-engine artifacts or bad
   adjustment state.
   Smallest honest test: data-gated on raw matched-trade or 1-second tape;
   scan unadjusted prints for tick-size violations, mantissa drift, and
   next-bar reversal. Existing adjusted daily/1H bars are not valid for this
   test because corporate-action normalization can create non-tick prices.

6. `omega_dendritic_margin_stress`: margin-call cascades may branch through
   unrelated winners as traders sell what they can, not what caused the loss.
   Smallest honest test: build a drawdown-covariance graph during market stress,
   estimate branching factor from lagged loser-to-winner sell propagation, and
   test whether branch factor `> 3` predicts next-day broad drawdown or
   top-book failure.

7. `omega_backtest_observer_decay`: alpha decay can be measured as a
   decoherence rate between locked backtest, pseudo-live, and paper/live
   monitor behavior.
   Smallest honest test: for saved strategy branches with live or pseudo-live
   reruns, measure Sharpe/relative-return decay as a function of test count,
   retune count, and time since freeze. This is a methodology audit, not a
   tradable signal.

8. `omega_foreign_pheromone_trails`: foreign capital may follow trail memory
   from prior successful exits rather than contemporaneous fundamentals.
   Smallest honest test: fit an ant-colony-style trail on CafeF foreign-flow
   net buy/sell persistence with evaporation; test whether trail intensity or
   trail breaks condition C16/insider outcomes. Reopens foreign flow only as a
   new path-memory representation, not another raw-rank window.

9. `omega_tectonic_sector_subduction`: sectors may accumulate stress like
   plates, with crashes as energy release rather than news reaction.
   Smallest honest test: estimate Gutenberg-Richter `b` values for sector
   drawdown magnitudes and cross-sector stress transfer; test whether abnormal
   `b` plus C16 boundary entropy predicts market-quake days better than
   ordinary breadth and volatility.

10. `omega_fibonacci_time_crystal`: some VN market cycles may lock onto
    Fibonacci trading-day periods rather than standard seasonal windows.
    Smallest honest test: predeclare Fibonacci lags `5,8,13,21,34,55`, run
    spectral/comb filters on VNINDEX breadth and C16 aggregates, and compare
    against non-Fibonacci lag controls under TRUE rolling holdout. Do not tune
    the unit cell on 2026.

11. `omega_shadow_liquidity_gravity_well`: with no historical book depth, C16
    and CafeF order counts can be treated as a dark-liquidity field; volume
    spikes with shrinking average order size may reveal hidden institutional
    slicing rather than real participation breadth.
    Smallest honest test: define fragmentation as sector-z-scored
    `log((buy_order_count + sell_order_count) / volume)` and flux as
    `abs(delta_price) / abs(delta_fragmentation)`, winsorized and sector
    demeaned. Test whether extreme flux divergence predicts next-day price-warp
    reversal, limit-boundary touch, or C16 IC lift versus ordinary volume-spike
    and order-count controls.

12. `omega_phobert_spin_phase_transition`: PhoBERT and Ollama-guarded news
    features may matter less as sentiment level than as sector spin alignment.
    A coherent market-wide spin state can create momentum, while high but
    incoherent sentiment is just paramagnetic noise.
    Smallest honest test: compute sector-weighted magnetization
    `M = sum(sentiment * sector_weight)` plus susceptibility as the change in
    `M` per article/news shock. Test whether susceptibility peaks predict
    trend reversal or Triple Storm failure better than raw sentiment, article
    count, and market-return controls.

13. `omega_zalo_proxy_turbulence_index`: without Zalo or Telegram feeds, 1H
    CafeF adjusted bars may proxy retail social turbulence through burst
    geometry. Smooth many-small bursts are laminar; rare sector-wide 1H volume
    shocks are turbulent retail churn.
    Smallest honest test: calculate intraday volume-burst kurtosis and a
    Reynolds proxy using mean 1H volume, 1H return volatility, and sector
    viscosity from Amihud/range/value traded. Test whether turbulent regimes
    mark S1/technical-indicator failure, C16 degradation, or contrarian C16
    lift under TRUE rolling holdout. This is a Zalo proxy only, not evidence of
    actual chat propagation.

14. `omega_ticker_soul_resonance`: ticker gematria and lunar day may proxy a
    narrow superstition-timing effect only if the effect appears in C16 order
    pressure, not just price or volume seasonality.
    Smallest honest test: predeclare one ASCII ticker mapping and lunar-day
    approximation, compute `R = abs((gematria(ticker) mod 29.5) - lunar_day)`,
    and test whether `R` near zero predicts C16/order-pressure spikes after
    weekday, month-end, holiday, Tet, and generic lunar controls. Low prior;
    kill unless it beats the broader `omega_gematric_liquidity_wells` control.

15. `omega_foreign_pheromone_half_life`: foreign-flow trail value may decay at
    a measurable half-life, and that half-life may shrink when the market has
    already priced in the foreign/upgrade narrative.
    Smallest honest test: historical test uses daily CafeF foreign-flow trails
    with exponential evaporation and VIX/yield macro gates; forward-only test
    uses 2026 liveboard snapshots plus 1H CafeF bars to measure whether local
    volume follows foreign scout flow within four trading hours. Do not treat
    the 4-hour version as a historical backtest until enough forward snapshots
    accumulate.

16. `omega_llm_market_language_inversion`: market action may behave like a
    token stream whose grammar is conditioned by PhoBERT/Ollama news states;
    syntax errors are price moves that contradict the news grammar.
    Smallest honest test: discretize next-day OHLCV into return/range/volume
    tokens, fit a frozen dev-only conditional token model from news embeddings,
    and test whether low perplexity or high syntax-error residuals predict
    reversals better than raw news sentiment and return controls.

17. `omega_vix_vnd_gravitational_lens`: VIX, DXY, S&P 500, and yields may bend
    VNINDEX returns away from local fundamentals, creating global-lensing
    residuals.
    Smallest honest test: fit rolling global-beta expected VNINDEX returns from
    available macro/global proxies, then test whether large lensing residuals
    condition C16, breadth, and foreign-flow edges. Any event-date assumptions
    must be verified from local macro/event data before activation.

18. `omega_mycelial_noise_floor_fft`: social echo may be visible in model
    residuals rather than chat feeds; repeated residual frequencies can mark
    retail synchronization.
    Smallest honest test: compute RL-matrix or S1 residuals versus 1H outcomes,
    run predeclared spectral tests on residual sequences, and compare Fibonacci
    frequency hits against non-Fibonacci controls. Do not use raw/adjusted bar
    differences as social evidence without a clear adjustment artifact model.

19. `omega_c16_quantum_tunneling`: high C16 pressure with stalled price may be
    a potential well that resolves as a gap or limit-boundary jump.
    Smallest honest test: define trapped pressure as high C16 plus low path
    efficiency/low realized return; define barrier width from recent high,
    price-limit distance, or resistance band; test gap-up/open breakout odds
    against ordinary C16, breakout, and volume-compression controls.

20. `omega_simulation_save_state_replay`: markets may replay earlier state
    sequences across different ticker sets when liquidity and news regimes
    align.
    Smallest honest test: hash or edit-distance compare normalized 1H volume
    and return sign sequences against prior sessions/checkpoint dates; test
    whether low-distance replays predict next-bar or next-day path repetition
    more than nearest-neighbor baselines.

21. `omega_krx_clock_jitter`: dissemination/matching-engine changes may create
    hour-boundary or session-open front-loading in 1H bars.
    Smallest honest test: if true 5-minute bars are unavailable, use 1H
    first-hour/open proxies and forward snapshots only; test post-KRX-date
    hour-boundary volatility concentration versus pre-date controls. Raw
    minute/tick data is required before claiming hardware latency.

22. `omega_ftse_upgrade_scent_decay`: upgrade-narrative foreign flow may
    evaporate before the actual event, turning buy-the-rumor into sell-the-fact.
    Smallest honest test: encode only locally verified upgrade-calendar dates,
    fit `net_foreign_flow * exp(-lambda * days_since_event_anchor)`, and test
    whether scent decay predicts C16 failure, breadth fade, or rally exhaustion
    after global-proxy controls.

23. `omega_vingroup_gravitational_lens`: dominant index names may frame-drag
    unrelated tickers into sympathy moves when their index contribution is
    extreme.
    Smallest honest test: compute rolling index-contribution mass for VIC/VHM
    and other leaders, then test whether tickers entering high-correlation
    orbital zones for 3 days reverse, continue, or decouple versus sector and
    market-beta controls.

24. `omega_rate_osmosis_liquidity_wilt`: high deposit/interbank-rate pressure
    may pull liquidity through the market membrane, reducing equity turgor.
    Smallest honest test: use locally available rates/macro proxies, value
    traded, 1H volume bursts, and Amihud to test whether rate pressure predicts
    liquidity wilt and C16 degradation beyond ordinary market-volatility
    controls. Do not hardcode current quoted rates without source verification.

25. `omega_phobert_semantic_saturation`: rallies may fail when news volume is
    high but semantic novelty is low.
    Smallest honest test: compute daily embedding entropy and KL divergence of
    CafeF/PhoBERT article vectors versus a rolling 30-day baseline; test whether
    low novelty plus rising price predicts hype exhaustion better than article
    count and raw sentiment.

26. `omega_zalo_ghost_order_turbulence`: CafeF average order size can proxy
    retail micro-turbulence when volume stays high but orders fragment.
    Smallest honest test: build an order-flow Reynolds proxy from order count,
    average order size, volume, and price range; test whether high-Re states
    invalidate support/resistance or weaken technical/S1 signals. This is the
    order-statistics sibling of `omega_zalo_proxy_turbulence_index`.

27. `omega_lunar_prop_desk_tide`: lunar phase/perigee may matter only if it
    shows up in proprietary desk behavior, not generic price seasonality.
    Smallest honest test: predeclare lunar phase/perigee approximation, test
    prop-desk buy/sell value and volume changes around new/full/perigee days,
    and require it to beat weekday, month-end, Tet, and earnings/dividend-event
    controls. Low prior.

28. `omega_global_gematria_resonance`: ticker gematria may interact with global
    index levels as a deliberately silly but cheap synchronicity control.
    Smallest honest test: predeclare one ticker mapping and one global-index
    proxy, test `mod(global_index_level, gematria)` buckets versus sector-relative
    returns, and kill unless it beats random ticker-code permutations.

29. `omega_c16_pressure_wavefunction`: C16 may be better represented as a
    probability-density squeeze than directional buy/sell pressure.
    Smallest honest test: estimate a pressure-density state from C16 level,
    C16 slope, range compression, and next limit-band distance; compare squeeze
    breakout odds to `omega_c16_quantum_tunneling`. Treat this as the continuous
    wavefunction variant of item 19, not a separate retune sweep.

30. `omega_forward_foreign_time_loop`: forward-only liveboard snapshots may
    reveal repeated foreign-flow motifs once enough forward history exists.
    Smallest honest test: compute cyclic fingerprints or CRC-style hashes over
    intraday foreign-flow snapshots and test for 22-day motif repeats. Data-gated
    until the forward snapshot surface has enough post-2026-04-09 history.

31. `omega_noether_action_density`: recurring weekday/session symmetries may
    imply a conserved action-density that fake moves must pay back.
    Smallest honest test: define a simple Lagrangian from return velocity,
    realized volatility, and volume-cost terms; test whether deviations from
    learned Friday/session symmetry predict equal-and-opposite anti-spikes under
    rolling holdout.

32. `omega_liquidity_allometry`: liquidity consumption may scale with market
    cap near a biological `3/4` power law, and deviations can flag overheating
    or hibernation.
    Smallest honest test: regress `log(value_traded)` on `log(market_cap)` by
    year/sector, estimate residual metabolism, and test whether hyper-metabolic
    or hibernating residuals condition C16, S1, and tradability outcomes.

33. `omega_topological_insulator_edges`: VN liquidity may conduct mostly at
    price boundaries, while the market bulk stays inert.
    Smallest honest test: bucket tickers by 52-week high/low distance and
    limit-band proximity; test whether conductivity from turnover, spread proxy,
    and range spikes only at the edges, and whether mean reversion fails there.

34. `omega_retail_bose_einstein_condensate`: after extended low-volatility
    cooling, retail behavior may collapse into one coherent macro-particle.
    Smallest honest test: identify low-volatility cooling windows, then measure
    cross-ticker correlation, same-hour volume-burst overlap, and limit-up
    clustering; test whether coherence length predicts market-wide jumps.

35. `omega_sector_seismic_gap`: sector subduction should show a missing band of
    small drawdowns before major sector quakes.
    Smallest honest test: extend `omega_tectonic_sector_subduction` with a
    Gutenberg-Richter seismic-gap feature: when small drops disappear but stress
    accumulates, test next-week blue-chip volatility and sector crash odds.

36. `omega_fibonacci_cellular_automaton`: VNINDEX up/down strings may follow
    simple local update rules around Fibonacci lags.
    Smallest honest test: encode daily up/down states, search only predeclared
    Wolfram-style rules using lags `2,3,5,8`, and compare forecast skill against
    shuffled controls and non-Fibonacci lags. Kill if it only works after rule
    mining on 2026.

37. `omega_foreign_pheromone_evaporation_rate`: foreign-flow influence may be
    dead when its half-life falls below two sessions.
    Smallest honest test: estimate rolling decay of foreign net buy predictive
    power for returns/C16 across 1-5 day horizons; if `T_half < 2` days, test
    whether foreign-flow headlines should be ignored in selection. This is the
    diagnostic version of items 15 and 22.

38. `omega_zipf_order_size_language`: order-size distributions may have a
    natural language law; deviations can flag block activity or unnatural
    slicing.
    Smallest honest test: with only CafeF daily average order size/counts, test
    cross-sectional rank-frequency slopes of average order size by day/sector;
    true trade-size Zipf tests are data-gated on tick-level prints.

39. `omega_riemann_volatility_music`: crash timing may contain spectral
    structure beyond ordinary calendar cycles.
    Smallest honest test: run predeclared spectral tests on VNINDEX `<= -2%`
    event spacing, compare against phase-randomized and calendar-controlled
    baselines, and treat any Riemann/GUE mapping as decoration unless it beats
    the controls out of sample.

40. `omega_news_jsonl_entropy_spring`: news surprise without price movement may
    compress a spring before a move.
    Smallest honest test: compute embedding KL divergence and article-volume
    surprise versus rolling 30-day history; test high-surprise/low-price-response
    states for next-day range expansion, C16 change, and event-surface lift.

41. `omega_market_integrated_information_phi`: the market may fail models when
    information channels become too causally integrated.
    Smallest honest test: estimate a cheap causal-density proxy among RL matrix
    scores, C16, PhoBERT features, breadth, and tradability flags; test whether
    high integration predicts model error, activation failure, or drawdown.

42. `omega_parasitic_ticker_mimicry`: low-quality tickers may mimic blue-chip
    intraday DNA to attract liquidity before draining it.
    Smallest honest test: build 1H pattern embeddings, find high-similarity
    pairs with low sector/fundamental overlap, and test whether mimic tickers
    show pump-fade, suspension, or tradability deterioration. Requires careful
    survivorship controls.

43. `omega_dividend_event_horizon`: high-yield dividend events may create a
    pre-ex-date time dilation and post-ex-date information loss.
    Smallest honest test: around dividend events, measure pre-event volume/news
    acceleration, ex-date gap entropy, and recovery half-life; test whether KL
    news surprise or yield-implied temperature predicts recovery better than
    simple dividend-yield controls.

44. `omega_margin_call_superposition`: prop-desk activity may act as a
    measurement spike that collapses sideways markets into direction.
    Smallest honest test: in low-volatility drift regimes, test whether
    proprietary-trading buy/sell spikes precede volatility expansion or
    directional resolution after controlling for index return, C16, and news.

45. `omega_akashic_volume_cymatics`: volume-per-second harmonics may be a
    stress test for matching-engine rhythm claims.
    Smallest honest test: convert 1H volume/count proxies into frequency-like
    bins, compare 432/440-style harmonic buckets against random harmonic
    controls, and kill unless effects survive sector, liquidity, and calendar
    controls. Very low prior.

46. `omega_ouroboros_model_feedback`: published recommendation artifacts may
    feed back into the market if external actors track similar signals.
    Smallest honest test: compare recommendation-candidate timestamps against
    next-day/next-hour volume, news, and return residuals; require a locked
    forward-only audit because historical artifacts may not represent what was
    visible at the time.

47. `omega_vnd_usd_entanglement_entropy`: DXY/VND shocks may alter VN30 state
    faster than local news channels reflect.
    Smallest honest test: compute lead-lag and transfer-entropy proxies between
    DXY/VND/global proxies and VN30/C16 states, then test whether apparent
    nonlocal moves remain after timestamp, holiday, and global-market controls.

48. `omega_ghost_ticker_survivorship_shadow`: delisted or missing tickers may
    leave survivorship-bias shadows in sector signals.
    Smallest honest test: reconstruct historical universes where possible,
    include dead/missing tickers as inactive or failure states, and test whether
    sector breadth/C16 conclusions change. This is a data-quality audit before
    it is an alpha hypothesis.

49. `omega_gaia_market_homeostasis`: VNINDEX may self-regulate around valuation
    and liquidity temperature; sectors with low heat capacity fail to absorb
    macro shocks.
    Smallest honest test: estimate market temperature from valuation proxies,
    liquidity, volatility, and breadth; estimate sector heat capacity from how
    much volume is needed to move price; test overheating/cooling states against
    reversal and drawdown outcomes.

50. `omega_simulation_escape_outflow`: unexplained liquidity disappearance may
    indicate capital leaving observable VN equity channels rather than rotating
    inside them.
    Smallest honest test: reconcile VN30 value-traded changes against foreign
    flow, proprietary trading, sector rotation, and macro/rate proxies; test
    residual outflow spikes for future drawdown or tradability failure. This is
    a residual-accounting check, not evidence of literal hidden actors.

## Geometry Refinements Worth Testing

Use these `X` labels as hypothesis labels only; do not treat them as activated
experiment IDs. Each test should be killed quickly if it cannot beat C16 or
Triple Storm controls.

- `X56_poincare_disk_liquidity_warp`: in a Poincare disk view, the 52-week high
  is the rim and distance expands nonlinearly near it.
  Smallest honest test: map price location into hyperbolic radius over the
  52-week range; test whether C16 IC spikes only in the outer 10% rim during
  down-market days, with C16 down-market as the control.

- `X57_voronoi_cell_sentiment_exhaustion`: sector leaders may own shrinking
  dominance cells before a topological sector reversal.
  Smallest honest test: represent liquid tickers by sector-relative return and
  C16 rank, approximate Voronoi cell areas, and test whether shrinking top-3
  sector-leader area plus high C16 predicts sector reversal; golden-ratio
  thresholds must be predeclared, not tuned.

- `X58_projective_horizon_signal`: price trend and C16 trend may meet at a
  projective vanishing point; shifting the vanishing point from future to past
  marks divergence.
  Smallest honest test: estimate 3-5 day price and C16 trend lines, compute the
  intersection time, and test future-to-past flips against Triple Storm entry
  states and C16 divergence controls.

- `X59_toroidal_liquidity_flow`: liquidity may wrap from large caps into
  smaller names instead of leaving the market.
  Smallest honest test: track large-cap C16 decay, small-cap volume
  acceleration, and cross-size flow curvature; test whether a predeclared
  poloidal-velocity threshold predicts global mean reversion.

- `X60_fractal_dimension_gap_fill`: institutional lamination may appear when
  intraday price paths become nearly one-dimensional.
  Smallest honest test: use available 1H CafeF adjusted bars to estimate a
  rough fractal dimension or path efficiency; test whether C16/Triple Storm IC
  is stronger when dimension is below `1.15`. Original 1-minute version is
  blocked until true minute bars exist.

## Immediate Next Actions

- Next branch: run one fixed portfolio/consumer integration audit for
  `h364_official_sentiment_x_earnings_guidance`; do not fit on `2026+`.
- If the fixed H364 consumer audit fails, keep H364 as offline local-news
  evidence and continue with broader `news_flow_disagreement` using H381/H364
  as anchors.
- Do not retune the live sticky branch off the H364 standalone result.

## Do Not Reopen Unless

- Do not retune timing rules on `2026+`; 2026 remains monitor/forward context
  unless the user explicitly authorizes that branch.
- Do not tune more C16 macro/gap/streak/extreme/sector-relative/persistence
  filters; those mechanisms are already failed.
- Do not continue standalone foreign-flow windows, foreign-support-on-C5
  variants, proprietary-flow rank/conflict variants, or sector-pressure
  variants unless a materially different data source, target, or market
  contract exists.
- Do not tune more event-v2 overlays, entry-label variants, payoff-shape
  filters, or sparse-clock variants unless the local Ollama event-family data
  changes the event representation or a downstream consumer contract changes.
- Do not tune more dividend or legal-holiday sparse-clock portfolio bonuses
  under the current top-5 executable selector.
- Do not continue linear smart-exit feature-set tweaks unless richer post-entry
  state/data or a materially different model contract appears.

## Pointers

- Detailed session traces: `notes/session_NN_log.md`
- Signal registry: [signal_library.md](./signal_library.md)
- Data/source inventory: [data_sources.md](./data_sources.md)
- Local BERT roadmap: [local_bert_roadmap.md](./local_bert_roadmap.md)
- Ollama probe log: [ollama_model_probe_log.md](./ollama_model_probe_log.md)
- Timing acquisition plan:
  [timing_data_acquisition_plan.md](./timing_data_acquisition_plan.md)
- Timing source scorecard:
  [timing_data_source_scorecard.csv](./timing_data_source_scorecard.csv)

## Working Rules

- For any material experiment, save a compact result summary and update the
  note stack.
- Use compact files for cheap context recovery before opening long session
  logs or findings chunks.
- Close out every material pass with this checklist:
  - session log updated
  - `sessions_compact.md` prepended with a source-linked entry
  - `live_state.md` updated only if current state, constraints, or immediate
    actions changed, with `Last verified` refreshed when checked
  - durable findings or dead ends promoted when warranted
  - `findings_compact.md` or `deadends_compact.md` updated only when durable
    memory changed, with source anchors included
- Keep this file focused on current state and immediate action. If a detail is
  not needed to decide the next pass, move it to a source note or compact view.
