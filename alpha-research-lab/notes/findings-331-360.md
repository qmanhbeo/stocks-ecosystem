# Findings 331-360

## F339: H379 Dynamic Candidate Thermodynamics Passes As Offline Policy Evidence (2026-05-04, Session 255)

Finding:
- Claim: the candidate panel contains enough pre-decision temperature
  information to choose portfolio breadth (`cash/top1/top2/top5/top10`) better
  than random K policies.
- Evidence: `analysis/h379_dynamic_candidate_thermodynamics.py` used TRUE
  walk-forward validation with train years strictly before each test year,
  `2019-2025` data only, and no S1/C16 baseline comparison. The primary
  benchmark was `2,000` random invested action policies over
  `top1/top2/top5/top10`.
- Result: mean policy absolute cycle return `+0.00665` versus random invested
  mean `+0.00508`, lift `+0.00157`; `4 / 5` walk-forward years beat the random
  invested mean; 2025 confirmation lift was `+0.00108`.
- Weakness: only `1 / 5` years beat the random invested p95, 2021 failed, and
  2025 was only `69.2` percentile versus random invested policies.

Why it matters:
- This reopens dynamic breadth only as offline policy evidence, not a live
  branch change. The signal is about when to concentrate/diversify/cash, not
  a new ticker-level alpha.
- The durable clue is `candidate_count`: it was selected in 2023, 2024, and
  2025, suggesting candidate-universe temperature may be a better next test
  than a broad multi-feature router.
- Next honest step is a narrower full-portfolio `candidate_count` K/cash router
  compared to random K/cash policies, with 2026 still excluded from fitting.

Source:
- [session_255_log.md](./session_255_log.md)
- `artifacts/run_summaries/20260504_124306_h379_dynamic_candidate_thermodynamics_research_branch_dynamic_candidate_thermodynamics.json`

## F340: H380 Candidate Count Router Strengthens The Portfolio-Policy Branch (2026-05-04, Session 257)

Finding:
- Claim: candidate-count regimes alone can route portfolio breadth
  (`cash/top1/top2/top5/top10`) better than random K/cash policies.
- Evidence: `analysis/h380_candidate_count_policy_router.py` used TRUE
  walk-forward validation with train years strictly before each test year,
  `2019-2025` data only, no `2026+`, and no S1/C16 baseline comparison. The
  only candidate inputs were raw `candidate_count`, 1-day and 5-day
  candidate-count changes, and distance from the 20-day trailing mean.
- Result: mean policy absolute cycle return `+0.00796` versus random K/cash mean
  `+0.00407`, lift `+0.00389`; mean lift versus random invested policies was
  `+0.00281`; `4 / 5` years beat both random K/cash and random invested means.
  The 2025 confirmation lift was `+0.00472` versus random K/cash and `+0.00381`
  versus random invested.
- Weakness: 2021 failed both random means, so this is not a universal live
  policy rule.

Why it matters:
- H380 addresses the H379 next-step directly and confirms that the durable
  policy clue was raw `candidate_count`: every fold selected raw count, not
  delta or rolling-mean transforms.
- Promote PP5 only as offline portfolio-policy evidence. Do not change the live
  sticky branch and do not add this to `signal_library.md` because it is not a
  ticker-day alpha signal.

Source:
- [session_257_log.md](./session_257_log.md)
- `artifacts/run_summaries/20260504_125947_h380_candidate_count_policy_router_research_branch_candidate_count_policy_router.json`

## F341: H381 Inverts The Silent-Order-Pressure Thesis (2026-05-04, Session 258)

Finding:
- Claim tested: C16 order pressure should be strongest when PhoBERT article
  counts show no public narrative.
- Evidence: `analysis/h381_silent_order_pressure.py` used fixed no-news states,
  TRUE walk-forward folds with train years strictly before each test year,
  `2016-2025` data only, no `2026+`, and direct C16 variation benchmarks.
- Result: no-news C16 was weaker, not stronger. `silent_5d` WF IC was `+0.0700`
  versus all-C16 `+0.0752` and active-5d-news C16 `+0.0846`. `silent_1d` WF IC
  was `+0.0720` versus active-1d-news C16 `+0.0890`. Down-market no-news
  controls failed the same way.

Why it matters:
- Kill `silent_order_pressure` under the current own-ticker PhoBERT article-count
  proxy. The result should be reframed as active narrative confirming C16 rather
  than no-news stealth accumulation.
- The next live queue item remains `news_flow_disagreement`, but it should start
  from H381's inversion: active-news plus C16 may be confirmation, while no-news
  C16 is not automatically cleaner.

Source:
- [session_258_log.md](./session_258_log.md)
- [deadends-001-030.md](./deadends-001-030.md) `D001`
- `artifacts/run_summaries/20260504_130641_h381_silent_order_pressure_research_branch_silent_order_pressure.json`

## F342: H364 Combined Local-News Audit Passes After The Ollama Residual Backfill Completes (2026-05-04, Session 259)

Finding:
- Claim: the completed local-news stack can produce a fixed confirmation-aware
  signal stronger than BERT-only source-conditioned sentiment.
- Evidence: Session 259 confirmed the guarded Ollama event-family residual
  backfill complete at `7344 / 7344` checkpoint batches, refreshed the combined
  local-news aggregate overlay, and ran
  `analysis/h364_combined_local_news_audit.py`. The audit used only
  `2016-2025` rows despite the authorized full Ollama input cache, with
  dev years `2016-2022`, validation years `2023-2024`, and confirmation year
  `2025`.
- Result: H364 `PASSED`. The best fixed feature was
  `h364_official_sentiment_x_earnings_guidance`, with avg IC `+0.01766`,
  dev IC `+0.0173`, validation IC `+0.0200`, confirmation 2025 IC `+0.0156`,
  `10 / 10` positive years, S1 corr `-0.0104`, and `103,248` active rows
  (`13.329%` coverage).

Why it matters:
- The month-blocked Ollama residual surface has now produced a real local-news
  candidate. The useful representation is official/regulatory source
  probability times sentiment times Ollama earnings/guidance event-family
  agreement, not pooled sentiment and not BERT-only sentiment.
- This is not a live-branch change. The next honest step is one fixed
  portfolio/consumer integration audit for
  `h364_official_sentiment_x_earnings_guidance`, with no `2026+` fitting.
- Broader `news_flow_disagreement`, official-delay, event-cascade, and
  source-triangle branches should treat this as the new local-news anchor.

Source:
- [session_259_log.md](./session_259_log.md)
- `artifacts/run_summaries/20260504_183132_h364_combined_local_news_audit_research_branch_combined_local_news_audit.json`

## F343: H382 Shows H364 Has Narrow Same-Support Consumer Value But Fails Broad Candidate-Pool Allocation (2026-05-04, Session 260)

Finding:
- Claim: the fixed H364 local-news feature can be consumed inside the candidate
  pool by selecting the highest-H364 buyable active-news candidate better than
  random candidate policies.
- Evidence: `analysis/h382_h364_local_news_consumer_integration.py` used TRUE
  walk-forward validation with train years strictly before each test year,
  `2019-2025` data only, no `2026+`, and only trained the consumer `K` choice
  from `top1/top2/top3/top5`. The primary benchmark was `5,000` random
  same-`K` selections among active buyable H364 candidates; the secondary
  benchmark was `5,000` random same-`K` selections among all buyable candidate
  rows.
- Result: H382 `PASSED` on the primary same-support benchmark. The selected
  policy was always `K=1`; mean policy return was `-0.00026` versus
  random-active `-0.00117`, mean lift `+0.00092`; `4 / 5` walk-forward years
  beat random-active mean, and 2025 confirmation lift was `+0.00296`.
- Caveat: the broad random-all benchmark failed. Random-all mean return was
  `+0.00342`, so mean lift versus random-all was `-0.00367`, and only `1 / 5`
  years beat random-all mean.

Why it matters:
- H364 is useful as a ranker inside its own active official/earnings-guidance
  event-news subset, not as a broad candidate-pool allocator.
- Keep H364 as offline local-news evidence and a feature anchor for
  `news_flow_disagreement`, official-delay, and source-triangle tests.
- Do not promote H364 into a live branch or broad consumer matrix contract from
  H382 alone.

Source:
- [session_260_log.md](./session_260_log.md)
- [deadends-001-030.md](./deadends-001-030.md) `D002`
- `artifacts/run_summaries/20260504_194152_h382_h364_local_news_consumer_integration_research_branch_h364_local_news_consumer_integration.json`

## F344: H383 Confirms Active-News C16 As A Flow/Text Confirmation State (2026-05-04, Session 261)

Finding:
- Claim tested: public text and posted-order pressure interact; disagreement
  states may mark traps, while active-news plus strong C16 may confirm demand.
- Evidence: `analysis/h383_news_flow_disagreement.py` used fixed C16/news
  state definitions, TRUE walk-forward folds with train years strictly before
  each test year, `2016-2025` data only, no `2026+`, and a primary next-day
  close-to-close relative-return target versus VNINDEX. The C16 score was
  `order_volume_ratio_rank`; the secondary diagnostic target was S1 `actual`.
- Result: H383 `PASSED`, but as confirmation rather than disagreement.
  `active_news_strong_flow` cleared the primary gate with WF mean relative IC
  `+0.10293`, S1 IC `+0.06972`, `8 / 8` positive years, 2025 relative IC
  `+0.12163`, and lift `+0.04005` versus the strong-flow baseline. The broader
  `active_news` control had relative IC `+0.11070` versus all-C16 `+0.09404`
  and no-news `+0.08852`. The secondary `positive_news_strong_flow` state was
  also strong with relative IC `+0.10854` and 2025 IC `+0.12854`.
- Failed sub-legs: `bullish_flow_no_news`, `bullish_flow_negative_news`, and
  `positive_news_weak_flow` did not beat their fixed baselines cleanly.

Why it matters:
- This confirms H381's inversion on a stronger payoff target: C16 improves
  when a public own-ticker narrative is active, not when own-ticker news is
  absent.
- Treat the live mechanism as flow/text confirmation, not public-text/order
  disagreement. The next honest step is one fixed consumer audit for
  `active_news_strong_flow` and `positive_news_strong_flow`; do not promote a
  live branch or matrix contract from IC evidence alone.

Source:
- [session_261_log.md](./session_261_log.md)
- `artifacts/run_summaries/20260504_195247_h383_news_flow_disagreement_research_branch_news_flow_disagreement.json`

## F345: H384 Rejects H383 Active-News Strong-Flow As A Candidate-Pool Allocator (2026-05-04, Session 262)

Finding:
- Claim tested: the H383 active/positive-news strong-flow IC edge can be
  consumed inside the buyable candidate pool by selecting the highest-C16
  candidates from those fixed states.
- Evidence: `analysis/h384_news_flow_confirmation_consumer.py` used TRUE
  walk-forward years `2021-2025`, `2019-2025` data only, no `2026+`, fixed
  H383 states, candidate-pool rows with `candidate_pool_rank <= 20`, and only
  trained the consumer `K` choice from prior years. The benchmarks were
  `5,000` random same-`K` selections from the same fixed state and all buyable
  candidate-pool rows.
- Result: H384 `FAILED`. `active_news_strong_flow` had mean policy absolute
  return `+0.00038` versus random-state `+0.00064` and random-all `+0.00375`;
  it beat each random mean in only `2 / 5` years. `positive_news_strong_flow`
  had mean policy `+0.00180` versus random-state `+0.00200` and random-all
  `+0.00371`, also only `2 / 5` years above each random mean. Both states had
  positive 2025 lifts, but failed the mean and consistency gates.

Why it matters:
- H383 remains useful offline IC evidence, but its fixed active/positive-news
  strong-flow states are not broad candidate-pool allocators under the current
  consumer contract.
- Do not promote H383 states into the live branch, shared matrix, or
  recommendation candidate contract from IC evidence alone. Continue with
  `official_attention_delay` or a materially different consumer contract.

Source:
- [session_262_log.md](./session_262_log.md)
- [deadends-001-030.md](./deadends-001-030.md) `D003`
- `artifacts/run_summaries/20260504_195935_h384_news_flow_confirmation_consumer_research_branch_news_flow_confirmation_consumer.json`

## F346: H385 Confirms Official Attention Delay With C16 Or Insider Support (2026-05-04, Session 263)

Finding:
- Claim tested: official/regulatory or forward-looking local-news rows need
  flow or insider confirmation and may pay after a delay, not necessarily on
  the headline day.
- Evidence: `analysis/h385_official_attention_delay.py` used fixed
  official/forward local-news states, C16 support
  (`order_volume_ratio_rank >= 0.80`), positive C5 insider support, TRUE
  walk-forward folds over `2018-2025`, and `2016-2025` data only. The primary
  target was 5d close-to-close excess return versus VNINDEX, with 1d payoff as
  a delay-shape control.
- Result: H385 `PASSED`. `official_supported` had mean 5d payoff `+0.006671`
  and 5d lift `+0.007408` versus `official_no_support`, with `8 / 8` positive
  5d-lift years and 2025 5d lift `+0.005566`. `official_forward_supported`
  had mean 5d payoff `+0.007290` and 5d lift `+0.007657` versus unsupported
  official/forward rows, also with `8 / 8` positive 5d-lift years and 2025
  5d lift `+0.006799`.
- Secondary substates agreed: `official_c16` had 5d lift `+0.008112`, and
  `forward_c16` had 5d lift `+0.007984`, both with `8 / 8` positive 5d-lift
  years.

Why it matters:
- The official-attention-delay branch is real as offline payoff evidence:
  unsupported official/forward rows were weak or negative, while support from
  C16 or insider conviction turned the state positive.
- The effect is delayed; the 5d lift is larger than the 1d lift for both
  primary states.
- Do not promote this into the live branch or a shared consumer contract yet.
  The next honest step is a fixed candidate-pool consumer audit with random
  same-support and random-all benchmarks.

Source:
- [session_263_log.md](./session_263_log.md)
- `artifacts/run_summaries/20260504_200524_h385_official_attention_delay_research_branch_official_attention_delay.json`

## F347: H386 Rejects H385 Official-Delay States As Candidate-Pool Allocators (2026-05-04, Session 264)

Finding:
- Claim tested: the H385 support-confirmed official/forward delayed-payoff
  states can be consumed inside the buyable candidate pool by selecting the
  best candidate-ranked rows from each fixed state.
- Evidence: `analysis/h386_official_delay_consumer_router.py` used TRUE
  walk-forward years `2021-2025`, `2019-2025` data only, no `2026+`, fixed
  H385 states, `candidate_pool_rank <= 20`, and only trained the consumer `K`
  choice from prior years. The deterministic selector used lowest
  `candidate_pool_rank`, with C16 only as a tie-breaker. Benchmarks were
  `5,000` random same-`K` selections from the same fixed state and all buyable
  candidate-pool rows.
- Result: H386 `FAILED`. `official_supported` had mean policy return
  `-0.00171` versus random-state `-0.00136` and random-all `+0.00368`, for
  lifts `-0.00035` and `-0.00540`; it beat random-all in only `1 / 5` years
  and 2025 random-all lift was `-0.00227`. `official_forward_supported` had
  mean policy return `-0.00187` versus random-state `-0.00130` and random-all
  `+0.00368`, for lifts `-0.00057` and `-0.00555`; it also beat random-all in
  only `1 / 5` years and had 2025 random-all lift `-0.00244`.

Why it matters:
- H385 remains useful as offline delayed-payoff evidence, but the current
  candidate-pool consumer contract cannot deploy it.
- Do not promote `official_supported` or `official_forward_supported` into the
  live branch, shared matrix, or recommendation candidate contract from
  H385/H386 alone.
- Reopen only with a materially different consumer contract, such as an
  event-sleeve, delayed holding target, or deterministic basket rule that is
  predeclared and benchmarked against random alternatives.

Source:
- [session_264_log.md](./session_264_log.md)
- [deadends-001-030.md](./deadends-001-030.md) `D004`
- `artifacts/run_summaries/20260504_201315_h386_official_delay_consumer_router_research_branch_official_delay_consumer_router.json`

## F348: H387 Rejects Insider-Down Rescue; Stock-Down High-C16 Is The Stronger Control (2026-05-04, Session 265)

Finding:
- Claim tested: positive C5 insider conviction after visible 1d/3d stock
  weakness becomes a stronger delayed-payoff state when confirmed by high C16.
- Evidence: `analysis/h387_insider_down_rescue.py` used fixed state
  definitions, TRUE walk-forward years `2018-2025`, `2016-2025` data only, no
  `2026+`, 5d close-to-close relative returns versus VNINDEX, and controls
  against ordinary insider rows, insider-plus-C16 rows, and stock-down-plus-C16
  rows.
- Result: H387 `FAILED`. `insider_down_high_c16` had mean 5d payoff
  `+0.008874` and beat ordinary `insider_buy` by `+0.00784`, but failed the
  meaningful controls: lift versus `insider_high_c16` was only `+0.00087` with
  `3 / 6` positive years and 2025 lift `-0.00286`; lift versus
  `stock_down_high_c16` was `-0.00308` with only `1 / 6` positive years and
  2025 lift `-0.00432`. The deeper drawdown variant also failed versus both
  high-C16 controls.

Why it matters:
- Do not open an insider-down rescue overlay under the current state and target.
- The stronger mechanism is high C16 after stock weakness, not the addition of
  insider support to that state.
- Keep H340-style positive C5 plus order-pressure as the preferred C5
  robustness path, and treat stock-down high-C16 as a control to respect in
  future hidden-flow tests.

Source:
- [session_265_log.md](./session_265_log.md)
- [deadends-001-030.md](./deadends-001-030.md) `D005`
- `artifacts/run_summaries/20260504_201913_h387_insider_down_rescue_research_branch_insider_down_rescue.json`

## F349: H388 Rejects Long-Dormancy Fresh Selection Pulse (2026-05-04, Session 266)

Finding:
- Claim tested: a ticker reappearing in the top candidate set after long
  dormancy carries more edge than stale repeats or incumbents.
- Evidence: `analysis/h388_fresh_selection_pulse.py` computed prior top-5 and
  top-10 candidate appearances using only earlier panel dates, tested buyable
  rows with `2019-2025` data only, no `2026+`, and TRUE walk-forward test
  years `2021-2025`. Fixed states separated previous-day incumbents, `2-19`
  trading-day stale repeats, `20+` trading-day fresh reappearances, and
  first-ever appearances.
- Result: H388 `FAILED`. `top5_fresh20` was positive and beat incumbents, but
  it did not beat `top5_stale_repeat`: mean lift was `-0.00016`, and 2025 lift
  was `-0.00269`. `top10_fresh20` also failed stale-repeat control with mean
  lift `-0.00068` and 2025 lift `-0.00098`. First-ever top-5 rows were sparse
  and negative.

Why it matters:
- Do not add a long-dormancy fresh-selection boost under the current
  entry-alpha contract.
- Candidate history may still matter, but the clue is short-repeat reentry
  rather than first return after long dormancy.
- Reopen only with a different policy contract, such as a predeclared
  short-repeat state, rank-transition state, or full portfolio policy benchmark.

Source:
- [session_266_log.md](./session_266_log.md)
- [deadends-001-030.md](./deadends-001-030.md) `D006`
- `artifacts/run_summaries/20260504_202357_h388_fresh_selection_pulse_research_branch_fresh_selection_pulse.json`

## F350: H389 Guarded-Ollama Event Cascade Fails To Reopen Event Timing (2026-05-04, Session 267)

Finding:
- Claim tested: the guarded Ollama event-family residual can revive event
  timing if first/repeat/family-transition states improve on old CafeF
  event-v2 controls.
- Evidence: `analysis/h389_post_ollama_event_cascade.py` used the completed
  guarded-Ollama daily aggregate, fixed first/repeat/transition state
  definitions, TRUE walk-forward years `2018-2025`, `2016-2025` data only, no
  `2026+`, and 5d close-to-close relative returns versus VNINDEX. The canonical
  run patched non-finite future-return handling before judgment.
- Result: H389 `FAILED`. The best cascade state was `event_first20`, with mean
  5d payoff `+0.002375`, but lifts were only `+0.00099` versus generic event,
  `+0.00114` versus repeat event, and `+0.00103` versus no-event rows; all
  missed the `+0.002` gate. `event_family_transition5` had still smaller mean
  lifts (`+0.00023` versus generic event). No event-family pocket cleared the
  MIXED gate.

Why it matters:
- The new guarded-Ollama event-family surface does not rescue the event-timing
  branch under the current target.
- H321 remains the stronger offline event timing clue, and H361 still blocks
  portfolio-level sparse-clock promotion.
- Keep event timing parked unless a materially different event target,
  timestamped source, or downstream consumer contract appears.

Source:
- [session_267_log.md](./session_267_log.md)
- [deadends-001-030.md](./deadends-001-030.md) `D007`
- `artifacts/run_summaries/20260504_203158_h389_post_ollama_event_cascade_research_branch_post_ollama_event_cascade.json`

## F351: H390 Leaves Calendar As Context, Not An Independent Mechanism Overlay (2026-05-04, Session 268)

Finding:
- Claim tested: the old calendar C16 edges are proxies for settlement,
  attention, liquidity, breadth, news volume, buyability, and down-market
  regimes rather than independent magic-date effects.
- Evidence: `analysis/h390_calendar_liquidity_mechanism.py` converted C16 into
  daily Spearman IC versus 1d and 5d relative returns plus S1 `actual`, merged
  candidate-panel date-level controls, and ran TRUE walk-forward residualization
  with no `2026+`. The saved daily panel spans `2019-01-02` through
  `2025-12-31`; test years are `2021-2025`.
- Result: H390 `MIXED`. The exact old `monday_jan_combo` retained 1d residual
  daily-C16-IC lift (`+0.02745`) and positive 2025 confirmation (`+0.08381`),
  but it had only one active date per evaluated year, just `2 / 4` positive
  1d residual-lift years, and negative mean 5d residual lift (`-0.04055`).
  `quarter_start` had negative 1d residual lift (`-0.00177`) despite positive
  5d residual lift (`+0.00866`), and `late_quarter_month` was negative on both
  1d and 5d residual lifts.

Why it matters:
- Calendar remains useful as context and a hypothesis generator, but the old
  exact calendar states should not be promoted as independent timing overlays,
  matrix columns, or recommendation policies under the current target.
- The cleaner clue is broader January/weekday context: diagnostic
  `january_first_10` had 1d residual lift `+0.03067` with `5 / 5` positive
  residual-lift years, but it was not a predeclared primary state and needs a
  separate fixed contract before it can matter.
- Reopen only with a predeclared broader January-window or weekday timing
  contract, a different 5d/execution target, or a downstream consumer that
  compares calendar context against mechanism-matched alternatives.

Source:
- [session_268_log.md](./session_268_log.md)
- [deadends-001-030.md](./deadends-001-030.md) `D008`
- `artifacts/run_summaries/20260504_204043_h390_calendar_liquidity_mechanism_research_branch_calendar_liquidity_mechanism.json`

## F352: H391 Rejects Entry-Panel Tradability Release Pulse (2026-05-04, Session 269)

Finding:
- Claim tested: a high-ranked entry candidate becoming buyable after a prior
  blocked-buy state has a short executable continuation edge.
- Evidence: `analysis/h391_tradability_release_pulse.py` used
  `candidate_panel_daily.parquet` release fields and `entry_labels_cycle5`
  cycle outcomes, fixed top-5/top-10 release states, TRUE walk-forward years
  `2021-2025`, `2019-2025` data only, no `2026+`, and same-year same-rank
  stable-buyable and non-release-buyable matched controls.
- Result: H391 `FAILED`. `top5_release` had mean cycle relative return
  `-0.032254`, hit rate `0.3048`, can-sell rate `0.8675`, and mean lift
  `-0.033668` versus matched stable/non-release controls, with only `1 / 5`
  positive matched-control years and 2025 lift `-0.080106`. `top10_release`
  was similarly negative: mean relative return `-0.027022`, can-sell rate
  `0.8896`, matched-control lift `-0.028365`, `1 / 5` positive years, and
  2025 lift `-0.066302`. Diagnostic `top20_release` also failed.

Why it matters:
- The entry-panel `release_flag` is a real state transition, but under this
  target it marks weak subsequent buys, likely delayed exhaustion after
  limit/blocked-buy pressure rather than continuation.
- Do not add a `wait_release` inclusion boost, live overlay, matrix column, or
  recommendation policy from the current release representation.
- Reopen only with materially different release evidence, such as order-book
  queue/open-fill data, intraday post-release absorption, or a rule that waits
  for re-block risk and next-day sellability to normalize before entry.

Source:
- [session_269_log.md](./session_269_log.md)
- [deadends-001-030.md](./deadends-001-030.md) `D009`
- `artifacts/run_summaries/20260504_204826_h391_tradability_release_pulse_research_branch_tradability_release_pulse.json`

## F353: H392 Parks C16-Insider-News Triangle; Broad Three-Sensor News Pocket Remains A Clue (2026-05-04, Session 270)

Finding:
- Claim tested: insider, order pressure, and local-news source/type agreement
  form a sparse high-conviction state beyond known two-way routes.
- Evidence: `analysis/h392_source_triangle_sparse.py` used fixed sensors for
  high C16, positive C5 insider, official/regulatory or stock-scope PhoBERT
  news, and forward-looking PhoBERT text. It tested `2016-2025` rows only, no
  `2026+`, TRUE walk-forward years `2018-2025`, and 5d relative-return payoff
  plus C16/C5 IC diagnostics.
- Result: H392 `MIXED`. The required core state `c16_insider_any_news` had
  positive mean 5d payoff `+0.003177`, but failed controls: mean 5d lift
  `-0.007315` versus `c16_insider_no_news`, `-0.005205` versus
  `c16_any_news_no_insider`, only `+0.000271` versus `exactly_two_sensors`,
  and 2025 lift `-0.003072` versus exactly-two. `c16_insider_source` had the
  same shape, losing to C16+insider-without-news and C16+news-without-insider.
  The broader `three_plus_sensors` state had mean 5d payoff `+0.008062` and
  lift `+0.005156` versus `exactly_two_sensors`, with `8 / 8` positive lift
  years, but 2025 lift was only `+0.001170`.

Why it matters:
- Do not promote C16+insider+news as a sparse high-conviction overlay or
  matrix/recommendation column under the current representation.
- The broad three-sensor clue is probably a C16 plus source/forward local-news
  pocket rather than an insider-confirmed triangle. `c16_source_forward` had
  mean 5d payoff `+0.008828`, but 2025 payoff was slightly negative.
- Reopen only with a narrower predeclared non-insider news triangle such as
  `c16_source_forward`, or with a materially different insider-quality
  representation.

Source:
- [session_270_log.md](./session_270_log.md)
- [deadends-001-030.md](./deadends-001-030.md) `D010`
- `artifacts/run_summaries/20260504_205532_h392_source_triangle_sparse_research_branch_source_triangle_sparse.json`

## F354: H393 Parks Nihilist Reversal; Stock-Down High-C16 Remains The Cleaner State (2026-05-04, Session 271)

Finding:
- Claim tested: high C16 after stock and market weakness works better when
  local news is weak or not bullish, marking hidden support after public
  capitulation.
- Evidence: `analysis/h393_nihilist_reversal.py` used fixed high-C16, trailing
  stock-down, trailing VNI-down, and no-bullish-news definitions; TRUE
  walk-forward years `2018-2025`; `2016-2025` data only; no `2026+`; and 5d
  relative-return payoff plus C16 IC diagnostics.
- Result: H393 `MIXED`. `nihilist_reversal` was positive, with mean 5d payoff
  `+0.010170` and mean C16 5d IC `+0.07738`, but it failed the important
  controls: mean 5d lift was only `+0.000169` versus
  `stock_market_down_high_c16`, `-0.002027` versus `stock_down_high_c16`,
  `+0.001525` versus raw high C16, and `+0.001472` versus active-news high
  C16; 2025 payoff was `-0.000982`. The simpler `stock_down_high_c16` remained
  stronger with mean 5d payoff `+0.012197`, C16 5d IC `+0.09182`, and 2025
  payoff `+0.002174`.

Why it matters:
- Do not promote a same-day nihilist-reversal overlay, matrix column, or
  recommendation policy under this no-bullish-news representation.
- The durable control remains stock weakness plus high C16. Adding market
  weakness and removing bullish-news support did not improve it.
- A narrow `nihilist_weak_active_news` clue had positive 2025 payoff
  (`+0.008064`), but it was not the primary state and needs a separate fixed
  contract before reuse.

Source:
- [session_271_log.md](./session_271_log.md)
- [deadends-001-030.md](./deadends-001-030.md) `D011`
- `artifacts/run_summaries/20260504_210147_h393_nihilist_reversal_research_branch_nihilist_reversal.json`
