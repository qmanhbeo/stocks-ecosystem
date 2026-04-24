# Job Watchdog Loop

What this file is for: the default polling, diagnosis, and intervention ladder
for managed heavy scripts.

## Cheap Polling Order

Use this order on every pass:

1. read the managed job contract
2. read the latest structured progress source, starting with the canonical
   status file when it exists
3. read cheap hardware telemetry
4. compare current progress to the job's recent baseline
5. sample a minimal raw-log slice only if the structured view is stale or
   unhealthy

When the job is in early startup or recently relaunched, poll more often. Once
the job is stable, widen the interval.

Default cadence:

- early startup or recent relaunch:
  - every `2-5` minutes
- stable long run:
  - every `10-15` minutes

## Health Classification

Classify the job as:

- `healthy and progressing`
  - structured progress advanced within the last two polling intervals
- `healthy but slow`
  - progress is moving, but throughput is materially below the job's recent
    baseline
- `stalled`
  - no structured progress and no meaningful artifact movement for more than
    two polling intervals
- `failed`
  - structured state or a minimal raw-log sample shows an unrecovered error
- `hardware-unsafe`
  - RAM, VRAM, or CPU pressure makes continued execution unsafe

If a heavy script has no canonical status file or progress logs and the script
is being materially touched, treat that missing observability as fixable debt.

## Slowdown Detection

Compare the current throughput to the job's own recent baseline, not to a
generic absolute target.

Default rule:

- treat throughput as degraded when it stays below `70%` of the recent median
  baseline for `3` consecutive polls
- do not try to optimize if the machine is already near its safe hardware limit

## Hardware Safety

Default machine-safety posture:

- avoid widening work when RAM is above `85%`
- avoid widening GPU work when VRAM is above `90%`
- if the machine is already overloaded, prefer serialize, pause, reduce batch
  width, or relaunch more safely

If the repo documents stricter hardware rules, follow the repo rules.

## Intervention Ladder

Use the lightest effective action:

1. observe
- structured state is healthy
- write nothing unless the pass itself is material

2. diagnose
- read the smallest additional structured surfaces
- sample only the last useful raw-log slice

3. optimize locally
- lower batch or worker width
- reduce parallelism
- switch to an already documented lightweight or resume-safe path
- add the canonical status file and progress logs when the current task
  materially touches a heavy script that lacks them
- patch only the local surface that caused the slowdown or failure

4. kill and relaunch
- only when the job is resumable or explicitly restart-safe
- read the latest structured state first so you do not throw away recoverable
  progress

5. park
- stop autonomous recovery when restart safety is unclear, output corruption is
  possible, or the needed fix escapes the local patch boundary

## Raw Log Rules

Only sample logs when:

- structured state is stale
- structured state contradicts the actual artifact surface
- the process is clearly failing or hung and structured state does not explain
  why

Read the smallest slice that explains the problem. Do not reload full giant log
files into context if the last useful lines are enough.
