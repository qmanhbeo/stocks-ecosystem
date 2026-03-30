# Stock-Specific Entry Alpha Design

This note documents a **future architecture branch**, not the current active branch.

Current active branch remains:
- live track: frozen sticky activation branch
- research track: acquisition-first timing data work from `notes/timing_data_acquisition_plan.md`

Use this note only when the lab intentionally reopens architecture work around the idea:

> sometimes the right action is not "turn the whole selector on"
> but "buy this specific stock now, even if the rest of the universe is weak"

## Why this branch exists

The current live implementation is mostly:

1. rank stocks cross-sectionally
2. decide whether the selector is globally `ON` or `OFF`
3. if `ON`, choose the top names subject to tradability and implementation rules

That works when the real edge is mostly date-level opportunity-set timing.

But it is the wrong abstraction if the true edge is often:
- one or two names are genuinely attractive
- the rest of the cross-section is mediocre
- forcing a top-5 fill is too blunt
- forcing a global `OFF` gate is also too blunt

So this branch proposes:
- keep **selection alpha** as the cross-sectional prior
- reinterpret **activation alpha** as an **exposure prior**
- add a new **entry alpha** layer that decides whether each candidate should actually be bought now

## Proposed architecture

### 1. Selection alpha

Keep the current selector ranking as the upstream prior:
- canonical starting point: `full_library + k5_r5_eq`
- optional offline comparator: `state_blend__h199_sector_laggard_gap_absorb__30`

Role:
- identify the candidate pool
- not force the final breadth

### 2. Entry alpha

New stock-level layer:
- input = ticker-specific candidate rows on signal date `T`
- output = `buy_now_score` or `buy_now_prob`
- decision = buy only if that ticker clears a threshold

Role:
- answer "should this stock be bought now?"
- allow `0..K` entries instead of forcing exactly `K`

### 3. Exposure alpha

Current activation branch should become a **soft portfolio prior**, not an unconditional veto.

Role:
- tighten or loosen the entry threshold
- optionally cap max breadth
- optionally scale gross invested weight

Examples:
- weak regime: require higher `buy_now_score`, cap breadth at `1-2`
- neutral regime: default threshold and default cap
- strong regime: allow lower threshold and full breadth

### 4. Exit alpha

Leave exit logic separate.

For first entry-alpha experiments:
- do **not** reopen exit research at the same time
- use a fixed baseline exit/hold contract so entry-alpha results stay interpretable

## What should change conceptually

Replace:
- `activation_off -> block every candidate`

With:
- `weak_exposure -> require stronger stock-level evidence`

That is the key shift.

## Canonical artifact plan

If this branch is opened, create a dedicated entry-alpha artifact family under `data/features/entry_alpha/`.

### A. Candidate panel

Path:
- `data/features/entry_alpha/candidate_panel_daily.parquet`

One row per `(time, ticker)` candidate.

Required columns:
- `time`
- `ticker`
- `selector_name`
- `selection_score`
- `selection_rank`
- `candidate_pool_rank`
- `can_buy_next_open`
- `can_sell_next_open`
- `is_held_prev_close`
- `activation_state`
- `activation_scale`
- `benchmark_state` features if used

Recommended candidate-universe rule:
- start from top `M=20` selector names per date
- hard minimum research version: top `M=10`
- include held names in a separate compatibility panel if needed

### B. Entry labels

Path:
- `data/features/entry_alpha/entry_labels_cycle5.parquet`

One row per candidate row in the candidate panel.

Required columns:
- `time`
- `ticker`
- `entry_open_t1`
- `cycle_exit_open`
- `cycle_return_net`
- `cycle_relative_return_vs_vnindex`
- `cycle_relative_return_vs_cash`
- `buy_now_label`

### C. Model scores

Path:
- `data/features/entry_alpha/entry_scores_daily.parquet`

Required columns:
- `time`
- `ticker`
- `entry_score`
- `entry_prob`
- `model_id`
- `threshold`
- `buy_now_pred`

### D. Final recommendation surface

Published through the shared recommendation engine:
- `data/features/recommendations/<profile>/latest_candidates.parquet`
- `data/features/recommendations/<profile>/manifest.json`

In that final candidate table, `score_final` should come from entry alpha, not just raw selector rank.

## Label contract

The first branch should use a simple, portfolio-aligned label.

### Baseline label

Signal timing:
- signal formed at `T` close
- entry at `T+1` open

Outcome horizon:
- hold until the next scheduled selector decision window
- for current `k5_r5_eq`, start with one selector cycle as the default horizon

Base target:
- `cycle_return_net = entry-to-cycle-exit return after fees`

Primary binary label:
- `buy_now_label = 1` if `cycle_return_net > cost_buffer`
- otherwise `0`

Recommended initial `cost_buffer`:
- round-trip fee proxy plus a small positive edge buffer

Why start here:
- this directly tests "is this stock worth buying now?"
- it does not depend on filling all `K` slots
- it naturally allows sparse books

### Optional secondary labels

Only after the baseline works:
- relative vs VNINDEX over the same cycle
- relative vs top-`K` basket mean
- asymmetric labels for high-conviction entry only

Do **not** start with a complicated pairwise replacement label.

## Feature contract

Start with existing daily and tradability data only.

Do not make this branch depend on new intraday data in its first pass.

### Minimum feature groups

1. Selector context
- `selection_score`
- `selection_rank`
- score gap vs next candidate
- score gap vs current held names

2. Tradability / implementation context
- `can_buy_next_open`
- recent blocked-buy counts
- `adv20`
- `tv_to_adv20`
- volume z-score
- ceiling/floor pressure proxies

3. Stock-level price state
- recent returns
- gap absorption
- compress/blowoff
- CLV / volatility / reversal features already in the matrix or nearby daily feature stack

4. Cross-sectional context
- percentile rank within candidate pool
- dispersion of the candidate pool
- breadth of buyable names

5. Exposure prior
- current H175-style activation signal
- but use it as a feature or threshold modifier, not as a hard veto

## Backtest contract

This branch should **not** be evaluated with the current fixed-width top-`K` contract first.

### First honest contract

Per signal date:
1. build candidate pool from top `M`
2. drop names that cannot be bought next open
3. score each candidate with entry alpha
4. buy only names with `entry_score >= threshold`
5. cap at `K`
6. if no names pass, stay partly or fully in cash

This is a **variable-breadth** portfolio by design.

### Why this is the correct contract

The hypothesis is exactly:
- sometimes one stock deserves buying
- the rest do not

So a fixed-width portfolio would dilute the signal and test the wrong thing.

### Evaluation order

1. always-on selector + entry alpha
2. always-on selector + entry alpha + sparse breadth
3. current sticky activation as soft prior
4. current sticky activation as hard veto only as a compatibility check

Do **not** start by mixing stock-level entry alpha into the frozen live branch.

## Sequential experiment ladder

If this branch is opened, run it as:

### H238: Candidate-panel contract

Implementation entrypoint:
- `analysis/h238_entry_alpha_candidate_panel.py`

Goal:
- publish the candidate panel and labels cleanly

Pass:
- clean panel
- no duplicate `(time, ticker)`
- stable cycle-aligned labels

Fail:
- label leakage or bad cycle alignment

### H239: Variable-breadth threshold baseline

Implementation entrypoint:
- `analysis/h239_entry_alpha_sparse_breadth_baseline.py`

Goal:
- test whether simple thresholding on existing selector score already beats fixed-width top-`K`

Examples:
- top-`M` candidates with `selection_score >= q80`
- score-gap threshold vs candidate `K+1`

Pass:
- sparse breadth improves validation without collapsing confirmation

Fail:
- thresholding alone adds nothing

### H240: Stock-level single-family entry screens

Goal:
- test simple daily/tradability entry rules before training a richer model

Examples:
- buy only if tradable + high conviction + low blocked-buy pressure
- buy only if score strong and local price-state confirms

Pass:
- at least one simple family shows consistent uplift over H239

Fail:
- no single-family entry evidence

### H241: Compact entry model

Goal:
- train a small supervised entry model on the candidate panel

Requirements:
- candidate-level walk-forward only
- no future cross-date leakage
- compact model first

Pass:
- improves H240 on validation and survives one-shot confirmation

Fail:
- no model uplift beyond simple thresholds

### H242: Soft exposure prior

Goal:
- combine the current activation family with entry alpha the right way

Test:
- activation as threshold shifter
- activation as max-breadth shifter
- activation as weight scaler

Pass:
- soft exposure prior beats pure entry-alpha baseline

Fail:
- activation only helps as a hard veto or not at all

### H243: Live-compatibility audit

Goal:
- test whether the entry-alpha winner can coexist with the frozen sticky live branch logic

Required checks:
- pseudo-live ladder
- parity against deterministic export
- sparse-book operational diagnostics

Pass:
- candidate for later live consideration

Fail:
- keep it offline only

## How this should plug into `shared-recommendation`

The shared recommendation layer already standardizes inference-time scoring and gating.

This branch should use it directly.

### Adapter plan

Keep:
- `SignalBlendAdapter` as the upstream selection prior

Add later:
- `EntryAlphaAdapter`
  - reads `data/features/entry_alpha/entry_scores_daily.parquet`
  - outputs `score_raw = entry_score`

### Policy plan

Keep:
- `TradabilityPolicy`

Add later:
- `ExposureBudgetPolicy`
  - reads global activation / exposure state
  - adjusts threshold or breadth
  - does **not** block all candidates by default

### Output behavior

Final candidate artifact should include:
- selector score
- entry score
- threshold used
- exposure regime
- blocked reasons
- final eligible flag

This lets alpha and RL-adjacent consumers read the same final contract.

## Guardrails

- Do not call this branch active while the acquisition-first timing branch is still the repo policy.
- Do not reopen generic activation tuning under a new name.
- Do not make global market timing the center of this branch.
- Do not start with a complex model before proving sparse variable-breadth baseline value.
- Do not mix new entry alpha and new exit alpha in the same first-pass ladder.

## Branch decision rule

Open this branch only if at least one of these becomes true:

1. acquisition-first timing work stalls or fails cleanly
2. forward live evidence suggests the main problem is breadth / forced-fill, not regime gating
3. the user explicitly chooses to reopen architecture work around stock-specific entry timing

Until then, treat this as a parked future branch design.
