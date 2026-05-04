# Portfolio Policy Library

This is the registry for portfolio-policy state in the alpha lab.

`signal_library.md` answers: which ticker-day signals contain predictive
information?

This file answers: when should the portfolio concentrate, diversify, hold,
wait, veto, or sit in cash?

Portfolio-policy state is not a standalone alpha signal. It is a date-level or
candidate-panel-level decision layer over already available selector, flow,
attention, and execution surfaces.

---

## Current Status

- We already track policy-state ingredients in research artifacts, especially
  `data/features/activation_state_daily.parquet`,
  `data/features/activation_meta_daily.parquet`, and
  `data/features/entry_alpha/candidate_panel_daily.parquet`.
- We do not yet publish a canonical
  `portfolio_policy_state_daily.parquet` consumer contract.
- H379/H380 provide offline evidence that candidate-panel state, especially raw
  `candidate_count`, can route K/cash decisions better than random policies.
  This is not a live-policy promotion.

## Evaluation Rules

Use these gates for any policy-state experiment:

1. Use a reusable script with saved artifacts.
2. Use TRUE walk-forward validation: train only on years strictly before the
   test year.
3. Do not fit on `2026+`; treat `2026+` as forward monitoring unless the user
   explicitly authorizes a different lockbox rule.
4. Compare against random policy baselines unless the branch is a direct
   variation of S1, C16, or another named signal.
5. Judge from saved summaries / parquet artifacts, not terminal output.
6. Keep actions long-only: cash, top-k, hold/sticky, wait/release, or veto.
   No shorts, synthetic hedges, or untradeable exposure assumptions.
7. Record whether the result is live promotion, offline evidence, or branch
   kill / park.

## Current Surfaces

| Surface | Role | Contract Level |
|---|---|---|
| `data/features/activation_state_daily.parquet` | Date-level selector/activation state. | Published feature surface |
| `data/features/activation_meta_daily.parquet` | Selector-efficacy activation metadata. | Published feature surface |
| `data/features/entry_alpha/candidate_panel_daily.parquet` | Candidate score shape, top-book breadth, buyability, blocked-buy, freshness-adjacent, and selector-health features. | Research artifact |
| `data/features/entry_alpha/entry_labels_cycle5.parquet` | Cycle labels used by entry/policy experiments. | Research artifact |
| `data/features/execution/tradability_daily.parquet` | Buy/sell/open tradability and execution-boundary state. | Published feature surface |
| `data/features/recommendations/<profile>/latest_candidates.parquet` | Model-agnostic candidate output consumed by downstream workflows. | Published recommendation surface |
| `artifacts/entry_alpha/*h379_dynamic_candidate_thermodynamics*` | Saved H379 broad policy-state experiment outputs. | Experiment artifact |
| `artifacts/entry_alpha/*h380_candidate_count_policy_router*` | Saved H380 narrowed candidate-count router outputs. | Experiment artifact |

## Action Vocabulary

Use this vocabulary for future policy surfaces and experiments.

| Action | Meaning |
|---|---|
| `cash` | No new long exposure. |
| `top1` | Concentrate in rank 1 only. |
| `top2` | Hold ranks 1-2. |
| `top5` | Default small book. |
| `top10` | Broaden exposure when the candidate set is diffuse. |
| `sticky_hold` | Keep qualifying incumbents despite normal rebalance churn. |
| `veto` | Refuse an otherwise attractive candidate. |
| `wait_release` | Wait for a blocked / limit-constrained name to become executable. |
| `scale_down` | Reduce K or exposure without going fully cash. |

## Policy-State Feature Families

These are the state families that should be tracked before adding another
portfolio-policy branch.

| Family | Examples | Interpretation |
|---|---|---|
| Candidate temperature | `candidate_count`, score entropy, rank gaps, top1-top5 spread, top5/top10 score std | How concentrated or diffuse the model's opportunity set is. |
| Execution boundary | buyable counts, blocked-buy counts, `can_buy_next_open`, limit-up/down, release flags | Whether desired exposure is executable now or delayed. |
| Selector health | recent selector return, hit rate, drawdown, turnover, cash, blocked-buy pain | Whether the current selector regime deserves trust. |
| Candidate memory | top-book overlap, top1 sameness, days since last top-k membership | Whether names are fresh discoveries or stale repeats. |
| Flow / attention disagreement | C16, insider, news/source/scope, no-news state, volume/order texture | Whether hidden demand is early, crowded, or contradicted. |
| Market mechanics | breadth, liquidity, boundary entropy, market-down state, calendar/settlement windows | Whether the market is in a regime where policy action matters. |

---

## Active / Frozen Policy Components

### PP1 — Frozen Sticky Live Branch

**Status:** live-monitor / frozen branch.

Current branch:

```text
full_library + k5_r5_eq + h175__rel2_gt0 + sticky_bonus_0p015
```

Policy role:
- `h175__rel2_gt0` is the on/off activation gate.
- `sticky_bonus_0p015` is a hold/retention policy that resists unnecessary
  churn in incumbents.
- `k5_r5_eq` is the frozen default breadth/action contract.

Do not retune this branch on `2026+`. Treat it as the live monitoring baseline
while research branches remain offline.

Source anchors:
- `README.md`
- `findings_compact.md` source anchors `F117-F143`.

### PP2 — Parked Complex Historical Winner

**Status:** parked.

Historical branch:

```text
full_library + k5_r5_eq + h175__rel2_gt0
  + sticky_bonus_0p015
  + impl__blocked5_q80
  + sector_cap_3
```

Policy role:
- implementation-pain veto,
- sector concentration cap,
- sticky hold.

This was the strongest historical system, but pseudo-live rollback rejected it.
Do not reopen it as the default live branch without a new locked protocol.

Source anchors:
- `README.md`
- `findings_compact.md` source anchors `F117-F143`.

### PP3 — Entry-Alpha Small-Book Contract

**Status:** offline evidence / parked.

Entry-alpha work showed the branch behaved more like a `top1` contract than a
`top5` timing overlay, but local confirmation overlays and label variants did
not produce a live-compatible replacement.

Policy role:
- useful as evidence that K matters,
- not sufficient as a promoted policy rule.

Source anchors:
- `findings_compact.md` source anchors `F157-F168`.
- Canonical artifacts:
  - `data/features/entry_alpha/candidate_panel_daily.parquet`
  - `data/features/entry_alpha/entry_labels_cycle5.parquet`
  - `data/features/entry_alpha/entry_scores_daily.parquet`

---

## Offline Policy Evidence

### PP4 — Dynamic Candidate Thermodynamics (H379)

**Status:** passed as offline policy evidence, not live promotion.

Claim:
- candidate-panel temperature can choose portfolio breadth
  (`cash/top1/top2/top5/top10`) better than random K policies.

Evidence:
- Reusable script:
  `analysis/h379_dynamic_candidate_thermodynamics.py`
- TRUE walk-forward test years: `2021-2025`.
- No `2026+` rows.
- Primary baseline: `2,000` random invested policies over
  `top1/top2/top5/top10`.

Result:
- mean policy absolute cycle return: `+0.00665`
- random invested mean: `+0.00508`
- mean lift: `+0.00157`
- years above random invested mean: `4 / 5`
- years above random invested p95: `1 / 5`
- 2025 confirmation lift: `+0.00108`

Read:
- This is real enough to keep the branch alive.
- It is not strong enough to change the live branch.
- `candidate_count` is the durable clue because it was selected in 2023, 2024,
  and 2025.

Follow-up:
- Addressed by H380 / PP5. Keep H379 as the broad-router parent evidence.

Source anchors:
- `F339`
- `session_255_log.md`
- `artifacts/run_summaries/20260504_124306_h379_dynamic_candidate_thermodynamics_research_branch_dynamic_candidate_thermodynamics.json`

---

### PP5 — Candidate Count Router (H380)

**Status:** passed as offline policy evidence, not live promotion.

Claim:
- raw `candidate_count` and a small set of predeclared candidate-count
  transforms can route breadth (`cash/top1/top2/top5/top10`) better than random
  K/cash policies.

Evidence:
- Reusable script:
  `analysis/h380_candidate_count_policy_router.py`
- TRUE walk-forward test years: `2021-2025`.
- No `2026+` rows.
- Primary baseline: `5,000` random K/cash policies over
  `cash/top1/top2/top5/top10`.
- Secondary baseline: `5,000` random invested policies over
  `top1/top2/top5/top10`.

Result:
- mean policy absolute cycle return: `+0.00796`
- random K/cash mean: `+0.00407`
- mean lift versus random K/cash: `+0.00389`
- mean lift versus random invested: `+0.00281`
- years above random K/cash mean: `4 / 5`
- years above random K/cash p95: `3 / 5`
- 2025 lift versus random K/cash: `+0.00472`
- 2025 lift versus random invested: `+0.00381`

Read:
- This strengthens dynamic breadth as a real portfolio-policy branch.
- It is still not a live branch because 2021 failed both random means and the
  rule is not a frozen consumer contract.
- Raw `candidate_count` is the durable state; every fold selected raw count,
  not delta or rolling-mean transforms.

Source anchors:
- `F340`
- `session_257_log.md`
- `artifacts/run_summaries/20260504_125947_h380_candidate_count_policy_router_research_branch_candidate_count_policy_router.json`

---

## Queued Policy Hypotheses

These are not promoted. They are here so future experiments use the right
contract and do not accidentally treat policy state as ticker alpha.

### PP6 — Fresh Selection Pulse

**Status:** queued / untested.

Hypothesis:
- a ticker entering the candidate set after long dormancy is different from a
  stale repeat or incumbent.

Policy action:
- concentration or inclusion boost for fresh discovery,
- possible veto or lower weight for stale repeat crowding.

Smallest honest test:
- compute days since last top-5/top-10 appearance from the candidate panel,
  then compare matched cycle returns for first-return, stale-repeat, and
  incumbent states.

### PP7 — Tradability Release Pulse

**Status:** queued / untested.

Hypothesis:
- alpha appears when a high-ranked name was good but unbuyable, then becomes
  buyable.

Policy action:
- `wait_release` followed by short-window inclusion, not a generic blocked-buy
  overlay.

Smallest honest test:
- `prev_can_buy_next_open == false`,
  `can_buy_next_open == true`,
  candidate rank,
  C16 support,
  and no immediate re-block.

### PP8 — Anti-Signal Annihilation Veto

**Status:** queued / untested.

Hypothesis:
- the long-only system may gain more by vetoing pretty candidates than by
  adding another weak long signal.

Policy action:
- veto high-ranked names when price score is attractive but flow, insider,
  attention, tradability, or sector context contradicts it.

Smallest honest test:
- apply veto only to candidate-book names,
- compare against random veto policies or matched random candidate drops,
- do not treat this as a short signal.

### PP9 — Candidate Civil War / Portfolio Uncertainty

**Status:** queued / untested.

Hypothesis:
- when S1, C16, insider, reversal, sector, and tradability voices nominate
  different names or sectors, the book should reduce K or exposure.

Policy action:
- `scale_down`, `cash`, or require stronger confirmation.

Smallest honest test:
- measure overlap among independent top-10 lists and test K/exposure policy
  decisions against random policy baselines.

---

## Future Canonical Surface

If this branch earns a maintained producer, the preferred research-owned surface
is:

```text
data/features/entry_alpha/portfolio_policy_state_daily.parquet
```

If downstream consumers need it as a shared contract, promote deliberately to:

```text
data/features/portfolio_policy_state_daily.parquet
```

Minimum columns:

```text
time
candidate_count
score_entropy_top10
score_spread_top1_top5
score_gap_5_6
top5_buyable_count
top10_buyable_count
blocked_buy_count_top10
buyable_breadth_all
liq_open_breadth_all
top5_overlap_prev
top1_same_prev
selector_recent_cycle_return
selector_recent_hit_rate
selector_recent_turnover
selector_recent_cash
selector_recent_blocked_buy
policy_action
policy_confidence
policy_reason_code
policy_version
```

Publication rule:
- keep experiment outputs under `artifacts/` until a frozen rule passes;
- keep research-owned daily state under `data/features/entry_alpha/` first;
- only promote to root `data/features/` after producer/consumer docs and
  downstream expectations are updated.
