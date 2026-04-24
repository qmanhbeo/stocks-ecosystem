# Low-Resource Data Pipeline Playbook

## Repo Rules To Re-read

- `AGENTS.md`
  - `Lightweight-First Rule`
  - `Thin-Orchestrator Rule`
- `README.md`
  - `Lightweight-First Execution Rule`
  - `Structure And Token Rule`
- `alpha-research-lab/README_for_AGENTS.md`
  - `Hard Resource Rule`
  - `Hard Structure Rule`

## Preflight Checklist

- Identify the canonical output path.
- Identify the owner script/module that should change.
- Inspect current file existence, size, row counts, and recent timestamps.
- Check whether a lighter publish-only or source-specific path already exists.
- Decide whether the task can be sequential and shard-based on `10GB RAM`.
- Decide the natural incremental output unit:
  - shard
  - file
  - day
  - batch
  - or another durable chunk the script can flush before finalization
- Decide the abort model before coding:
  - what survives a crash or manual stop
  - what remains staged and unpublished until finalize
  - how resume finds the last safe completed chunk

## Implementation Checklist

- Preserve root `data/` ownership rules.
- Keep one user-facing entrypoint.
- Split non-trivial stage logic into focused modules.
- Add stage caches, manifests, checkpoints, or shards if the workload can be
  interrupted or exceed comfortable memory.
- For scripts that can run longer than `2-3` minutes, flush partial durable
  outputs as each meaningful chunk completes instead of buffering the full
  result set for one terminal dump.
- If the consumer contract wants one final file, still write shard or stage
  outputs first and compact or finalize at the end.
- Make partial progress abort-safe by default:
  - append only to chunk-safe outputs
  - keep incomplete writes away from the published contract path
  - use manifests or checkpoints that let resume skip completed chunks
- Emit concise progress logs at chunk boundaries, phase changes, retries, and
  width reductions so the run never stays silent for long.
- Finalize outputs atomically.
- Do not change consumer contracts unless the task actually requires it.

## Verification Checklist

- Run focused tests around the changed path first.
- Verify the produced artifact path, schema, and row coverage.
- Confirm rerun/resume behavior when manifests or checkpoints are involved.
- Confirm that aborting between chunks does not corrupt the published output
  surface.
- State clearly if broader rebuilds or live refreshes were not run.

## Handoff Checklist

- Update the relevant docs if a new path, command, or artifact exists.
- Record the next exact command if the work is resumable.
- If the job has any unsafe restart edge case, document it explicitly.
- Leave machine-readable manifests or summaries whenever possible.
