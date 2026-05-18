# Session 74 Log

## Objective
Turn the post-Session-73 branch state into an executable acquisition-first plan.

The modeling conclusion coming in was already clear:
- do not reopen activation tuning on the current local data stack
- do not reopen exit tuning on the current local data stack
- if timing research is to continue honestly, the next work must be new data acquisition

This session therefore focused on codifying the next branch, not on opening another hypothesis family.

## Starting point

Session 73 had already established:
- event surface v1 exists and is published
- event surface v1 failed the continuation / exit predictive gate
- local intraday coverage is unusable (`FPT` 1H only)
- local order-book / queue history is absent
- live branch stays frozen:
  - `full_library + k5_r5_eq + h175__rel2_gt0 + sticky_bonus_0p015`

What was still missing was a durable, explicit acquisition-first decision tree.

## What changed

### New canonical acquisition docs

Added:
- `notes/timing_data_acquisition_plan.md`
- `notes/timing_data_source_scorecard.csv`

These now define the active non-live branch.

### Branch logic now codified

Acquisition order is now explicit:
1. intraday / auction data first
2. richer company-event source second
3. otherwise stop timing research and wait for real data access or more forward live evidence

### Viability gates now explicit

Intraday / auction data is only usable if it clears:
- multi-ticker coverage
- historical access
- held-row coverage gate
- session/timestamp continuity
- enough fields to derive opening / first-hour / close-auction features

Richer company-event data is only usable if it clears:
- first-public timestamp recovery
- company-specific timing, not only quarter-phase
- material information improvement over event surface v1
- coverage / leakage checks

## Docs updated

Updated:
- `README.md`
- `README_for_AGENTS.md`
- `notes/live_state.md`
- `notes/data_sources.md`
- `notes/findings.md`

Main effect:
- future sessions should start from the acquisition plan, not from old timing scripts
- the branch order is now durable lab policy rather than conversational guidance

## Durable findings added

- `F155`
- `F156`

## Branch decision

Session 74 does **not** reopen any timing model branch.

The active next branch is:
- acquisition-first timing data work

The live branch remains:
- frozen
- monitor only

## Validation

Session 74 was a docs/planning codification pass.

Checks completed:
- `git diff --check` passed
