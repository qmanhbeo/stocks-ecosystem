# Heavy Script Observability

What this file is for: the machine-wide minimum observability contract for
heavy scripts on this machine.

## Default Rule

Heavy scripts should not be opaque. For any new heavy script, or any existing
heavy script that is being materially edited, require:

- a machine-readable status file
- periodic human-readable progress logs
- incremental durable outputs, checkpoints, or shard files when the run is
  expected to last beyond `2-3` minutes

Canonical status path:

- `artifacts/job_status/<job>.json`

`<job>` should be a stable lowercase snake_case slug that matches the script's
purpose. Keep the same slug in:

- the status filename
- the `job` field inside the status file
- any log prefix or operator-facing docs for that script

## When This Is Required

Require the contract when the script is expected to:

- run longer than a few minutes
- consume meaningful RAM, VRAM, CPU, disk, or network for a sustained period
- backfill or process a large corpus
- train or evaluate a local model
- build large staged artifacts or checkpoints
- be resumed, monitored, or handed off to another agent later

Tiny probes, one-off inspection snippets, and short utility scripts do not need
this contract.

## Legacy Rule

Existing heavy scripts without the contract are grandfathered.

That means:

- `job-watchdog` may still supervise them through manifests, summaries,
  checkpoints, artifact mtimes, and minimal raw-log sampling
- but the missing contract is technical debt
- once such a script is materially touched, add the observability contract as
  part of that pass unless the user explicitly requests no file changes

No logging at all is not acceptable for a heavy script that is being newly
created or materially refactored.

For the same class of script, "hold the full result in memory and dump it only
at the end" is not acceptable by default unless the output is truly tiny.

## Minimum Status File

The status file should stay compact and machine-readable. Require these top-
level fields:

- `job`
- `status`
- `started_at`
- `updated_at`
- `last_heartbeat`
- `phase`
- `progress`
- `throughput`
- `artifacts`
- `error` when failed

Use job-native progress, not fake percentages. Good units include:

- rows
- shards
- batches
- epochs
- days
- files
- retries

The `progress` field should make it obvious what has completed and what
remains. The `throughput` field should record the current or recent rate when
that rate is meaningful for slowdown detection.

If the repo already emits richer manifests or run summaries, the status file is
the cheap current heartbeat, not a replacement for those richer artifacts.

## Minimum Incremental Persistence

Heavy scripts expected to run beyond `2-3` minutes should leave durable partial
work behind as they go. Good forms include:

- append-safe row groups or parquet shards
- per-day or per-file partial outputs
- checkpoint directories
- candidate state or epoch summaries
- manifest counters that prove completed chunks
- partial prediction shards that can later be compacted

Bad default:

- materialize a large corpus in memory
- stay silent for a long interval
- write one giant terminal dump only at the end

If the final consumer contract wants one file or one published directory, still
prefer a two-step shape:

1. write incremental shard or stage outputs during execution
2. compact or finalize into the public contract at the end

That keeps long runs resume-safe and keeps watchdog supervision grounded in real
durable progress instead of hope.

## Abort-Safe Default

Prefer long-running heavy scripts that are abort-safe by default.

For this machine, that means:

- completed chunks or checkpoints survive crashes and manual stops
- incomplete writes do not corrupt the published consumer-facing path
- public outputs are promoted only on safe atomic boundaries
- resume can discover the last safe completed boundary without guesswork

If a heavy script cannot meet that standard, the limitation should be explicit
in the script contract and operator docs rather than hidden in behavior.

## Minimum Progress Logs

Heavy scripts should also emit periodic human-readable progress lines. Keep them
concise and milestone-based.

Each progress line should say:

- the current phase
- what unit advanced
- the current rate when meaningful
- the next milestone or checkpoint target when known
- the next incremental flush or checkpoint target when known
- any retry, cooldown, or width reduction when that materially changed behavior

Good triggers for a progress line:

- every N batches, shards, days, or files
- on phase changes
- on retry or cooldown
- when batch width, worker width, or device mode changed
- on completion or failure

Do not spam logs every loop iteration when the same signal can be emitted at a
coarser, still-useful interval.
