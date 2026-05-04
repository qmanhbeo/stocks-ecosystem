# Findings Compact

What this file is for: compact full-history recovery notes for durable
findings. It is a thematic digest of [findings.md](./findings.md) and the
chunked `findings-*.md` files, not the append-only source of truth.

Update this file only when a new durable finding changes a theme, creates a new
theme, or materially changes the current read of an existing theme. Keep entries
grouped by idea, not one line per finding. Existing finding labels have legacy
gaps and duplicates; the chunk files remain canonical. Every compact finding
entry must include source anchors: stable finding IDs or source session links.

## Current Read

- Live/research posture: the active live branch remains the frozen sticky
  selector lineage, while research is local-news, data-acquisition, and
  side-channel driven rather than live-branch retuning. Source anchors: `F117-F143`,
  `F155-F156`, `F271-F283`, `F296-F303`.

- Best currently published side-channel promotion: C16 scoped CafeF order
  pressure is a shared opt-in feature contract. H356-H360 show strong standalone
  IC, residual selector value, bounded executable uplift, publication, and
  published-contract parity. Source anchors: `F296-F301`.

- Insider/weakness interactions: H387 rejected the insider-down rescue overlay.
  Positive insider plus stock weakness plus high C16 beat ordinary insider rows
  but failed the stronger insider-C16 and stock-down-C16 controls; stock-down
  high-C16 remained the cleaner control state. Source anchors: `F348`, `D005`.

- Calendar/timing context: old calendar filters remain useful as context, but
  H390 parks exact-state calendar promotion under the current target. Exact
  `monday_jan_combo` retained a 1d residual C16-IC lift after mechanism
  controls, but it was only one active test date per evaluated year, had only
  `2 / 4` positive 1d residual-lift years, and had negative mean 5d residual
  lift; `quarter_start` and late quarter-month timing did not retain positive
  1d residual lift. Source anchors: `F351`, `D008`.

- Tradability-release context: H391 rejected the current entry-panel
  `release_flag` as a `wait_release` buy signal. Top-5/top-10 rows becoming
  buyable after prior blocked-buy states had negative cycle relative returns,
  negative same-rank matched-control lifts, weak 2025 confirmation, and weaker
  sellability health than stable buyable controls. Source anchors: `F352`,
  `D009`.

- Source-triangle context: H392 rejected the C16+insider+news core under the
  current C5/PhoBERT representation. `c16_insider_any_news` was positive but
  lost to both C16+insider-without-news and C16+news-without-insider controls;
  the broader `three_plus_sensors` pocket beat exactly-two sensors, suggesting
  the live clue is a non-insider C16+source+forward news pocket, not an
  insider-confirmed triangle. Source anchors: `F353`, `D010`.

- Capitulation context: H393 found high C16 after stock and market weakness
  without bullish news is positive, but not better than the simpler
  `stock_down_high_c16` control. Stock-down high-C16 remains the cleaner
  hidden-support state; same-day no-bullish-news/market-down additions are
  parked unless a weak-active-news or intraday absorption contract is opened.
  Source anchors: `F354`, `D011`.

- Local-news status: the blocked Ollama residual backfill is complete and H364
  produced the first combined local-news pass. The current anchor is
  `h364_official_sentiment_x_earnings_guidance`, with avg IC `+0.01766`,
  dev/validation/confirmation IC `+0.0173 / +0.0200 / +0.0156`, `10 / 10`
  positive years, and S1 corr `-0.0104`. This is candidate/offline evidence
  but H382 narrowed its consumer status: same-support active-news ranking passed
  random-active, while broad candidate-pool allocation failed random-all. H383
  then confirmed the broader interaction mechanism: C16 is stronger when
  own-ticker news is active, and `active_news_strong_flow` /
  `positive_news_strong_flow` are confirmation states, not disagreement states.
  H384 then rejected those H383 states as candidate-pool allocators under
  random same-support and random-all policy benchmarks. H385 then confirmed a
  different local-news mechanism: official/regulatory or forward-looking rows
  need C16 or insider support and pay with delay; `official_supported` and
  `official_forward_supported` had 5d lifts around `+0.0074` to `+0.0077`
  versus unsupported controls with `8 / 8` positive years. H386 then rejected
  those states as candidate-pool allocators under deterministic candidate-rank
  selection and random same-support/random-all policy benchmarks. Source
  anchors: `F342-F347`, `D002-D004`.

## Reference Baselines (Walk-Forward IC)
- Random: ~0.00 (noise benchmark)
- C16: +0.078 (order pressure)
- S1: +0.149 (best published - PRIMARY for RL)

## Reference Baselines (Walk-Forward IC)
- Random: ~0.00 (noise benchmark)
- C16: +0.078 (order pressure)
- S1: +0.149 (best published - PRIMARY for RL)

## All Real Signals for RL (IC > 0.05 vs Random)

### Tier 1: Primary Signals (IC > 0.10)
| Signal | IC | vs Random | Use |
|--------|-----|---------|-----|
| **S1 (xs_proba)** | 0.149 | +0.15 | **BEST - PRIMARY** |
| **Triple Storm** | 0.158 | +0.16 | liquid+down+divergence boost |
| monday_jan_combo | 0.1109 | +0.11 | raw calendar combo; exact promotion parked by H390 |
| X53 (Liquid C16) | 0.137 | +0.14 | C16 + liquidity filter |

### Tier 2: Enhancement Filters (IC 0.08-0.10)
| Signal | IC | vs Random | Use |
|--------|-----|---------|-----|
| C16 divergence | 0.108 | +0.11 | price vs C16 disagreement |
| quarter_start | 0.098 | +0.10 | raw timing filter; exact promotion parked by H390 |
| market_breadth A/D Q1 | 0.093 | +0.09 | breadth filter |
| vol_high | 0.0941 | +0.09 | volume regime filter |
| X54 (Braid) | 0.080 | +0.08 | sector unanimity |
| C16 baseline | 0.078 | +0.08 | order pressure |
| february_mid | 0.0858 | +0.09 | calendar |
| march_late | 0.0833 | +0.08 | calendar |
| monday | 0.0836 | +0.08 | calendar |
| october | 0.0817 | +0.08 | calendar |
| january_first_10 | 0.0817 | +0.08 | calendar |

### Tier 3: Weak/Contextual (IC 0.05-0.08)
| Signal | IC | vs Random | Use |
|--------|-----|---------|-----|
| rank_time_acceleration | 0.0576 | +0.06 | independent state feature |
| vol_low | 0.0695 | +0.07 | volume regime (inverse) |
| yearend | 0.0652 | +0.07 | weak calendar |
| midyear | 0.0711 | +0.07 | failed |

### S244 New Signals (independent vs Random)
| Signal | IC | vs Random | Verdict |
|--------|-----|---------|--------|
| insider_buy_lead | 0.1113 | +0.11 | REAL (+40% boost) |
| consecutive_down_days | 0.1030 | +0.10 | REAL - filter |
| dividend_30d | 0.0934 | +0.09 | REAL - event driver |
| rank_time_acceleration | 0.0576 | +0.06 | REAL - state feature |

### S245-S247 C16 Contrarian Signals
| Signal | IC | vs Baseline | Verdict |
|--------|-----|-------------|--------|
| down_market_c16 | +0.098 | +26% | **REAL** - TIER 2 |
| deep_down_c16 | +0.093 | +20% | **REAL** - TIER 2 |
| sector_pressure_momentum | +0.078 | +0% | FAILED |

### S248-S252 Bright-Mind Failed
| Signal | IC | vs Baseline | Verdict |
|--------|-----|-------------|--------|
| macro_c16_regime | +0.077 | +0% | FAILED |
| gap_open_c16 | +0.075 | -4% | FAILED |
| consecutive_down | +0.078 | +0% | FAILED |
| c16_extreme_down | +0.028 | -63% | FAILED (sparse) |
| c16_entropy | ~0.08 | ~0.08 | WEAK - dead end |

### S253 TRUE Walk-Forward Validation (IC > 0.05)
| Signal | True WF IC | Std | Verdict |
|--------|-----------|-----|--------|
| insider_lead | 0.1093 | 0.036 | **REAL** ✅ |
| consecutive_down | 0.1047 | 0.011 | **REAL** ✅ |
| down_market_c16 | 0.0992 | 0.007 | **REAL** ✅ |

## All Real Signals for RL (IC > 0.05 vs Random) — Complete Inventory

### Tier 1: Primary Signals (IC > 0.10)
| Signal | IC | vs Random | Type |
|--------|-----|---------|------|
| S1 (xs_proba) | 0.149 | +0.15 | PRIMARY |
| Triple Storm | 0.158 | +0.16 | enhancement |
| monday_jan_combo | 0.1109 | +0.11 | raw calendar combo; exact promotion parked by H390 |
| X53 (Liquid C16) | 0.137 | +0.14 | liquidity filter |
| consecutive_down_days | 0.1030 | +0.10 | market streak |
| **insider_buy_lead** | **0.1113** | **+0.11** | **insider lead** |

### Tier 2: Enhancement/Filters (IC 0.08-0.10)
| Signal | IC | vs Random | Type |
|--------|-----|---------|------|
| C16 divergence | 0.108 | +0.11 | price disagreement |
| quarter_start | 0.098 | +0.10 | raw timing; exact promotion parked by H390 |
| dividend_30d | 0.0934 | +0.09 | event driver |
| market_breadth A/D Q1 | 0.093 | +0.09 | breadth filter |
| vol_high | 0.0941 | +0.09 | volume regime |
| february_mid | 0.0858 | +0.09 | calendar |
| march_late | 0.0833 | +0.08 | calendar |
| monday | 0.0836 | +0.08 | calendar |
| october | 0.0817 | +0.08 | calendar |
| january_first_10 | 0.0817 | +0.08 | calendar |

### Tier 3: State Features (IC 0.05-0.08)
| Signal | IC | vs Random | Type |
|--------|-----|---------|------|
| rank_time_acceleration | 0.0576 | +0.06 | state feature |
| X54 (Braid) | 0.080 | +0.08 | sector filter |
| C16 baseline | 0.078 | +0.08 | order pressure |
| vol_low | 0.0695 | +0.07 | volume regime |
| yearend | 0.0652 | +0.07 | calendar |
| midyear | 0.0711 | +0.07 | calendar |

### Key RL Use Cases
1. **Primary signal**: S1 (0.149)
2. **Enhancement filters**: vol_high, monday_jan, divergence, liquid, down_market
3. **RL state features**: calendar-day, volume regime, market breadth, quarter timing

Source anchors: Sessions 220, 226, 228, 229, 230, 231, 232, 234, 235, 236, 237, 238, 242, 243.

- Current parked branches: event-v2 sparse-clock, dividend-clock timing,
  legal-holiday timing, standalone foreign/proprietary flow, old OHLCV
  residual queue, and smart-exit ML are parked under the current target/selector
  contracts. Source anchors: `F285-F295`, `F302-F304`.

## Core Signal Lineage

- Early single-stock work established that raw drift and standard OHLCV
  technicals were not enough, while market-relative targets and cross-sectional
  framing created the first durable signal. The signal was strongest when
  evaluated across the VN universe rather than as a narrow FPT-only pattern.
  Source anchors: `F1-F28`.

- The XS momentum/volume lineage converged on a 1-day/5-day barrier family with
  strong cross-sectional rank behavior. H93 became the main promoted RL signal
  surface, while many common additions such as quarterly fundamentals, sector
  relative features, VIX-as-feature, IC filters, and proba momentum did not
  improve the core. Source anchors: `F29-F58`.

- Dense feature exploration created the initial C-signal library: useful axes
  included position-size-normalized insider behavior, intra-sector mean
  reversion, ceiling momentum, volume z-score, Amihud illiquidity, gap
  acceptance, compression blow-off, and residualized H127. Many adjacent raw
  feature families were too weak or redundant. Source anchors: `F59-F90`.

## Portfolio, Execution, And Live Branch

- Portfolio construction and execution reality became first-order constraints:
  simple fixed long-only construction beat early ML selectors, but deployability
  under ADV/capacity gates failed. The repo locked in long-only policy,
  signal-date liquidity alignment, explicit tradability, and no synthetic hedge
  assumptions. Source anchors: `F91-F113`.

- RL comparison set a high bar rather than replacing the deterministic stack:
  same-universe RL had useful comparator value, S1-only RL was interesting but
  seed-unstable, and richer signal sets hurt early portfolio-choice RL. Key
  anchors: `F114-F116`.

- Activation research split the problem into selection alpha versus activation
  alpha. Smoothed selector efficacy became the winning activation mechanism,
  then sticky retention and implementation-pain vetoes improved the historical
  system. The more complex blocked-buy plus sector-cap winner failed
  pseudo-live, so the simpler sticky branch became the credible live branch.
  Source anchors: `F117-F139`.

- The locked anti-leakage protocol is now a durable lab rule: dev `2015-2022`,
  validation `2023-2024`, one-shot confirmation `2025`, and `2026+` as forward
  lockbox/monitor-only unless explicitly allowed. Sequential hypothesis
  ladders became the standard method. Source anchors: `F140`, `F143`.

## Selector And Entry Alpha

- First post-freeze selector discovery found standalone/tradability-conditioned
  atoms, but additive selector promotion mostly failed. The H199 sector-laggard
  gap-absorb family was worth carrying as offline evidence, but stronger
  selection alpha alone did not replace the live branch. Source anchors:
  `F141-F150`.

- Entry-alpha work showed the branch behaves more like a small-book `top1`
  contract than a `top5` timing overlay. Local confirmation, label sharpening,
  sparse catalysts, selector-relative variants, and report-window switchboards
  did not create a live-compatible replacement. Source anchors: `F157-F168`.

- Dynamic candidate breadth now has stronger offline portfolio-policy evidence,
  not a live branch change. H379 showed candidate-panel temperature could route
  K/cash decisions versus random K policies; H380 then narrowed the branch to
  candidate-count-only transforms and passed versus random K/cash policies with
  mean cycle lift `+0.00389`, `4 / 5` years above random K/cash mean, and 2025
  lift `+0.00472`. The durable clue is raw `candidate_count`; it is a
  portfolio-policy state, not a ticker-level signal. H388 then rejected
  long-dormancy fresh reappearance as a candidate-history boost; short-repeat
  controls were stronger than `20+` day fresh returns. Source anchors: `F339`,
  `F340`, `F349`, `D006`.

- Event/reduced-shape timing work found useful narrow evidence but kept
  boundaries tight: CafeF company news was real but sparse, the `1H` intraday
  surface was a reduced-shape research contract, and universal five-bar/auction
  claims remained dishonest. Breakout-entry trust was the strongest relocation
  of reduced-shape intraday evidence. Source anchors: `F169-F180`.

- The breakout/reduced-shape branch produced several narrow offline passes, but
  failed to become a broad operational branch. Survivor/trust gates worked on
  observed sleeves and carried books, then failed current-account compatibility
  or confirmation transportability. Source anchors: `F181-F212`.

## News, Events, And Disclosure Data

- Rebuilt LLM/news surfaces showed real edge only in routed states. Follow-up
  and miss-state news mattered more than pooled simple sentiment, news decay
  was real but not clean as a single-class half-life, and market-attention or
  broad raw attention proxies did not stabilize an event-v2 router. H381 killed
  the simple no-news C16 stealth thesis under current PhoBERT article counts:
  active-news C16 was stronger than no-news C16, so the next route is
  text-flow disagreement / confirmation, not "absence of own news" by itself.
  Source anchors: `F204`, `F213-F215`, `F237`, `F341`, `D001`.

- Event-v2 source work reopened a real sparse timing branch: richer CafeF
  event-v2 mapping improved source quality, same-day first-public and
  low-repeat states survived as sparse evidence, and H321 found a self-exciting
  cascade state. Additive integration, entry-label transfer, payoff-shape
  promotion, portfolio sparse-clock rescue, and the guarded-Ollama
  first/repeat/family-transition reopening test then failed. Source anchors:
  `F222-F241`, `F289`, `F292`, `F302`, `F350`, `D007`.

- Official-disclosure and HNX work is source-first, not alpha-ready: official
  disclosure timing, HNX transfer, and the current HNX disclosure history remain
  data-blocked for the HOSE matrix until broader history or a HOSE/HSX bridge
  exists. Source anchors: `F235`, `F290`.

- Public-investment and lexical/news surrogate attempts recovered pieces of
  structure but did not produce promoted routers or preserve the desired
  short-horizon authority/novelty contracts. Source anchors: `F242`, `F249-F252`.

## Flow, Order Stats, And Daily Side Channels

- Historical foreign-flow source availability changed over time: vnstock lacked
  usable historical daily foreign flow, CafeF later exposed a real archive, and
  the source passed acquisition audit. Raw ranks, room scarcity, residual
  discontinuities, accumulation/change-points, foreign-insider agreement,
  proprietary-flow agreement/conflict, and sector ownership pressure did not
  create a promoted standalone branch. Source anchors: `F59`, `F243-F248`, `F253`,
  `F285`, `F287-F291`.

- CafeF order-statistics and proprietary-trading surfaces reopened daily
  side-channel research but not true queue/open-fill research. H340 established
  same-day buy-volume pressure as a strong C5 rewrite, H341 showed exec-rate
  stacking was redundant, and H356-H360 promoted the broader C16 scoped
  order-pressure contract. Source anchors: `F260-F263`, `F296-F301`.

- True historical queue/depth remains outside the current local stack. The
  practical maximum is daily side channels plus reduced-shape intraday unless
  forward collection matures or a paid vendor supplies queue/order-book history.
  Source anchors: `F244`, `F260-F261`.

## Exit Alpha And Calendar Timing

- Early exit work closed generic continuation/hold-vs-exit and event-surface
  exit branches on current data. Timing research then moved to data acquisition
  first rather than more local rule tuning. Source anchors: `F151-F156`.

- Legal-exit oracle work showed upper-bound value, but simple hold/sell
  MDP-lite, entry-time horizon routing, H337/H338/H339 smart-exit variants, and
  later order-pressure post-entry state did not learn enough of the rare
  profitable continuation pockets. Source anchors: `F254-F259`, `F295`.

- Dividend/calendar research remains offline context only: the old broad
  dividend-calendar model input failed, H354 found a small pre-ex payoff hint,
  and H362 failed the executable sparse-clock portfolio rescue. H363 then found
  one legal-holiday post-5 top-book payoff hint, but the fixed `+0.015`
  sparse portfolio bonus had `0.00% / 0.00%` validation/confirmation relative
  deltas and failed the portfolio gate. Source anchors: `F294`, `F303-F304`.

## Local ML, Data Pipelines, And Operator Rules

- Low-resource local-ML is now an explicit contract: plan against `3GB VRAM /
  10GB RAM`, keep heavy local jobs observable and restart-safe, fail fast when
  CUDA is hidden on the WSL box, and avoid broad parallel local-model work while
  the Ollama residual backfill is active. Source anchors: `F271-F283`.

- PhoBERT is the primary local-news production lane. The repo now has
  forward-looking, sentiment, article-scope, and source-type head paths, with
  calibrated binary thresholds, task-appropriate split contracts,
  checkpointed publish, and repo-level offline runtime guards. Source anchors:
  `F271`, `F274-F281`, `F284`.

- The default Ollama residual lane is intentionally narrow: event-family-only,
  BERT-gated, score-cached, and residual to PhoBERT rather than a broad
  full-field local replacement. The first completed backfill enabled H364, where
  official/regulatory source probability, sentiment, and Ollama
  earnings/guidance agreement passed the standalone local-news gate. H382 says
  the feature is an event-subset ranker, not a broad candidate allocator. Source
  anchors: `F274`, `F282-F283`, `F342-F343`, `D002`.

## Maintenance Rule

- When a future session promotes a durable finding, update the source
  `findings-*.md` chunk first. Then update this compact file only if the new
  finding changes one of the grouped themes or creates a new theme.
