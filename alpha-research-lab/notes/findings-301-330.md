# Findings 301-330

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
