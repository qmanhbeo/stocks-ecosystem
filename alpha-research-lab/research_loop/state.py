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
        "active_cycle_started_at": None,
        "active_cycle_log_path": None,
        "active_loop_log_path": None,
        "active_command": None,
        "active_pid": None,
        "last_completed_at": None,
        "active_phase": None,
        "active_agent": None,
        "active_phase_started_at": None,
        "active_phase_log_path": None,
        "last_completed_phase": None,
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
    active_cycle_started_at: str = None,
    active_cycle_log_path: str = None,
    active_loop_log_path: str = None,
    active_command: str = None,
    active_pid: int = None,
    clear_active: bool = False,
    last_completed_at: str = None,
    active_phase: str = None,
    active_agent: str = None,
    active_phase_started_at: str = None,
    active_phase_log_path: str = None,
    last_completed_phase: str = None,
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
        active_cycle_started_at: Set active cycle start timestamp.
        active_cycle_log_path: Set active cycle log path.
        active_loop_log_path: Set active loop log path.
        active_command: Set active command string.
        active_pid: Set active process ID.
        clear_active: Clear all active_* fields.
        last_completed_at: Set last completed timestamp.
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
    if active_cycle_started_at is not None:
        state["active_cycle_started_at"] = active_cycle_started_at
    if active_cycle_log_path is not None:
        state["active_cycle_log_path"] = active_cycle_log_path
    if active_loop_log_path is not None:
        state["active_loop_log_path"] = active_loop_log_path
    if active_command is not None:
        state["active_command"] = active_command
    if active_pid is not None:
        state["active_pid"] = active_pid
    if clear_active:
        state["active_cycle_started_at"] = None
        state["active_cycle_log_path"] = None
        state["active_loop_log_path"] = None
        state["active_command"] = None
        state["active_pid"] = None
    if last_completed_at is not None:
        state["last_completed_at"] = last_completed_at
    if active_phase is not None:
        state["active_phase"] = active_phase
    if active_agent is not None:
        state["active_agent"] = active_agent
    if active_phase_started_at is not None:
        state["active_phase_started_at"] = active_phase_started_at
    if active_phase_log_path is not None:
        state["active_phase_log_path"] = active_phase_log_path
    if last_completed_phase is not None:
        state["last_completed_phase"] = last_completed_phase

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