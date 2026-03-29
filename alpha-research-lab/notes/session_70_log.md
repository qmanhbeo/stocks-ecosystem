# Session 70 Log

## Objective
Open a new sequential hypothesis ladder for **exit alpha** without changing the frozen live branch.

Hard rules unchanged:
- long-only only
- no synthetic hedges
- no shorting assumptions
- ADV / capacity parked for the current-account branch
- no tuning on `2026+`
- sequential hypothesis ladders remain mandatory

## Starting point

Session 69 ended with:
- frozen live branch:
  - `full_library + k5_r5_eq + h175__rel2_gt0 + sticky_bonus_0p015`
- offline lead selector:
  - `state_blend__h199_sector_laggard_gap_absorb__30`
- selector-discovery ladder closed under the locked protocol

That left one clear missing layer:
- selection alpha = what to buy
- activation alpha = when to have exposure
- exit alpha = when to stop holding a bought name after entry

The plan for Session 70 was:
1. add pluggable exit-rule support to the deterministic engine
2. test exit families always-on first
3. only if one family wins, test frozen sticky-activation compatibility
4. keep the live sticky branch unchanged unless the compatibility gate passes

## Implementation

New/extended code:
- `src/deterministic_portfolio.py`
  - added pluggable exit-rule support
  - added exit diagnostics to daily outputs, summaries, and blotters
- `src/exit_alpha.py`
  - exit-rule spec helper
  - canonical exit-state panel builder
- `src/exit_experiment_utils.py`
  - shared full-library backbone loader
  - shared multi-variant exit runner
- `src/exit_branch_utils.py`
  - anchor / baseline resolution across sequential exit ladders
- `tests/test_exit_alpha.py`

New experiment scripts:
- `analysis/h207_rank_decay_exit.py`
- `analysis/h208_time_plus_decay_exit.py`
- `analysis/h209_sticky_winner_exit.py`
- `analysis/h210_liquidity_deterioration_exit.py`
- `analysis/h211_strength_exhaustion_exit.py`
- `analysis/h212_replacement_pressure_exit.py`
- `analysis/h213_exit_activation_compatibility.py`

Implementation bug fixed during the branch:
- `replacement_pressure` allows `rank_exit_threshold=None`
- the shared engine was incorrectly forcing that through `int(None)`
- fixed in `src/deterministic_portfolio.py`
- reran the final branch steps after the fix

## H207 — Rank-Decay Exit

Goal:
- test whether the selector should sell after legal hold age when a held name falls enough in the cross-sectional ranking

Result:
- **PASS**
- promoted anchor:
  - `rank_decay__rank_exit_threshold_5p0__replacement_margin_0p05`
  - validation relative `+48.96%`
  - validation delta vs always-on baseline `+5.51%`
  - validation IR `0.89`
  - validation IR delta `+0.07`
  - confirmation relative `-20.49%`
  - confirmation delta `-0.48%`

Interpretation:
- explicit exit logic can improve the always-on selector
- the branch had a real anchor worth carrying forward

## H208 — Time-Plus-Decay Exit

Goal:
- test whether exits need extra maturation beyond the legal minimum hold age

Result:
- **FAIL**
- best candidate improved validation somewhat but failed the locked promotion rule
- no promoted variant over the H207 anchor

Interpretation:
- extra hold-time logic did not beat the simpler rank-decay anchor

## H209 — Sticky-Winner Exit

Goal:
- test whether the sticky retention idea also helps on the exit side

Result:
- **FAIL**
- best sticky-winner exit improved slightly
- it did not clear the promotion gate over the H207 anchor

Interpretation:
- sticky retention is useful in the live branch, but not enough here to create a better exit family

## H210 — Liquidity-Deterioration Exit

Goal:
- accelerate exits when sellability degrades after entry

Result:
- **FAIL**
- the baseline H207 anchor remained the winner
- liquidity-deterioration exits added no value under the locked protocol

Interpretation:
- post-entry liquidity stress is not the main missing edge in this branch

## H211 — Strength-Exhaustion Exit

Goal:
- test whether some positions should be sold because they have already run hard and their score has weakened

Result:
- **PASS**
- promoted exit winner:
  - `strength_exhaustion__return_since_entry_threshold_0p15__score_drop_threshold_0p05`
  - validation relative `+54.45%`
  - validation delta vs H207 anchor `+5.48%`
  - validation IR `1.17`
  - validation IR delta `+0.28`
  - confirmation relative `-4.70%`
  - confirmation delta vs H207 anchor `+15.79%`

Interpretation:
- the strongest exit family in Session 70 is not simple decay
- it is an exhaustion-style exit that reacts to a strong prior run plus score weakening

## H212 — Replacement-Pressure Exit

Goal:
- test whether exits should be driven by incoming challengers rather than weakness of the held name itself

Result:
- **FAIL**
- the H211 winner remained the branch leader
- replacement-pressure exits did not beat it

Interpretation:
- the current exit edge is better explained by strength exhaustion than by challenger pressure

## H213 — Frozen Sticky-Activation Compatibility

Goal:
- test whether the H211 winner actually helps the active live-compatible branch

Comparison set:
- incumbent sticky branch:
  - `full_library_plus_sticky`
- always-on exit winner:
  - `winner_always_on`
- sticky branch plus exit winner:
  - `winner_plus_sticky`

Result:
- **FAIL**

Incumbent sticky branch:
- validation relative `+29.65%`
- validation IR `0.61`
- confirmation relative `+18.80%`

Winner plus sticky:
- validation relative `+28.45%`
- validation IR `0.62`
- confirmation relative `+14.63%`

Always-on exit winner:
- validation relative `+54.45%`
- validation IR `1.17`
- confirmation relative `-4.70%`

Interpretation:
- exit alpha is real under the always-on selector
- but the promoted exit winner does **not** improve the frozen sticky live branch
- therefore it is not deployable evidence yet

## Branch decision

Live branch:
- unchanged
- keep:
  - `full_library + k5_r5_eq + h175__rel2_gt0 + sticky_bonus_0p015`

Offline research conclusions:
- exit alpha exists
- current best offline exit family:
  - `strength_exhaustion__return_since_entry_threshold_0p15__score_drop_threshold_0p05`
- do not promote it to live
- close the H207-H213 branch cleanly

Do not reopen:
- H207-H213 threshold retuning on the same locked protocol window

Next honest branch requirement:
- a genuinely new exit hypothesis family, or
- a genuinely new data family, or
- continue monitoring the frozen live branch only

## Artifacts

New summaries:
- `artifacts/run_summaries/latest_portfolio_exit_rank_decay.json`
- `artifacts/run_summaries/latest_portfolio_exit_time_plus_decay.json`
- `artifacts/run_summaries/latest_portfolio_exit_sticky_winner.json`
- `artifacts/run_summaries/latest_portfolio_exit_liquidity_deterioration.json`
- `artifacts/run_summaries/latest_portfolio_exit_strength_exhaustion.json`
- `artifacts/run_summaries/latest_portfolio_exit_replacement_pressure.json`
- `artifacts/run_summaries/latest_portfolio_exit_activation_compatibility.json`

Detailed outputs:
- `artifacts/portfolio_baselines/*h207_rank_decay_exit*`
- `artifacts/portfolio_baselines/*h208_time_plus_decay_exit*`
- `artifacts/portfolio_baselines/*h209_sticky_winner_exit*`
- `artifacts/portfolio_baselines/*h210_liquidity_deterioration_exit*`
- `artifacts/portfolio_baselines/*h211_strength_exhaustion_exit*`
- `artifacts/portfolio_baselines/*h212_replacement_pressure_exit*`
- `artifacts/portfolio_baselines/*h213_exit_activation_compatibility*`

## Validation

Session 70 hygiene completed:
- `python -m py_compile` passed on new code
- focused tests passed:
  - `tests/test_exit_alpha.py`
  - `tests/test_additive_selector_research.py`
- `git diff --check` passed
