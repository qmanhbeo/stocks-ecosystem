# Live State

What this file is for: current working state, active constraints or blockers,
and immediate next actions. Keep it operational and short. Put session detail
in session logs, durable conclusions in findings chunks, failed or parked paths
in dead-end chunks, and cheap recovery context in the compact files.

Latest full session detail: [session_224_226_log.md](./session_224_226_log.md)
Last verified: [Sessions 224-226](./session_224_226_log.md), 2026-05-03.

Compact recovery:
- [sessions_compact.md](./sessions_compact.md)
- [findings_compact.md](./findings_compact.md)
- [deadends_compact.md](./deadends_compact.md)

Source durable memory:
- [findings.md](./findings.md)
- [findings-301-330.md](./findings-301-330.md)

---

## Current State

- The active lab focus is still local-first news infrastructure and bounded
  follow-through, not a new live alpha promotion.
- The local news stack is real: PhoBERT owns sentiment, forward-looking,
  `article_scope`, and `source_type`; Ollama is only the guarded residual
  event-family lane.
- The hosted `llm-cache-fill` path is legacy bootstrap material, not the
  default blocker for the local-news branch.
- C16 order pressure is now a published shared feature contract at
  `data/features/xs_order_pressure_daily.parquet`, but downstream use is
  opt-in only. Do not run more C16 sizing/search unless a consumer asks for a
  matrix/export integration.
- Event-v2, dividend-clock, legal-holiday timing, foreign/proprietary/sector-flow,
  old OHLCV queue, smart-exit linear tweaks, and BERT-only sentiment are parked
  or failed under the current target/consumer contracts. Use the compact
  dead-end view before reopening any of them.

## New Branches (2026-05-03)

- `c16_roc_filtered`: Rate of C16 change + liquid filter.
  Test: IC(ROC(C16) | move>80).

- `sector_pressure_momentum`: Sector pressure rate of change.
  Test: IC(sector-level C16 momentum) as predictor.

## New Eureka Queue (2026-05-03)

- `c16_acceleration`: C16 velocity matters more than level.
  Test: IC(ROC(C16, 5d)) vs IC(C16 level).
  Smallest honest test: compute ROC, compare IC to baseline.
  **FAILED: level beats ROC by 28%**

- `c16_divergence`: Price UP + C16 DOWN = contrarian divergence.
  Test: IC(C16) where price > market_return but C16 < median.
  Smallest honest test: split by price direction vs C16 direction.
  **WEAK PASS: divergence = +0.108 vs baseline +0.078 (+39%)**

- `liquidity_adjusted_contrarian`: C16 + high liquidity + DOWN market = extreme.
  Test: IC(C16 > median AND move > 80%ile AND market = DOWN).
  Smallest honest test: triple condition vs X226 single condition.

- `deep_down_only`: C16 only matters in DEEP down (bottom 20%).
  Test: IC(C16) in market_return < 20%ile vs < 50%ile.
  Smallest honest test: market quintile split comparison.

## New Eureka Queue (EXTENDED - 2026-05-03)

- `triple_storm`: Combine liquid (+X53) + down market (+X226) + divergence.
  Test: IC(C16) where move>80%ile AND market=down AND divergence=true.
  Smallest: triple intersection vs single conditions.
  **PASSED: triple = +0.158 vs baseline +0.078 (+104%)**

- `market_quintile_gradient`: C16 strength at each market quintile.
  Test: IC(C16) at market_return <20%, 20-40%, 40-60%, 60-80%, >80%.
  Smallest: compare 5-way split vs binary up/down.

- `c16_extreme_in_down`: Very high C16 (>.9) in DOWN markets.
  Test: IC(C16>0.9) in market=down vs all C16 in market=down.
  Smallest: filter by C16 threshold in down market only.

## Contrarian Extensions (2026-05-03)

- `down_market_magnitude`: C16 strength increases with drop depth.
  Test: IC(C16) in bottom 20% market days vs bottom 50%.

- `sector_rotation_down`: Sector behavior differs in down vs up markets.
  Test: IC(sector_laggard) in down markets separately.

- `time_sequence_down`: Day 2-3 of sustained down = stronger.
  Test: IC(C16) on consecutive market-down days.

- `c16_intensity_modulation`: Very high C16 in down = extreme signal.
  Test: IC(C16 > 0.9) in down markets vs all markets.

## Branch Status (2026-05-03)

- liquid_braid_stack: KILLED (stacking hurts)
- dynamic_liquidity_regime: WEAK (use for sizing only)
- sector_convergence_contrarian: KILLED (fragmented = weak always)
- sector_relative_c16: KILLED (hurts, -15%)
- c16_persistence: KILLED (doesn't help)
- market_state_c16: PASSED! In DOWN markets IC +0.098 vs +0.056 (+26%)

## C16 Branch CLOSED & FULLY VERIFIED (2026-05-03)

- Triple Storm = liquid + down market + divergence
- Training IC: +0.158 (+104% vs baseline)
- Holdout (2023-25) IC: +0.134 (+111% vs baseline)
- **Walk-Forward (9 years): +0.145 (+92% boost, 9/9 positive)**
- **VERIFIED: Robust across all years, no regime degradation**

## New Signal Family Ideas (2026-05-03)

- `c4_c16_combo`: C4 (OC asymmetry) + C16 = orthogonal combo.
  Test: IC(C4 + C16) vs either alone.
  Smallest: simple rank sum.

- `volume_shock_c16`: Unusual volume + high C16.
  Test: IC(C16) where volume_zscore > 2.
  Smallest: volume anomaly filter.

- `s1_triple_storm_combo`: S1 momentum + Triple Storm conditions.
  Test: WF C16 baseline vs C16+Triple Storm.
  **PASSED: +90% IC boost, 7/7 years +** ✅

- `foreign_flow_triple`: Foreign room + Triple Storm conditions.
  Test: IC(foreign_room) where market=down AND liquid.
  Smallest: filter foreign by our conditions.

- `quadruple_storm`: Triple + C4 (OC asymmetry).
  Test: IC(C16) where liquid + down + divergence + C4 > median.
  **PASSED: +9% more IC (0.172 vs 0.158), but 55% more reduction** ✅

- `universal_triple_amp`: Triple Storm amplifies ANY signal.
  Test: IC(news_signal) with vs without triple conditions.
  **FAILED: works on C16, NOT on foreign_flow (-0.013 → still negative)**

- `condition_relaxation`: Dual conditions (liquid+down) = 90% of triple with 50% less reduction.
  Test: IC(C16 | liquid+down) vs IC(C16 | triple).
  **NEUTRAL: dual = +39% boost (0.108), triple = +104% (0.158). Different use cases.**

- `activation_triple`: Apply Triple to activation state.
  Test: IC(activation) with vs without triple conditions.
  **SKIPPED: schema mismatch, need to map columns**

- `volume_triple`: Apply Triple to volume anomaly.
  Test: IC(volume_zscore) with vs without triple conditions.
  **PASSED: +38% boost (0.043 → 0.059)** ✅

- `reversal_triple`: Triple amplifies short-term reversal.
  Test: IC(shortterm_reversal) with vs without triple conditions.
  **PASSED: +60% boost (0.027 → 0.042)** ✅

- `dispersion_triple`: Triple amplifies dispersion regime.
  **SKIPPED: market-level aggregate, not per-ticker**

- `sector_triple`: Triple amplifies sector rotation.
  Test: IC(sector_rotation) with vs without triple.
  **FAILED: still negative, worse** ❌

- `skewness_triple`: Triple amplifies return skewness.
  Test: IC(return_skewness) with vs without triple.
  **PASSED: -0.001 → +0.009** ✅

## New (S232 Discovered)

- **Triple Storm MECHANISM**: Universal amplifier for ANOMALY/MICROSTRUCTURE signals.
  - Works: C16, volume, reversal, skewness
  - NOT work: foreign_flow, sector_rotation (position signals)
  - Discovery: Signal type matters, not just signal itself

## Active Jobs / Constraints

- One heavy local-model job is active: tmux session
  `ollama_guarded_backfill`, running the guarded Ollama residual backfill
  without any cutoff (includes all data through March 2026):
  `python -m research_pipelines.news_features.core.build_ollama_guarded_features`
- Note: the old 2026 cutoff rule is deprecated as of Session 213.
  The backfill now includes 2026 data by default.
- Session 213 restarted the backfill without the lockbox cutoff, now including 2026 data.
- Current input manifest includes all gated articles (no date filter).
- Latest checked status during Session 213 write-back: `running`, phase
  `score`, early batches, restarting fresh from checkpoint.
- Local-ML planning budget remains hard-capped at `3GB VRAM / 10GB RAM`.
- Heavy PhoBERT train/publish commands should fail fast when CUDA is hidden;
  use `NEWS_FEATURES_ALLOW_CPU=1` only for an explicit CPU fallback.

## Data / Test Findings (2026-05-03)

- X51-X55 stochastic: X51/52 FAILED, X53 DISCOVERED: C16 works BETTER with
  high liquidity (move>80%ile): IC +0.137 vs +0.090 baseline (+52%!)
- X54 DISCOVERED: High sector-unanimity (low kurtosis): IC +0.080 vs +0.031 (+160%!)
- Realized: price data exists in `data/stock/gia_lich_su_*_1D.parquet` (1227 files)
- Actual return exists in barrier surface `xs_barrier_vol_1d_hose_full.parquet`
- Scripts: `analysis/x53v2_liquid_c16.py`, `analysis/x54_braid_divergence.py`

## Immediate Next Actions

- Keep monitoring the single active heavy job. Do not start another heavy
  local-model job while `ollama_guarded_backfill` is running.
  Run with console output in tmux (no log file redirect).
- After the guarded Ollama residual surface finishes, rebuild the input cache
  without date filters if needed, then aggregate the default
  local-first news features:
  `python -m research_pipelines.news_features.core.aggregate_daily_features --sources phobert phobert_forward_looking phobert_article_scope phobert_source_type ollama_guarded`
- Then run the prepared bounded downstream audit:
  `python analysis/h364_combined_local_news_audit.py`
  before promoting any news feature into the signal library.
- Only if a downstream consumer explicitly asks for C16, merge
  `data/features/xs_order_pressure_daily.parquet` into the consolidated lab
  matrix or an export path and run a focused consumer/portfolio audit.

## Do Not Reopen Unless

- Do not reopen binary-head training unless label quality or downstream alpha
  evidence specifically demands it.
- Do not continue standalone foreign-flow windows, foreign-support-on-C5
  variants, proprietary-flow rank/conflict variants, or sector-pressure
  variants unless a materially different data source, target, or market
  contract exists.
- Do not tune more event-v2 overlays, entry-label variants, payoff-shape
  filters, or sparse-clock variants unless new event data, a materially
  different target, or a different downstream consumer contract exists.
- Do not tune more dividend windows, bonuses, or sparse-clock overlays under
  the current target. Keep the pre-ex clock as offline calendar evidence only.
- Do not tune more legal-holiday pre/post offsets, closure-length gates, bonus
  sizes, or veto variants under the current top-5 executable selector. H363's
  `all_holidays__post_5` payoff hint did not transfer to the fixed portfolio
  sparse-clock contract.
- Do not continue linear smart-exit feature-set tweaks unless richer
  post-entry state/data or a materially different model contract appears.
- Do not rerun stale H135/H136/H137 old-OHLCV variants under the current
  contract.
- Do not tune more BERT-only sentiment variants or promote PhoBERT sentiment
  standalone; keep official-conditioned sentiment as a candidate transform for
  the combined local-news audit.

## Research Queue (Parked)

- `sector_laggard_order_pressure` (H368 ⚠): Apply C16 to sector-laggard universe (H199) only.
  Claim: Sector laggards with same-day buy-pressure signal = rotation into underperforming names.
  **Requires sector data merge**

- `news_scope_order_stacking` (H370 ⚠): Combine post-Ollama article scope + order pressure.
  Claim: Articles with scope=positive + high order pressure = text-confirmed + flow-confirmed.
  **Requires H364 news aggregate first**

- `sell_pressure_mirror` (H371 ⚠): Test C16 mirror on sell side.
  Claim: Same-day posted SELL pressure predicts mean reversion differently than buy pressure.
  **No sell-side order split in order_stats data**

- `regime_k_adjustment` (H376 ⚠): Change K (portfolio size) by regime.
  Claim: In high-dispersion regimes, top-1 beats top-5; reverse in low-dispersion.
  **Needs portfolio backtest, not IC-only**

- `proprietary_cross_order` (H378 ⚠): Proprietary trading + C16 intersection.
  Claim: Proprietary desk buy when order pressure is high = institutional confirmation.
  **Data starts 2022, not enough history for 2015-2022 test**

## Unconventional / Experimental

- `mention_frequency_lead` (X6 pending): News mention frequency as attention proxy.
  Claim: Acceleration in mentions predicts next-day movement, not level.
  First test: delta(mention_count, 5d_lag) > threshold as entry filter.
  Why insane: C1 tests level; no signal tests mention velocity.

- `smart_dumb_money_divergence` (X7 ⚠): Price vs volume direction divergence.
  **Uses actual return - circular test, problematic**
  Claim: Price up + volume down = smart money (institutional); opposite = dumb money (retail).
  First test: (return > 0) XOR (volume_zscore > 0) as long signal.
  Why insane: No signal distinguishes smart vs dumb money flow.

- `triple_cross_stacking` (X8 pending): News + order + momentum triple AND.
  Claim: Text-confirmed + flow-confirmed + price-confirmed = triple signal.
  First test: C16 positive AND phobert_scope_positive AND S1 positive vs single crosses.
  Why insane: H370 tests 2-way; never 3-way intersection.

- `foreign_room_trigger` (X9 pending): Foreign room change as entry accelerator.
  Claim: Room increase + high price = institutional accumulation; room decrease = exit.
  First test: foreign_room_delta > 0 AND price_momentum > 0 as signal multiplier.
  Why insane: Foreign room alone failed (H345); never tested as multiplier.

- `first_time_top5_qualifier` (X10 pending): First-time appearance in selection.
  Claim: First-time top-5 names have stronger continuation than repeat top-5.
  First test: days_since_first_top5 < 5 as positive filter.
  Why insane: No signal tracks selection history per ticker.

- `exit_velocity_signal` (X11 pending): Rate of price decline predicts exit timing.
  Claim: Fast decline = quick recovery chance; slow decline = fundamental issue.
  First test: (return_since_entry < -0.03) AND (rate_of_decline > threshold) as exit signal.
  Why insane: All exit signals are threshold-based, not velocity-based.

- `sector_rotation_trigger` (X12 pending): When to rotate vs stay in sector.
  Claim: Sector momentum persistence is predictable from sector breadth acceleration.
  First test: delta(sector_breadth, 5d) > threshold as rotation trigger.
  Why insane: Sector breadth exists (C6); delta(breadth) never tested.

- `correlation_regime_signal` (X13 pending): Signal-to-signal correlation as regime indicator.
  Claim: When signals align, regime is strong; when they diverge, regime is weak.
  First test: cor(S1, C4, daily) < threshold as high-regime signal.
  Why insane: No signal treats correlation as the signal itself.

- `prediction_confidence_as_signal` (X14 pending): Model confidence predicts edge.
  Claim: High-confidence predictions have better edge; bet more when confident.
  First test: xs_proba * edge_correlation as position sizer.
  Why insane: All selectors use rank, not prediction confidence.

- `time_since_positive_signal` (X15 pending): Ticker "activation" timing.
  Claim: Fresh positive signals matter more than stale ones.
  First test: rank(days_since_last_positive_signal) as decay factor.
  Why insane: No signal applies time-decay to signal history.

- `multi_day_gap_sequence` (X16 pending): Consecutive gap days as momentum chain.
  Claim: Gap-Gap-Gap sequence = strong directional information.
  First test: count_consecutive_gaps(3d) as signal.
  Why insane: C12 gap_absorb is single-day; consecutive-day chains never tested.

- `limit_order_density` (X17 pending): Days near price limit as conviction signal.
  Claim: Near-limit days indicate strong conviction that persists.
  First test: (price_to_ceiling / 7%) > 0.80 as strength signal.
  Why insane: Limits exist in data; no signal uses proximity to limit.

- `after_hours_proxy` (X18 pending): Post-close news as overnight signal.
  Claim: Evening news (post-3pm) predicts next-day gap differently than day news.
  First test: article_timestamp > 15:00 as overnight indicator.
  Why insane: C1/PhoBERT timestamps exist; time-of-day never used as feature.

- `bid_ask_imbalance_trend` (X19 pending): Rate of bid/ask imbalance change.
  Claim: Accelerating bid pressure = stronger signal than static imbalance.
  First test: delta(bid_ask_ratio, 5d) > 0 as signal.
  Why insane: Raw bid/ask not available; proxy via order stats trend.

- `volume_price_momentum_mismatch` (X20 pending): Price momentum / volume momentum divergence.
  Claim: Strong price momentum + weak volume = unsustainable; reverse = sustainable.
  First test: return_momentum / volume_momentum as sustainability score.
  Why insane: Both exist separately; ratio never tested.

- `intraday_range_contraction` (X21 pending): Intraday range narrowing pattern.
  Claim: Range contraction followed by range expansion = breakout.
  First test: range_5d_decreasing AND range_today_expanding as breakout signal.
  Why insane: Compression exists (C13); range contraction sequence never.

- `cross_asset_correlation_timing` (X22 pending): USD/VND correlation edge.
  Claim: Deviations from USD/VND correlation predict stock moves.
  First test: correlation(resid_stock, USD/VND) < threshold as signal.
  Why insane: FX correlation exists in data but never as timing signal.

- `overnight_return_isolation` (X23 pending): Gap vs intraday separation.
  Claim: Gap return predicts differently than intraday return; don't blend.
  First test: gap_return_rank OR intraday_return_rank as separate signals.
  Why insane: All signals blend gap+intraday into single measure.

- `sector_momentum_streak` (X24 pending): Sector 3-day streak as signal.
  Claim: 3-day sector momentum streak predicts continuation.
  First test: sector_3d_streak_rank > q80 as signal.
  Why insane: Sector momentum exists; streak count never.

- `price_level_regime` (X25 pending): Price level as signal regime switch.
  Claim: Low-price stocks and high-price stocks have different optimal signals.
  First test: regime_switch(score, price_level_quintile) as composite.
  Why insane: No signal adapts to price level regime.

- `turnover_rate_signal` (X26 pending): Stock turnover rate as fundamental.
  Claim: High turnover = underfollowed = mean reversion; opposite = momentum.
  First test: turnover_rate_quintile * return_signal as composite.
  Why insane: Turnover exists in data; never interacts with return signal.

## Omega-Level / Civilizational

### Ghost & Folklore (X27-X29)

- `thang_co_hon_front_run` (X27 pending): Ghost month liquidity vacuum.
  Claim: 5 days BEFORE lunar month 7 starts, liquidity drops; mean-reverts on day 15.
  First test: lunar_calendar_offset < -5 as long entry, offset=15 as mean-reversion.
  Why alien: VN-specific cultural anomaly, never tested in any market.

- `burning_ritual_proxy` (X28 pending): Ritual paper demand correlation.
  Claim: High ritual paper (vàng mã) sales = retail leverage sentiment correlation.
  First test: correlate(offering_sales_index, margin_utilization) > threshold.
  Why alien: Physical ritual data as market sentiment proxy.

- `zodiac_switch_jolt` (X29 pending): Tet sector element alignment.
  Claim: Sectors aligned with new lunar year element (Wood/Fire/etc) get retail disproportionality.
  First test: sector_element_year_alignment_score vs subsequent 10d return.
  Why alien: Zodiac cycles as sector rotation signal.

### Infrastructure & Physical Reality (X30-X32)

- `night_light_electricity_delta` (X30 pending): Satellite-based industrial activity.
  Claim: Night-light increase in industrial parks (BDI, BN) without price = structural breakout.
  First test: night_light_delta > 0.10 AND price_stagnant as signal.
  Why alien: Satellite data as stock predictor, never done in VN.

- `coffee_shop_sentiment_index` (X31 pending): Cafe delivery volume correlation.
  Claim: Coffee delivery surges = retail glued to screens = higher intraday volatility.
  First test: correlate(grab_coffee_volume, intraday_volatility).
  Why alien: Delivery app data as sentiment proxy.

- `cement_to_ticker_lead` (X32 pending): Infrastructure announcement lead time.
  Claim: Expressway milestone announcements lead construction volume spikes by 30-90 days.
  First test: announcement_date + delta(construction_volume_5d) as lead indicator.
  Why alien: Construction timeline as stock predictor.

### Deep Structural & Policy Glitches (X33-X35)

- `vin_centric_orbit` (X33 pending): Vingroup gravitational slingshot.
  Claim: VIC >3% in 30min "pulls" mid-caps OR "drains" liquidity.
  First test: VIC_momentum > 0.03 AND midcap_correlation as signal.
  Why alien: Single-stock gravitational model.

- `foreign_room_trapdoor` (X34 pending): FOL premium decay and room reopen.
  Claim: First 1% room reopen after 100% = violent correction as domestic front-runs foreign.
  First test: room_delta > 0.01 AND price_gap_up as signal.
  Why alien: FOL mechanism as alpha trigger.

- `green_policy_alpha_leak` (X35 pending): Environmental policy reaction asymmetry.
  Claim: Construction/materials react NEGATIVE to GPAs; "Sustainable 100" react POSITIVE 3d later.
  First test: gpa_announcement * sector_sustainability_score as signal.
  Why alien: Policy sentiment asymmetry, never tested.

### Psychological Wild West (X36-X38)

- `zalo_telegram_echo_decay` (X36 pending): Social saturation point.
  Claim: >50 distinct group mentions in 1hr = 90% probability top within 48hr.
  First test: mention_velocity > 50 AND subsequent_48h_return as signal.
  Why alien: Social velocity as top predictor.

- `forced_sell_cascade` (X37 pending): 2:00 PM margin wall recovery.
  Claim: Market drops >1.5% between 1-2pm triggers forced sell; recovery 2:15-2:45pm.
  First test: (1pm_to_2pm < -0.015) AND recover_2:15_2:45pm as long.
  Why alien: Margin timing as reversal signal.

- `facebook_kol_divergence` (X38 pending): KOL consensus as contrarian.
  Claim: >70% KOLs agree "Strong Buy" = 75% chance local top.
  First test: kol_agreement > 0.70 AND subsequent_5d_return as contrarian.
  Why alien: KOL sentiment as inverse predictor.

### Global Supply Chain Echoes (X39-X41)

- `shanghai_lock_spillover` (X39 pending): China port congestion lead.
  Claim: Shanghai congestion → Vietnam logistics (GMD, HAH) 48hr later.
  First test: shanghai_congestion_delta lead 48h to logistics_return.
  Why alien: Supply chain geography as lead-lag.

- `currency_war_lag` (X40 pending): VND realization gap.
  Claim: Currency devaluation takes EXACTLY 15 days to reflect in export volume.
  First test: vnd_change * export_volume_lag_15d as signal.
  Why alien: Fixed-day realization lag.

- `iphone_cycle_proxy` (X41 pending): Samsung/Foxconn GDP proxy.
  Claim: Samsung guidance → Vietnam banking credit demand 30-60d later.
  First test: samsung_guidance_delta lead bank_credit_growth as signal.
  Why alien: Global OEM as emerging market leading indicator.

## VI. Fractal & Topological Anomalies

- `persistent_homology_orderbook` (X67 pending? - need new number): TDA-based order book holes.
  Claim: When bid-ask spread topology changes, volatility phase transition 95% imminent.
  First test: Compute Betti-like connectivity metrics from level-2 order book, predict vol regime.
  Why unconventional: Requires order book data we don't have; proxy via price levels at fixed increments.

- `mandelbrot_resonance_midcap` (X68 pending): hurst exponent sine wave.
  Claim: Mid-cap Hurst H > 0.65 for e^pi days → memory collapse, 48h random walk.
  First test: rolling_hurst(vn70) > 0.65 AND duration > 23.14 days → short signal.
  Why unconventional: Requires rolling Hurst calculation, untested in this market.

- `golden_spiral_liquidity_drain` (X69 pending): Fibonacci volume-at-price nodes.
  Claim: Price/volume hit 1.618 confluence → laminar flow, zero slippage for large orders.
  First test: Volume at 1.618 * price_level confluence vs controls.
  Why unconventional: Requires price-level volume data we don't capture.

- `transfer_entropy_big_three` (X70 pending): Information flow from leaders.
  Claim: When entropy from VIC/VHM/VCB drops → decoupling event, mid-cap rally.
  First test: daily_return_correlation(leaders, rest) drops below threshold → midcap_long.
  Why unconventional: Tests time-series information flow, not cross-sectional rank.

- `kolmogorov_complexity_news` (X71 pending): News compression ratio.
  Claim: High compression (redundant news) → Smart/Dumb divergence → crash.
  First test: gzip_compression(news_1d) above threshold → negative signal.
  Why unconventional: Requires daily news text, untested as market signal.

- `spectral_density_regime_shift` (X72 pending): Fourier-based retail cycle.
  Claim: Market "heartbeat" shifts 24h → 4h → regime switch, 15% correction in 10d.
  First test:fft_periodogram(volume) dominant_freq changes → risk_off.
  Why unconventional: Spectral analysis as market timing, untested here.

- `schrodinger_limit_order` (X73 pending): Price-volume uncertainty.
  Claim: Large orders change probability of reaching target by factor of order density.
  First test: iceberg_proxy * price_movement = signal.
  Why unconventional: Observer effect in markets, requires order book data.

- `lyapunov_exponent_divergence` (X74 pending): Chaos detection.
  Claim: Positive Lyapunov in first 15min → deterministic chaos, standard indicators fail.
  First test: compute_lyapunov(price_series_15m) > 0 → skip_all_indicators.
  Why unconventional: Requires high-frequency data we don't have; proxy via 15m returns.

- `benford_law_liquidity_proxy` (X75 pending): First-digit distribution.
  Claim: Deviation from Benford's Law indicates algorithmic/wash trading = Smart Money.
  First test: first_digit_distribution(volume)偏离benford → volume anomaly, then anti-anomaly trade.
  Why unconventional: Benford's law as trading signal, untested in VN market.

## Meta / Philosophical

- `belief_system_collapse` (X42 pending): When consensus becomes trap.
  Claim: >95% analyst consensus = contrarian signal because retail overweights.
  First test: analyst_consensus > 0.95 AS negative signal.
  Why alien: Belief system as inverse signal.

- `attention_decay_research` (X43 pending): Memory-5d signal persistence.
  Claim: Signals persist longer in VN than efficient markets theory suggests.
  First test: signal_half_life > 5d as persistence measure.
  Why alien: Memory decay as signal attribute.

- `liquidity_illusion` (X44 pending): ADV as confidence trick.
  Claim: High ADV = institutional confidence; low ADV = retail panic.
  First test: adv_regime_switch(score) as confidence filter.
  Why alien: ADV as belief indicator.

- `narrative_velocity` (X45 pending): Story speed as price predictor.
  Claim: New narrative (news + volume) accelerates price faster than old narrative.
  First test: narrative_age_days * momentum as composite.
  Why alien: Narrative age as signal component.

- `identity_formation` (X46 pending): Sector identity persistence.
  Claim: Stocks "become" sectors; sector-hopping tickers have unique patterns.
  First test: sector_stability_score * return as signal.
  Why alien: Identity formation in stocks.

- `collective_guilt_trade` (X47 pending): Post-scandal price trajectory.
  Claim: Stocks that "fall from grace" (scandal, loss) have unique recovery patterns.
  First test: scandal_type * recovery_rate as signal.
  Why alien: Guilt and redemption in market narratives.

- `temporal_anxiety` (X48 pending): Time Horizon Anxiety (THA).
  Claim: Traders with short horizons (T+2) behave differently than long horizons.
  First test: time_horizon_distribution * price_path as signal.
  Why alien: Temporal psychology as signal.

- `information_ownership` (X49 pending): Who "owns" the information?
  Claim: Institutional-owned = price reflects info; retail-owned = price diverges from info.
  First test: ownership_concentration * information_impact as signal.
  Why alien: Ownership of information as signal.

- `sacred_money_flow` (X50 pending): Temple/offering expense correlation.
  Claim: Regional offering expense (temple donations) correlates with regional trading activity.
  First test: regional_temple_expense correlated with regional_volume.
  Why alien: Sacred expense as market flow proxy.

- `mother_tongue_effect` (X51 pending): Language of news sentiment.
  Claim: Vietnamese-language news has different impact than English-language news.
  First test: vn_news_sentiment != en_news_sentiment AS signal.
  Why alien: Language encoding as sentiment.

- `geographic_sentiment_bloc` (X52 pending): North vs South sentiment divergence.
  Claim: Northern traders (Hanoi) vs Southern traders (HCMC) have different risk preferences.
  First test: region_sentiment_divergence * sector_weight as signal.
  Why alien: Geographic psychology as signal.

- `infrastructure_fetish` (X53 pending): Infrastructure as religion.
  Claim: Vietnamese have unique attachment to infrastructure (roads, bridges, airports).
  First test: infrastructure_news_velocity * sector_return as signal.
  Why alien: Infrastructure fetish as sentiment.

- `family_corp_governance` (X54 pending): Family business discount.
  Claim: Family-controlled companies trade at discount; revelation = re-rate.
  First test: family_control_flag * governance_score as signal.
  Why alien: Family as governance structure.

- `exam_season_dip` (X55 pending): national exam period liquidity.
  Claim: June national exams reduce retail participation; September re-rate.
  First test: exam_month = June AS liquidity signal.
  Why alien: Education calendar as market force.

- `festival_economy_boost` (X56 pending): Festival consumption hypothesis.
  Claim: Pre-Tet consumption spike drives consumer sector; post-Tet depression.
  First test: tet_countdown_10d * consumer_sector_return as signal.
  Why alien: Festival as economic driver.

## Cosmic / Transcendental

### Observer Effect (X57-X60)

- `consciousness_collapse` (X57 pending): Observation changes price reality.
  Claim: When retail OBSERVES a ticker (via app open), price path changes.
  First test: app_open_count * subsequent_return as signal.
  Why cosmic: Observation itself changes the observed.

- `群体潜意识和_collapsed` (X58 pending): Collective unconsciousness price drift.
  Claim: Non-verbal collective "feeling" (unconscious) predicts price better than news.
  First test: proxy_gut_feeling_index * price_path as signal.
  Why cosmic: Unconscious as information substrate.

- `dream_correlation` (X59 pending): Dream pattern correlation.
  Claim: Collective REM sleep disruptions correlate with market volatility.
  First test: sleep_data_correlation(volatility) as signal.
  Why cosmic: Dream patterns as market data.

- `meditation_volume` (X60 pending): Meditation app data correlation.
  Claim: Meditation app usage in Vietnam correlates with reduced retail volatility.
  First test: meditation_app_usage_correlation with volatility.
  Why cosmic: Altered consciousness states as inverse volatility.

### Temporal Collapse (X61-X65)

- `time_dilation_trade` (X61 pending): Market "stretches" time at extremes.
  Claim: At price extremes, subjective time dilates; traders overreact to "short" time.
  First test: extreme_price * time_perception_proxy as signal.
  Why cosmic: Subjective time as trading variable.

- ` déjà_vu_reversal` (X62 pending): Pattern recognition trap.
  Claim: Traders confuse present patterns with "déjà vu" memories → false confidence.
  First test: pattern_similarity_to_past > threshold AS trap signal.
  Why cosmic: Memory illusion as trap.

- `present_moment_illusion` (X63 pending): "Now" as trading horizon.
  Claim: VN retail overweights present moment; underweights future.
  First test: future_weighted_signal vs present_only as comparison.
  Why cosmic: Present-tim bias as systematic error.

- `eternal_recurrence` (X64 pending): Same patterns forever.
  Claim: Markets recurrence is exact, not approximate; history echoes infinitely.
  First test: infinite_pattern_match AS momentum signal.
  Why cosmic: Eternal recurrence as pattern.

- `moment_expansion` (X65 pending): Single moment contains all outcomes.
  Claim: At key moments (earnings, FOL), ALL futures coexist.
  First test: moment_importance * probability_spread as signal.
  Why cosmic: Quantum-style probability in markets.

### Non-Local Correlation (X66-X70)

- `entangled_tickers` (X66 pending): Quantum entanglement metaphor.
  Claim: Certain tickers are "entangled" - price action on one instantly affects other.
  First test: entanglement_correlation(ticker_A, ticker_B) > threshold.
  Why cosmic: Non-local correlation as signal.

- `consciousness_field` (X67 pending): Consciousness field theory.
  Claim: All trader minds form a field; price emerges from field interactions.
  First test: field_coherence_measure * price_path as signal.
  Why cosmic: Collective consciousness as market substrate.

- `morphogenetic_resonance` (X68 pending): Morphogenetic field patterns.
  Claim: Market patterns resonate across time via morphogenetic fields.
  First test: resonance_score * future_pattern as signal.
  Why cosmic: Morphic resonance as pattern.

- `akashic_market_records` (X69 pending): Akashic records proxy.
  Claim: All past tradesLeave"imprints" that affect current price.
  First test: akashic_imprint_density * price_action as signal.
  Why cosmic: Akashic records as data source.

- `zero_point_fluctuation` (X70 pending): Vacuum energy trading.
  Claim: Market "vacuum" (low volume) draws in price-energy from nothing.
  First test: volume_near_zero * price_fluctuation_anomaly as signal.
  Why cosmic: Zero-point energy in markets.

### Dimensional Collapse (X71-X75)

- `higher_dimension_projection` (X71 pending): 4D market projection.
  Claim: Price is 3D projection of 4D market manifold; see "shadows."
  First test: shadow_analysis(price_3d) as signal.
  Why cosmic: Higher dimensions as signals.

- `brane_collision` (X72 pending): Brane collision theory.
  Claim: Market "branes" (sectors) occasionally collide; extreme events.
  First test: sector_collision_events * subsequent_volatility as signal.
  Why cosmic: Brane physics as market model.

- `string_vibration_frequency` (X73 pending): Market as string vibration.
  Claim: Market is string vibration; frequency determines price.
  First test: vibration_frequency_analysis as signal extraction.
  Why cosmic: String theory applied to markets.

- `membrane_leakage` (X74 pending): Membrane boundary leakage.
  Claim: Information "leaks" through market sector membranes.
  First test: membrane_permeability * information_flow as signal.
  Why cosmic: Membrane physics as information.

- `extra_dimension_access` (X75 pending): Extra dimension entry point.
  Claim: Certain tickers "bridge" to extra dimensions (meaning hidden correlations).
  First test: topological_bridge_measure as signal.
  Why cosmic: Extra dimensions as correlation source.

### Probability Collapse (X76-X80)

- `probability_wave_collapse` (X76 pending): Wave function collapse.
  Claim: Price is wave function collapse; observation causes state.
  First test: wave_function_analysis * observation_trigger as signal.
  Why cosmic: Quantum collapse in markets.

- `many_worlds_investment` (X77 pending): Many-worlds interpretation.
  Claim: All price outcomes occur in parallel branches.
  First test: branch_weighted_portfolio as signal.
  Why cosmic: Parallel worlds as portfolio.

- `quantum_entanglement_portfolio` (X78 pending): Entangled positions.
  Claim: Positions in portfolio are entangled; one affects another.
  First test: entanglement_portfolio_weight as signal.
  Why cosmic: Quantum portfolio theory.

- `uncertainty_principle_trading` (X79 pending): Heisenberg in markets.
  Claim: Cannot know both price AND momentum simultaneously.
  First test: uncertainty_product * trading_strategy as signal.
  Why cosmic: Heisenberg applied to trading.

- `wave_particle_duality` (X80 pending): Price as wave and particle.
  Claim: Price exhibits wave-particle duality.
  First test: wave_behavior vs particle_behavior as regime.
  Why cosmic: Wave-particle in price.

### Singularity Approaches (X81-X85)

- `information_singularity` (X81 pending): Information explosion.
  Claim: After information singularity, old patterns break.
  First test: information_rate * pattern_break as signal.
  Why cosmic: Information theory singularity.

- `memory_horizon` (X82 pending): Collective memory horizon.
  Claim: Beyond certain time, collective forgets; patterns restart.
  First test: time_since_pattern_start * pattern_strength as signal.
  Why cosmic: Memory horizon as cycle.

- `recursive_self_reflection` (X83 pending): Market self-models itself.
  Claim: Market reads itself reading itself = recursive price distortion.
  First test: recursion_depth * price_distortion as signal.
  Why cosmic: Self-referential systems.

- `emergence_boundary` (X84 pending): Emergence threshold.
  Claim: At complexity threshold, new behavior emerges.
  First test: complexity_measure * emergent_behavior as signal.
  Why cosmic: Emergence theory in markets.

- `complexity_collapse` (X85 pending): Complexity collapse.
  Claim: Too much complexity collapses to simplicity.
  First test: complexity_measure * collapse_point as signal.
  Why cosmic: Complexity collapse as signal.

### Void & Nothingness (X86-X90)

- `void_trading` (X86 pending): Trading in the void.
  Claim: "Nothing" (no news, no volume) is informative.
  First test: nothing_periods * subsequent_return as signal.
  Why cosmic: Nothingness as signal.

- `absence_signal` (X87 pending): Signal from absence.
  Claim: Absence of signal IS the signal.
  First test: signal_absence_period * return as signal.
  Why cosmic: Absence as presence.

- `negative_space` (X88 pending): Negative space trading.
  Claim: "Negative" price space (below zero) matters.
  First test: negative_space_analysis as signal.
  Why cosmic: Negative space in price.

- `emptiness_as_creator` (X89 pending): Emptiness creates.
  Claim: Market "emptiness" (low participation) paradoxically creates opportunity.
  First test: emptiness_measure * opportunity_signal as signal.
  Why cosmic: Emptiness as creator.

- `nothingness_boundary` (X90 pending): Boundary of nothing.
  Claim: There's a boundary where "something" becomes "nothing."
  First test: boundary_proximity * state_change as signal.
  Why cosmic: Nothing/something boundary.

### Transcendence (X91-X95)

- `market_enlightenment` (X91 pending): enlightenment event.
  Claim: Market "enlightenment" → no more price movement.
  First test: enlightenment_indicator * subsequent_volatility.
  Why cosmic: Enlightenment in markets.

- `egodeath_trading` (X92 pending): Trader ego death.
  Claim: At ego-death, traders "become" market; lose individual identity.
  First test: ego_collapse_indicator * behavior_change as signal.
  Why cosmic: Ego death as trading state.

- `unity_perception` (X93 pending): All-is-one perception.
  Claim: At extremes, all tickers perceived as ONE.
  First test: unity_measure * correlation Explosion as signal.
  Why cosmic: Unity consciousness in markets.

- `infinite_patience` (X94 pending): Infinite time horizon.
  Claim: Some traders operate at infinite time horizon.
  First test: infinite_time_trader_presence * price_path as signal.
  Why cosmic: Infinite patience trading.

- `market_satori` (X95 pending): Satori (sudden enlightenment).
  Claim: Market "satori" = sudden fundamental revaluation.
  First test: satori_trigger_conditions * revaluation_magnitude as signal.
  Why cosmic: Satori as market event.

### Divine / Mythological (X96-X100)

- `karmic_debt_offset` (X96 pending): Karma in markets.
  Claim: Past losses create "karmic debt" that must be repaid.
  First test: cumulative_loss * subsequent_gain_probability as signal.
  Why cosmic: Karma as mechanism.

- `dharma_cycle` (X97 pending): Dharma (duty) cycles.
  Claim: Each ticker has "dharma" (essential nature); cycles of duty.
  First test: dharma_cycle_phase * price_action as signal.
  Why cosmic: Dharma as cycle driver.

- `rita_order` (X98 pending): Cosmic order (Rita).
  Claim: Underlying cosmic order governs price; breaking = correction.
  First test: rita_violation * correction_magnitude as signal.
  Why cosmic: Rita as market law.

- `prana_flow` (X99 pending): Prana (life force) in capital.
  Claim: Capital has "life force"; flows between tickers.
  First test: prana_flow_indicator * price_movement as signal.
  Why cosmic: Prana as market flow.

- `atman_acceleration` (X100 pending): Atman (soul) in price.
  Claim: Price contains "soul" (inner essence); actions on soul drive price.
  First test: atman_presence * price_action as signal.
  Why cosmic: Soul in price action.

## Stochastic Resonance & Noise (X51-X55)

- `fibonacci_tick_liquidity_trap` (X51 pending): Whole-number price proximity.
  Claim: Retail stop-loss clusters at whole/half-integer levels. C16 stronger when price within 0.618% of whole number.
  Test: IC(C16) vs distance_to_whole_number.

- `fourier_ghost_cycles` (X52 pending): Hidden heartbeat frequency.
  Claim: C16 works 2x better at specific cycle frequency (3.5 or 7 days).
  Test: FFT on C16 daily IC, filter by peak frequency alignment.

- `order_flow_cavitation` (X53 pending): Vacuum effect under high pressure.
  Claim: High C16 + stagnant price = liquidity vacuum = next-day gap-up.
  Test: C16>90th + price_move<10th percentile → next-day return.

- `braid_divergence` (X54 pending): Signal unanimity across brokers.
  Claim: Sector-wide pressure unanimity (low kurtosis) = robust signal.
  Test: C16 kurtosis across sector contributors vs win rate.

- `lempel_ziv_complexity` (X55 pending): Tape complexity filter.
  Claim: C16 stronger when tape is repetitive (low complexity).
  Test: C16 IC in bottom complexity decile vs top.

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
