# Dead Ends Compact

What this file is for: compact recovery notes for durable failed, parked,
closed, blocked, or explicitly non-promotable paths. The chunked source of
truth now starts at [deadends.md](./deadends.md); older entries before that
index are derived from chunked findings and session logs.

Do not add a path here just because one test was mixed. Add it when the durable
record says the current path should stop, stay parked, or reopen only under a
specified changed condition. Keep links to source `F` IDs so the original
evidence remains traceable. Every compact dead-end entry must include source
anchors: stable dead-end IDs, finding IDs, or source session links.

## Resolution: Methodology Skepticism

- S253 TRUE walk-forward validation: CONFIRMED signals are REAL.
  All 3 top signals passed stricter rolling holdout validation.
  Low variance = no overfitting.
  Source: F337, F338

## Current Hard Stops

- Same-day nihilist reversal is parked. H393 found high C16 after stock and
  market weakness with no bullish news was positive, but it failed the simpler
  `stock_down_high_c16` control by `-0.00203` mean 5d lift and had negative
  2025 payoff. Reopen only with a predeclared weak-active-news subset,
  intraday absorption after capitulation, or a delayed re-entry consumer.
  Source anchors: `D011`, `F354`.

- C16+insider+news source-triangle promotion is parked under the current
  representation. H392 found `c16_insider_any_news` had positive mean 5d
  payoff, but lost to C16+insider-without-news and C16+news-without-insider
  controls, and 2025 lift versus exactly-two sensors was negative. The broader
  `three_plus_sensors` clue should be reopened only as a predeclared
  non-insider C16+source+forward news pocket or with materially different
  insider-quality data. Source anchors: `D010`, `F353`.

- Entry-panel tradability release is killed under the current cycle-label
  target. H391 found top-5/top-10 rows that became buyable after a prior
  blocked-buy state were negative and weaker than same-rank stable/non-release
  buyable controls (`top5_release` matched lift `-0.03367`, 2025 lift
  `-0.08011`; `top10_release` matched lift `-0.02837`, 2025 lift `-0.06630`).
  Reopen only with order-book queue/open-fill data, intraday post-release
  absorption, or a fixed wait-for-reblock/sellability-normalization contract.
  Source anchors: `D009`, `F352`.

- Calendar mechanism promotion is parked under the current target. H390 found
  exact `monday_jan_combo` retained 1d residual C16-IC lift after mechanism
  controls, but the state was only one active date per evaluated year, had
  only `2 / 4` positive 1d residual-lift years, and had negative mean 5d
  residual lift; `quarter_start` and late quarter-month timing did not retain
  positive 1d residual lift. Reopen only with a broader predeclared
  January/weekday contract, a different execution/5d target, or a downstream
  mechanism-matched consumer. Source anchors: `D008`, `F351`.

- Guarded-Ollama event cascade does not reopen event timing. H389 found the
  best state, `event_first20`, had mean 5d lift only `+0.00099` versus generic
  event and `+0.00114` versus repeat event, below the reopening gate; transition
  and family pockets were weaker. Keep event timing parked unless the target,
  source timestamping, or downstream consumer changes. Source anchors: `D007`,
  `F350`.

- Long-dormancy fresh selection is killed under the current entry-alpha
  candidate-history representation. H388 found `top5_fresh20` beat incumbents
  but failed stale-repeat control (mean lift `-0.00016`, 2025 lift
  `-0.00269`), and `top10_fresh20` failed stale-repeat control too. Reopen only
  with a materially different short-repeat, rank-transition, or portfolio
  policy contract. Source anchors: `D006`, `F349`.

- Insider-down rescue is killed under the current C5/stock-down/high-C16
  representation. H387 found `insider_down_high_c16` beat ordinary insider
  rows but failed the meaningful high-C16 controls: mean 5d lift was only
  `+0.00087` versus `insider_high_c16` and `-0.00308` versus
  `stock_down_high_c16`, with negative 2025 lifts versus both. Reopen only
  with materially different insider event-quality or timing data. Source
  anchors: `D005`, `F348`.

- H385 official-delay consumer promotion is parked. H385 passed as offline
  delayed-payoff evidence, but H386 failed the fixed candidate-policy
  follow-through: `official_supported` mean lift was `-0.00035` versus
  random-state and `-0.00540` versus random-all; `official_forward_supported`
  mean lift was `-0.00057` versus random-state and `-0.00555` versus
  random-all. Use H385 as delayed official-attention context, not as a broad
  allocator. Source anchors: `D004`, `F346-F347`.

- H383 active/positive-news strong-flow consumer promotion is parked. H383
  passed as offline IC evidence, but H384 failed the fixed candidate-policy
  follow-through: `active_news_strong_flow` mean lift was `-0.00026` versus
  random-state and `-0.00337` versus random-all; `positive_news_strong_flow`
  mean lift was `-0.00020` versus random-state and `-0.00191` versus
  random-all. Use H383 as context, not as a broad allocator. Source anchors:
  `D003`, `F344-F345`.

- H364 broad candidate-pool consumer promotion is parked. H382 passed only the
  same-support active-news random benchmark (`+0.00092` mean lift,
  `4 / 5` years above random-active mean) but failed broad random-all
  allocation (`-0.00367` mean lift, `1 / 5` years above random-all mean).
  Use H364 as an event-subset ranker or interaction anchor, not as a broad
  portfolio allocator. Source anchors: `D002`, `F343`.

- Silent order pressure is killed under the current own-ticker PhoBERT
  article-count proxy. H381 found no-news C16 weaker than all-C16 and
  active-news C16: `silent_5d` WF IC `+0.0700` versus all-C16 `+0.0752` and
  active-5d-news C16 `+0.0846`. Reopen only with a materially different
  "not public yet" representation, such as Ollama event-family states,
  peer/co-mention narrative vacuum, source-type timing, or another non-count
  proxy. Source anchors: `D001`, `F341`.

- S244 weak/inconsistent signals:
  - c16_entropy: WEAK (inconsistent year-to-year) - dead end
  - disclosure_shock_reaction: NO DATA - blocked (empty source)
  Source: [session_244_log.md](./session_244_log.md)

- Event-v2 timing is parked under the current executable top-5 selector:
  H321 remains offline sparse evidence, but additive integration, entry-label
  transfer, payoff-shape promotion, and sparse-clock portfolio rescue all
  failed. Reopen only with new event data, a materially different target, or a
  downstream consumer contract that is not the current selector. Source anchors:
  `F241`, `F289`, `F292`, `F302`.

- Dividend-clock timing is parked: broad calendar model inputs failed, the
  pre-ex payoff hint was too small, and the fixed sparse-clock portfolio bonus
  failed validation. Reopen only with a different calendar target or downstream
  consumer contract. Source anchors: `F294`, `F303`.

- Legal public-holiday timing is parked under the current executable top-5
  selector: H363 found a clean `all_holidays__post_5` top-book payoff hint, but
  the required fixed sparse-clock portfolio bonus did not change validation or
  confirmation relative returns. Do not tune more holiday offsets, closure
  gates, bonus sizes, or veto variants unless the target or downstream consumer
  contract changes. Source anchors: `F304`.

- Standalone foreign/proprietary flow is parked on current data: raw CafeF
  foreign-flow ranks, room scarcity, residual discontinuities,
  accumulation/change-points, foreign-C5 agreement, proprietary agreement or
  conflict, and sector ownership pressure all failed promotion. Reopen only
  with a materially different data source, target, or interaction contract.
  Source anchors: `F247-F248`, `F253`, `F285`, `F287-F291`.

- Smart-exit ML is parked until richer post-entry state or a different model
  contract exists. The legal-exit oracle has upper-bound value, but simple
  hold/sell, entry-time horizon routing, replacement-aware and skip-aware
  variants, and order-pressure post-entry state did not learn enough of the
  rare continuation pockets. Source anchors: `F151-F154`, `F254-F259`, `F295`.

- Old OHLCV residual queue items H135/H136/H137 are closed under the current
  contract. Do not rerun gap/compression/long-horizon residual variants unless
  a new target, execution contract, or non-price state changes the meaning of
  C11/C13 residuals. Source anchors: `F206-F207`, `F286`.

## Signal And Feature Dead Ends

- Standard OHLCV technical analysis and extended raw OHLCV feature additions
  did not create edge in the early single-stock setup; later common variants
  such as proba momentum, VIX-as-feature, IC stability filters, sector-relative
  additions, and raw quarterly fundamentals did not improve the promoted XS
  model stack. Source anchors: `F2`, `F5`, `F23`, `F36`, `F40`, `F42-F43`, `F57`.

- C16 stacking filters (S221): Combining liquid + braid/sector filters OVERFILTERS,
  reducing sample below statistical validity. Stacking hurts: IC -18% vs baseline.
  Source anchors: Session 221.

- C16 sector-relative adjustment (S224): Subtract sector median to remove sector bias
  HURTS signal: -15% IC. Keep absolute C16. Source: Session 224.

- C16 persistence (S225): Yesterday's pressure confirming today's doesn't help.
  IC -17%. Source: Session 225.

- Rank time acceleration (S244): Rank velocity WORSE than rank level.
  IC 0.0576 vs baseline 0.0778 (-26%). All 8 years negative delta.
  Confirms: level > velocity pattern (same as C16 ROC failure S227).
  Source: session_244_log.md

## Bright-Mind Failed Experiments (S248-S252)

- macro_c16_regime (S248): Macro VIX regime doesn't condition C16.
  IC +0.078 BULL vs +0.077 BEAR (+0%) - no boost.
  Source: F332

- gap_open_c16 (S249): Previous day's return direction doesn't help C16.
  IC +0.075 gap positive vs +0.079 none (-4%) - no boost.
  Source: F333

- vol_shock_c16 (S250): Volume shock proxy insufficient data.
  Could not compute meaningful volume signal.
  Source: F334

- consecutive_down_c16 (S251): Day 2/3 streak doesn't compound.
  IC +0.078 day1 = day2 = day3 (0%) - no compounding.
  Source: F335

- c16_extreme_down (S252): Very high C16 (>0.9) too sparse.
  IC +0.028 vs +0.078 baseline (-63%) - signal lost.
  Source: F336

- News keyword and simple pooled sentiment paths are not enough by themselves:
  keyword sentiment added no IC, rolling aggregation did not fix sparsity,
  body-text ticker extraction hurt quality, the keyword lexicon path was
  exhausted, and simple LLM/PhoBERT pooled sentiment did not clear standalone
  promotion. Source anchors: `F60`, `F63-F65`, `F204`, `F284`.

- Earnings quality, VN30 rebalancing proximity, Corwin-Schultz spread proxy,
  raw return skewness, and several dense calendar/earnings features failed
  standalone or risk-adjusted bars. Source anchors: `F70-F71`, `F76`, `F78`,
  `F83-F84`.

- Sector and ownership routing mostly failed after the core library was known:
  sector sub-models underperformed pooled models, sector conditioning did not
  rescue compression blow-off, sector-level foreign pressure failed, and
  H319/H320 style ownership/criticality routers did not beat simpler controls.
  Source anchors: `F61`, `F207`, `F238-F239`, `F291`.

## Portfolio And Execution Dead Ends

- Retail-scale deployability is not solved by simple construction changes:
  ADV floors and participation caps broke the long-only edge, soft
  tradability-aware scoring did not create a viable retail region, multi-day
  entry slicing did not rescue benchmark-relative economics, and variable
  breadth failed after liquidity gating. Source anchors: `F91`, `F97`, `F100-F101`,
  `F103-F106`, `F108-F109`, `F113`.

- Early ML-style construction selection did not survive honest walk-forward.
  Fixed simple constructions and later selector-efficacy activation were more
  credible than broad model-selection meta-rules. Source anchors: `F95-F96`, `F118`,
  `F120`.

- Complexity around the activation champion mostly failed: three-state sizing,
  walk-forward rule selection, compact meta-models, local guards, exposure
  sizing, basket-coherence guards, and sticky-plus-sector stacking did not beat
  the simpler champion branch. Source anchors: `F122`, `F125`, `F130-F133`, `F138`.

- The complex `blocked5<=q80 + sector_cap_3` historical winner is not the live
  branch because it failed expanding-train/next-year pseudo-live testing. Use
  the simpler sticky branch unless a new locked protocol changes the evidence.
  Source anchors: `F137-F139`.

## Selector, Entry, And Intraday Dead Ends

- The first post-freeze additive selector path closed: H151 failed, H152 atoms
  did not survive selector-level promotion, and later H203/H204 selector
  discovery exhausted the current ladder. Source anchors: `F141`, `F144`, `F147-F149`.

- Entry-alpha remains parked as a small-book offline branch. Small-book
  contracts, local confirmation/calibration, label sharpening, sparse catalysts,
  selector-relative rescue, report-window switchboards, contradiction overlays,
  and dynamic breadth did not create a live-compatible replacement. Source anchors:
  `F157-F168`.

- Generic continuation/exit timing rules failed before deterministic
  integration, and event/corporate surfaces did not create useful continuation
  or exit signals under the locked protocol. Source anchors: `F151-F155`, `F174`,
  `F177-F178`.

- Reduced-shape intraday produced useful narrow evidence but is not a universal
  branch. Top-k stress routing, event-conditioned disagreement, strict
  confirmation split, and current-account compatibility checks failed enough
  that the surviving evidence must stay sleeve-specific. Source anchors:
  `F185-F196`, `F199-F203`, `F209-F212`.

## Data-Availability Dead Ends And Blocks

- True historical queue/open-fill alpha remains source-blocked locally.
  Current open data supports daily side channels and reduced-shape intraday,
  not historical order-book depth or a universal queue artifact. Source anchors:
  `F244`, `F260-F261`.

- HNX official disclosures are wired but not yet a usable HOSE historical
  bridge. Do not run disclosure alpha IC until broader history or a HOSE/HSX
  official source exists. Source anchors: `F235`, `F290`.

- Public-investment and several news-surrogate routes recovered structure but
  did not create promoted routers: beneficiary routing, title-sequence novelty,
  hybrid novelty cascade, lexical event-family routing, and surrogate
  disagreement tail all missed their promotion contracts. Source anchors:
  `F242`, `F249-F252`.

- Local full-schema Ollama replacement is not the default path. The durable
  local-news architecture is PhoBERT-first plus a narrow event-family Ollama
  residual; broad generator fields remain optional diagnostics. Source anchors:
  `F274`, `F282-F283`.

## Maintenance Rule

- When future findings close or park a branch, update the source
  `findings-*.md` chunk first. Add or adjust this compact file only when the
  result should prevent future rediscovery or materially changes a reopening
  condition.
