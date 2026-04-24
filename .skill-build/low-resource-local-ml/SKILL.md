---
name: low-resource-local-ml
description: Plan, probe, implement, or verify local-model workflows for the stocks ecosystem under constrained WSL hardware. Use when building or changing PhoBERT, Ollama, transformers, encoder-distillation, local inference, staged training, checkpointed evaluation, or other local ML pipelines that must fit the default `10GB RAM` and `3GB VRAM` environment.
---

# Low-Resource Local ML

## Overview

Operate local ML work in this workspace as a constrained-system problem first
and a modeling problem second. Assume the default environment is WSL with
`10GB RAM` and `3GB VRAM`, and bias toward sequential, checkpointed,
inspection-heavy workflows unless the user explicitly overrides that profile.

## Read Order

1. Read the repo-wide hard rules first.
- `/home/manh/stocks-ecosystem/AGENTS.md`
- `/home/manh/stocks-ecosystem/README.md`

2. Read the lab workflow contract next.
- `/home/manh/stocks-ecosystem/alpha-research-lab/README.md`
- `/home/manh/stocks-ecosystem/alpha-research-lab/README_for_AGENTS.md`

3. Load task-specific docs only as needed.
- `/home/manh/stocks-ecosystem/data/README.md` when the task touches shared
  datasets
- `/home/manh/stocks-ecosystem/alpha-research-lab/notes/local_bert_roadmap.md`
  for local encoder strategy
- `/home/manh/stocks-ecosystem/alpha-research-lab/research_pipelines/news_features/README.md`
  when the work touches news-local lanes

4. Load `references/local-ml-playbook.md` when you need the compact checklist
for probing, implementation, verification, and handoff.

## Hard Defaults

- Assume one heavy local model or one heavy training process at a time.
- Probe current model availability, dataset size, cache state, and artifact
  layout before implementing.
- For any new or materially touched heavy script, require the machine-wide
  heavy-script observability contract from
  `/home/manh/.codex/skills/job-watchdog/references/heavy-script-observability.md`:
  - `artifacts/job_status/<job>.json`
  - periodic human-readable progress logs
  - incremental durable state such as staged datasets, checkpoint shards,
    candidate state, or prediction shards for any script expected to run beyond
    `2-3` minutes
- Grandfather legacy heavy scripts that lack that contract, but treat the
  missing status/logging surface as debt and add it when the script is
  materially touched.
- Treat "load everything, run silently, dump once at the end" as a design
  defect for heavy local-ML scripts unless the total output is genuinely tiny.
- Prefer abort-safe-by-default long runs.
- Assume training or inference can be interrupted at any time and make sure
  completed epochs, candidates, shards, or checkpoints survive aborts.
- If a long local-ML job cannot safely resume from the last checkpoint or safe
  chunk, document that limitation explicitly in the command surface and docs.
- Prefer encoder-first and task-specific heads over broad generator contracts on
  the default hardware unless the user explicitly wants otherwise.
- Use micro-batches, gradient accumulation, and sequential candidate runs before
  considering broader sweeps.
- Split teacher/stage/train/publish concerns into focused modules behind one
  stable entrypoint.
- Add manifests, candidate state, checkpoint shards, and run summaries whenever
  the workflow can fail midway.

## Workflow

1. Classify the request.
- Decide whether it is inference, weak-label extraction, stage building,
  fine-tuning, evaluation, or publish wiring.

2. Probe before patching.
- Inspect local model caches, current dataset sizes, current manifests, and the
  exact artifact contract already in place.

3. Design for survival on the default box.
- Keep model work sequential.
- Prefer stage datasets over repeatedly rescanning raw inputs.
- Pick a natural incremental persistence unit such as epoch, candidate, shard,
  or checkpoint interval and make partial durable state visible before the run
  finishes.
- Keep partial progress abort-safe:
  - save checkpoints or shards on safe boundaries
  - stage incomplete public outputs away from consumer-facing paths
  - atomically promote winner or published outputs only after safe completion
- Degrade to smaller micro-batches and longer runtime before widening memory
  usage.

4. Implement with structure discipline.
- Keep orchestration thin.
- Put teacher, stage, training, and evaluation logic in separate modules when
  the workflow is non-trivial.
- Leave enough machine-readable state that another engineer can resume after a
  crash.
- For heavy scripts, add the canonical status file, progress logs, and
  incremental outputs alongside manifests, candidate state, checkpoint shards,
  or run summaries.
- Document the exact resume point and any unsafe restart edge case when restart
  cannot simply continue from the last checkpoint.

5. Verify and hand off.
- Run focused tests and syntax/import checks first.
- State clearly whether a real model run was executed or only the pipeline/test
  path was verified.
- Record the exact next command and any hardware-sensitive assumptions.

## Output Pattern

End with:

- `task type`
- `hardware assumptions`
- `artifacts or models touched`
- `verification run`
- `what was not executed`
- `resume or next command`

## Resources

Load `references/local-ml-playbook.md` when you need the compact checklist for
probing, implementation, verification, and handoff. Load
`/home/manh/.codex/skills/job-watchdog/references/heavy-script-observability.md`
when creating or materially touching a heavy script.
