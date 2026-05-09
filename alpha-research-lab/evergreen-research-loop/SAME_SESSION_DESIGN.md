# OpenCode Session Design

## Verified Local Behavior

- Slash skill prompts such as `/bright-mind`, `/experimentor`, and `/manh-memory-system` work in `opencode run`.
- They work when passed as positional CLI text and when sent through stdin.
- They also work in continued sessions, but only because the build agent interprets the text and loads the skill.
- `/compact` is different. It is not a skill, and `opencode run` does not handle it reliably as a true compaction command.

## Why The Old Design Was Wrong

The previous multi-cycle batching design assumed:

1. `/bright-mind` style inputs and `/compact` were the same class of slash feature.
2. `opencode run --continue` plus `/compact` could safely compact a session between cycles.

Local probes disproved that:

- Skill slashes are plain user text that the build agent can interpret.
- True compaction in interactive OpenCode is represented as a dedicated `compaction` message part, not a literal `/compact` text message.
- Sending `/compact` through `opencode run` stdin appends literal slash text and does not produce a compaction part.
- Positional `/compact` also does not give a reliable production compaction path.

## Current Production Design

Use **one fresh OpenCode session per cycle**.

Within a cycle:

1. Phase 1 starts a fresh session with a unique title.
2. The orchestrator resolves the exact session id from OpenCode's local SQLite state.
3. Phases 2-5 reuse that session via `--session <id>`, not global `--continue`.

Across cycles:

1. Do not rely on `/compact`.
2. Write `evergreen-research-loop/state/cycle_handoff.md` at the end of each successful cycle.
3. Start the next cycle fresh and read that handoff plus the canonical repo notes.

## Safety Rationale

- Avoids global `--continue` collisions with unrelated OpenCode sessions.
- Avoids fake `/compact` prompts that silently become plain text.
- Keeps recovery explicit through a durable handoff file and the canonical note stack.
