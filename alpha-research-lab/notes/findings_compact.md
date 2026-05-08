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

- S24x/S25x methodology correction: S272 supersedes the old S253
  "skepticism resolved" note. `actual` in the S1 parquet is a future binary
  barrier label, so S244/S246/S247/S253 market-down and consecutive-down
  states were partly target-derived. Correct observable VNI-down states are
  only modest C16 context (`+0.0771` / `+0.0806` avg IC versus C16 `+0.0738`),
  and observable stock-down states are weaker than C16. `insider_buy_lead`
  survives as real support context (`+0.1050`, `11 / 11` positive years);
  high buy-order-count volume context is modest (`+0.0844`). Do not promote
  S244 `consecutive_down`, target-derived `down_market_c16`, or
  `deep_down_c16`. Source anchors: `F355`, `D012`.

- Insider event-time clock: H398 independently reproduced the S272 positive
  insider lead. `insider_tplus1` reached avg C16 IC `+0.10498`, `11 / 11`
  positive years, and `+0.03000` lift versus same-ticker non-event dates; T0
  was also strong at `+0.10816`. The quiet pre-reaction thesis failed:
  reacted T+1 rows beat pre-reaction by `+0.01811` avg IC, and high buy-order-
  count T+1 rows were the strongest rank-quality pocket (`+0.13776` avg IC).
  Keep insider lead; park the current no-news/no-high-count pre-reaction
  variant. Source anchors: `F362`, `D014`.

- Crowd-count context: H399 says high buy-order count is a modest conditioner,
  not a signal. `buy_count_rank` was anti-predictive (`-0.01075`, `3 / 8`
  positive years); `high_buy_count` improved C16 IC only to `+0.08463`
  (`+0.00944` lift versus all rows). The clean pocket was C8 high volume-z
  (`+0.10258`, `8 / 8`), and high count added almost nothing on top. The best
  real crowd clue was `count_high_size_weather_low20` (`+0.10083`, `+0.01620`
  lift versus high count) but with only `5 / 8` positive lift years. Source
  anchors: `F363`, `D015`.

- Oracle-shadow regime follow-through: H394 found only a weak honest
  observable shadow of the target-breadth weather that made the invalid S24x
  states look strong. A rolling ridge date model predicted future S1
  barrier-breadth with avg date IC `+0.05019` and `7 / 8` positive years, but
  the best honest predicted bucket lifted C16 by only `+0.00342` versus all
  rows and `+0.00416` versus random dates, below promotion gates, and degraded
  S1. H399 found the H394 low-weather bucket can still be weak context inside
  high-count/high-average-buy-size rows, but not stable enough for promotion.
  Observable `VNI down 2d` remained the cleaner context. Source anchors:
  `F358`, `F363`, `D013`.

- Weak-signal quorum: H395 confirms that weak IC `0.01-0.05` evidence should
  not be discarded. A train-selected equal-weight low-parent-corr quorum from
  predeclared C4-C14/news/official/calendar/context votes reached avg IC
  `+0.05826`, `7 / 7` positive years, S1 corr `+0.27541`, C16 corr `-0.00685`,
  and beat both random weak baskets and the best component. This is a strong
  composite RL-state candidate, not a new independent primitive. H396 then
  confirmed the distinction: H395 survives S1/C16 residualization
  (`+0.01669`, `7 / 7`) but not residualization against its C-vote ingredients
  (`+0.00187`). C13/C10/C6 are the clean residual primitive survivors. H400
  then rejected adding a fixed calendar weak-prior vote: the non-calendar
  quorum stayed at `+0.05826`, while the calendar-added quorum fell to
  `+0.05605` with `0 / 7` positive lift years. Source anchors:
  `F359-F360`, `F364`, `D016`.

- Experiment hygiene: lightweight signal/state/context branches now have a
  shared scaffold. Start from `analysis/_template_research_branch.py` and
  `src/experiment_contract.py`; the contract renames raw S1 `actual` to
  target-only `s1_barrier_hit_1d`, blocks `2026+` by default, validates
  target/state overlap, computes pooled/yearly/phase IC summaries, and writes
  standard run summaries. Source anchor: `F357`.

- Best currently published side-channel promotion: C16 scoped CafeF order
  pressure is a shared opt-in feature contract. H356-H360 show strong standalone
  IC, residual selector value, bounded executable uplift, publication, and
  published-contract parity. Source anchors: `F296-F301`.

- Insider/weakness interactions: H387 rejected the insider-down rescue overlay.
  Positive insider plus stock weakness plus high C16 beat ordinary insider rows
  but failed the stronger insider-C16 and stock-down-C16 controls; stock-down
  high-C16 remained the cleaner control state. H398 says this does not kill
  event-time insider lead; the stronger continuation clue is reaction
  confirmation, especially high buy-order count. Source anchors: `F348`,
  `F362`, `D005`, `D014`.

- Calendar/timing context: old calendar filters remain useful as context, but
  H390 parks exact-state calendar promotion under the current target. Exact
  `monday_jan_combo` retained a 1d residual C16-IC lift after mechanism
  controls, but it was only one active test date per evaluated year, had only
  `2 / 4` positive 1d residual-lift years, and had negative mean 5d residual
  lift; `quarter_start` and late quarter-month timing did not retain positive
  1d residual lift. H400 also rejected dense calendar as a weak quorum prior:
  the pooled calendar vote had `-0.00827` avg IC and reduced the H395 quorum.
  Source anchors: `F351`, `F364`, `D008`, `D016`.

- Tradability-release context: H391 rejected the current entry-panel
  `release_flag` as a `wait_release` buy signal. Top-5/top-10 rows becoming
  buyable after prior blocked-buy states had negative cycle relative returns,
  negative same-rank matched-control lifts, weak 2025 confirmation, and weaker
  sellability health than stable buyable controls. Source anchors: `F352`,
  `D009`.

- Forced-seller daily states: H426 rejected the current forced-seller detector
  as an entry-candidate allocator. The broad core from 3d weakness, volume
  spike, sell-pressure, rising/high average sell size, and no active bad news
  had only `+0.000230` mean lift versus random-state, `1 / 5` positive WF
  years, and `-0.002047` lift versus random-all. Floor and large-down variants
  also failed, and literal tradability release had only `7` rows. The
  next-day C16 turn clause needs a delayed-entry or intraday/queue protocol
  before it is decision-time valid. Source anchors: `F382`, `D025`.

- Portfolio veto context (H401): rejected broad side-channel disagreement as a
  top-5 cash veto. `support_count_le1`, `pretty_price_weak_flow`,
  `news_hype_weak_flow`, and `weak_flow_weak_sector` all reduced cycle
  relative returns versus no-veto. The only survivor is strict
  `support_count_zero`, with tiny lift (`+0.000167` vs no-veto, `6 / 7`
  positive years) that failed random p95. Source anchors: `F365`, `D017`.

- Order fragmentation context (H402): tested order-count/volume fragmentation
  ratios as proxies for book depth beyond raw C16. Fragmentation added marginal
  IC beyond C16 (+0.00753) but with poor year consistency (2/8 positive)
  and C16 itself was negative IC in this period. The only strong standalone
  proxy was avg buy-minus-sell size (+0.03033 IC). Do not promote as a
  ranker; avg size could be useful as a high-C16 conditioner with different
  data. Source anchors: `F366`.

- Flow regime context (H403): Reynolds number Re = velocity * breadth / viscosity
  (using volume-z as velocity proxy) adds +0.044 IC beyond C16 baseline
  with 6/8 positive years. Re high bucket is strongest (+0.01429 IC).
  NOT a signal-library promotion (IC < 0.05) but useful as C16 ranker
  within Re regime or portfolio policy context. Source anchors: `F367`.

- Sector event lightcone (H405): both own-ticker and sector-peer events
  add negative IC (own: -0.00481, sector: -0.00698, both 0/8/1/8 pos years).
  Confirms prior news/event feature failures. Do not reopen as count-based
  features. Source anchors: `F369`, `D020`.

- Conservation residual (H406): expected from flow predicts forward at
  +0.00983 IC (3/3 pos years) but residual inversely predicts -0.02861 IC
  (0/3 pos years). Model captures flow; residual is mean-reverting noise.
  Do not reopen as conservation-break alpha. Source anchors: `F370`, `D021`.

- Phase lag cross-product (H407): lagged C16 × price cross-product adds +0.022 IC
  with 7/8 positive years. This is NEW feature class - cross-product of lags,
  different from level derivatives (ROC, Haar - failed) or simple lags.
  NOT signal-library (IC < 0.05) but useful as C16 conditioner. Source anchors: `F371`.

- S1×C16 cross-product (H408): cross adds +0.108 but WORSE than S1 alone (+0.118).
  C16 alone is negative (-0.030). Cross doesn't beat S1 standalone - 0.010 IC penalty.
  Do not promote as signal. Source anchors: `F372`.

- Volume×C16 cross-product (H409): cross adds +0.017 but WORSE than Volume alone (+0.077).
  CRITICAL: Volume alone (`order_volume_ratio`) is +0.077 IC, 8/8 pos years - NEW SIGNAL!
  Recommend signal library addition. Source anchors: `F373`.

- Volume+S1 additive (H410): additive 0.25V+0.75S = +0.12649 IC, BEATS both standalones!
  Cross-products hurt (H408, H409) but additive works (+0.009 IC lift over S1).
  Recommend: 0.25×Vol + 0.75×S1 as simple combination ranker. Source anchors: `F374`.

- Volume+C16 additive (H412): FAILED. C16 is too weak (-0.0008 IC).
  Best additive = +0.073, WORSE than Volume alone (+0.075). C16 cannot be rescued.
  Source anchors: `F376`.

- Triple signal additive (H413): PASSED! 0.1V+0.9S = +0.135 IC, beats H410.
  Lower volume (10%) + higher S1 (90%) wins. New standard: 0.1V+0.9S.
  Source anchors: `F377`.

- Alternative target test (H414): PASSED! Additive works on ALL horizons (1d, 10d, 20d).
  Same +0.017 to +0.019 lift across targets. Generalizable pattern confirmed.
  Source anchors: `F378`.

- Weight optimization (H415): MIXED. 15V+85S = +0.136 (marginal +0.001 over H413).
  Optimum in 10-15% volume range. Keep H413 as standard.
  Source anchors: `F379`.

- Market state gated (H416): PASSED! Works in BOTH market states.
  VNI up: +0.016 lift, VNI down: +0.018 lift. ROBUST pattern.
  Source anchors: `F380`.

- Hold-out 2025 test (H417): PASSED! +0.014 lift on 2025, same as long-term +0.017.
  PROVES NOT survivor bias - pattern is REAL.
  Source anchors: `F381`.

- Foreign flow addition (H418): FAILED. Foreign has near-zero IC (+0.004).
  Adding it HURTS (-0.006). Same as C16 - too weak to contribute.
  Source anchors: `D023`.

- Insider addition (H419): MIXED. Insider alone NEGATIVE (-0.002).
  Adding gives +0.0004 (within noise). All weak signals confirmed.
  Source anchors: `D024`.

- Volume attention budget (H427): PASSED. Date-level volume concentration
   (Herfindahl) acts as market regime indicator. Mid-concentration (Q3) has
   mean IC 0.1389 vs baseline 0.1264, lift +0.0125, 8/8 positive years.
   Both extreme concentration (Q5) and extreme distribution (Q1) hurt signal
   quality. Offline evidence, needs candidate-count policy follow-through.
   Source anchor: Session 306.

- Midbook imbalance (H428): FAILED. Higher buy/sell volume imbalance
   correlates with WEAKER C16 signal (Q5 vs Q1 IC lift -0.0385 dev, -0.0116 val).
   Direct prediction is weakly positive (IC +0.0194 dev, +0.0373 val) but below
   IC > 0.05 threshold. Interpretation: high imbalance indicates weakness,
   not hidden depth. Do not reopen as C16 conditioner or standalone signal.
   Source anchor: Session 307.

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

- Horizon routing for local-news states: H397 explains why some IC/payoff
  evidence failed broad candidate allocation. Active/positive-news strong-flow
  is a 1d C16 ranker (`+0.02257` / `+0.02536` IC lift versus strong-flow), not
  a 5d allocator; official and official-forward supported attention are 5d
  payoff states (`+0.00650` / `+0.00662` net lift, `8 / 8` positive years).
  H364 positive was too sparse under the min-row gate, and C5 rank-within-
  insider failed without killing S272 insider lead. Source anchor: `F361`.

## Reference Baselines (Walk-Forward IC)
- Random: ~0.00 (noise benchmark)
- C16: +0.078 (order pressure)
- S1: +0.149 (best published - PRIMARY for RL)

## Signal Promotion Rule

- Strong standalone signal promotion: IC `> 0.05`, decision-time observable,
  independent from existing library signals (`corr < 0.30`), positive in at
  least `60%` of tested years, and not a target-derived state.
- Weak candidate/context: IC between `0.01` and `0.05`, or IC `> 0.05` with
  limited coverage, sparse-state caveats, or unresolved consumer fit.
- Parent-signal filters and rewrites must be judged by incremental lift versus
  the parent and matched controls. IC `> 0.05` versus random is real edge but
  not a new promotion if it is mostly raw S1/C16/etc. re-bucketing.
  Source anchor: `F356`.

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
| insider_buy_lead | 0.1050 | +0.11 | REAL after S272 next-trading-day audit |
| consecutive_down_days | target-derived | n/a | INVALID from S244/S253 record |
| dividend_30d | 0.0526-0.0557 | +0.05 | weak/context only after corrected window audit |
| rank_time_acceleration | 0.0548 | +0.05 | weak, below C16 |

### S245-S247 C16 Contrarian Signals
| Signal | IC | vs Baseline | Verdict |
|--------|-----|-------------|--------|
| target-derived down_market_c16 | +0.098 | leaky | INVALID |
| observable_vni_down | +0.077 | +0.003 | modest context only |
| observable_vni_down_2d | +0.081 | +0.007 | modest context only |
| target-derived deep_down_c16 | +0.093 | leaky / mislabeled | INVALID |
| sector_pressure_momentum | +0.078 | +0% | FAILED |

### S248-S252 Bright-Mind Failed
| Signal | IC | vs Baseline | Verdict |
|--------|-----|-------------|--------|
| macro_c16_regime | +0.077 | +0% | FAILED |
| gap_open_c16 | +0.075 | -4% | FAILED |
| consecutive_down | +0.078 | +0% | FAILED |
| c16_extreme_down | +0.028 | -63% | FAILED (sparse) |
| c16_entropy | ~0.08 | ~0.08 | WEAK - dead end |

### S253 Validation Status
Superseded by S272. S253 did not implement the advertised TRUE train
`T-2,T-1` -> test `T` protocol, and its market/consecutive regimes were
derived from same-date S1 `actual`. Keep only the insider-lead survivor from
the corrected audit. Source anchors: `F355`, `D012`.

## All Real Signals for RL (IC > 0.05 vs Random) — Complete Inventory

### Tier 1: Primary Signals (IC > 0.10)
| Signal | IC | vs Random | Type |
|--------|-----|---------|------|
| S1 (xs_proba) | 0.149 | +0.15 | PRIMARY |
| Triple Storm | 0.158 | +0.16 | enhancement |
| monday_jan_combo | 0.1109 | +0.11 | raw calendar combo; exact promotion parked by H390 |
| X53 (Liquid C16) | 0.137 | +0.14 | liquidity filter |
| **insider_buy_lead** | **0.1050** | **+0.11** | **insider lead; S272 survivor** |

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
| rank_time_acceleration | 0.0548 | +0.05 | weak, below C16 after S272 |
| X54 (Braid) | 0.080 | +0.08 | sector filter |
| C16 baseline | 0.078 | +0.08 | order pressure |
| vol_low | 0.0695 | +0.07 | volume regime |
| yearend | 0.0652 | +0.07 | calendar |
| midyear | 0.0711 | +0.07 | calendar |

### Key RL Use Cases
1. **Primary signal**: S1 (0.149)
2. **Enhancement filters**: vol_high, monday_jan context, divergence, liquid,
   observable VNI-down context only
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

## New Signal Discovery (H428-H433 Batch)

- C18 rank delta (H431): NEW SIGNAL. C16 rank CHANGE (delta) predicts better than
  level. Q5_incr (increasing rank) has +0.1290 IC (+0.0114 lift vs baseline), 8/8
  positive years. Validation confirms Q5_incr +0.1310 vs level +0.0633. Captures
  flow acceleration that level misses. Use as conditioner or additive component.
  Source anchors: `F384`, signal library updated.

- S1 rank degradation (H428): FAILED. Top S1 quintile tickers do NOT decay in
  next-day IC - they IMPROVE by +0.0263 lift. Q3 (mid-S1) is weakest pocket.
  Do not use S1 rank as error-state indicator. Source anchors: `F385`, `D027`.

- Signal half-life routing (H429): FAILED. Pre-declared half-life classes do NOT
  show horizon-specific advantage. All classes degrade at longer horizons;
  1d baseline always best. Do not route signals to different horizons.
  Source anchors: `F386`, `D028`.

- Candidate entropy (H430): MIXED. Q2 best in dev (+0.0105), validation prefers
  high-entropy (+0.0143). Pattern inconsistent - not a clean predictor.
  Source anchors: `F387`.

- Volume-price divergence (H432): FAILED. All divergence states have negative
  lift vs baseline (real_force -0.0261, fade -0.0289). Energy conservation
  hypothesis doesn't translate to alpha. Source anchors: `F388`, `D029`.

- State transition (H433): MIXED. D2 (moderate decreasing delta) best (+0.0088),
  but pattern inconsistent. Event-count level negative (-0.0065), delta provides
  some value but not strong enough to promote. Source anchors: `F389`.

- Signal strength gating (H434): PASSED. High strength (S1×C18 product) shows
  +0.0111 IC lift over low strength. Works strongest in stress years
  (2020 +0.0553, 2021 +0.0710). Not a ranker replacement but useful as
  dynamic position sizing signal. Source anchor: `F390`.

## Maintenance Rule

- When a future session promotes a durable finding, update the source
  `findings-*.md` chunk first. Then update this compact file only if the new
  finding changes one of the grouped themes or creates a new theme.
