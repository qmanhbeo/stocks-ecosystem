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
        "loop_started_at": None,
        "loop_completed_at": None,
        "last_loop_max_cycles": None,
        "last_loop_completed_cycles": 0,
        "last_stop_reason": None,
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
    loop_start: bool = False,
    loop_complete: bool = False,
    loop_max_cycles: int = None,
    loop_completed_cycles: int = None,
    stop_reason: str = None,
) -> Dict[str, Any]:
    """
    Update specific fields in state.
    Returns the updated state.

    Args:
        real_cycle: If True, increment cycle_count (only for real evergreen pass).
                   If False, do not increment (for dry-runs/skips).
        loop_start: If True, record loop_started_at.
        loop_complete: If True, record loop_completed_at.
        loop_max_cycles: Set last_loop_max_cycles.
        loop_completed_cycles: Set last_loop_completed_cycles.
        stop_reason: Set last_stop_reason.
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
    if loop_start:
        state["loop_started_at"] = datetime.now().isoformat()
    if loop_complete:
        state["loop_completed_at"] = datetime.now().isoformat()
    if loop_max_cycles is not None:
        state["last_loop_max_cycles"] = loop_max_cycles
    if loop_completed_cycles is not None:
        state["last_loop_completed_cycles"] = loop_completed_cycles
    if stop_reason is not None:
        state["last_stop_reason"] = stop_reason

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