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

- C16 enhancement discoveries (S220-S231): 
  - Liquid filter (C16>50% + move>80%) = +15% IC boost in WF (X53).
  - C16 is CONTRARIAN: works +22% better in DOWN markets in WF (X226).
  - C16 divergence: price vs C16 direction disagreement = +39% IC boost (X228).
  - **Triple Storm: liquid + down + divergence = +92% IC boost in WF (X229, X231)**!
  - **HOLDOUT CONFIRMED: +111% boost (X230)**!
  - **WALK-FORWARD VERIFIED: 9/9 years positive (X231)**!
  - **Triple Storm EXTENSIONS (S232)**: Universal amplifier!
    - Works: C16 (+104%), S1 (+90%), volume (+38%), reversal (+60%), skewness (+)
    - NOT work: foreign_flow, sector_rotation (position signals stay negative)
    - Mechanism: amplifies ANOMALY/MICROSTRUCTURE signals, not position signals
  - **Combo discoveries (S234)**:
    - c13_c16_combo: +9% over C16 alone (best orthogonal combo)
    - volume_shock_c16: +16% boost (volume anomaly amplifies C16)
  - **S235 new findings**:
    - C16 entry timing: decays fast - T+0 is optimal (T+1 drops 74%)
    - vnindex_momentum: C16 +15% better when index momentum negative
    - news_c16_divergence: FAILED (sentiment too weak)
  - **S238 new findings**:
    - market_breadth: A/D Q1-Q2 +30% better than Q4-Q5 (contrarian breadth)
    - quarter_start: +26% (NEW!), quarter_end: -15% (institutional pump is noise)
    - price_tier: weak +13%
  - **S242 new findings**:
    - january_first_10: +5% IC boost (NEW!)
    - volume regime: high volume = +21% boost, low volume = -11% (confirmed S237)
  - Reusable script: x240_wf_ic_test.py
  - **Key mechanism**: Quarter START beats END - opposite of Western效应!
  Source anchors: Sessions 220, 226, 228, 229, 230, 231, 232, 234, 235, 236, 237, 238.

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
  broad raw attention proxies did not stabilize an event-v2 router. Source anchors:
  `F204`, `F213-F215`, `F237`.

- Event-v2 source work reopened a real sparse timing branch: richer CafeF
  event-v2 mapping improved source quality, same-day first-public and
  low-repeat states survived as sparse evidence, and H321 found a self-exciting
  cascade state. Additive integration, entry-label transfer, payoff-shape
  promotion, and portfolio sparse-clock rescue then failed. Source anchors:
  `F222-F241`, `F289`, `F292`, `F302`.

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
  full-field local replacement. Source anchors: `F274`, `F282-F283`.

## Maintenance Rule

- When a future session promotes a durable finding, update the source
  `findings-*.md` chunk first. Then update this compact file only if the new
  finding changes one of the grouped themes or creates a new theme.
