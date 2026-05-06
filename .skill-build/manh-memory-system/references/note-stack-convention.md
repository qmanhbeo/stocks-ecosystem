# Repo Memory Lookup

Load this file only when `SKILL.md` is not specific enough. Normal memory
write-back should use the short skill instructions alone.

## Baseline Files

Fresh repos:
- `README_for_AGENTS.md`: workflow, guardrails, note locations, common commands.
- `notes/live_state.md`: current state, blockers/jobs, immediate next actions.
- `notes/sessions_compact.md`: newest-first recovery lines for material sessions.
- `notes/findings_compact.md`: thematic summary of durable findings.
- `notes/deadends_compact.md`: thematic summary of durable failed/parked paths.
- `notes/session_00001.md`: first material session log.
- `notes/findings_00001_00030.md`: durable finding entries.
- `notes/dead_ends_00001_00030.md`: durable dead-end entries.

Legacy mappings to preserve when coherent:
- workflow: `AGENTS.md`, `docs/operator_guide.md`
- live state: `notes/next_steps.md`, `notes/current_state.md`, `TODO.md`,
  `STATUS.md`
- sessions: `notes/session_*.md`, `docs/worklog/*.md`, dated logs
- durable memory: `notes/findings*.md`, `notes/dead_ends*.md`, `docs/adr/*.md`,
  `LESSONS.md`

## File Duties

`live_state.md` should stay short and include:
- `Current State`
- `Active Jobs / Constraints`
- `Immediate Next Actions`
- `Do Not Reopen Unless`
- `Pointers`
- `Last verified: <session/date>` when checked or refreshed

Session logs should include:
- what changed and why
- assumptions and failed attempts
- validation run or explicitly not run
- `Results`
- next exact step
- durable-promotion status: finding/dead-end IDs touched, or none
- links back to live state and source durable entries

Compact files:
- are recovery views, not source truth
- must include source anchors: session links, finding IDs, or dead-end IDs
- should be terse and newest/useful-first
- must not invent conclusions missing from source notes

Durable findings:
- use stable IDs `F00001`, `F00002`, ...
- store positive conclusions, reusable lessons, or durable observations
- include limits/qualifiers and source session links

Durable dead ends:
- use stable IDs `D00001`, `D00002`, ...
- store failed, rejected, parked, or blocked paths future agents should avoid
- include the failure reason, reopening condition when relevant, and source links

## Numbering

Fresh-repo rules:
- session filenames are 5 digits: `session_00001.md`, `session_00002.md`
- finding/dead-end chunks contain 30 entries
- chunk names use inclusive ranges:
  - `findings_00001_00030.md`, then `findings_00031_00060.md`
  - `dead_ends_00001_00030.md`, then `dead_ends_00031_00060.md`
- entry IDs continue across chunks
- do not create separate index files for findings or dead ends
- do not manually number entries inside compact files

## Material-Pass Closeout

A material pass is work likely to matter in a future session: behavior changes,
root-cause investigations, pipeline/model/data changes, architecture, contracts,
schemas, or meaningful verification/failure analysis.

Closeout checklist:
- session log updated
- `sessions_compact.md` prepended with a source-linked entry
- `live_state.md` updated only if current state, blockers, jobs, or next actions
  changed; refresh `Last verified` when checked
- durable findings promoted only when the conclusion should persist
- durable dead ends promoted only when the failure/parked path should persist
- `findings_compact.md` or `deadends_compact.md` updated only when durable memory
  changed

Usually skip note updates for typo-only edits, formatting-only cleanup, pure Q&A,
or trivial one-line work with no durable consequence.

## Operator README Trigger

Add or refresh a folder README only for script-heavy or operationally important
surfaces such as `data_tools/`, `scripts/`, `pipelines/`, or `jobs/`.

Do it when commands, inputs/outputs, checkpoints, resume behavior, heavyweight
warnings, or published contracts changed materially.
