# Root Agent Workflow

What this file is for: the workflow doc for machine-wide changes made at the
workspace root of `/home/manh/stocks-ecosystem/`.

## What This Repo Is For

This root repo coordinates the shared workspace:

- ecosystem-level contracts
- shared `data/` ownership and producer-consumer boundaries
- root docs and execution rules
- repo-owned skill specifications in `.skill-build/`

Use child repos for repo-local feature work. Use the root when the change is
machine-wide, workspace-contract-wide, or shared across repos.

## Work Loop

1. Read `README.md` and `AGENTS.md`.
2. Identify whether the change belongs at the root or in a child repo.
3. If the task changes a machine-wide global skill sourced here, update the
   repo-owned source copy first, then mirror the installed runtime copy.
4. Record material machine-wide global-skill work in:
   - `/home/manh/.codex/memories/global-skills/`
5. Do not keep machine-wide global-skill history in repo-root `notes/`.

## Heavy Script Rule

`job-watchdog` owns the machine-wide observability rule for heavy scripts.

For any new heavy script, or any materially touched heavy script, default to:

- canonical status file:
  - `artifacts/job_status/<job>.json`
- periodic human-readable progress logs

Legacy heavy scripts are grandfathered, but missing observability is debt and
should be repaired when the script is materially touched.

## Global Skill Memory Home

Machine-wide global-skill history now lives under:

- `/home/manh/.codex/memories/global-skills/`

That memory home owns:

- live state for machine-wide skill changes
- session history for global-skill revisions
- durable findings and dead ends for cross-repo skill conventions

Use
`/home/manh/.codex/skills/manh-memory-system/references/note-stack-convention.md`
as the canonical note convention source for that memory stack.

## Current Root-Owned Skill Source

The repo-owned edit surface for machine-wide skills added from this workspace is
under:

- `.skill-build/`

Installed runtime copies currently include:

- Codex: `~/.codex/skills/<skill-name>/`
- OpenCode: `~/.config/opencode/skills/<skill-name>/`

Treat `.skill-build/<skill-name>/` as the versioned source of truth and keep
installed runtime copies mirrored from it. The `experimentor` skill now points
new lightweight VN stock-lab experiments to
`alpha-research-lab/analysis/_template_research_branch.py` and
`alpha-research-lab/src/experiment_contract.py` so agents do not hand-roll S1
target semantics, no-`2026+` guards, state validation, IC summaries, or
run-summary artifacts.
