# AGENTS

See `README_for_AGENTS.md` for workflow, guardrails, note locations, and the unified CLI command surface.

See `notes/live_state.md` for current state, blockers, jobs, next actions.

Canonical runtime entrypoint:
- `python cli.py <subcommand> [args...]`

Artifact policy quick rule: timestamped outputs under `artifacts/*/<timestamp>/` are scratch/legacy clues; decision-grade validation outputs belong under `artifacts/canonical_wfv/`.
