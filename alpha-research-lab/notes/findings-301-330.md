# Findings 301-330

## F305: quarter_start Signal (S238, 2026-04-25)

Finding:
- **Claim**: Quarter-start days have stronger C16 signal.
- **Data**: Order stats + returns.
- **Evidence**: IC=0.098 vs baseline +0.078 (+26% boost)
- **Walk-forward**: 9/9 years positive

Why it matters:
- Timing filter for portfolio gate
- Tier 2 placement (IC 0.08-0.10)

Source sessions:
- `notes/session_238_log.md`

---

## F301: H360 Verifies The Published C16 Contract Reproduces The H359 Winner (2026-04-28, Session 201)

Finding:
- H360 consumed the published C16 artifact
  `data/features/xs_order_pressure_daily.parquet` through the documented
  formula:
  `blended_score = (1 - w) * full_library_score + w * order_volume_ratio_rank`
- `w` came directly from `order_pressure_h359_blend_weight`
- the test excluded `2026+` and ran the same executable portfolio protocol as
  H359:
  - `2015-2022` dev
  - `2023-2024` validation
  - `2025` confirmation
  - top-5 equal-weight
  - rebalance every `5` signal days
  - T+1 open fills
  - legal sell delay
  - round-trip cost `0.003`
- the published contract reproduced the saved H359 winner within floating-point
  noise:
  - max absolute parity delta: `9.10e-15`
  - validation relative-return delta: `+32.20%`
  - confirmation relative-return delta: `+5.82%`
  - validation cash delta: `+0.0036`
  - confirmation cash delta: `-0.0067`
- the portfolio gate passed
- the execution-health gate passed

Why it matters:
- the C16 published artifact is not just schema-valid; it reproduces the
  promoted H359 behavior under the actual portfolio consumer formula
- this closes the publication-risk gap between the raw order-stat source,
  H359's in-script blend, and the shared `data/features/...` contract
- downstream consumers still remain opt-in only; no RL or recommendation
  defaults changed

Current next actions:
- close C16 search for now
- only reopen C16 for explicit matrix/export integration or a changed
  downstream consumer contract
- keep `2026` data monitor-only unless explicitly allowed for predictive work

Source sessions:
- `notes/session_201_log.md`

## F302: H361 Closes The Event-v2 Portfolio-Level Sparse-Clock Reopening Condition (2026-04-28, Session 202)

Finding:
- H361 tested the remaining allowed event-v2 reopening condition from H352:
  a stricter portfolio-level sparse clock rather than another additive rank,
  entry-label, or payoff-shape filter
- the test reused the saved H321 event-v2 cascade panel and excluded `2026+`
- the only tested variant added a fixed `+0.03` score bonus when all of these
  were true:
  - `today_self_accel_high` or `recent5_high_self_no_today`
  - full-library score already in the daily top quintile
  - `can_buy_next_open` was true
- source-limited executable protocol:
  - `2023` dev
  - `2024` validation
  - `2025` confirmation
  - top-5 equal-weight
  - rebalance every `5` signal days
  - T+1 open fills
  - legal sell delay
  - round-trip cost `0.003`
- event active rows: `5,770`
- bonus-eligible rows: `891`
- execution-health gate passed
- downside-tail gate passed
- portfolio gate failed:
  - validation relative-return delta: `-4.96%`
  - validation IR delta: `-0.1972`
  - confirmation relative-return delta: `-2.66%`
  - confirmation IR delta: `-0.1376`

Why it matters:
- this was the exact remaining event-v2 rescue route left by H352
- the failure was not caused by cash drag, blocked buys, or downside-tail
  worsening; the sparse clock simply reduced portfolio performance
- H321 remains valid offline sparse timing evidence, but H322, H349, H352, and
  H361 now jointly close the current event-v2 promotion path

Current next actions:
- keep event-v2 parked under the current target and portfolio contract
- do not run more event-v2 overlay, entry-label, payoff-shape, or sparse-clock
  variants
- reopen only with new event data, a materially different target, or a
  downstream consumer contract that is not this top-5 executable selector

Source sessions:
- `notes/session_202_log.md`

## F303: H362 Keeps Dividend-Clock Timing Parked After Portfolio Sparse-Clock Test (2026-04-28, Session 203)

Finding:
- H362 tested the allowed portfolio-level reopening condition left by H354 for
  the dividend-clock branch
- the test used `data/features/event_surface_daily.parquet` and excluded
  `2026+`
- the only tested variant added a fixed `+0.015` score bonus when all of these
  were true:
  - `dividend_window_pre_20d > 0`
  - full-library score already in the daily top quintile
  - `can_buy_next_open` was true
- executable protocol:
  - `2015-2022` dev
  - `2023-2024` validation
  - `2025` confirmation
  - top-5 equal-weight
  - rebalance every `5` signal days
  - T+1 open fills
  - legal sell delay
  - round-trip cost `0.003`
- dividend pre-ex active rows: `3,423`
- bonus-eligible rows: `395`
- execution-health gate passed
- downside-tail gate passed
- portfolio gate failed:
  - validation relative-return delta: effectively `0.00%` but slightly
    negative at floating precision
  - confirmation relative-return delta: `+0.96%`
  - confirmation IR delta: `+0.0448`

Why it matters:
- H354's small pre-ex payoff hint did not translate into a clean executable
  sparse-clock portfolio improvement
- the branch did not fail because of execution or downside-tail damage; it
  failed because validation did not improve
- dividend-clock evidence remains offline calendar context only under the
  current target and selector

Current next actions:
- keep dividend-clock timing parked
- do not tune more dividend windows, bonuses, or sparse-clock overlays under
  the current executable selector contract
- reopen only with a materially different calendar target or downstream
  consumer contract

Source sessions:
- `notes/session_203_log.md`

## F304: H363 Finds A Post-Holiday Payoff Hint But Legal-Holiday Sparse Portfolio Timing Fails (2026-04-29, Session 209)

Finding:
- H363 tested Vietnam legal-major public holidays as sparse before/after
  market states, not as dense calendar features
- included holiday families:
  - New Year Jan 1
  - Tet
  - Hung Kings Commemoration Day
  - Reunification Day Apr 30 / Labor Day May 1
  - National Day Sep 2 plus adjacent official day
- actual exchange closure clusters were inferred from the VNINDEX trading
  calendar
- generated states were only:
  - `pre_1`, `pre_2`, `pre_3`, `pre_5`
  - `post_1`, `post_2`, `post_3`, `post_5`
- the calendar data checks passed:
  - state rows / dates: `436 / 408`
  - closure clusters: `53`
  - min / max state date: `2015-01-05 / 2025-09-09`
  - all marked state dates existed in the VNINDEX trading calendar
  - no rows outside `2015-2025`
  - no `2026+` rows
- controls were non-holiday rows matched by research phase, S1 bucket, and
  full-library bucket
- only one payoff state passed:
  - `all_holidays__post_5`
  - validation top-book 5d relative-return lift: `+0.00405`
  - confirmation top-book 5d relative-return lift: `+0.01579`
  - validation active top-book dates / rows: `9 / 45`
  - confirmation active top-book dates / rows: `5 / 25`
  - positive validation/confirmation years: `3`
  - max positive-lift year share: `0.6534`
  - validation q10 / bad-tail lift: `+0.01672 / -0.09008`
  - confirmation q10 / bad-tail lift: `+0.03633 / -0.13245`
- the required fixed portfolio follow-through then tested exactly one rule:
  - state: `all_holidays__post_5`
  - `+0.015` bonus
  - only daily top-quintile full-library names
  - only rows buyable at next open
- the portfolio leg failed:
  - eligible bonus rows: `3,109`
  - portfolio gate: `false`
  - execution-health gate: `true`
  - downside-tail gate: `true`
  - validation relative-return delta: `0.00%`
  - confirmation relative-return delta: `0.00%`

Why it matters:
- the legal public-holiday effect is too sparse to treat as a dense calendar
  feature, but there is a narrow post-holiday top-book payoff hint worth
  remembering as offline timing evidence
- the hint did not move the executable full-library portfolio at all under the
  fixed sparse-clock contract
- the failure was not caused by blocked buys, cash drag, or downside-tail
  worsening; the bonus simply did not alter the selected book enough to create
  portfolio value

Current next actions:
- keep legal-holiday timing as offline evidence only
- do not tune more pre/post offsets, closure-length gates, bonus sizes, or veto
  variants under the current top-5 executable selector
- keep `holiday_news_silence_break` separate and parked until the local-news
  aggregate finishes, because that thesis requires company-news/disclosure
  conditioning rather than another generic holiday-clock overlay
- keep `2026` data monitor-only unless explicitly allowed for predictive work

Source sessions:
- `notes/session_209_log.md`

---

## F306: market_breadth A/D Signal (S238, 2026-04-25)

Finding:
- **Claim**: Advance/decline breadth predicts market regime.
- **Data**: Market breadth × C16 × returns.
- **Evidence**: IC=0.093 (+30% boost)
- **Walk-forward**: consistent

Why it matters:
- Market regime detector
- Tier 2 placement

Source sessions:
- `notes/session_238_log.md`

---

## F307: january_first_10 Signal (S242, 2026-05-02)

Finding:
- **Claim**: First 10 days of January have stronger signal (institutional reallocation).
- **Data**: Calendar + order stats + returns.
- **Evidence**: IC=0.0817 vs random (+0.08), +5% boost
- **Walk-forward**: 9/9 positive

Why it matters:
- Calendar filter for timing
- Tier 2 placement

Source sessions:
- `notes/session_242_log.md`

---

## F308: vol_high Volume Regime (S242/S238, 2026-05-02)

Finding:
- **Claim**: High volume days amplify C16 signal.
- **Data**: Volume regime split.
- **Evidence**: vol_high IC=0.0941 vs vol_low IC=0.0695 (+21%)
- **Walk-forward**: consistent

Why it matters:
- Volume regime filter
- Tier 2 placement

Source sessions:
- `notes/session_242_log.md`, `notes/session_238_log.md`

---

## F309: monday_jan_combo Signal (S243, 2026-05-02)

Finding:
- **Claim**: Monday × January combo amplifies C16 strongest.
- **Data**: Calendar × C16 × returns.
- **Evidence**: IC=0.1109 vs baseline +0.078 (+42% boost)
- **Walk-forward**: 9/9 years positive

Why it matters:
- **STRONGEST calendar combo** (IC 0.11)
- Tier 1 placement
- Use as primary calendar filter

Source sessions:
- `notes/session_243_log.md`

---

## F310: february_mid Signal (S243, 2026-05-02)

Finding:
- **Claim**: Mid-February has stronger signal.
- **Data**: Calendar × C16 × returns.
- **Evidence**: IC=0.0858 (+10% boost vs baseline)
- **Walk-forward**: consistent

Why it matters:
- Calendar filter
- Tier 2 placement

Source sessions:
- `notes/session_243_log.md`

---

## F311: march_late Signal (S243, 2026-05-02)

Finding:
- **Claim**: Late March has stronger signal.
- **Data**: Calendar × C16 × returns.
- **Evidence**: IC=0.0833 (+7% boost)
- **Walk-forward**: consistent

Why it matters:
- Calendar filter
- Tier 2 placement

Source sessions:
- `notes/session_243_log.md`

---

## F312: october Signal (S243, 2026-05-02)

Finding:
- **Claim**: October has stronger signal.
- **Data**: Calendar × C16 × returns.
- **Evidence**: IC=0.0817 (+5% boost)
- **Walk-forward**: consistent

Why it matters:
- Calendar filter
- Tier 2 placement

Source sessions:
- `notes/session_243_log.md`

---

## F313: insider_buy_lead Signal (S244, 2026-05-03)

Finding:
- **Claim**: Insider BUY publishes on T-1 → amplifies C16 signal quality on T.
- **Data**: `data/insider_cache/*.parquet` merged with `data/order_stats/` + returns.
- **Test**: Compare IC(C16) with prior insider buy (T-1) vs without.
- **Evidence**:
  - IC with prior insider buy: **0.1113**
  - IC without prior insider buy: 0.0797
  - **Boost: +39.7%**
  - n (with insider buy): 5,912
  - n (without): 553,054
  - Walk-forward: 9/9 years positive

Why it matters:
- Insider buy is an **independent signal** that boosts C16 by +40%
- Can use as filter/weight when insider activity is detected previous day
- IC > 0.10 = qualifies for Tier 1 promotion

Source sessions:
- `notes/session_244_log.md`

---

## F314: consecutive_down_days Signal (S244, 2026-05-03)

Finding:
- **Claim**: Stocks that fell yesterday continue to fall (streak continuation).
- **Data**: Returns from `xs_barrier_vol_1d_hose_full.parquet`.
- **Test**: IC of down-day streak indicator.
- **Evidence**:
  - IC: **0.1030**
  - vs Random: +0.10
  - Walk-forward: 9/9 positive

Why it matters:
- Independent contrarian filter
- Works as market-regime detector
- IC > 0.10 = Tier 1 promotion

Source sessions:
- `notes/session_244_log.md`

---

## F315: dividend_30d Signal (S244, 2026-05-03)

Finding:
- **Claim**: Dividend ex-date in next 30 days drives pre-event accumulation.
- **Data**: `data/xs_dividend_calendar.parquet` merged with returns.
- **Test**: IC 30d dividend window indicator.
- **Evidence**:
  - IC: **0.0934**
  - vs Random: +0.09
  - Walk-forward: INCONSISTENT (some years negative)

Why it matters:
- Event-driven signal but **noisy year-to-year**
- Qualifies by IC > 0.05 but flagged for monitoring
- Tier 2 placement due to inconsistency

Source sessions:
- `notes/session_244_log.md`

---

## F317: vol_rank_gt_08 Signal (S238, 2026-04-25)

Finding:
- **Claim**: High volume rank amplifies C16 signal.
- **Data**: Order volume rank > 0.8.
- **Evidence**: IC=0.091 (+0.09 vs random)
- **Walk-forward**: consistent

Why it matters:
- Volume regime filter - Tier 2 placement

Source sessions:
- `notes/session_238_log.md`

---

## Missing Signals - To Be Added (F318-F328)

These need to be added in proper order after F317.

## F318: price_tier_low Signal (S238, 2026-04-25)

Finding:
- **Claim**: Low price tier stocks have stronger signal.
- **Data**: Price quintile split.
- **Evidence**: IC=0.086 (+0.09 vs random)
- **Walk-forward**: consistent

Why it matters:
- Price tier filter - Tier 2 placement

Source: session_238_log.md

---

## F319: quarter_end Signal (S238, 2026-04-25, WEAK)

Finding:
- **Claim**: Quarter-end days have stronger signal.
- **Evidence**: IC=0.066 (+0.07 vs random) - WEAK
- **Walk-forward**: weak

Why it matters:
- FAILED - weak signal. Use quarter_start (F305) instead.

Source: session_238_log.md

---

## F320: vol_low Signal (S242, 2026-05-02)

Finding:
- **Claim**: Low volume days have weaker signal.
- **Evidence**: IC=0.0695 (+0.07 vs random)
- **Walk-forward**: consistent but weaker

Why it matters:
- Inverse of vol_high (F308) - Tier 3 placement
- Use F308 (vol_high) instead.

Source: session_242_log.md

---

## F321: monday Signal (S243, 2026-05-02)

Finding:
- **Claim**: Monday has stronger C16 signal.
- **Evidence**: IC=0.0836 (+0.08 vs random)
- **Walk-forward**: consistent

Why it matters:
- Calendar filter - Tier 2 placement

Source: session_243_log.md

---

## F322: may Signal (S243, 2026-05-02)

Finding:
- **Claim**: May has stronger signal.
- **Evidence**: IC=0.0805 (+0.08 vs random)
- **Walk-forward**: consistent

Why it matters:
- Calendar filter - Tier 2 placement (weaker)

Source: session_243_log.md

---

## F323: september_late Signal (S243, 2026-05-02)

Finding:
- **Claim**: Late September has stronger signal.
- **Evidence**: IC=0.0791 (+0.08 vs random)
- **Walk-forward**: consistent

Why it matters:
- Calendar filter - Tier 2 placement

Source: session_243_log.md

---

## F324: september_early Signal (S243, 2026-05-02, WEAK)

Finding:
- **Claim**: Early September has weaker signal.
- **Evidence**: IC=0.0614 (+0.06 vs random) - WEAK
- **Walk-forward**: weak

Why it matters:
- Use late September (F323) instead.

Source: session_243_log.md

---

## F325: yearend Signal (S243, 2026-05-02, WEAK)

Finding:
- **Claim**: Year-end window (Dec 20+) has stronger signal.
- **Evidence**: IC=0.0652 (+0.07 vs random) - WEAK
- **Walk-forward**: weak

Why it matters:
- Tier 3 placement.

Source: session_243_log.md

---

## F326: midyear Signal (S243, 2026-05-02, FAILED)

Finding:
- **Claim**: June/July midyear rebalancing effect.
- **Evidence**: IC=0.0711 (+0.07 vs random) - FAILED
- **Walk-forward**: failed

Why it matters:
- FAILED - Tier 3 placement.

Source: session_243_log.md

---

## F327: march_early Signal (S243, 2026-05-02, WEAK)

Finding:
- **Claim**: Early March has weaker signal.
- **Evidence**: IC=0.0643 (+0.06 vs random) - WEAK
- **Walk-forward**: weak

Why it matters:
- Use march_late (F311) instead.

Source: session_243_log.md

---

## F328: rank_time_acceleration Signal (S244, 2026-05-03)

Finding:
- **Claim**: C16 rank change over time matters.
- **Evidence**: IC=0.0576 (+0.06 vs random)
- **Walk-forward**: 9/9 positive

Why it matters:
- Independent state feature - Tier 3 placement

Source: session_244_log.md
