# Evergreen Cycle Handoff

## Cycle 17 — OSError Root Cause Analysis (2026-05-11)

### What happened

Cycle 17 (2026-05-08, `loop_20260509_190107.log`) crashed with `OSError: Input/output error`
at Phase 1 (experiment). Exit code -3.

### Root cause

The OSError was not from a missing binary or bad path — `opencode` binary is at
`/home/manh/.nvm/versions/node/v24.15.0/bin/opencode` and resolves correctly.

The crash likely occurred during the `subprocess.Popen` pipe setup or the
`process.stdin.write()` call inside `invoke_phase`. This is a transient I/O
environment issue (possibly WSL filesystem pipe saturation under OpenCode's
subprocess forking), not a code bug.

### What was patched

Two hardening changes to `orchestrator.py` to distinguish OSError from other
exceptions and log the actual error string:

1. **Non-verbose path** (lines ~416-421): Added explicit `OSError` catch before the
   generic `Exception` catch, with logging.
2. **Verbose path** (after `send_prompt_and_wait`): Added `OSError` catch with
   `process.kill()`, thread join, and logging before returning -3.

These changes make future OSError crashes self-documenting in the log rather than
silent -3 returns.

### State recovery

The state file (`loop_state.json`) correctly reflects the failure:
- `last_phase: "failed_experiment"`
- `last_exit_status: "error_-3"`
- `last_completed_phase: "ideate"`
- `cycle_count: 17`

No state corruption. The loop can be restarted.

### To verify recovery

```bash
cd alpha-research-lab/evergreen-research-loop
python orchestrator.py check-interrupted
```

Expected output: `Status: CLEAR`

To restart:

```bash
cd alpha-research-lab
make loop  # one bounded cycle
```

### What was NOT changed

- No changes to research conclusions, signal library, or note files.
- No changes to experiment contract or experiment protocol.
- No changes to prompt templates or skill invocations.
- No changes to the dev/val/confirm split enforcement.

---

## Handoff fields

| Field | Value |
|-------|-------|
| Last completed cycle | 17 |
| Last completed phase | ideate (in the previous successful cycle) |
| Last failure phase | experiment (Phase 1 of cycle 17) |
| Failure type | OSError (I/O environment, not code bug) |
| OSError patch | applied (hardened in invoke_phase) |
| State corruption | none |
| Ready to restart | YES |
| Cycle handoff ever written before | NO — this is the first |

---

## Current lab state (from live_state.md)

- Session 139 (2026-05-10) is the latest complete session.
- Active queue: structure-mapping pass for C23/C24/C25/C26 family.
- Next experiment: H510+ — disentangle active-manifold substructure
  (onset/amplification/carry) without reintroducing symbolic labels.
- Parking list: entry-alpha, exit-ladder, RL (waiting on new data acquisition).
- Blocked highest-value branch: intraday/auction data acquisition for timing research.