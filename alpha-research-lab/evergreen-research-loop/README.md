# Research Loop Orchestrator

A bounded orchestrator that wraps around the `evergreen-research-loop` skill.

## Purpose

This module provides:
- State persistence across runs
- One-shot invocation of the evergreen-research-loop agent
- Structured logging per cycle
- Lightweight decision logic (should we run? skip?)

## Design Principle

**The orchestrator is NOT the research brain.**

- It does NOT decide hypotheses
- It does NOT run experiments
- It does NOT write findings

It wraps around `evergreen-research-loop` which remains the "research brain".

## Files

```
evergreen-research-loop/
├── Makefile          # Human interface
├── orchestrator.py   # Main logic
├── config.py         # Constants
├── state.py          # State helpers
├── log.py            # Logging helpers
├── state/
│   └── loop_state.json  # Persistent state
├── logs/
│   └── cycle_*.log      # Per-run logs
└── README.md
```

## Quick Start

```bash
cd alpha-research-lab

# Show current state
make status

# Run one cycle (invokes evergreen)
make cycle

# Run dry-run (decision logic only, no opencode)
make dry-run

# Reset state
make reset
```

## Production Usage

**Recommended: Run inside tmux to survive SSH disconnects**

```bash
# Start a new tmux session
tmux new -s research_loop

# Navigate to alpha-research-lab root (where Makefile lives)
cd ~/stocks-ecosystem/alpha-research-lab

# Run the loop (watch live output)
make loop MAX_CYCLES=1 SESSION_BATCH_SIZE=1

# In another terminal, tail the logs
make tail
```

If the session is interrupted (SSH disconnect, timeout), you can recover:
```bash
# Check for interrupted state
make check-interrupted

# Recover safely
make recover-interrupted
```

## Verbosity Modes

**Concise mode (default):**
```bash
make loop MAX_CYCLES=1 SESSION_BATCH_SIZE=1
```
- Suppresses noisy OpenCode stdout/stderr from terminal
- Shows heartbeat progress every 30 seconds: `Phase 1/4: experiment running... elapsed=30s`
- Shows phase completion: `Phase 1/4: experiment completed in 112s`
- Full raw output still written to session log files

**Verbose mode:**
```bash
make loop MAX_CYCLES=1 SESSION_BATCH_SIZE=1 VERBOSE=1
```
- Streams full OpenCode output live to terminal
- Same as original behavior

**Custom heartbeat interval:**
```bash
make loop MAX_CYCLES=1 SESSION_BATCH_SIZE=1 HEARTBEAT_SECONDS=60
```

Variables:
- `VERBOSE` - Set to 1 for verbose output (default: 0)
- `HEARTBEAT_SECONDS` - Heartbeat interval in seconds (default: 30)
- `SESSION_BATCH_SIZE` - compatibility flag only; values `>1` are ignored because each cycle now starts a fresh OpenCode session

## Session Model

The loop now uses **one fresh OpenCode session per cycle**.

Within a cycle:

1. Phase 1 creates a fresh session with a unique title.
2. The orchestrator resolves the exact session id from OpenCode's local SQLite state.
3. Later phases reuse that session via `--session <id>`.
4. The final handoff phase updates `evergreen-research-loop/state/cycle_handoff.md`.

Across cycles:

- The next cycle starts fresh.
- The agent reads `cycle_handoff.md` plus canonical repo notes as recovery context.
- The loop does **not** rely on `/compact`, because local `opencode run` does not provide a reliable CLI compaction path.

## What `make cycle` Does

1. Loads state from `state/loop_state.json`
2. Inspects `live_state.md` for hypothesis queue
3. Checks tmux for heavy jobs
4. Decides: run evergreen OR skip
5. Invokes `opencode run --agent evergreen-research-loop` if ready
6. Updates state file
7. Writes log to `logs/cycle_YYYYMMDD_HHMMSS.log`
8. Exits

## What `make dry-run` Does

Same as cycle but:
- Never invokes opencode
- Logs the decision that would have been made
- Useful for debugging without spending tokens

## State File

`state/loop_state.json`:

```json
{
  "version": "1.0",
  "cycle_count": 1,
  "last_phase": "completed",
  "last_run_timestamp": "2026-05-08T16:30:00",
  "last_session_hint": "304",
  "last_h_hint": "H426",
  "last_decision": "run_evergreen",
  "heavy_job_detected": false,
  "last_exit_status": "success"
}
```

## Safety

- No infinite loops
- No background daemons
- No auto-tmux spawning
- No git commits
- No touching 2026 data
- One pass only, then exit

## Notes

- Slash skills such as `/experimentor` are handled by the build agent from normal message text.
- `/compact` is not treated the same way; interactive OpenCode can emit a dedicated compaction event, but `opencode run` cannot be trusted to reproduce that from stdin.
- See `SAME_SESSION_DESIGN.md` for the verified transport behavior.
