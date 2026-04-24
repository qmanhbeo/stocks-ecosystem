---
name: job-watchdog
description: Supervise heavy scripts under local hardware constraints. Use when running, monitoring, resuming, diagnosing, repairing, or optimizing long or hardware-sensitive jobs such as model training, staged builders, heavyweight local inference, resumable backfills, or any other script that should be watched through structured progress and auto-recovered when safe.
---

# Job Watchdog

## Overview

Operate heavy scripts as managed jobs, not as blind terminal sessions. Use a
structured-state-first loop: start with the cheapest structured signals, keep
the machine inside hardware limits, and intervene automatically within the
local job surface when the job is stalled, failed, or materially
underperforming.

## Read Order

1. Read the managed repo's workflow and hard rules first.
- the repo's `README.md`
- the repo's `README_for_AGENTS.md`, `AGENTS.md`, or equivalent workflow doc

2. Read the managed repo's memory docs before material watchdog work when they
exist.
- the live-state note
- the latest relevant session log
- the active durable findings chunk
- the active durable dead-ends chunk

3. Load the compact watchdog references as needed.
- `references/watchdog-contract.md`
- `references/heavy-script-observability.md`
- `references/watchdog-loop.md`
- `references/watchdog-notes.md`
- `references/stocks-ecosystem-example.md` when the task matches this workspace

## Hard Defaults

- Treat any heavy or hardware-sensitive script as a managed job.
- For new or materially touched heavy scripts, require the common
  observability contract:
  - machine-readable status file at `artifacts/job_status/<job>.json`
  - periodic human-readable progress logs
  - incremental durable outputs, checkpoints, or shard files for scripts
    expected to run beyond `2-3` minutes
- Grandfather legacy heavy scripts that do not yet expose the contract, but
  treat missing observability as debt and add the contract when the script is
  materially touched.
- Treat silent long runs and one-shot terminal dumps as design defects for
  heavy scripts unless the total output is genuinely tiny.
- Prefer abort-safe-by-default long jobs:
  - completed chunks should survive manual stops or crashes
  - published outputs should only move at safe atomic boundaries
  - any unsafe restart limitation should be explicit, not implicit
- Prefer manifests, run summaries, checkpoint state, compact status files, and
  artifact mtimes over raw stdout or stderr.
- Treat raw logs as fallback evidence only when structured state is stale,
  contradictory, or clearly unhealthy.
- Keep one heavy managed job active at a time unless the repo explicitly
  documents safe concurrency.
- Check CPU, RAM, and GPU VRAM before widening throughput, restarting, or
  running another heavy job.
- Auto-recovery is allowed:
  - kill
  - patch
  - relaunch
  - park
- Limit auto-fixes to the local job surface:
  - the entry script
  - immediate helper modules
  - checkpoint, manifest, and status surfaces
  - repo note surfaces
- Do not auto-commit.
- Do not widen into broad refactors without user input.

## Workflow

1. Classify the job first.
- Identify the job class, structured progress sources, restart safety, and the
  local patch boundary.
- Decide whether the script already satisfies the heavy-script observability
  contract or must be upgraded as part of the current material pass.
- Decide whether the script persists meaningful incremental outputs yet or is
  still hoarding work in memory until the end.
- Decide whether the job is actually abort-safe yet or only partially
  resumable.

2. Probe cheaply before acting.
- Read structured status first.
- Check hardware headroom.
- Sample only the smallest raw-log slice needed if structured state is not
  enough.

3. Judge the current state.
- Classify the job as:
  - healthy and progressing
  - healthy but slow
  - stalled
  - failed
  - hardware-unsafe

4. Intervene automatically when safe.
- Prefer the lightest correction that restores safe progress.
- If the job is resumable, preserve checkpointed work before restarting.
- If the job is materially slower than its own recent baseline and hardware
  headroom exists, optimize the local surface before widening resource usage.

5. Write the pass back into repo memory.
- For material interventions, update the managed repo's live-state note, session
  log, and durable findings or dead ends as appropriate.
- Use
  `/home/manh/.codex/skills/manh-memory-system/references/note-stack-convention.md`
  as the canonical machine-wide note convention source.
- If the repo has no coherent memory stack, bootstrap the light minimum using
  `manh-memory-system`.

## Resources

Use:

- `references/watchdog-contract.md` for the managed-job contract
- `references/heavy-script-observability.md` for the required status and
  progress-log contract for heavy scripts
- `references/watchdog-loop.md` for the polling and intervention ladder
- `references/watchdog-notes.md` for note-writeback rules
- `references/stocks-ecosystem-example.md` for concrete examples in this
  workspace
