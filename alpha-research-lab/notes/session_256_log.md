# Session 256 Log

Date: 2026-05-04
Focus: Portfolio-policy library documentation

## Summary

- Added `notes/portfolio_policy_library.md` as the sibling registry to
  `notes/signal_library.md`.
- Clarified the distinction between ticker-level alpha signals and date-level /
  candidate-panel-level portfolio-policy state.
- Documented the current policy-state surfaces, action vocabulary, evaluation
  protocol, active frozen policy components, H379 offline policy evidence, and
  queued policy hypotheses.
- Updated `README.md` start-here pointers, `live_state.md`, and
  `sessions_compact.md`.

## Scope

This was a documentation / memory-stack pass only.

No experiment was run, no data surface was rebuilt, and no live branch changed.

## Key Additions

- `portfolio_policy_library.md` now records:
  - strict policy-experiment evaluation rules;
  - current state surfaces such as activation state, activation meta,
    entry-alpha candidate panel, tradability, and recommendations;
  - action vocabulary: `cash`, `top1`, `top2`, `top5`, `top10`,
    `sticky_hold`, `veto`, `wait_release`, and `scale_down`;
  - active/frozen policy components;
  - H379 `dynamic_candidate_thermodynamics` as offline evidence;
  - queued branches such as `candidate_count` router, `fresh_selection_pulse`,
    `tradability_release_pulse`, anti-signal veto, and candidate civil war;
  - a future path for `portfolio_policy_state_daily.parquet`.

## Current Read

The lab already tracks many portfolio-policy ingredients, but they are scattered
across activation surfaces and entry-alpha research artifacts. There is not yet
a canonical published policy-state surface. The right next research step remains
a narrower full-portfolio `candidate_count` K/cash router, as identified by
H379 / F339.

