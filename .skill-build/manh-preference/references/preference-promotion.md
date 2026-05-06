# Preference Promotion

What this file is for: the canonical workflow for deciding when a hidden
preference should stay local, become explicit, or be promoted into a
machine-wide rule.

## Promotion Loop

1. Observe the correction or friction.
- Notice when the user corrects a recurring behavior, naming, ownership choice,
  logging choice, or planning style.

2. Identify the failure type.
- repeated ambiguity
- repeated wasted work
- repeated cleanup
- repeated mismatch between local "reasonable judgment" and Manh's actual
  preference

3. Classify the ownership.
- repo-local
- subsystem-local
- machine-wide

4. Decide whether it is promotable.
- Promote when the preference is:
  - repeated
  - cross-cutting
  - decision-complete
  - likely to save recovery cost, token cost, or confusion later

5. Encode it mechanically.
- Add or tighten a rule using the canonical rule format.
- Update dependent skills by reference rather than duplicating the whole rule.

## Promotion Threshold

Default:
- promote after repeated pain, repeated correction, or repeated ambiguity cost

Do not promote:
- one-off taste preferences that have not changed outcomes
- repo-local habits that do not generalize
- rules that are still too vague to enforce mechanically

## Ownership Rule

- Machine-wide preferences belong in `manh-preference`.
- Repo-local preferences belong in the owning repo docs or notes.
- Note-stack structure and note numbering belong in `manh-memory-system`, not
  here.

## Anti-Bloat Rule

- Keep the active preference contract short.
- Keep examples sparse.
- Prefer tightening one existing rule over adding several overlapping rules.
- Prefer hardening an existing skill over creating a new one unless the work is
  clearly a new class.
