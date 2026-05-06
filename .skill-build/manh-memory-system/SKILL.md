---
name: manh-memory-system
description: "Maintain low-token repo memory: live_state.md, session logs, compact views, and durable findings/dead ends. Use for note bootstrap/reconciliation or material work write-back."
---

# Manh Memory System

Purpose: save future context. Keep memory terse, source-linked, and useful for
recovering current state, evidence, and next actions.

## Core Rules

- Inspect existing `README`, `AGENTS`, `notes/`, status files, and script docs
  before creating anything. Preserve coherent legacy names; add links or missing
  layers before renaming.
- Live brain: `notes/live_state.md` for current state, blockers/jobs, immediate
  next actions, and pointers. Keep it short; do not put narratives or durable
  findings there. Grandfather `next_steps.md` or `current_state.md` only when a
  repo already uses them coherently.
- Fresh baseline: `README_for_AGENTS.md`, `notes/live_state.md`,
  `notes/sessions_compact.md`, `notes/findings_compact.md`,
  `notes/deadends_compact.md`, `notes/session_00001.md`,
  `notes/findings_00001_00030.md`, `notes/dead_ends_00001_00030.md`.
- Material pass: work likely to matter later, such as behavior changes, repairs,
  investigations, architecture/contracts/schemas, pipelines, or meaningful
  verification/failure analysis. Skip typo-only, formatting-only, pure Q&A, and
  trivial edits with no durable consequence.
- After a material pass, update only what changed: session log,
  `sessions_compact.md`, `live_state.md` if current truth/blockers/jobs/next
  actions changed, durable findings/dead ends only for memory that should
  persist, and compact findings/dead ends only when durable memory changed.
- Use source anchors: session links, finding IDs, or dead-end IDs. Do not copy
  long detail into compact or live-state files.

## Reference

Do not load `references/note-stack-convention.md` by default. Load it only for
fresh bootstrap exact sections/numbering, ambiguous legacy reconciliation,
chunk rollover or durable ID numbering, or operator README trigger details.
