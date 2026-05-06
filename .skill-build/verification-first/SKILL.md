---
name: verification-first
description: Enforce a probe-first, verify-after workflow for engineering tasks. Use when implementing or reviewing code that should begin with preflight inspection, continue with focused implementation, then run the narrowest meaningful tests first and only broaden verification when shared contracts or cross-module behavior changed.
---

# Verification First

## Overview

Do not implement blind. Reconstruct the current contract first, patch the
smallest correct surface, and verify proportionally.

## Machine-Wide Defaults

- Apply Manh's machine-wide cross-cutting defaults from
  `/home/manh/.codex/skills/manh-preference/references/working-defaults.md`
  before deciding how much to inspect, verify, or broaden.
- Probe the current code, data, artifacts, and owner boundaries before editing.
- Start with the narrowest meaningful verification.
- Broaden to larger suites only when the change affects shared contracts,
  cross-module behavior, or public entrypoints.
- Say explicitly what was not verified.
- Leave a clear handoff note when the verification surface is incomplete.

## Repo Rule Pointer

When the current task is inside `/home/manh/stocks-ecosystem`, re-read:

- `/home/manh/stocks-ecosystem/AGENTS.md`
- `/home/manh/stocks-ecosystem/README.md`
- `/home/manh/stocks-ecosystem/alpha-research-lab/README_for_AGENTS.md`

Treat the repo probe-first, lightweight-first, and structure rules as hard
constraints.

## Memory-System Rule

Treat the repo note stack as part of verification discipline.

- Before material work, read the repo workflow doc plus the live-state note and
  the latest relevant session plus durable findings and dead-ends notes when
  they exist.
- Use
  `/home/manh/.codex/skills/manh-memory-system/references/note-stack-convention.md`
  as the canonical machine-wide note convention source.
- Follow the repo's established numbering if it is already coherent and
  grandfathered. Otherwise use the strict fresh-repo convention from
  `manh-memory-system`.
- After any material implementation, investigation, repair, or architecture
  pass, update the appropriate note layer unless the work is trivial or the
  user explicitly requested no file changes:
  - live-state note when the current verified state or next step changed
  - session log for the pass
  - durable findings when the verified conclusion should survive the current
    session
  - durable dead ends when the rejected or failed path should survive the
    current session
  - operator README when a script-heavy surface changed materially

## Workflow

1. Preflight.
- Inspect the current file or artifact, owner path, and contract.

2. Implement narrowly.
- Change only the surfaces required to satisfy the request.

3. Verify in layers.
- Syntax/import checks if the change moved code.
- Focused tests around the edited path.
- Broader suite only if the change widened the contract.

4. Report honestly.
- State what was verified.
- State what remains unverified.
- State the next exact command if more verification is still needed, and write
  the relevant verification outcome into the proper note layer.

## Resources

Load `references/verification-checklist.md` when you need the compact
checklist. Load
`/home/manh/.codex/skills/manh-preference/references/working-defaults.md`
when cross-cutting defaults matter. Load
`/home/manh/.codex/skills/manh-memory-system/references/note-stack-convention.md`
when you need the canonical note-stack rules.
