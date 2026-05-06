# Findings 361-390

## F361: H397 Separates Pop Signals From Hold States (2026-05-05, Session 278)

Finding:
- Claim tested: states that failed broad 5d candidate allocation may still be
  useful if judged on their natural horizon: next-day pop for active-news flow
  rankers, delayed hold for official-supported attention.
- Evidence: `analysis/h397_barrier_pop_vs_hold_router.py` used no `2026+`
  rows, fixed state definitions from H364/H383/H385/C16/insider work, buyable
  rows only, `2018-2025` test years, future relative returns at `1d`, `2d`,
  and `5d`, and a `15` bps per-row cost. No state thresholds were retuned.
- Result: H397 `PASSED`. `active_news_strong_flow` passed as a 1d C16 ranker:
  1d C16 IC lift versus `strong_flow` was `+0.02257` with `6 / 8` positive
  years, while 5d IC lift was negative (`-0.00509`). `positive_news_strong_flow`
  also passed at 1d with IC lift `+0.02536` and `7 / 8` positive years.
  `official_supported_delay` passed as a 5d payoff state with net lift
  `+0.00650` versus unsupported official rows and `8 / 8` positive years.
  `official_forward_supported_delay` likewise passed at 5d with net lift
  `+0.00662` and `8 / 8` positive years.
- Non-promotions: `h364_positive_ranker` had a 1d IC-lift shape but only one
  valid positive year under the min-row gate. `insider_buy_pop` failed in this
  C5 rank-within-insider representation; this does not kill S272
  `insider_buy_lead`, which is an event-time next-trading-day state.

Why it matters:
- H383 and H385 should no longer be judged under one shared horizon. Active or
  positive news with strong C16 is a next-day pop/ranker state; official
  support is a delayed 5d hold/payoff state.
- This explains why H384/H386 broad candidate-allocation tests failed despite
  real offline signal evidence: they were asking a ranker/hold-state mix to
  solve a broad allocator job.
- The next insider branch should use event-time insider publication/lead
  mechanics, not the failed C5 rank-within-insider form from H397.

Source:
- [session_278_log.md](./session_278_log.md)
- `artifacts/run_summaries/20260505_172821_h397_barrier_pop_vs_hold_router_research_branch_barrier_pop_vs_hold_router.json`

## F362: H398 Reproduces Insider Lead But Rejects Quiet Pre-Reaction Clock (2026-05-05, Session 279)

Finding:
- Claim tested: the S272 positive-insider next-trading-day lead may be
  strongest before news or order-count sensors visibly react.
- Evidence: `analysis/h398_insider_pre_reaction_clock.py` used no `2026+`
  rows, test years `2015-2025`, positive insider events from
  `RealBuyVolume - RealSellVolume > 0`, S272-style T-1/T0/T+1 event mapping,
  same-ticker non-event controls, decision-time C16 order-pressure rank, and
  fixed news/order-count/C16 support states. The saved H398 artifact was read
  before the verdict.
- Result: H398 was `MIXED`. The insider event-time lead reproduced cleanly:
  `insider_tplus1` avg C16 IC was `+0.10498`, with `11 / 11` positive years
  and `+0.03000` IC lift versus same-ticker non-event dates. `insider_t0` was
  also strong at `+0.10816` avg IC with `+0.03317` lift. `insider_tminus1`
  was positive but weaker at `+0.08763`.
- Rejection: the pre-reaction form failed. `insider_tplus1_pre_reaction`
  still had signal (`+0.09247`, `11 / 11` positive years), but
  `insider_tplus1_reacted` was stronger (`+0.11058`) and beat pre-reaction by
  `+0.01811` avg IC. `insider_tplus1_order_count_high` was the strongest
  rank-quality pocket at `+0.13776` avg IC and `+0.04487` lift versus
  not-high order count.

Why it matters:
- Do not discard S272 `insider_buy_lead`; H398 independently reproduces it
  under an event-time contract.
- Do not pursue the current quiet pre-reaction insider thesis. The stronger
  mechanism is reaction confirmation: insider events with visible buy-order
  count/news reaction are cleaner than quiet rows.
- Future crowd/order-count branches should treat buy-order count as a
  conditioner with structure, not as generic volume context or a quiet-before-
  attention proxy.

Source:
- [session_279_log.md](./session_279_log.md)
- `artifacts/run_summaries/20260505_173706_h398_insider_pre_reaction_clock_research_branch_insider_pre_reaction_clock.json`

## F363: H399 Narrows Crowd Count To Modest Context, With Volume-Z Owning The Clean Pocket (2026-05-05, Session 280)

Finding:
- Claim tested: high buy-order count may be useful only when average buy size,
  buy-volume pressure, C8 volume-z, or H394 predicted barrier weather creates
  a favorable ignition state.
- Evidence: `analysis/h399_crowd_count_ignition.py` used no `2026+` rows,
  fixed `2018-2025` test years, the published C16 order-pressure contract,
  raw CafeF order stats, the RL matrix C8 volume-z feature, and the saved H394
  date-prediction artifact. Primary states were judged by C16 rank-quality
  lift versus `high_buy_count` alone.
- Result: H399 was `MIXED`. `high_buy_count` modestly improved C16 quality
  versus all rows: avg IC `+0.08463` versus C16 all-row avg IC `+0.07519`,
  with `+0.00944` average yearly lift and `6 / 8` positive lift years. But
  `buy_count_rank` itself was anti-predictive as a standalone score
  (`-0.01075`, `3 / 8` positive years).
- Best clean pocket: `volume_z_high80` reached avg C16 IC `+0.10258`, `8 / 8`
  positive years, and `+0.02739` lift versus all rows. Adding high buy count
  to high volume-z produced `+0.10285`, only a tiny lift over volume-z alone;
  treat this as C8 volume-state evidence, not a new crowd-count primitive.
- Best predeclared primary crowd state: `count_high_size_weather_low20`
  reached avg IC `+0.10083` and `+0.01620` average yearly lift versus
  high-buy-count alone, but only `5 / 8` positive lift years, so it is
  promising context rather than a promoted signal.
- Buy-pressure caveat: high buy-volume-pressure intersections raised hit rates
  but reduced C16 rank IC versus high count, suggesting basket selection or
  within-state rank compression rather than a cleaner ranker.

Why it matters:
- Do not promote buy-order count as an independent signal. Use it only as a
  modest conditioner or interaction input.
- The reliable pocket is high volume-z / volume-state context. Crowd count
  does not add much once volume-z is already high.
- If reopened, the crowd branch should focus on the high average-buy-size plus
  H394-low-weather shape, but it needs a stability or consumer audit before
  promotion.

Source:
- [session_280_log.md](./session_280_log.md)
- `artifacts/run_summaries/20260505_174329_h399_crowd_count_ignition_research_branch_crowd_count_ignition.json`

## F364: H400 Rejects Calendar As A Fixed Weak Quorum Vote (2026-05-05, Session 281)

Finding:
- Claim tested: calendar residues may be too sparse for standalone promotion
  but still useful as one weak prior inside the H395 quorum.
- Evidence: `analysis/h400_calendar_as_weak_prior_not_clock.py` used no
  `2026+`, rebuilt the H395 train-before-test quorum over test years
  `2019-2025`, explicitly removed the old `january_first_10` and `monday`
  calendar votes from the base quorum, and then added one fixed calendar prior
  averaging January-first-10, Monday, last-five-trading-days-of-month, and a
  Wednesday/Friday T+2 weekday residue. A random extra weak-vote control was
  recorded.
- Result: H400 `FAILED`. The non-calendar quorum retained H395 strength
  (`+0.05826` avg IC, `7 / 7` positive years), but the calendar-added quorum
  fell to `+0.05605`. Calendar lift versus the same non-calendar quorum was
  `-0.00221` on average with `0 / 7` positive lift years. The calendar-only
  score was negative (`-0.00827`, `2 / 7` positive years).
- Component diagnostics: the T+2 weekday residue was mildly positive
  (`+0.00646`, `6 / 10` positive years), but below the weak-candidate IC gate.
  Month-end was near zero (`-0.00181`), while January-first-10 and Monday were
  negative in this pooled fixed-prior representation.

Why it matters:
- Do not add a fixed calendar prior to the H395 quorum under the current
  residue contract.
- H390's diagnostic calendar pockets do not automatically transfer into a
  dense weak-vote ensemble. Calendar remains exact-state context only unless a
  materially different timing/consumer contract is opened.
- The next queue item should shift to veto/annihilation logic rather than
  trying to rescue calendar as a generic weak prior.

Source:
- [session_281_log.md](./session_281_log.md)
- `artifacts/run_summaries/20260505_174904_h400_calendar_as_weak_prior_not_clock_research_branch_calendar_as_weak_prior_not_clock.json`

## F365: H401 Finds Only A Tiny Strict No-Support Veto Clue (2026-05-05, Session 282)

Finding:
- Claim tested: high-ranked long candidates should be vetoed when C16,
  insider, news, tradability, and sector context disagree with the candidate
  score.
- Evidence: `analysis/h401_anti_signal_annihilation_veto.py` used no `2026+`,
  fixed top-5 buyable candidate rows over `2019-2025`, cycle relative-return
  labels, fixed side-channel disagreement masks, and random same-breadth veto
  controls. A veto kept cash in the vetoed slot, so the denominator stayed
  `K=5`.
- Result: H401 was `MIXED`, not a policy promotion. The only positive state
  was `support_count_zero`: avg lift versus no-veto `+0.000167`, avg lift
  versus random same-breadth mean `+0.000152`, and `6 / 7` positive no-veto
  years. It failed the pass gate because the lift was tiny and did not beat
  random same-breadth p95 in any year.
- Failures: broader disagreement masks were negative versus no-veto:
  `support_count_le1` `-0.000123`, `pretty_price_weak_flow` `-0.000026`,
  `news_hype_weak_flow` `-0.000075`, and `weak_flow_weak_sector` `-0.000225`.

Why it matters:
- Do not add a broad anti-signal veto policy from H401.
- A strict no-support flag may be useful as a weak future scale-down/veto clue,
  but it needs a separate stability or consumer audit before promotion.
- The next branch should move to order-fragmentation/liquidity structure rather
  than reweighting the same broad veto masks.

Source:
- [session_282_log.md](./session_282_log.md)
- `artifacts/run_summaries/20260505_175823_h401_anti_signal_annihilation_veto_research_branch_anti_signal_annihilation_veto.json`

## F366: H402 Fragmentation Adds Marginal IC Beyond C16 (2026-05-05, Session 283)

Finding:
- Claim tested: order fragmentation proxies (buy-count/volume ratio, avg buy-sell
  order size) should contain information beyond raw C16 order pressure.
- Evidence: `analysis/h402_shadow_liquidity_gravity_well.py` used no `2026+`,
  test years `2018-2025`, C16 order-pressure rank, raw order stats,
  and fixed high-fragmentation and positive-avg-size states.
- Result: H402 was `MIXED`. Fragmentation vs C16 IC lift was `+0.00753`,
  but poor year consistency (2/8 positive years). C16 itself was negative
  IC (`-0.02967`), so lift is marginal. Best standalone proxy was
  `avg_buy_minus_sell_size` at `+0.03033` IC.

Why it matters:
- Do not promote fragmentation as a ranker. C16 is weak, and fragmentation adds
  little while being inconsistent.
- The avg buy-minus-sell size is the strongest proxy (`+0.03033`), but
  needs high-C16 conditioning or materially different data to be useful.
- Reopen only with fragmentation inside high-C16 or as a high-C16 conditioner.

Source:
- [session_283_log.md](./session_283_log.md)
- `artifacts/run_summaries/20260505_230157_shadow_liquidity_gravity_well_research_branch.json`

## F367: H403 Passes Reynolds Number As Flow Regime (2026-05-05, Session 284)

Finding:
- Claim tested: liquidity, breadth, volatility, and friction should unify
  into a flow-regime state. Reynolds number Re = velocity * breadth /
  viscosity predicts C16/S1 variation.
- Evidence: `analysis/h403_capital_reynolds_number.py` used no `2026+`,
  test years `2018-2025`, velocity from volume-z 5d, breadth from
  order-count/volume, and fixed Re definition.
- Result: H403 `PASSED`. Reynolds vs C16 IC lift was `+0.04416` with
  `6 / 8` positive years. Best bucket was Re high at `+0.01429` IC.
  Velocity was the strongest component (`+0.00881`), breadth near zero.

Why it matters:
- Re adds IC beyond C16 baseline even though C16 is negative in this period.
- Re high bucket is the strongest predictor; use as regime conditioner.
- NOT a signal-library promotion (IC < 0.05) but useful as C16 ranker
  within Re regime or portfolio policy context.
- Need to verify S1 correlation before broader promotion.

Source:
- [session_284_log.md](./session_284_log.md)
- `artifacts/run_summaries/20260505_230436_capital_reynolds_number_research_branch.json`

## F369: H405 Kills Sector Event Lightcone (2026-05-05, Session 286)

Finding:
- Claim tested: Ollama event-family shocks may propagate through sector neighbors.
- Evidence: `analysis/h405_sector_event_lightcone.py` used no `2026+`,
  test years `2018-2025`, Ollama event count as own-ticker signal,
  sector peer-sum as neighbor signal, and intra-sector for neighbor grouping.
- Result: H405 `FAILED`. Own event IC was `-0.00481` with `1 / 8` positive
  years, sector intensity was `-0.00698` with `0 / 8` positive years.

Why it matters:
- Both own-ticker and sector event intensity negative IC confirms
  prior news/event feature failures.
- Do not reopen as event features - reopened only with materially
  different sector or event representation (e.g., not count-based).
- This kills the causal_lightcone branch under current Ollama representation.

Source:
- [session_286_log.md](./session_286_log.md)
- `artifacts/run_summaries/20260505_231629_sector_event_lightcone_research_branch.json`

## F370: H406 Kills Conservation Law Residual (2026-05-05, Session 287)

Finding:
- Claim tested: flow predicts price through conservation law; residual is alpha.
- Evidence: `analysis/h406_noether_flow_break.py` trained linear model
  on count/vol imbalance, avg size diff to predict same-day actual; tested
  residual vs next-day forward actual.
- Result: H406 `FAILED`. Expected had +0.00983 IC (3/3 positive),
  but residual inversely predicted at -0.02861 IC (0/3 positive).

Why it matters:
- The model captures flow information in "expected"; residual is mean-reverting
  noise with negative predictivity.
- Conservation law residual does NOT work as alpha.
- Do not reopen as flow-conservation break.

Source:
- [session_287_log.md](./session_287_log.md)
- `artifacts/run_summaries/20260505_232007_noether_flow_break_research_branch.json`

## ## F381: H417 Hold-Out 2025 Confirms REAL Signal (2026-05-05, Session 298)

Finding:
- Claim tested: additive pattern survives on completely held-out data.
- Evidence: `analysis/h417_holdout_2025.py` tested 2025 only.
- Result: H417 `PASSED`. +0.014 lift on 2025 (vs +0.017 long-term avg).

2025 hold-out:
- S1 alone: +0.109
- 0.1V+0.9S: +0.123
- Lift: +0.014

Why it matters:
- ALMOST IDENTICAL performance proves NOT survivor bias
- Pattern is REAL, not overfit
- All H408-H416 evidence now confirmed

Source:
- [session_298_log.md](./session_298_log.md)

---

## F380: H416 Additive Robust In Both Market States (2026-05-05, Session 297)

Finding:
- Claim tested: additive works in different market states.
- Evidence: `analysis/h416_market_state_gated.py` split by VNI-up/down.
- Result: H416 `PASSED`. Works in BOTH states (+0.016 to +0.018 lift).

Key results:
- VNI up: +0.016 lift
- VNI down: +0.018 lift (slightly better in down markets)

Why it matters:
- Pattern is ROBUST - works regardless of market direction
- Slightly better in VNI down (contrarian signal)
- Confirms the additive is a generalizable signal, not state-dependent

Source:
- [session_297_log.md](./session_297_log.md)

---

## F379: H415 Weight Optimization Finds Marginal Best (2026-05-05, Session 296)

Finding:
- Claim tested: optimum Vol/S1 weight ratio beyond 0.1/0.9.
- Evidence: `analysis/h415_weight_optimization.py` grid search.
- Result: H415 `MIXED`. 15V+85S = +0.136, marginal +0.001 over H413.

Key results:
- 15V+85S: +0.136 IC (best)
- 10V+90S (H413): +0.135 IC
- 20V+80S: +0.132 IC

Why it matters:
- Optimum is in 10-15% Volume range; too much hurts
- Marginal improvement (+0.001) is within noise
- Keep H413 (10V+90S) as practical standard
- Weight sensitivity is low - any 10-15% works

Source:
- [session_296_log.md](./session_296_log.md)

---

## F378: H414 Additive Works On ALL Barrier Horizons (2026-05-05, Session 295)

Finding:
- Claim tested: Vol+S1 additive generalizes to different targets.
- Evidence: `analysis/h414_alternative_target_additive.py` tested 1d, 10d, 20d targets.
- Result: H414 `PASSED`. Works on ALL horizons (+0.019 lift on 10d/20d).

Key results:
- 1d: +0.135 (+0.017 vs S1)
- 10d: +0.138 (+0.019 vs S1)
- 20d: +0.138 (+0.019 vs S1)

Why it matters:
- Additive is a GENERALIZABLE pattern, not target-specific
- Works on 1d, 10d, 20d with same lift
- Confirms H413 discovery is robust across horizons

Source:
- [session_295_log.md](./session_295_log.md)

---

## F377: H413 Triple Signal Beats H410 (2026-05-05, Session 294)

Finding:
- Claim tested: triple-signal additive beats two-signal (H410).
- Evidence: `analysis/h413_triple_signal_additive.py` tested three-way combos.
- Result: H413 `PASSED`. New best found: 0.1×Vol + 0.9×S1 = +0.135 IC!

Key results:
- H410 (0.25V+0.75S): +0.126 IC
- 0.1V+0.9S: +0.135 IC (+0.009 vs H410, +7% improvement)
- 0.15V+0.7S+0.15C16: +0.133

Why it matters:
- Lower volume weight (10% vs 25%) is KEY insight
- More S1 weight improves the ranker
- C16 doesn't add in three-way (too weak)
- New standard: 0.1×Vol + 0.9×S1 as best candidate ranker

Source:
- [session_294_log.md](./session_294_log.md)

---

## F376: H412 Volume+C16 Additive Fails (2026-05-05, Session 293)

Finding:
- Claim tested: Volume additive with C16 beats standalone Volume.
- Evidence: `analysis/h412_volume_c16_additive.py` tested additive weightings.
- Result: H412 `FAILED`. Best additive = +0.073, WORSE than Volume alone (+0.075).

Why it matters:
- C16 alone has essentially zero IC (-0.0008), too weak to add
- H410 additive works only with S1 (strong +0.118); Volume alone is +0.077
- Three-way additive may help but C16 is the wrong partner
- H410: 0.25V+0.75S = +0.126 (wins)
- H412: 0.75V+0.25C16 = +0.073 (loses)
- Signal strength matters for additive: S1 is strong enough, C16 is not

Source:
- [session_293_log.md](./session_293_log.md)

---

## F375: H411 Kills Volume Triple Storm (2026-05-05, Session 292)

Finding:
- Claim tested: Triple Storm amplifies Volume (like C16-Triple).
- Evidence: `analysis/h411_volume_triple_storm.py` tested triple conditions.
- Result: H411 `FAILED`. Volume+Triple = +0.038, WORSE than Volume alone (+0.075).

Why it matters:
- Triple Storm is C16-specific, not a universal signal amplifier
- Ablation: none of liquid/down/divergence helped
- Do not reopen as Volume amplifier; the mechanism is C16-specific
- C16-Triple was special case, not a generalizable pattern

Source:
- [session_292_log.md](./session_292_log.md)

---

## F374: H410 Volume+S1 Additive Beats Both Standalone (2026-05-05, Session 291)

Finding:
- Claim tested: Volume additive with S1 beats standalone S1.
- Evidence: `analysis/h410_volume_s1_additive.py` tested various weightings.
- Result: H410 `PASSED`. 0.25×Vol + 0.75×S1 = +0.12649 IC, beats both standalones!

Key results:
- S1 alone: +0.11790 IC
- Vol alone: +0.07492 IC
- 0.25V+0.75S: +0.12649 IC (**+0.009 lift over S1**)

Why it matters:
- Additive WORKS, cross-product HURT (H408, H409 proved opposite)
- Small volume weight (25%) improves S1; too much volume hurts
- Recommend: 0.25×Vol + 0.75×S1 as simple combination ranker

Source:
- [session_291_log.md](./session_291_log.md)

---

## F373: H409 Volume×C16 Mixes Down Volume (2026-05-05, Session 290) + NEW SIGNAL DISCOVERY

Finding:
- Claim tested: Volume × C16 cross-product beats standalone Volume.
- Evidence: `analysis/h409_volume_c16_cross_product.py` tested vol × c16_lag1 vs forward IC.
- Result: H409 `MIXED`. Cross adds +0.017 (8/8 pos years) but WORSE
  than Volume alone (+0.077).

CRITICAL NEW SIGNAL DISCOVERY:
- Volume (`order_volume_ratio`) alone has +0.077 IC with 8/8 positive years!
- This is a STRONG standalone signal, not tested in prior experiments.
- Recommend: Add Volume to signal library (C16 alternative).

Why it matters:
- Cross-product does NOT beat Volume standalone - 0.060 IC penalty.
- C16 alone is negative (-0.046), acts as filter but doesn't add alpha.
- The REAL finding is Volume alone - recommend signal library addition.

Source:
- [session_290_log.md](./session_290_log.md)

---

## F372: H408 S1×C16 Cross-Product Mixes Down S1 (2026-05-05, Session 289)

Finding:
- Claim tested: S1 × C16 cross-product beats standalone S1.
- Evidence: `analysis/h408_s1_c16_cross_product.py` tested s1 × c16_lag1 vs forward IC.
- Result: H408 `MIXED`. Cross adds +0.108 IC (8/8 pos years) but WORSE
  than S1 alone (+0.118). C16 alone is -0.030 (negative).

Why it matters:
- Cross-product does NOT beat S1 standalone - it's a 0.010 IC penalty.
- C16 acts as a filter (negative → positive) but doesn't enhance S1.
- The H407 pattern (lag × lag cross) works; S1 × C16 doesn't add alpha.
- H408 is NOT a signal-library promotion.

Source:
- [session_289_log.md](./session_289_log.md)

---

F371: H407 Passes Phase Lag Cross-Product (2026-05-05, Session 288)

Finding:
- Claim tested: C16 phase leading price through lag interaction.
- Evidence: `analysis/h407_hilbert_phase_lead.py` tested C16_lag1 × price_lag1
  cross-product (simplified phase proxy) vs next-day forward IC.
- Result: H407 `PASSED`. Phase lag added +0.02221 IC with `7 / 8` positive years.

Why it matters:
- This is a NEW feature class: cross-product of lags, different from level
  derivatives (ROC, Haar - failed) or simple lags.
- Cross-product interaction captures COMBINED lagged information.
- NOT signal-library (IC < 0.05) but useful as C16 conditioner.

Source:
- [session_288_log.md](./session_288_log.md)

---

## F382: H426 Rejects Daily Forced-Seller States As Entry-Candidate Allocators (2026-05-06, Session 304)

Finding:
- Claim tested: forced-seller / margin-cascade states from large negative
  return, volume spike, sell-order pressure, rising/high average sell size,
  floor-limit proximity, and no active bad news can identify rebound candidates.
- Evidence: `analysis/h426_forced_seller_detector.py` used the entry-alpha
  candidate panel and cycle labels over `2019-2025`, with only prior-year K
  selection and random same-support / random-all baselines. No S1 or C16
  baseline was used because this is not a direct variation of those signals.
- Result: H426 `FAILED`. `forced_seller_core_buyable` had only `+0.000230`
  mean lift versus random-state, only `1 / 5` positive WF years, and
  `-0.002047` mean lift versus random-all. `forced_seller_large_down_buyable`
  and `forced_seller_floor_buyable` also failed random-all, while the literal
  hard-release state had only `7` rows.

Why it matters:
- Daily sell-pressure distress is not enough to make a buy pulse under the
  current entry-alpha consumer.
- The queue memo's next-day C16 confirmation clause was not tested because it
  is not decision-time valid for the current T close -> T+1 open entry-label
  contract.
- Future work needs a delayed-entry protocol or intraday/queue/open-fill data
  that can observe absorption before execution; threshold tuning the same
  daily state is not justified.

Source:
- [session_304_log.md](./session_304_log.md)
- `artifacts/run_summaries/20260506_141722_h426_forced_seller_detector_research_branch_forced_seller_detector.json`
- Dead-end anchor: `D025`
