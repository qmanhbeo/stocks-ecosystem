---
name: bug-police
description: Dedicated bug-sweep workflow for triaging suspected defects, separating real bugs from false positives, planning safe patch sequences, implementing fixes, and verifying regressions. Use when asked to do a bug sweep, investigate multiple suspected issues, debug correctness problems, audit silent data corruption, NaN or Inf generation, stale outputs, off-by-one behavior, wrong metrics, or turn a list of suspected bugs into confirmed fixes and notes.
---

# Bug Police

## Overview

Run bug sweeps that optimize for correctness, not patch count. Confirm or falsify each suspected bug, prioritize confirmed issues by impact, patch the smallest safe surface, and verify the regression directly.

## Sweep Workflow

1. Build the case.
- Read the exact files, docs, and bug report before proposing fixes.
- Convert each claim into one of: `confirmed`, `not-a-bug`, `needs-evidence`, `out-of-scope`.
- Focus on concrete failure modes: silent corruption, wrong metrics, stale artifacts, NaN or Inf generation, off-by-one boundaries, hidden skips, path-contract drift, broken defaults.

2. Confirm before patching.
- Reproduce with a failing test, targeted command, synthetic fixture, or direct control-flow proof.
- Trace the data path until the effect is explicit.
- Do not patch style issues, weak smells, or hypothetical risks as bugs.

3. Plan the patch set.
- Order confirmed bugs by severity, blast radius, and ease of verification.
- Keep unrelated fixes separate even if they are nearby in code.
- Decide the verification path before editing: unit test, integration smoke test, fixture, stdout capture, or direct command.
- Note docs or cross-project contracts that must change with the fix.

4. Implement carefully.
- Patch the smallest correct surface first.
- Preserve existing behavior outside the confirmed bug.
- Add a focused regression test for the exact failure mode when practical.
- If producer and consumer share the broken contract, patch both sides in the same sweep.

5. Verify and close.
- Run the narrowest meaningful verification first, then any broader slice justified by the risk.
- Report confirmed fixes, disproven claims, residual risks, and commands or tests actually run.

## Confirmation Standards

Treat a bug as `confirmed` only when at least one is true:

- Reproduce the failure with a test or command.
- Prove the bug directly from code or data flow.
- Show behavior contradicting a documented contract and identify the implementation break.

Treat a bug as `not-a-bug` when guards, invariants, or existing behavior make the reported failure impossible.

Treat a bug as `needs-evidence` when the concern is plausible but not yet proven.

## Patch Planning Rules

- Prioritize bugs that can silently corrupt data, misstate evaluation, or poison features with NaN or Inf.
- Preserve the user’s candidate list and annotate status instead of replacing the scope wholesale.
- Prefer one concise sweep note with sections for `confirmed`, `not-a-bug`, `out-of-scope`, and `verification`.
- Avoid folding cleanup, refactors, or retuning into a bug fix unless they are required to make the fix correct.
- If the worktree is dirty, do not revert unrelated changes.

## Verification Patterns

- For math bugs, add an edge-case fixture that hits the broken denominator or boundary.
- For path or contract bugs, verify both launch context and artifact resolution.
- For stale-output bugs, rerun the export and confirm stale files or stale references are handled.
- For hidden skips or diagnostics, capture stdout or stderr in a focused test.
- For boundary bugs, assert metadata and terminal behavior together.

## Output Pattern

- Start with a short plan when the sweep covers multiple issues.
- Maintain a clear status for each suspected bug: `confirmed`, `not-a-bug`, `needs-evidence`, or `out-of-scope`.
- End with changed files, verification performed, and anything still unverified.
