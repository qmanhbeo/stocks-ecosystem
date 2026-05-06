# Manh Machine-Wide Working Defaults

What this file is for: the canonical cross-cutting defaults that future agents
should apply broadly on substantial work unless a named carve-out applies.

## Hardware

### Conservative Local Budget

Default:
- Plan heavy local work against a conservative machine budget, not the visible
  ceiling.

Scope:
- local ML
- heavy pipelines
- long-running scripts

Carve-out:
- a repo can document a stricter local limit
- the user can explicitly override the budget for a task

Legacy behavior:
- older scripts may assume a looser budget; tighten them when materially
  touched

Related:
- `low-resource-data-pipeline`
- `low-resource-local-ml`
- `job-watchdog`

## Scripts And Runtime

### Observable Long Jobs

Default:
- Any heavy or multi-minute script should be observable, incremental,
  abort-safe, and resumable by default.

Scope:
- training
- backfills
- staged builders
- heavyweight inference
- any script expected to run beyond `2-3` minutes

Carve-out:
- tiny outputs or genuinely short jobs do not need the full heavy-script
  contract

Legacy behavior:
- grandfather legacy opaque scripts, but treat missing observability as debt
  and repair on touch

Related:
- `job-watchdog`
- `low-resource-data-pipeline`
- `low-resource-local-ml`

### Meaningful Logging

Default:
- Prefer meaningful milestone logs, not silence and not spam.

Scope:
- heavy scripts
- staged pipelines
- long verification passes

Carve-out:
- very small scripts can log minimally if their structured status is still
  clear

Legacy behavior:
- silent long scripts are tolerated only until the next material touch

Related:
- `job-watchdog`

### Mixed Responsibility Is The Real Bloat

Default:
- A script is "too big" mainly when it mixes multiple responsibilities, not
  only when it crosses a line-count threshold.

Scope:
- pipeline entrypoints
- training scripts
- builders and publish flows

Carve-out:
- a larger file is acceptable when the workflow is genuinely single-purpose and
  still easy to inspect

Legacy behavior:
- grandfather coherent older files; split them when change pressure or recovery
  cost becomes high

Related:
- `pipeline-architect`

## Notes And Ownership

### Recovery Over Narrative

Default:
- Notes should optimize for recovery, restart, and handoff, not for rich
  narrative history.

Scope:
- live state
- session logs
- durable findings and dead ends

Carve-out:
- research branches can include extra narrative when it changes experimental
  interpretation

Legacy behavior:
- older narrative-heavy notes can remain, but new material sessions should stay
  recovery-first

Related:
- `manh-memory-system`

### Pointer Completeness Over Extreme Sparseness

Default:
- Missing a crucial pointer is worse than carrying a small amount of extra note
  text.

Scope:
- links between live state, sessions, durable findings, dead ends, operator
  docs, and active artifacts

Carve-out:
- avoid redundant pointer spam when one precise pointer is enough

Legacy behavior:
- add missing pointers when touching an existing note surface

Related:
- `manh-memory-system`

### Semantic Ownership Wins

Default:
- Durable writeback should go to the semantic owner of the contract, not merely
  the directory where code changed.

Scope:
- repo notes
- machine-wide skills
- subsystem operator docs

Carve-out:
- when the semantic owner is genuinely ambiguous, prefer the smallest local
  surface and make the ambiguity explicit

Legacy behavior:
- older misplaced notes can stand unless they actively confuse recovery

Related:
- `manh-memory-system`

## Verification And Planning

### Inspect Then Ask Narrowly

Default:
- Inspect first, then ask only the smallest question that materially changes
  the work.

Scope:
- planning
- debugging
- architecture
- implementation

Carve-out:
- ask earlier only when the ambiguity is high-impact and cannot be resolved
  locally

Legacy behavior:
- none; this is a behavior default rather than a file migration rule

Related:
- `verification-first`

### Probe-First, Short Concrete Plan

Default:
- For non-trivial tasks, probe the real state first and then form a short,
  concrete plan rather than an essay-like theoretical setup.

Scope:
- implementation
- reviews
- bug work
- pipeline changes

Carve-out:
- longer planning is acceptable when the task is explicitly planning-only or
  architecture-heavy

Legacy behavior:
- none

Related:
- `verification-first`
- `pipeline-architect`

## Architecture

### Harden Existing Skills First

Default:
- Prefer strengthening an existing skill or contract before inventing a new
  skill.

Scope:
- machine-wide skill work
- repo skill work

Carve-out:
- create a new skill when the work is genuinely a new class with distinct
  triggers and references

Legacy behavior:
- keep existing skills even if the boundary would be drawn differently now

Related:
- `manh-preference`

### Tighten The Same Contract Only

Default:
- Adjacent hardening is acceptable only when it tightens the same contract that
  the current task already opened.

Scope:
- implementation side quests
- local process hardening
- neighboring docs

Carve-out:
- broader fixes still require explicit user direction

Legacy behavior:
- none

Related:
- `manh-preference`

## Communication

### Concise But Decision-Dense

Default:
- Report work back concisely, but include exact outcomes, blockers, and next
  steps.

Scope:
- user updates
- final handoff
- note writeback

Carve-out:
- provide more detail when the user explicitly asks for depth or the risk is
  high

Legacy behavior:
- none

Related:
- `manh-preference`
