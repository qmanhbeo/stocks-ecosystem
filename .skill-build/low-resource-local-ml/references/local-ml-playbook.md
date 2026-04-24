# Low-Resource Local ML Playbook

## Repo Rules To Re-read

- `AGENTS.md`
  - `Lightweight-First Rule`
  - `Thin-Orchestrator Rule`
- `README.md`
  - `Structure And Token Rule`
- `alpha-research-lab/README_for_AGENTS.md`
  - `Hard Resource Rule`
  - `Hard Structure Rule`

## Preflight Checklist

- Confirm the default hardware assumption still applies: `10GB RAM`,
  `3GB VRAM`, WSL.
- Inspect local model availability before choosing candidate checkpoints.
- Inspect dataset size, staged caches, manifests, and existing run summaries.
- Decide whether the task is inference-only, data staging, or training.
- Decide the natural incremental persistence unit:
  - checkpoint interval
  - epoch
  - candidate
  - prediction shard
  - or another chunk that can be written safely before the run ends
- Decide the abort model before coding:
  - what survives a crash or manual stop
  - how resume discovers the last safe checkpoint or shard
  - which outputs stay staged until the run is safely complete

## Implementation Checklist

- Keep one stable command or entrypoint.
- Split teacher/stage/train/eval logic into focused modules for non-trivial
  workflows.
- Prefer sequential candidate runs.
- Use micro-batches and gradient accumulation before larger live batches.
- Save machine-readable manifests, candidate state, and winner summaries.
- For scripts expected to run beyond `2-3` minutes, write partial durable state
  as the work advances instead of keeping the whole result or prediction corpus
  in memory for one terminal dump.
- Make partial progress abort-safe by default:
  - save checkpoints or shards on natural safe boundaries
  - avoid publishing incomplete outputs into consumer-facing paths
  - keep enough state to resume after an interrupted run without replaying the
    entire corpus unless that limitation is explicitly documented
- Emit concise progress logs on phase changes, batch or epoch milestones,
  retries, and width reductions so the run is not silent.
- Finalize public outputs only after all required intermediate steps succeed.

## Verification Checklist

- Run syntax/import checks after refactors.
- Run focused tests around dataset staging and resume logic.
- Confirm that interrupting between safe boundaries would preserve completed
  work and keep published outputs coherent.
- Verify broader suite coverage if shared contracts moved.
- State explicitly whether a real fine-tune or inference pass was run.

## Handoff Checklist

- Record the next exact command.
- Record what artifacts are safe to reuse.
- Record which stages are complete and which are still pending.
- If the job has any unsafe restart edge case, document it explicitly.
