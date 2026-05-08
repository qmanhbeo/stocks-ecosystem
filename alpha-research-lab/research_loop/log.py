"""
Logging setup for the research loop.
"""

import os
import sys
from datetime import datetime
from pathlib import Path
from config import LOGS_DIR


def ensure_logs_dir() -> None:
    """Ensure logs directory exists."""
    os.makedirs(LOGS_DIR, exist_ok=True)


def create_cycle_log() -> str:
    """Create a new cycle log file and return its path."""
    ensure_logs_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = os.path.join(LOGS_DIR, f"cycle_{timestamp}.log")
    return log_path


def log_message(message: str, level: str = "INFO") -> None:
    """Log a message to both stdout and the current log file."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{timestamp}] [{level}] {message}"
    print(formatted)


def write_log(log_path: str, content: str) -> None:
    """Write content to a specific log file."""
    with open(log_path, "a") as f:
        f.write(content + "\n")


def start_cycle_log() -> str:
    """Start a new cycle log, return the path."""
    log_path = create_cycle_log()
    header = f"=== Research Loop Cycle Started at {datetime.now().isoformat()} ==="
    write_log(log_path, header)
    return log_path


def end_cycle_log(log_path: str, status: str, elapsed_seconds: float) -> None:
    """Write cycle completion to log."""
    footer = f"=== Cycle Completed: {status} (elapsed: {elapsed_seconds:.1f}s) ==="
    write_log(log_path, footer)


def format_state_summary(state: dict) -> str:
    """Format state dict for logging."""
    lines = ["--- Current State ---"]
    for key, value in state.items():
        if value is not None:
            lines.append(f"  {key}: {value}")
    return "\n".join(lines)