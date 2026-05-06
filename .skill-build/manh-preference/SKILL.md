---
name: manh-preference
description: Apply and maintain Manh's machine-wide working defaults. Use on substantial work when cross-cutting preferences such as ambiguity handling, ownership, script shape, observability, restart safety, planning depth, verification posture, or communication style should guide the task, or when repeated corrections should be promoted into explicit machine-wide rules.
---

# Manh Preference

## Overview

Treat Manh's working style as an explicit machine-wide contract, not as a set
of hidden preferences to rediscover through mistakes. Load this skill broadly
on substantial work so cross-cutting defaults are active before implementation
drifts.

## Read Order

1. Ground in the current repo and task first.
- Read the repo workflow docs and any hard local rules.
- Inspect the current code, notes, artifacts, and operator surfaces before
  applying cross-cutting defaults.

2. Load the canonical preference references.
- `references/working-defaults.md`
- `references/rule-format.md`
- `references/preference-promotion.md`
- `references/known-preferences.md`

3. Then apply only the rules that matter for the current task.
- Do not bulk-load every reference when a smaller slice is enough.

## Hard Defaults

- Use this skill broadly on substantial work, not only when explicitly named.
- Treat the references here as the canonical source for Manh's machine-wide
  working defaults.
- Keep domain logic in domain skills; keep cross-cutting defaults here.
- Prefer exact defaults plus explicit carve-outs over soft prose.
- Prefer hardening existing skills over creating new skills unless the work is
  clearly a new class of task.
- Promote a newly surfaced preference into a machine-wide rule only after
  repeated pain, repeated correction, or repeated ambiguity cost.
- Grandfather coherent legacy surfaces, but repair them when materially touched.
- Keep the preference system compact:
  - short rules
  - clear scope
  - named carve-outs
  - no essay-like repetition

## Workflow

1. Inspect before applying.
- Reconstruct the local repo rules and current task surface first.
- Decide which cross-cutting preference categories actually matter.

2. Apply the canonical defaults.
- Use the rules in `references/working-defaults.md` as the first-pass
  operating contract for substantial work.

3. Detect preference drift.
- Notice when the user corrects the same kind of behavior again.
- Notice when a hidden preference caused wasted work, ambiguity, or cleanup.

4. Classify the rule.
- Decide whether the discovered preference is:
  - repo-local
  - subsystem-local
  - machine-wide
- Decide whether it is still situational or should now be promoted.

5. Promote only when justified.
- If the preference is repeated, machine-wide, and decision-complete, record it
  in the canonical references here and align affected skills by reference.
- Do not duplicate the whole contract across other skills.

## Resources

Use:

- `references/working-defaults.md` for the active contract
- `references/rule-format.md` for the exact rule shape
- `references/preference-promotion.md` for promotion and ownership rules
- `references/known-preferences.md` for the currently surfaced defaults and
  their rationale
