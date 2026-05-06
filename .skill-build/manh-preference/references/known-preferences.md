# Known Surfaced Preferences

What this file is for: the currently known machine-wide defaults that were made
explicit through recent repeated corrections and hardening passes.

## Current Defaults

- Prefer mechanical defaults over soft guidance.
- Prefer exact defaults with explicit carve-outs.
- Inspect first, then ask narrowly.
- Prefer probe-first, short concrete plans on non-trivial work.
- Prefer concise but decision-dense communication.
- Prefer semantic ownership for durable writeback and memory location.
- Prefer notes that optimize for recovery and restart.
- Missing a crucial pointer is worse than carrying a small amount of extra note
  text.
- Prefer hardening existing skills over creating new ones.
- Adjacent hardening is allowed only when it tightens the same contract.
- Mixed-responsibility scripts are the real form of bloat.
- Long jobs should be observable, incremental, abort-safe, and resumable by
  default.
- Prefer meaningful milestone logging over silence or spam.
- Grandfather legacy surfaces, then repair on touch.

## Why These Became Explicit

These defaults were promoted because recent machine-wide work repeatedly showed
that leaving them implicit caused:
- note ownership confusion
- silent or opaque long-running scripts
- oversized mixed-responsibility files
- vague or duplicated skill rules
- extra token cost during recovery and handoff

## Maintenance Rule

When a new repeated preference becomes decision-complete, add it here and align
`working-defaults.md` rather than scattering the rule across unrelated skills.
