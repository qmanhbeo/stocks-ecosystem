# Same-Session Three-Phase Orchestration Design

## Feasibility: CONFIRMED ✅

Prototype v3 verified:
- Three-phase sequential messages in ONE session: **PASSED**
- Slash skill syntax (`/bright-mind`) inside session: **PASSED**
- Context recall (Phase 1 → Phase 2 → Phase 3): **PASSED**

## Session Transport Methods

| Method | Works | Notes |
|--------|-------|-------|
| `--continue` | ✅ YES | Resumes last session reliably |
| `--session <id>` | ✅ YES (manual test) | Requires session ID capture |
| `session list` from subprocess | ❌ NO | Returns empty in subprocess context |

**Recommendation**: Use `--continue` for production. It's simpler and reliable.

## Session ID Capture

The `opencode session list` command behaves differently:
- Works from CLI (interactive)
- Returns empty/incomplete from subprocess.run()

**Solution**: Don't capture session ID. Use `--continue` which implicitly resumes last session.

## Explicit `--session` for Future

If we need explicit session targeting later, we can:
1. Parse `opencode session list` output from stdout directly in a wrapper script
2. Use a small shell script that captures and returns the session ID
3. Accept the risk of `--continue` for now

For now, `--continue` is production-safe.

## Command Pattern for Production

```bash
# Phase 1: bright-mind
opencode run "Phase 1 prompt..." --dir alpha-research-lab --title "cycle-N"

# Phase 2: experimentor
opencode run --continue "Phase 2 prompt..." --dir alpha-research-lab

# Phase 3: manh-memory-system
opencode run --continue "Phase 3 prompt..." --dir alpha-research-lab
```

## Slash Skills

- `/bright-mind`, `/experimentor`, `/manh-memory-system` all work inside a session
- Tested and confirmed: skill loads correctly within continued session
- Can be mixed with regular prompts in same message

## Risks

1. **Session collision**: If multiple processes use `--continue` simultaneously, they may share session
2. **Session expiry**: Long-running loops might hit session limits
3. **State persistence**: Disk memory (session_*.md, live_state.md) is still source of truth

## Recommendation

**Safe to refactor orchestrator** to use `--continue` for same-session three-phase flow.

Architecture for refactor:
1. One `opencode run` call per phase
2. Use `--continue` flag for phases 2 and 3
3. Keep disk memory as source of truth
4. Track `active_session_id` in state for debugging (optional)