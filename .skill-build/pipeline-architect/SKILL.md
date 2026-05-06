---
name: pipeline-architect
description: Design or refactor non-trivial pipelines so they stay maintainable, low-context, and operationally clear. Use when a workflow needs a thin entrypoint, focused stage modules, explicit ownership boundaries, contract-aware docs updates, or cleanup of a large mixed-responsibility script into a smaller orchestrator plus stage files.
---

# Pipeline Architect

## Overview

Treat pipeline structure as an operational constraint. Favor one stable
user-facing entrypoint backed by a small number of focused stage modules.

## Machine-Wide Defaults

- Apply Manh's machine-wide cross-cutting defaults from
  `/home/manh/.codex/skills/manh-preference/references/working-defaults.md`
  before deciding how much to split, stage, or document.
- Prefer a thin orchestrator over a large mixed-responsibility script.
- Split real stages such as fetch, teacher, stage, build, train, publish, or
  verify into modules that can be inspected independently.
- For any new or materially touched heavy script, require the machine-wide
  heavy-script observability contract from
  `/home/manh/.codex/skills/job-watchdog/references/heavy-script-observability.md`:
  - `artifacts/job_status/<job>.json`
  - periodic human-readable progress logs
  - incremental durable outputs, checkpoints, or shard files for scripts
    expected to run beyond `2-3` minutes
- Grandfather legacy heavy scripts that lack that contract, but treat the
  missing status/logging surface as debt and add it when the script is
  materially touched.
- Do not design multi-minute heavy scripts around one giant terminal dump.
  Choose natural persistence boundaries and make partial durable progress
  visible before finalization.
- Prefer abort-safe-by-default long jobs:
  - completed chunks should survive crashes and manual stops
  - published outputs should only move on safe atomic boundaries
  - any unsafe restart limitation should be explicit in the command surface and
    docs
- Do not introduce a new abstraction framework unless reuse pressure is already
  real.
- Keep file boundaries optimized for maintenance and token efficiency, not just
  style.
- Update contract docs when paths, commands, schemas, or workflow expectations
  change.

## Repo Rule Pointer

When the current task is inside `/home/manh/stocks-ecosystem`, re-read:

- `/home/manh/stocks-ecosystem/AGENTS.md`
- `/home/manh/stocks-ecosystem/README.md`
- `/home/manh/stocks-ecosystem/alpha-research-lab/README_for_AGENTS.md`

Treat the repo `Thin-Orchestrator Rule`, `Structure And Token Rule`, and
consumer/producer doc-update expectations as hard constraints.

## Memory-System Rule

Treat the repo note stack as part of the architecture surface.

- Before material work, read the repo workflow doc plus the live-state note and
  the latest relevant session plus durable findings and dead-ends notes when
  they exist.
- Use
  `/home/manh/.codex/skills/manh-memory-system/references/note-stack-convention.md`
  as the canonical machine-wide note convention source.
- Follow the repo's established numbering if it is already coherent and
  grandfathered. Otherwise use the strict fresh-repo convention from
  `manh-memory-system`.
- After any material implementation, refactor, investigation, or architecture
  pass, update the appropriate note layer unless the work is trivial or the
  user explicitly requested no file changes:
  - live-state note when the active structure or next step changed
  - session log for the pass
  - durable findings when the structural conclusion should survive the current
    session
  - durable dead ends when the rejected or parked path should survive the
    current session
  - operator README when a script-heavy or pipeline-heavy surface changed
    materially

## Workflow

1. Map the current structure.
- Identify the entrypoint, the real stages, the shared helpers, and the user- or
  consumer-facing contract.

2. Choose the smallest clean split.
- Keep one canonical command.
- Separate stage logic only where there is real ownership or operational value.

3. Patch boundary surfaces together.
- Code structure.
- Public command surface.
- Heavy-script observability surface:
  - `artifacts/job_status/<job>.json`
  - periodic human-readable progress logs
  - incremental durable outputs or checkpoints on natural work-unit boundaries
  - abort-safe staging and atomic finalization for published outputs
- Manifest or artifact expectations.
- Docs, note-stack updates, and handoff notes.

4. Verify behavior stayed stable.
- Run focused tests and imports first.
- Broaden verification if shared contracts changed.

## Resources

Load `references/architecture-checklist.md` when you need the compact
checklist. Load
`/home/manh/.codex/skills/manh-preference/references/working-defaults.md`
when cross-cutting defaults matter. Load
`/home/manh/.codex/skills/manh-memory-system/references/note-stack-convention.md`
when you need the canonical note-stack rules. Load
`/home/manh/.codex/skills/job-watchdog/references/heavy-script-observability.md`
when the pipeline work creates or materially touches a heavy script.
