# Watchdog Note Write-Back

What this file is for: the rule for recording material watchdog work in the
managed repo's own memory stack.

## Canonical Note Convention

Use
`/home/manh/.codex/skills/manh-memory-system/references/note-stack-convention.md`
as the canonical machine-wide note convention source.

The managed repo's existing convention wins when it is coherent and already in
use. If the repo has no coherent stack, bootstrap the light minimum through
`manh-memory-system`.

## Read Before Material Work

Before a material watchdog pass, read:

- the repo workflow doc
- the live-state note
- the latest relevant session
- the active findings chunk
- the active dead-ends chunk

## What Counts As Material Watchdog Work

Treat the pass as material when the watchdog does any of these:

- kills a job
- patches code or status surfaces
- relaunches a job after diagnosis
- changes batch width, worker width, or other hardware-sensitive settings
- identifies a reusable failure mode or optimization lesson
- bootstraps or repairs the repo note stack itself

Simple observation without action does not need a file write unless the user
asked for a recorded status pass.

## Where Each Update Goes

- live-state note
  - current active job state changed
  - next exact action changed
  - a blocker or hardware constraint became current
- session log
  - every material watchdog pass
- durable findings
  - reusable positive lesson, stable recovery rule, or durable optimization
- durable dead ends
  - rejected recovery path, unsafe intervention, or durable non-working fix
- operator README
  - when a script-heavy operational surface changed materially and future
    operators need the new rule

## Pointer Rules

Keep links explicit:

- live-state note points to the latest watchdog-related session
- session log points to any durable finding IDs or dead-end IDs touched
- durable findings and dead ends point back to the source session
- if nothing durable was promoted, say that explicitly in the session log

## Root Rule

The managed repo is the primary home for material watchdog memory. Do not keep
a separate global watchdog ledger as the main record.
