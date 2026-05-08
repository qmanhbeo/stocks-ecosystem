"""
State file management for the research loop.
"""

import json
import os
from datetime import datetime
from typing import Optional, Dict, Any
from config import LOOP_STATE_FILE, STATE_VERSION


def create_initial_state() -> Dict[str, Any]:
    """Create the initial empty state."""
    return {
        "version": STATE_VERSION,
        "cycle_count": 0,
        "last_phase": "none",
        "last_run_timestamp": None,
        "last_session_hint": None,
        "last_h_hint": None,
        "last_decision": "none",
        "heavy_job_detected": False,
        "last_exit_status": "none",
        "created_at": datetime.now().isoformat(),
    }


def load_state() -> Dict[str, Any]:
    """Load state from file, or return initial state if not exists."""
    if os.path.exists(LOOP_STATE_FILE):
        with open(LOOP_STATE_FILE, "r") as f:
            return json.load(f)
    return create_initial_state()


def save_state(state: Dict[str, Any]) -> None:
    """Save state to file."""
    with open(LOOP_STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def update_state(
    phase: str = None,
    decision: str = None,
    session_hint: str = None,
    h_hint: str = None,
    heavy_job: bool = None,
    exit_status: str = None,
    real_cycle: bool = False,
) -> Dict[str, Any]:
    """
    Update specific fields in state.
    Returns the updated state.

    Args:
        real_cycle: If True, increment cycle_count (only for real evergreen pass).
                   If False, do not increment (for dry-runs/skips).
    """
    state = load_state()

    if phase is not None:
        state["last_phase"] = phase
    if decision is not None:
        state["last_decision"] = decision
    if session_hint is not None:
        state["last_session_hint"] = session_hint
    if h_hint is not None:
        state["last_h_hint"] = h_hint
    if heavy_job is not None:
        state["heavy_job_detected"] = heavy_job
    if exit_status is not None:
        state["last_exit_status"] = exit_status
    if real_cycle:
        state["cycle_count"] += 1
        state["last_run_timestamp"] = datetime.now().isoformat()

    save_state(state)
    return state


def reset_state() -> None:
    """Delete state file, effectively resetting the loop."""
    if os.path.exists(LOOP_STATE_FILE):
        os.remove(LOOP_STATE_FILE)


def get_current_cycle() -> int:
    """Get current cycle count."""
    state = load_state()
    return state.get("cycle_count", 0)