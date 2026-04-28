# Dead Ends Compact

What this file is for: compact recovery notes for durable failed, parked,
closed, blocked, or explicitly non-promotable paths. These entries are derived
from the chunked findings and session logs because the repo does not currently
maintain separate durable dead-end chunk files.

Do not add a path here just because one test was mixed. Add it when the durable
record says the current path should stop, stay parked, or reopen only under a
specified changed condition. Keep links to source `F` IDs so the original
evidence remains traceable. Every compact dead-end entry must include source
anchors: stable dead-end IDs, finding IDs, or source session links.

## Current Hard Stops

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
