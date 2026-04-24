# Job Watchdog Contract

What this file is for: the canonical contract for treating a heavy script as a
managed job instead of an opaque terminal command.

The detailed observability contract for heavy scripts lives in
`heavy-script-observability.md`. Use that reference when creating or materially
touching a heavy script.

## What Counts As A Managed Job

Treat a script as managed when one or more of these are true:

- it is expected to run for more than a few minutes
- it can saturate RAM, VRAM, CPU, disk, or network for a meaningful period
- it is resumable through checkpoints, manifests, or staged outputs
- it writes large intermediate artifacts or long backfills
- a future agent would need structured status to recover the pass cheaply

For new or materially touched heavy scripts, this also means the script should
expose the common observability contract at:

- `artifacts/job_status/<job>.json`
- periodic progress logs
- incremental durable outputs or checkpoints on natural work-unit boundaries

Treat abort-safe-by-default as the preferred machine-wide runtime posture for
those jobs.

Typical classes:

- training
- backfill
- staged builder
- heavyweight local inference or extraction
- long repair or republish pass

## Managed Job Definition

Before supervising a job, reconstruct this contract from the repo:

- `repo_root`
- `working_directory`
- `launch_command`
- `entry_surface`
  - main script or module
- `job_class`
- `structured_progress_sources`
  - manifests
  - run summaries
  - checkpoint directories
  - incremental shard or partial-output directories
  - canonical status file at `artifacts/job_status/<job>.json`
  - artifact mtimes or row counts when they are part of the repo contract
- `primary_outputs`
- `resumability`
  - resumable
  - restart-safe but not resumable
  - unsafe to restart without user input
- `abort_safety`
  - completed chunks survive aborts
  - published outputs stay coherent after aborts
  - any unsafe restart edge case is explicit
- `safe_restart_rule`
  - exact rule for when kill and relaunch is allowed
- `hardware_profile`
  - CPU-heavy
  - GPU-heavy
  - mixed
- `local_patch_boundary`
  - entry script
  - immediate helpers
  - checkpoint, manifest, and status surfaces
  - repo note surfaces
- `note_destination`
  - the managed repo's own memory stack
- `throughput_signal`
  - rows
  - shards
  - batches
  - epochs
  - days
  - files
  - or another job-native unit

## Structured Progress Hierarchy

Use this evidence order by default:

1. machine-readable manifests or summaries
2. canonical status file or equivalent compact runtime state
3. checkpoint counts, shard counts, or output growth
4. file mtimes on the structured outputs above
5. minimal raw-log sample

Do not tail full logs by default when a manifest or summary already answers the
question.

When the status file is missing on a legacy heavy script, fall back gracefully.
When the script is materially touched, add the missing observability contract.

## Restart Safety

Treat these cases differently:

- `resumable`
  - checkpoint or manifest state can preserve completed work
  - kill and relaunch is allowed after reading the current state first
- `restart-safe`
  - no checkpointing, but restarting only repeats bounded work without corrupting
    outputs
- `unsafe`
  - kill and relaunch could corrupt outputs, lose critical state, or duplicate
    side effects
  - do not auto-restart without user input

If restart safety is not discoverable, treat it as `unsafe` until proven
otherwise.

## Abort Safety

Prefer long jobs that are abort-safe by default.

That means:

- completed chunks, checkpoints, or shards survive a crash or manual stop
- incomplete work stays staged away from published consumer-facing outputs
- published outputs move only on safe atomic boundaries
- resume can discover the last safe completed boundary mechanically

Bad default:

- kill the process and hope the half-written output is still usable
- write directly into the public output path for the full duration of the run
- require a future agent to guess whether restart is safe

If a job cannot satisfy this standard, document the exact unsafe edge case in
the script contract and operator docs.

## Lifecycle States

Use these states when reasoning about the job:

- `queued`
- `running`
- `healthy_slow`
- `stalled`
- `failed`
- `patching`
- `redeploying`
- `completed`
- `parked`

`parked` means the watchdog intentionally stopped automatic recovery because the
surface is no longer safe for autonomous intervention.

## Patch Boundary

Auto-fixes may touch only:

- the job entrypoint
- immediate helper modules
- checkpoint, manifest, and status writers or readers
- repo note files required for material write-back

Do not use the watchdog as permission to do unrelated cleanup or broad
architecture work.
