# Session 126 Log — 2026-05-09

## Evergreen OpenCode Slash / Compaction Investigation

**Decision: INFRA CONFIRMED**

### Goal
Determine exactly how OpenCode handles slash skills and `/compact` across:

- interactive OpenCode chat
- `opencode run`
- `opencode run --interactive`
- `opencode run --continue`
- stdin-provided prompts
- positional CLI prompts

Then patch the evergreen loop if `/compact` is not a reliable `opencode run` feature.

### Local OpenCode facts

- `opencode --version` = `1.14.42`
- `which opencode` = `/home/manh/.nvm/versions/node/v24.15.0/bin/opencode`
- `opencode run --help` exposes `--interactive` and `--demo`
- `opencode run --help` does **not** expose `/compact` as a normal CLI feature
- `opencode run --help` says `--demo` only enables demo slash commands in direct interactive mode
- `opencode debug skill` confirms `bright-mind`, `experimentor`, `manh-memory-system`, and `evergreen-research-loop` are real installed OpenCode skills under `~/.config/opencode/skills/`
- `opencode debug agent compaction` confirms OpenCode has a hidden native `compaction` agent

### Probe Summary

| Probe | Command shape | Session id | Result |
|-------|---------------|------------|--------|
| positional plain | `opencode run --dir /tmp/opencode_cli_probe_suite/plain --title probe-positional-plain "Reply with exactly POS_OK."` | `ses_1f202d740ffe7Y6MEUJQ7X6hwO` | Normal text message, normal 2-message history |
| stdin plain | `opencode run --dir /tmp/opencode_cli_probe_suite/stdin --title probe-stdin-plain` with stdin `Reply with exactly STDIN_OK.` | `ses_1f202cceeffeYyy9N2uAaMcHHF` | Normal text message, normal 2-message history |
| `--continue` plain | fresh seed + `opencode run --continue --dir /tmp/opencode_cli_probe_suite/continue` with stdin `Reply with exactly CONT_OK.` | `ses_1f202c0b5ffeg6SZUrxqkr9xH2` | Same session reused correctly; message count grew from 2 to 4 |
| `/compact` via stdin continue | fresh seed + `opencode run --continue --dir /tmp/opencode_cli_probe_suite/compact` with stdin `/compact` | `ses_1f202accaffepyA98WiCun2q3X` | `/compact` stored as literal user text; assistant reasoned about it and replied `READY.`; no compaction event |
| `/experimentor` positional | `opencode run --dir /tmp/opencode_cli_probe_suite/skills --title probe-slash-experimentor /experimentor` | `ses_1f2022745ffeqQZ28ub6CwW6Fx` | Skill loaded; assistant explicitly said experimentor skill loaded |
| `/manh-memory-system` positional | `opencode run --dir /tmp/opencode_cli_probe_suite/skills --title probe-slash-memory /manh-memory-system` | `ses_1f2020386ffeDy09a6k0swO53B` | Skill loaded; assistant summarized memory-system contract |
| `/bright-mind` positional | `opencode run --dir /tmp/opencode_cli_probe_suite/skills --title probe-slash-bright-mind /bright-mind` | `ses_1f2028aa9ffe9qU8JF77xk6v43` | Skill loaded; then failed only because the temp workspace lacked alpha-research-lab files |
| `/experimentor` via stdin | `opencode run --dir /tmp/opencode_cli_probe_suite_b/skills --title probe-stdin-slash-experimentor` with stdin `/experimentor` | `ses_1f2010523ffeDNzl1tvHnuYh8m` | Skill loaded from stdin message too |
| `/bright-mind` via stdin | `opencode run --dir /tmp/opencode_cli_probe_suite_b/skills --title probe-stdin-slash-bright` with stdin `/bright-mind` | `ses_1f200acfbffe0FarvFziE9CQuh` | Skill loaded from stdin message too |
| `/experimentor` in continued session | fresh seed + positional `/experimentor`, then stdin `/experimentor` in same session | `ses_1f2008be5ffegHIimEgL4aG0Lp` | Skill loaded in continued session too; slash skill text works under `--continue` |
| `/compact` positional | `opencode run --dir /tmp/opencode_cli_probe_suite_b/compact --title probe-positional-compact /compact` | `ses_1f2004e63ffe0xHm8uIFZj8Yel` | Entered an unreliable custom-slash/task path; did **not** become a clean compaction event |
| `/compact` in interactive demo mode | `opencode run --interactive --demo --dir /tmp/opencode_demo_interactive --title probe-demo-interactive /compact` | `ses_1f1fc76a0ffempaX835Dxux1Jg` | `--demo` only exposes `/permission`, `/question`, `/fmt`; `/compact` still treated as ordinary text |

### Critical Session Evidence

1. **Slash skills are not UI-only slash commands**

The actual stored OpenCode sessions for `/experimentor`, `/bright-mind`, and `/manh-memory-system` kept the user text literally as `/skill-name`, then the assistant reasoning explicitly said it was loading the requested skill. This happened for:

- positional `opencode run`
- stdin `opencode run`
- continued sessions

So slash skill invocation in `run` is real, but it is mediated by the build agent interpreting text, not by a client-only slash-command router.

2. **`/compact` is different**

When `/compact` was sent through the same stdin path the loop uses, the stored session looked like:

- user text part: `/compact`
- assistant reasoning about the string `/compact`
- assistant reply `READY.`

That is plain-text handling, not real compaction.

3. **Real interactive compaction is represented differently**

Existing local session `ses_1f2198556ffeML2acu0PukYppR` (`cycle-18`) contains a user message whose part is:

```json
{"type":"compaction","auto":false,"tail_start_id":"msg_e0de7a927001DPy0a9qNU2GQl7"}
```

That is the important distinction:

- real interactive compaction = dedicated `compaction` message part
- fake CLI `/compact` = literal text `/compact`

So the interactive chat layer can emit a real compaction event that `opencode run` stdin does not reproduce.

4. **Current evergreen loop skill phases were actually working**

The recent real evergreen session `ses_1f2198556ffeML2acu0PukYppR` stored the experiment prompt as literal user text beginning with:

`/experimentor please proceed with the next best/most relevant item in queue ...`

The assistant then explicitly reasoned that it needed to load the `experimentor` skill, and proceeded correctly. This means the loop's skill invocation path was not the primary bug. The unreliable part was the attempted between-cycle compaction path and the broader reliance on global `--continue`.

### Diagnosis

1. `/bright-mind`, `/experimentor`, and `/manh-memory-system` are real OpenCode skills, not project-local fake commands.

2. In `opencode run`, skill-like slash text works because the build agent interprets the message and loads the skill. This works from positional args, stdin, and continued sessions.

3. `/compact` is **not** a slash skill. It behaves like an interactive client command / compaction event, not like plain user text.

4. `opencode run` does not provide a reliable production path for emitting that compaction event from stdin. Sending `/compact` through bash is therefore a fake compaction request.

5. `--continue` still resumes the last session globally, so even when it works it is collision-prone for automation.

### Patch Applied

Patched the evergreen loop away from fake `/compact` and global `--continue` assumptions:

- removed cross-cycle `/compact` behavior from the orchestrator design
- changed prompts to explicit natural-language skill requests instead of slash dependency
- added `evergreen-research-loop/prompts/handoff.md`
- added durable handoff file `evergreen-research-loop/state/cycle_handoff.md`
- changed the cycle flow to:
  - experiment (fresh session)
  - experiment (`--session <resolved id>`)
  - memory (`--session <resolved id>`)
  - ideate (`--session <resolved id>`)
  - handoff (`--session <resolved id>`)
- resolved the exact session id from OpenCode's local SQLite state after phase 1
- stored `active_session_id` / `last_session_id` in loop state
- changed loop behavior to one fresh OpenCode session per cycle; `SESSION_BATCH_SIZE > 1` is now compatibility-only and ignored
- required the handoff file to be updated before the cycle is considered healthy
- updated loop README / design docs / Makefiles to reflect the new model

### Verification

```bash
python3 -m py_compile alpha-research-lab/evergreen-research-loop/orchestrator.py \
  alpha-research-lab/evergreen-research-loop/config.py \
  alpha-research-lab/evergreen-research-loop/state.py \
  alpha-research-lab/evergreen-research-loop/log.py

cd alpha-research-lab/evergreen-research-loop
python3 -u orchestrator.py dry-run --max-cycles 2 --session-batch-size 3
```

Both passed. The dry-run now shows one fresh session per cycle plus a final handoff phase, with `SESSION_BATCH_SIZE=3` explicitly ignored.

### Verdict

Use **fresh session per cycle + explicit handoff file** as the production architecture. Same-session reuse is still fine **inside** a single cycle once the exact session id is resolved, but cross-cycle batching via fake `/compact` is not trustworthy.

### Default Operator Settings

After verification, changed the evergreen loop defaults to the safest operator baseline:

- `DEFAULT_MAX_CYCLES = 1`
- `DEFAULT_SESSION_BATCH_SIZE = 1`
- top-level and repo-local Makefiles now default to `MAX_CYCLES ?= 1` and `SESSION_BATCH_SIZE ?= 1`

This keeps a no-arg `make loop` bounded to one fresh-session cycle unless the operator explicitly widens it.
