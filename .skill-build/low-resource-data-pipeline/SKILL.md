---
name: low-resource-data-pipeline
description: Design, refactor, extend, repair, or review data-ingestion and data-builder pipelines for the stocks ecosystem under constrained local hardware. Use when adding or changing fetchers, backfills, staged builders, publish flows, manifests, checkpoints, shard-based processing, resume logic, or validation paths, especially in `alpha-research-lab/data_tools/` and producer code that writes into the root `data/` warehouse.
---

# Low-Resource Data Pipeline

## Overview

Operate data pipelines for this workspace as low-resource, resume-safe systems.
Assume the default box is WSL with `10GB RAM` and treat that as a hard design
constraint unless the user explicitly says otherwise.

## Read Order

1. Read the repo-wide hard rules first.
- `/home/manh/stocks-ecosystem/AGENTS.md`
- `/home/manh/stocks-ecosystem/README.md`

2. Read the producer contract next.
- `/home/manh/stocks-ecosystem/alpha-research-lab/README.md`
- `/home/manh/stocks-ecosystem/alpha-research-lab/README_for_AGENTS.md`

3. If the task touches shared or maintained datasets, read:
- `/home/manh/stocks-ecosystem/data/README.md`
- `/home/manh/stocks-ecosystem/alpha-research-lab/data_tools/README.md`

4. Load `references/pipeline-playbook.md` when you need the compact execution
checklist for probing, implementation, verification, and handoff.

## Hard Defaults

- Treat root `data/` as canonical.
- Probe the current owner, artifact state, row counts, and file layout before
  implementing.
- For any new or materially touched heavy script, require the machine-wide
  heavy-script observability contract from
  `/home/manh/.codex/skills/job-watchdog/references/heavy-script-observability.md`:
  - `artifacts/job_status/<job>.json`
  - periodic human-readable progress logs
  - incremental durable outputs, checkpoints, or shard files for any script
    expected to run beyond `2-3` minutes
- Grandfather legacy heavy scripts that lack that contract, but treat the
  missing status/logging surface as debt and add it when the script is
  materially touched.
- Treat end-of-run giant dumps as a design defect for heavy scripts unless the
  total output is genuinely tiny. Prefer append, shard, checkpoint, or finalize
  flows over hoarding full results in memory.
- Prefer abort-safe-by-default designs for long jobs.
- Assume interruption can happen at any time and make sure completed chunks
  survive aborts through append-safe shards, checkpoints, staged outputs, or
  atomic finalization.
- If a long job cannot safely resume from the last completed checkpoint or
  chunk, state that limitation explicitly in the script contract and docs
  instead of leaving restart behavior ambiguous.
- Prefer the narrowest safe fetch/build/repair path over full rebuilds.
- Build stage/checkpoint/resume/finalize flows when a pipeline can be large or
  interruptible.
- Keep one stable entrypoint and split real logic into focused stage modules.
- Do not add new large mixed-responsibility scripts when teacher/build/publish
  or fetch/stage/build concerns can be separated cleanly.
- Write machine-readable manifests or summaries whenever another engineer may
  need to resume the work.

## Workflow

1. Classify the request.
- Decide whether it is a fetcher, repair, staged builder, publish path, or
  contract change.

2. Probe before patching.
- Inspect the real input/output paths, canonical owner script, current coverage,
  and whether a narrower path already exists.

3. Design for the default hardware profile.
- Stream or batch large joins.
- Avoid all-at-once full-corpus materialization when a shard path can produce
  the same contract.
- Pick a natural incremental persistence unit such as day, shard, file, or
  batch and write durable progress there as work completes.
- Keep partial progress abort-safe:
  - write append-safe chunks
  - stage incomplete outputs away from published paths
  - atomically finalize public outputs only after a safe boundary completes
- Prefer sequential stages over concurrent heavy work.

4. Implement with structure discipline.
- Keep orchestration thin.
- Put heavy stage logic into focused modules.
- Add manifests, checkpoints, and atomic finalization where interruption risk is
  real.
- For heavy scripts, add the canonical status file, progress logs, and
  incremental outputs alongside those richer manifests or checkpoints.
- Document the exact resume point and any unsafe restart edge case when the job
  cannot simply continue from the last checkpoint.

5. Verify and hand off.
- Run the narrowest meaningful tests first, then broader targeted verification.
- Record exactly what was built, how to resume, and what remains out of scope.

## Output Pattern

End with:

- `request class`
- `owner script or modules`
- `inputs touched`
- `outputs expected`
- `verification run`
- `resume or follow-on steps`

## Resources

Load `references/pipeline-playbook.md` when you need the compact execution
checklist for probing, implementation, verification, and handoff. Load
`/home/manh/.codex/skills/job-watchdog/references/heavy-script-observability.md`
when creating or materially touching a heavy script.
