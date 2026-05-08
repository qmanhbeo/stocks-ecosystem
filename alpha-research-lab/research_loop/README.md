# Research Loop Orchestrator - MVP

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
research_loop/
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
cd alpha-research-lab/research_loop

# Show current state
make status

# Run one cycle (invokes evergreen)
make cycle

# Run dry-run (decision logic only, no opencode)
make dry-run

# Reset state
make reset
```

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

## Not Implemented (MVP)

- `make loop` (bounded iterations)
- `make resume` (continue from crash)
- `make stop` (clean interrupt)
- Parallel jobs
- Heavy job auto-detection beyond tmux

## Next Steps (Future)

- Add bounded loop (`make loop`)
- Add resume capability
- Add heavy job watchdog integration
- Add automatic session log parsing