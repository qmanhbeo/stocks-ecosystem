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

- C23-family structural compression: recent branches around C23/C24/C25/C26
  increasingly behave like regime slicing rather than new primitives. Strong
  states (C23, C24, cofire_2, c16_low×C23, freshness subsets) stay positive,
  while many additional micro-conditioners are weak/sparse/dead (D042-D049).
  Working interpretation: the lab is mapping one latent liquidity-stress /
  participation regime with multiple emissions, not discovering many separate
  orthogonal alphas. Treat current priority as ontology and latent-state
  mapping, not threshold mining. Source anchors: `F393`, `F394`, `F412`,
  `F414`, `F419`, `F423`, `F424`, `D042-D049`.

- Multi-signal extension frontier (post-F445/F447): binary low-breadth gating
  remains the strongest confirmed amplifier on top of `composite_2plus`, while
  recent extensions failed by sparsity or negative incremental lift
  (blocked-triple, breadth weighting, blocked single-signal pre-convergence,
  tight-capacity modulation). New update: persistence shows a bounded sweet
  spot (`20-30` accumulated active days in a 60d window) that beats very-long
  accumulation (`31+`) by `+0.0135` while both remain positive. Current read:
  keep `composite_2plus` and `composite_2plus × low_breadth` as the stable
  base contract, with bounded accumulation as a secondary conditioner. New
  timing-distribution result: same-day multi-signal concentration strongly beats
  spread-across-days accumulation (`+0.0624`), reinforcing same-day co-occurrence
  as the core mechanism. New concentration result: within low-breadth states,
  concentrated signal mass beats distributed mass (`+0.0209`), adding a
  promotable concentration conditioner for this branch. Source anchors: `F445`,
  `F446`, `F447`, `F459`, `F460`, `F461`, `D072-D075`, `D093-D099`.

- Latent-state machine evidence: H507 produced the first explicit transition
  map for the C23 family and supports a compact state organization: quiet
  dominates coverage, while onset/amplified/router/carry states all show
  materially higher IC than all-rows with `11 / 11` positive years, and the
  dominant flow pattern is `onset/amplified/router -> carry -> quiet`.
  Interpretation remains structural (not deployability): this supports running
  router-equivalence ablation next before opening new hypothesis mining.
  Source anchor: Session 139 (`H507`).

- Router-equivalence compression evidence: H508 confirms that freshness,
  cofire, and low-C16 router states are nested C23 projections rather than
  independent primitives (all three have no support outside C23 under residual
  tests). C23 keeps strong residual IC after removing freshness, while C24
  remains a distinct emission channel with strong `C24 | not C23` residual IC.
  Working ontology after compression: dominant C23-family primitive +
  router/timing/amplification layers + distinct C24 primitive. Source anchor:
  Session 139 (`H508`).

- Unsupervised latent rediscovery evidence: H509 removed symbolic C23/freshness/
  cofire/carry/low-C16 labels from state construction and fit emission-space
  clustering on dev years only (`k=4/5/6`, frozen assignment out of sample).
  Structure did not collapse: best `k=6` cluster achieved avg IC `0.2084`
  versus all-rows `0.1302`, with random-lift gap `+0.0746`, strong quiet
  separation, and a distinct C24-like channel recovered post-hoc. The strongest
  high-IC latent pocket is primarily illiquidity plus low-pressure/negative-
  imbalance structure rather than ceiling states, while C24 appears as a
  separate queue-friction channel. Caveat: onset/amplification/carry are only
  partially disentangled (low direct one-to-one Jaccard), and selected `k=6`
  should not be treated as uniquely proven because k-choice used full-period IC
  diagnostics. H511 then enforced strict dev-only `k` selection and active-only
  subclustering: quiet structure stayed strong and active clusters still beat
  random, but C24 recovery degraded (`0.591`) and onset/amplification/carry
  separation remained weak (`mean max-Jaccard 0.059`). H512 immediately showed
  this was largely a representation-selection issue: with C24-preserving global
  `k=4`, C24 recovery returned (`0.966`), active-vs-random gap improved
  (`+0.060`), and mean onset/amplified/carry separation rose to `0.105` with
  two strong non-sparse active clusters. H513 then passed the explicit
  robustness audit: both strong clusters remain phase-positive in validation and
  confirmation and concentration stays below one-pocket risk (`0.576 < 0.80`).
  H514-H516 then resolved the amplified-axis branch: naive silhouette-selected
  refinement was mixed, but constrained active-k selection on the same refined
  representation recovered strong amplified overlap and passed robustness gates.
  H517 then formalized that into a guarded active-k contract, which keeps H512
  stable and corrects H514 drift. H518 further narrows the remaining weakness:
  carry-axis underlap looks representation-limited (low overlap despite
  phase-stable carry IC), not a latent-state collapse. Current read:
  active-manifold decomposition is robust; next gains should come from targeted
  carry-representation refinements under the guarded contract. Source
  anchors: Session 139 (`H509` + interpretation audit), `F417`, `F418`,
  `F419`, `F420`.

- Carry-amplified structural conflict: H519-H521 tested whether carry-state
  overlap could be improved without degrading amplified-state overlap. Both
  strong carry features (flow_persist, imbalance_persist) and weak features
  (simple lags: lag2_order_volume_ratio_rank, order_pressure_sustain) improve
  carry separation (+25-62%) but damage amplified overlap (-38-80%). This is
  not a feature engineering issue but a structural property of the observable
  manifold: carry and amplified are in inherent tension. The latent space can
  cleanly separate 2-3 states (quiet + 1-2 active) but not all three of
  onset/amplified/carry simultaneously. Source anchors: Session 333 (`H519`),
  Session 334 (`H521`).

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
  feature families were too weak or redundant. Source anchors: `F59-F89`.

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

- Volume-adjusted price momentum (H435a): PASSED. volume_z_q5 (high volume)
  achieves IC=0.157 (8/8 positive years), the strongest single volume state.
  Return/volume ratio (efficiency) shows Q5=0.100 vs Q1=0.054, but the key is
  volume LEVEL not the ratio. Confirms why H413 additive works (0.1×Vol + 0.9×S1).
  Source anchor: Session 313.

- Candidate rank actual gap (H435b): FAILED. Q5 absolute gap has negative IC (-0.82)
  while Q1 has positive (0.64). Higher prediction-error predicts WORSE returns,
  not surprise alpha. Do not use as signal. Source anchor: Session 314.

- Signal ignorance weight (H436): FAILED. Ignoring S1/C16 in predicted degrade-state
  HURTS performance (IC=0.053 vs 0.120 baseline). Top-10 buyers in composite
  degrade-state achieve IC=0.10 (STRONGER than all-rows), while ignoring drops
  to IC=0.053 (WORSE). S1/C16 are robust across all tested regimes. Do not
  reopen as cash/veto signal. Source anchor: `D030`, Session 315.

- Replacement quality revival (H437): FAILED. Entering tickers have weaker IC (0.066)
  than exiting tickers (0.126), stable tickers (0.079), and all-rows (0.117).
  Enter vs exit lift is -0.060, opposite of hypothesis. Aligns with H388 finding
  that fresh reappearances are not strong. Source anchor: `D031`, Session 316.

- News consensus divergence (H438): MIXED. Consensus news states show IC~0.10
  (8/8 positive years), but divergence states are weaker (0.093-0.097).
  Divergence vs consensus lift is -0.009, meaning disagreement does NOT indicate
  hidden information. Consensus works but not as divergence play. Source anchor:
  Session 317.

- Volatility regime transition (H439): MIXED. High volatility states are MUCH
  stronger (IC=0.17-0.20) than low vol (0.09-0.10). Within high-vol, contracting
  beats expanding (+0.009), but this is a LEVEL effect not transition. The primary
  finding is vol LEVEL matters; transition is secondary. Use as conditioner,
  not standalone signal. Source anchor: Session 318.

- News novelty first repeat (H440): PASSED. First-in-5d news has IC=0.123 vs
  repeat IC=0.091 (+0.032 lift, 8/8 positive years). Combined with strong C16 flow,
  first+flow achieves IC=0.161 (best state). This is a NEW signal finding:
  news novelty matters, not just news presence. Source anchor: `F392`, Session 319.

- Cross-ticker correlation shock (H441): FAILED. Date-level cross-sectional
  correlation regime predicts only +0.0033 IC lift, below the 0.01 threshold.
  Secondary finding: C16 flow works better in high-corr dates (0.167 vs 0.144),
  first-news prefers low-corr dates (0.153 vs 0.130), but primary shock mechanism
  is too weak. Source anchor: `D032`, Session 320.

- Ticker rank acceleration (H442): FAILED. Second derivative of C16 rank (acceleration)
  has near-zero IC lift (+0.0009) vs first derivative. C16 rank LEVEL dominates
  (IC=0.158 vs acceleration=0.120). Both accel_up+flow and accel_down+flow are
  equal (~0.147), showing acceleration direction doesn't matter. H431 rank delta
  worked because it correlated with rank level, not as independent second-order
  signal. Do not reopen as rank acceleration signal. Source anchor: `D033`, Session 321.

- Volatility regime transition (H446): PASSED. Vol EXPANSION (5d vol change > 0) has
  IC=0.175 vs baseline 0.130 (+0.0449 lift, 11/11 positive years). Vol CONTRACTION
  has IC=0.122 (-0.0085 lift). This is DIFFERENT from H439 vol LEVELS - vol CHANGE
  (expansion) itself is a positive signal regardless of vol level. When volatility
  is increasing, S1 quality improves substantially. Use as regime conditioner for
  S1 quality prediction. Source anchor: Session 102.

- Volume-adjusted price momentum (H447): MIXED/OPPOSITE. Hypothesis was high return + 
  high volume = "real force" (positive), high return + low volume = "fade" (negative).
  OPPOSITE: low_return_low_vol IC=0.204 (+0.0746 lift, 11/11 pos years) is STRONGEST,
  real_force (high_return_high_vol) IC=0.111 (-0.019 lift) UNDERPERFORMS. This is a
  CONTRARIAN signal, not momentum. The volume-adjusted framework works but direction
  is inverted: "cheap moves" = mean reversion, not "real force" = sustained. Dead-end
  D036 for original hypothesis; use low_return_low_vol as contrarian conditioner.
  Source anchor: Session 103.

- Vol expansion + contrarian combo (H448): PASSED. vol_expansion (H446) × low_return_low_vol
  (H447) COMBO is STRONGEST: IC=0.2069 (+0.0771 lift, 11/11 pos years), beats vol_expansion 
  alone by +0.0316, beats low_return_low_vol alone by +0.0025. Captures the oversold-in-
  expanding-vol regime better than either component alone. Use as conditioner/ranker - adds
  +0.0316 IC vs vol_expansion alone. NEW SIGNAL. Source anchor: Session 104, F393.

- Vol contraction mean reversion (H449): MIXED. vol_contraction × high_return shows 
  vol_contraction_exhaustion IC=0.1043 (-0.0255 lift) = mean reversion (negative IC), 
  while vol_expansion_momentum IC=0.1671 (+0.0373) = positive momentum. Pattern confirmed 
  real but direction is wrong for long-only - it's a mean reversion signal, not a buy signal. 
  Dead-end D037 for direct long-only use. Use vol_expansion_momentum side instead. 
  Source anchor: Session 105.

- Volume acceleration signal (H450): MIXED. vol_accel_high_return IC=0.1346 (+0.0047 lift), 
  but low_vol (volume LEVEL low) IC=0.1821 (+0.0522 lift) is STRONGER. Acceleration helps 
  for high return (+0.0474 vs high_vol), but volume LEVEL dominates overall. No new signal - 
  use low_vol as primary, acceleration is secondary. Source anchor: Session 106.

- Buy-sell imbalance in stress (H451): PASSED. buy_heavy_expansion IC=0.1809 (+0.0508 lift,
  11/11 pos years) is STRONGEST! Buy-heavy imbalance works ONLY in vol expansion periods
  (+0.0699 lift vs contraction), sell-heavy is always negative. NEW SIGNAL - use as
  regime-dependent conditioner. Source anchor: Session 107, F394.

- Volume level vs direction divergence (H452): MIXED. vol_expanding_high_return IC=0.1671
  (+0.0373 lift) beats high_vol_level_high_return (+0.1112, -0.0186 lift) by +0.0559 for
  momentum case. But low_vol_level_low_return (0.2045, +0.0747) still dominates for contrarian.
  Pattern confirmed but no incremental value - use components separately. Source anchor: Session 108.

- Order flow imbalance momentum (H453): PASSED. C21 NEW SIGNALS! level + momentum + vol
  combos beat H451 level-only by +0.0201-0.0260 IC. buy_heavy_accel_expansion IC=0.2320
  (+0.1019 lift, 11/11 pos years), sell_heavy_decel_expansion IC=0.2369 (+0.1069 lift,
  11/11 pos years). Imbalance delta is independently informative: imbalance_accelerating
  alone IC=0.1601 (+0.0300 lift). Both acceleration AND deceleration in vol expansion are
  positive (different mechanisms). Stable imbalance underperforms - change IS the signal.
  Source anchor: Session 109, F449.

- Implied limit proximity (H454): PASSED. C22 NEW SIGNAL! approaching_ceiling IC=0.2170
   (+0.0872 lift, 11/11 pos years). Limit proximity is regime-independent - vol expansion adds
   only +0.0004 IC. High volume WITH near-limit is WEAKER (0.1375 vs 0.2166) - queue pressure
   thesis fails. Approaching floor weaker than ceiling (+0.0313 lift). Use as standalone ranker,
   not volume-augmented. Source anchor: Session 110, F450.

## Batch 8 Findings (H463-H468, Sessions 116-118)

- Amihud illiquidity × vol expansion (H463): PASSED. C23 NEW SIGNAL! high_illiq_expansion IC=0.2616
  (+0.1318 vs baseline, +101% boost). STRONGEST signal in library. Illiquid stocks amplify regime
  effects dramatically. OHLCV inline from 1227 per-ticker parquet files (ticker from filename).
  C23 beats C21b (0.2369), C21a (0.2320), C22 (0.2170), C20 (0.2105). Source: F451, Session 116.

- Time-of-day calendar pattern (H464): PASSED (weak). Monday IC=0.1434 (+0.0132 lift, 11/11 pos years).
  STRONGEST calendar pattern. Friday negative (-0.0183). Month-end modest (+0.0065). Not standalone
  promotion — weak RL context only. Source: F398, Session 117.

- Signal orthogonality audit (H465): MIXED. C20/C21/C22 combos are ALL WORSE than best individual
  signal (C21a×C22: -0.0115 vs max). vol_expansion is the common regime driver making signals
  redundant when combined. Signals are ADDITIVE in portfolio sense (different days fire), not
  combinatorial. D041: do NOT combine C20/C21/C22. Source: F397, Session 117.

- Crowd exhaustion reversal (H466): PASSED (mechanism inverted). two_days_exhaustion IC=0.2013
  (+0.0711, 3/3 pos years) — STRONGEST. But mechanism is CONTINUATION, not reversal. H445's
  "exhaustion = worst state" means signal at PEAK, not reversing. NOT a new signal — it's momentum
  of C16 amplified by time. Source: F395, Session 118.

- Multi-day ceiling pressure (H467): PASSED. C24 NEW SIGNAL! limit_2_of_3 IC=0.2353 (+0.1052 vs
  baseline, 8/8 pos years). Hit +7% limit 2+ times in last 3 days = sustained queue pressure.
  Beats C22 single-day (0.2162) by +0.0191 IC. Multi-day accumulation beats single-day.
  Source: F452, Session 118.

- Market breadth regime (H468): MIXED. vol_expansion_in_breadth_bottom20 IC=0.1936 (+0.0635) — vol
  expansion works best in NARROW markets. vol_expansion_in_breadth_top20 IC=0.1588 (+0.0287) —
  weaker in broad markets. breadth_top20 NEGATIVE (-0.0199 vs baseline). Use as soft filter
  only, not hard gate. Source: F396, Session 118.

**Confirmed signal rankings (IC vs baseline 0.130):**
C23 (0.2616) > C21b (0.2369) > C24 (0.2353) > C21a (0.2320) > C22 (0.2170) > C26 (0.1889) > C25 (0.1733) > C20 (0.2105)
vol_expansion is universal amplifier for ALL signals; vol_contraction is NO-GO.
Signals NOT combinable — D041.

**Batch 11 / EUREKA queue findings (H472-H474, Sessions 121-123):**

- LAR ratio anti-predictive (H472): Return / Amihud ratio (Q5) = IC 0.087 (-0.032 lift).
  Mid LAR (Q3) = IC 0.145 (+0.025). return_5d_pos_illiq = IC 0.163 (+0.044) = illiquid
  momentum (C23-style). return_5d_pos_liq = IC 0.052 (-0.067) = liquid crowd blowoff.
  Ratio collapses two correlated effects into one confusing metric. Dead-end for LAR.
  Source: Session 121.

- News velocity anti-predictive (H473): high_velocity Q5 = IC 0.088 (-0.032 lift).
  Fast-arriving news = crowd-following, not breaking alpha. mid_velocity only +0.008.
  Low_velocity too sparse (most tickers have 0 news). Third dimension beyond novelty
  (H440) and presence (H445) is noise. Dead-end for news velocity. Source: Session 122.

- Capacity as positive signal (H474): PASSED. tight_capacity (Q1: lowest order count)
  = IC 0.184 (+0.065 lift, 8/8 pos years). loose_capacity = IC 0.074 (-0.046).
  Mechanism: sparse order flow = hidden demand / under-followed alpha. Different from
  H391 binary release — this is CONTINUOUS signal. tight_expansion sparse (2/8 years).
  C27 candidate: use tight_capacity as positive filter for low-activity names, not veto.
  Source: Session 123.

## Batch 9 Findings (H469-H471, Session 119)

- Foreign flow momentum (H469): MIXED. ff_decel_exp IC=0.1376 (+0.0074, 11/11). Marginal signal only.
  H443 killed raw direction variants; momentum doesn't rescue it. Soft filter only, not promotion.
  Source: Session 119.

- VWAP deviation regime (H470): PASSED. C25 NEW SIGNAL! vwap_below_10_exp IC=0.1733 (+0.0431 lift,
  11/11 pos years). Stocks trading far below daily VWAP in vol expansion = "cheap" vs average.
  Under-followed/illiquid stocks amplify (same mechanism as C23). C25 beats baseline by +33%.
  Source: F399, Session 119.

- Order flow microstructure (H471): PASSED. C26 NEW SIGNAL! buy_heavy_illiq_exp IC=0.1889 (+0.0587 lift,
  11/11 pos years). Buy-heavy order flow + illiquidity + vol expansion = institutional hidden demand.
  Both buy_heavy and sell_heavy work with illiq+expansion (different mechanisms: buy=accumulation,
  sell=forced-sell rebound). Source: F399, Session 119.

**Universal pattern confirmed:** ALL strong signals share structure: **specific behavior + illiquidity + vol_expansion**.
C23 (illiq×expansion), C24 (ceiling×expansion), C25 (VWAP deviation+illiq+expansion), C26 (buy flow+illiq+expansion).
D041 CONFIRMED: signals share vol_expansion+illiquidity as universal amplifier. Do NOT combine as composite entries.

## Queue Status (2026-05-08)

**Batch 9 COMPLETE:** H469 MIXED, H470 PASSED (C25), H471 PASSED (C26).
New signals: C18 (H431), C19 (H448), C20 (H451), C21 (H453), C22 (H454), C23 (H463), C24 (H467), C25 (H470), C26 (H471)

## Batch 10 Findings (H449, Session 120)

- Order flow momentum (H449): PASSED (findings OPPOSITE). c16_level_high IC=0.1614 (+0.0326, 11/11 pos years) — BEST state. BUT C16 ACCELERATION (second derivative) is NOT predictive - c16_accel_expanding IC=0.1219 (-0.0069), c16_accel_neutral IC=0.1287 (-0.0001), all WORSE than baseline. ACCELERATION DOES NOT ADD VALUE. The edge comes from LEVELS (high pressure, high volume), not MOMENTUM (changes). Confirms H443 pattern: foreign flow momentum and C16 momentum both NEGATIVE. Confirms H446/H447: vol LEVEL matters, not change. Use C16 level as regime conditioner, not its derivative. Dead-end for acceleration signals. Source: Session 120.

## Maintenance Rule

- When a future session promotes a durable finding, update the source
  `findings-*.md` chunk first. Then update this compact file only if the new
  finding changes one of the grouped themes or creates a new theme.
