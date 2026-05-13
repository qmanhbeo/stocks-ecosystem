# Session 66 Log

## Objective
Reopen alpha discovery in parallel while freezing the active live sticky branch.

Hard rules unchanged:
- long-only only
- no synthetic hedges
- no shorting assumptions
- ADV / capacity parked for the current-account branch
- no tuning on `2026+`

## Starting point

Session 65 left the repo in the right operational posture:
- live branch frozen at:
  - `full_library + k5_r5_eq + h175__rel2_gt0 + sticky_bonus_0p015`
- forward monitoring only on `2026+`
- local activation tuning paused unless sticky fails forward

That freed the offline branch to move back to selection-side research.

The main process risk was leakage:
- reusing `2023-2025` too casually
- inventing new selectors without a clear evaluation contract

So Session 66 first codified the protocol, then ran the first two research experiments under it.

## Protocol implementation

New shared code:
- `src/research_protocol.py`
- `src/tradability_conditioned_research.py`

Locked protocol:
- dev / discovery: `2015-2022`
- validation: `2023-2024`
- one-shot confirmation: `2025`
- forward lockbox: `2026+`

This is now the canonical selection-side evaluation split.

## H151 — tradability-conditioned composite bakeoff

Goal:
- test whether the strongest H150 conditional-uplift signals form a stronger narrow selector than the current full-library baseline

Candidates:
- `core_4 = S1 + C7 + C12 + C13`
- `core_5 = S1 + C7 + C10 + C12 + C13`
- `core_6 = S1 + C7 + C8 + C10 + C12 + C13`
- baseline:
  - `full_library`

Construction:
- top-5
- equal-weight
- rebalance every 5 signal days
- no ADV cap

Result:
- baseline stayed best on validation:
  - `+43.45%` relative vs VNINDEX
  - IR `0.8211`
- narrow composites all failed validation:
  - `core_5`: `-23.98%`, IR `-0.4041`
  - `core_6`: `-33.20%`, IR `-0.6980`
  - `core_4`: `-54.97%`, IR `-1.4111`
- none survived `2025` confirmation
- no promoted selector candidate

Interpretation:
- H150’s strongest conditional components do not automatically form a better standalone selector
- the existing `full_library` selector remains the right backbone

## H152 — tradability-conditioned signal search

Goal:
- search for new stock-level alpha only inside tradable / liquidity-opening states

Primary state:
- `liq_open_basic = can_buy_next_open & tv_to_adv20 >= 1.10 & clv >= 0.45`

Candidate families tested:
- `h152_liq_open_continue_3`
- `h152_limit_release_pressure`
- `h152_sector_laggard_tradable`
- `h152_gap_quality_entry`
- `h152_breakout_volume_quality`

Standalone dev-pass survivors:
- `h152_sector_laggard_tradable`
  - dev IC `+0.0264`
  - corr with S1 `+0.1536`
  - validation IC `+0.0163`
- `h152_limit_release_pressure`
  - dev IC `+0.0236`
  - corr with S1 `+0.1552`
  - validation IC `+0.0127`
- `h152_liq_open_continue_3`
  - dev IC `+0.0248`
  - corr with S1 `+0.1331`
- `h152_breakout_volume_quality`
  - dev IC `+0.0196`
  - corr with S1 `+0.1006`

But naive selector relevance was poor:
- validation relative returns stayed negative for every dev-pass signal
- no signal was promoted to selector stage

Interpretation:
- there are still tradability-conditioned alpha atoms available
- but they are not ready to replace the current selector as stand-alone always-on systems

## Branch decision

Session 66 did **not** change the live branch.

Live track:
- keep sticky frozen
- continue `H179/H183` only

Research track:
- `H151` is complete and failed cleanly
- `H152` is complete first-pass and produced candidate atoms, not a new selector

So the next offline branch should be:
1. `H196`: additive bakeoff with the strongest `H152` atoms on top of the current selector backbone
2. if that fails, `H197`: second-wave tradability-conditioned signal families

Important anti-leakage rule:
- do not keep tuning the current `H151/H152` families against `2025`
- use dev / validation to rank them
- touch `2025` once per promoted candidate only

## Artifacts

Session 66 summaries:
- `artifacts/run_summaries/latest_portfolio_tradability_composite_bakeoff.json`
- `artifacts/run_summaries/latest_tradability_conditioned_signal_search.json`

Detailed outputs:
- `artifacts/portfolio_baselines/*h151_tradability_conditioned_composite_bakeoff*`
- `artifacts/portfolio_baselines/*h152_tradability_conditioned_signal_search*`

## Validation

Session 66 hygiene completed:
- `python -m py_compile` passed on new code
- focused tests passed:
  - `tests/test_research_protocol.py`
  - `tests/test_tradability_conditioned_research.py`
- `git diff --check` passed
