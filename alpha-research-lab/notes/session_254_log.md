# Session 254 Log

Date: 2026-05-03
Focus: Bright-mind eureka generation and live-state hypothesis queue cleanup

## Summary

- Read repo memory, compact findings/dead ends, recent sessions, data contract,
  key published schemas, and active job state.
- Collapsed `live_state.md` from a stale multi-thousand-line hypothesis dump
  into a concise operational queue.
- Added 10 ranked, falsifiable hypotheses without assigning `H` numbers.

## Current Beliefs Reconstructed

- Live-promotable: keep the frozen sticky branch unchanged; no new live alpha
  promotion from this pass.
- Strong offline evidence: S1, C16/order pressure, Triple Storm, insider buy
  lead, consecutive down, down-market C16, volume/calendar/breadth filters, and
  the local PhoBERT heads.
- Fragile but useful: dividend context, rank-time acceleration, official-
  conditioned sentiment, event-v2 sparse evidence, and entry-alpha small-book
  behavior.
- Parked or killed under current contracts: C16 macro/gap/streak/extreme/
  sector-relative/persistence filters, event-v2 sparse-clock portfolio rescue,
  dividend/legal-holiday sparse clocks, standalone foreign/proprietary/sector
  flow, old OHLCV queue variants, and linear smart-exit tweaks.
- Unknown and high-upside: cross-source routers, absence-of-news states,
  representation changes from the Ollama event-family residual, dynamic K/
  breadth targeting, and selection-history freshness.

## Ranked Dossier

### 1. silent_order_pressure

- Claim: C16 is strongest when order pressure appears before any public
  narrative.
- Mechanism: informed demand is visible in posted orders before CafeF/local-news
  coverage catches up.
- Evidence from history: C16 is real; news is useful only in routed states;
  pooled sentiment failed.
- Why not already killed: no prior branch tested absence-of-news crossed with
  a proven side channel.
- Required data: `xs_order_pressure_daily`, PhoBERT ticker-day article counts,
  returns/tradability.
- First honest test: TRUE rolling holdout IC for C16 on no-news versus active
  stock-news rows, with a down-market control.
- Branch ladder: pass -> sparse router or portfolio bonus; mixed -> restrict to
  no-news after recent drawdown; fail -> kill no-news C16 router.
- Upside: high, because it can turn news absence into a timing signal.

### 2. news_flow_disagreement

- Claim: public text and posted orders disagree before the best reversals and
  traps.
- Mechanism: flow reveals informed accumulation/distribution while narratives
  lag or overreact.
- Evidence from history: price/C16 divergence worked; simple sentiment failed
  only as pooled standalone.
- Why not already killed: prior news failures did not test text-vs-flow
  disagreement buckets.
- Required data: C16, PhoBERT sentiment, forward-looking, article-scope,
  source-type, returns.
- First honest test: IC and matched returns for bullish-flow/negative-news,
  bullish-flow/no-news, positive-news/weak-flow, and aligned controls.
- Branch ladder: pass -> two-way router; mixed -> keep only negative-news
  reversal; fail -> kill text-flow disagreement.
- Upside: high, because it joins the two strongest live infrastructure themes.

### 3. official_attention_delay

- Claim: official/regulatory and forward-looking articles pay only when flow or
  insider support confirms them, often with delay.
- Mechanism: official information is credible but slow to price; side-channel
  support selects which filings matter.
- Evidence from history: official-conditioned PhoBERT had offline evidence;
  standalone official/sentiment promotion failed.
- Why not already killed: standalone failure does not kill interaction or
  delayed-reaction targets.
- Required data: PhoBERT source-type and forward-looking ticker-day features,
  C16, insider cache, 1d/5d returns.
- First honest test: TRUE WF IC and payoff by official/high-forward-looking
  plus C16/insider support versus official-only rows.
- Branch ladder: pass -> delayed event router; mixed -> only insider-confirmed
  official rows; fail -> keep official heads diagnostic only.
- Upside: high if it recovers a sparse authoritative event channel.

### 4. dynamic_breadth_option

- Claim: the right portfolio decision is often K, not which stock.
- Mechanism: score concentration, buyable breadth, and candidate entropy say
  whether the book should be top-1, top-2, or top-5.
- Evidence from history: entry-alpha behaved like a small-book contract; local
  entry overlays failed; activation meta already captures selector state.
- Why not already killed: H238-H246 killed stock-level overlays on the current
  label, not a day-level breadth-policy target.
- Required data: `activation_state_daily`, `activation_meta_daily` pre-decision
  columns, entry candidate panel, portfolio returns.
- First honest test: group rebalance dates by spread/entropy/buyable breadth
  and compare fixed K with TRUE WF year splits.
- Branch ladder: pass -> deterministic K router; mixed -> cap to K=1/5 switch;
  fail -> keep entry-alpha parked.
- Upside: high because it attacks portfolio construction without new data.

### 5. insider_down_rescue

- Claim: insider buys after visible weakness are different from ordinary
  insider buys.
- Mechanism: insiders buying into weakness reveal conviction; C16 checks
  whether outside demand agrees.
- Evidence from history: insider lead, consecutive down, and down-market C16
  all passed TRUE WF validation.
- Why not already killed: the separate signals passed; C16 streak compounding
  failed, but not insider-after-weakness confirmation.
- Required data: insider cache, stock returns, C16, tradability.
- First honest test: prior insider buy x 1-3 day drawdown x C16 rank with
  sample-size guard and TRUE WF controls.
- Branch ladder: pass -> sparse high-conviction filter; mixed -> restrict to
  executive/largeholder buys; fail -> use insider lead alone.
- Upside: medium-high, sparse but grounded.

### 6. fresh_selection_pulse

- Claim: first reappearance in the top candidate set after dormancy carries
  more edge than repeated membership.
- Mechanism: rediscovery and ranking shock create incremental attention; stale
  incumbents already had their move.
- Evidence from history: sticky retention helped portfolio stability, but
  entry-alpha local overlays failed.
- Why not already killed: sticky was a retention rule; selection-history
  freshness was not tested as a stock-level alpha state.
- Required data: `entry_alpha/candidate_panel_daily`, cycle labels, candidate
  ranks.
- First honest test: days since last top-5/top-10 candidate appearance versus
  matched cycle returns and IC.
- Branch ladder: pass -> freshness feature; mixed -> only first top-5 after
  long dormancy; fail -> do not use selection history.
- Upside: medium-high and CPU-cheap.

### 7. post_ollama_event_cascade

- Claim: Ollama event-family residuals can revive event timing only if they
  change the event representation.
- Mechanism: first-event, repeated-event, and event-family transitions may
  encode cascades old CafeF event-v2 mappings blurred.
- Evidence from history: H321 had sparse event evidence; H361 killed the old
  sparse-clock rescue.
- Why not already killed: this requires new event-family data from the current
  guarded backfill.
- Required data: completed `ollama_guarded_*` datasets plus old event-v2
  controls.
- First honest test: first/repeat/family-transition states versus H321/H361
  controls through 2025.
- Branch ladder: pass -> new event representation; mixed -> only first-event
  transitions; fail -> keep event timing parked.
- Upside: medium-high, blocked until the active job finishes.

### 8. calendar_as_liquidity_mechanism

- Claim: calendar edges are proxies for settlement, attention, and breadth
  states, not magic dates.
- Mechanism: month/week effects concentrate liquidity and order pressure.
- Evidence from history: monday-January, quarter-start, and several calendar
  filters passed; holiday sparse clocks failed.
- Why not already killed: calendar passed, but the mechanism was not
  decomposed.
- Required data: calendar filters, activation state, C16, volume, breadth,
  news counts.
- First honest test: retest calendar IC after matching/residualizing volume,
  breadth, news volume, buyable breadth, and down-market state.
- Branch ladder: pass -> mechanism-aware calendar router; mixed -> keep only
  residual calendar; fail -> demote calendar to proxy diagnostics.
- Upside: medium, useful for robustness.

### 9. tradability_release_pulse

- Claim: a high-ranked name becoming buyable after a blocked or limit-constrained
  state has a short executable continuation edge.
- Mechanism: constrained demand spills into the first legally buyable open.
- Evidence from history: price-limit features exist; blocked-buy complexity
  failed as broad activation overlay.
- Why not already killed: release-after-constraint is a stock-level event, not
  a global blocked-buy veto.
- Required data: entry candidate panel release/tradability columns, price-limit
  features, cycle labels.
- First honest test: `release_flag` and `prev_can_buy_next_open == false` to
  `can_buy_next_open == true` on high-rank names; compare matched returns and
  execution health.
- Branch ladder: pass -> release pulse entry feature; mixed -> only top-rank
  release; fail -> keep blocked-buy rules parked.
- Upside: medium, implementation-relevant.

### 10. source_triangle_sparse

- Claim: insider, order pressure, and local-news source type form a sparse
  high-conviction state even when two-way routes are noisy.
- Mechanism: independent human, order, and text channels agreeing should reduce
  false positives.
- Evidence from history: insider and C16 passed; foreign/proprietary and broad
  news routes failed.
- Why not already killed: the confirmed triangle pieces differ from the killed
  foreign/proprietary routes.
- Required data: insider cache, C16, PhoBERT source/scope/forward-looking,
  returns.
- First honest test: require at least two of prior insider buy, high C16,
  official/stock-scope news, and forward-looking text; enforce strict support
  and TRUE WF.
- Branch ladder: pass -> sparse high-conviction feature; mixed -> keep only
  insider+C16+official; fail -> avoid source stacking.
- Upside: medium, sparse but potentially clean.

## Live-State Writeback

- Updated [live_state.md](./live_state.md) with the concise hypothesis queue,
  active Ollama status, immediate next actions, and do-not-reopen rules.
- No durable finding was added because this pass generated hypotheses only; no
  experiment result was produced.
