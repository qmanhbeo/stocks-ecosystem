"""
Orchestrator for the research loop.

This module handles:
- State persistence
- Decision logic (lightweight)
- Invoking the evergreen-research-loop skill
- Logging
- Clean exit

IMPORTANT: This is NOT the research brain. It wraps around evergreen-research-loop.
"""

import os
import subprocess
import sys
import time
import glob
from datetime import datetime
from typing import Tuple, Optional, Dict, Any

import config
import state
import log


def check_heavy_job_running() -> bool:
    """
    Check if any heavy job is running.
    Checks:
    1. tmux sessions with heavy keywords
    2. artifacts/job_status/*.json files with running/active/in_progress status
    """
    try:
        result = subprocess.run(
            ["tmux", "list-sessions", "-F", "#{session_name}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        sessions = result.stdout.strip().split("\n") if result.stdout.strip() else []
        heavy_keywords = ["ollama", "backfill", "train", "build"]
        for session in sessions:
            for kw in heavy_keywords:
                if kw in session.lower():
                    log.log_message(f"Heavy job detected in tmux: {session}", "WARN")
                    return True
    except Exception:
        pass

    job_status_dir = os.path.join(config.RESEARCH_LAB, "artifacts", "job_status")
    if os.path.exists(job_status_dir):
        for json_file in glob.glob(os.path.join(job_status_dir, "*.json")):
            try:
                import json
                with open(json_file, "r") as f:
                    content = json.load(f)
                    status = content.get("status", "").lower()
                    if status in ["running", "active", "in_progress", "pending"]:
                        log.log_message(f"Heavy job detected in job_status: {json_file}", "WARN")
                        return True
            except Exception:
                pass

    return False


def check_hypothesis_queue() -> Tuple[bool, int]:
    """
    Check if hypothesis queue exists in live_state.md.
    Returns: (exists, rough_item_count)
    """
    if not os.path.exists(config.LIVE_STATE_PATH):
        return False, 0
    try:
        with open(config.LIVE_STATE_PATH, "r") as f:
            content = f.read()

        if "Hypothesis Queue" not in content:
            return False, 0

        start_idx = content.find("## Hypothesis Queue")
        if start_idx == -1:
            return False, 0

        queue_section = content[start_idx:start_idx+2000]
        bullet_count = queue_section.count("\n- ")

        return True, bullet_count
    except Exception:
        return False, 0


def inspect_current_state() -> Dict[str, Any]:
    """
    Lightweight inspection of repo state.
    Returns a dict with current info.
    """
    queue_exists, queue_count = check_hypothesis_queue()

    info = {
        "heavy_job": check_heavy_job_running(),
        "hypothesis_queue_exists": queue_exists,
        "hypothesis_queue_count": queue_count,
    }

    st = state.load_state()
    info["last_session"] = st.get("last_session_hint")
    info["last_h"] = st.get("last_h_hint")
    info["cycle_count"] = st.get("cycle_count", 0)

    return info


def decide_action(inspect_info: Dict[str, Any], dry_run: bool = False) -> Tuple[str, str]:
    """
    Lightweight decision logic.

    Returns: (decision, reason)
    """
    if inspect_info["heavy_job"]:
        return "skip_heavy", "Heavy job detected"

    if not inspect_info["hypothesis_queue_exists"]:
        return "skip_empty_queue", "No hypothesis queue in live_state.md"

    if dry_run:
        return "dry_run", "Dry-run mode requested"

    return "run_evergreen", "Ready to run evergreen-research-loop pass"


def build_prompt() -> str:
    """Build the prompt for the evergreen-research-loop agent."""
    prompt = """
Proceed with one bounded research pass.

OPERATIONAL SOURCE OF TRUTH:
- Use alpha-research-lab/notes/live_state.md as the current operational source.
- Treat next_steps.md as stale/legacy unless needed for archaeology.

INSTRUCTIONS:
1. Recover current state from live_state.md, sessions_compact.md, findings_compact.md.
2. Decide whether to ideate, experiment, watch a job, or write memory.
3. Load bright-mind / experimentor / job-watchdog / manh-memory-system ONLY when their escalation trigger is hit.
4. Do NOT load all skills by default.

CONSTRAINTS:
- Do not touch 2026 data.
- Keep the lab long-only.
- Run at most one heavy job at a time.
- Never erase failed branches - park or kill with evidence.

EXPERIMENT PROTOCOL:
- Run the smallest honest test.
- Use reusable scripts from analysis/h4XX.py when possible.
- Compare against random baselines unless directly modifying S1/C16.
- Read saved artifacts from artifacts/run_summaries/ BEFORE judging results.

MEMORY:
- Write session notes to session_NN_log.md.
- Update live_state.md ONLY if current truth/blockers/jobs changed.
- Update findings_compact.md or deadends_compact.md if durable memory changed.
- Update signal_library.md or portfolio_policy_library.md only on promotion.

OUTPUT:
- Report what changed or why skipped.
- Stop after one pass.
"""
    return prompt.strip()


def invoke_evergreen(prompt: str) -> Tuple[int, str, str]:
    """
    Invoke the evergreen-research-loop agent via opencode run.

    Returns: (return_code, stdout, stderr)
    """
    cmd = [
        config.OPENCODE_BINARY,
        "run",
        "--dir", "alpha-research-lab",
        "--agent", "evergreen-research-loop",
        "--title", "research-loop-cycle",
    ]

    try:
        result = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=config.OPENCODE_TIMEOUT_SECONDS,
            cwd=config.REPO_ROOT,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", f"Timeout after {config.OPENCODE_TIMEOUT_SECONDS}s"
    except FileNotFoundError:
        return -2, "", f"opencode binary not found: {config.OPENCODE_BINARY}"
    except Exception as e:
        return -3, "", str(e)


def run_cycle(dry_run: bool = False) -> int:
    """
    Execute one complete cycle.

    Returns: exit code (0 = success, non-zero = failure)
    """
    start_time = time.time()

    log_path = log.start_cycle_log()
    log.write_log(log_path, f"Working directory: {config.REPO_ROOT}")
    log.write_log(log_path, f"Research lab: {config.RESEARCH_LAB}")

    current_state = state.load_state()
    log.write_log(log_path, log.format_state_summary(current_state))

    inspect_info = inspect_current_state()
    log.write_log(log_path, f"Inspection: {inspect_info}")

    decision, reason = decide_action(inspect_info, dry_run)
    log.write_log(log_path, f"Decision: {decision} ({reason})")

    state.update_state(phase="decision", decision=decision)

    if decision == "run_evergreen":
        log.write_log(log_path, "Invoking evergreen-research-loop...")

        prompt = build_prompt()
        log.write_log(log_path, f"Prompt length: {len(prompt)} chars")

        returncode, stdout, stderr = invoke_evergreen(prompt)

        log.write_log(log_path, f"Return code: {returncode}")

        if returncode == 0:
            state.update_state(
                phase="completed",
                exit_status="success",
                real_cycle=True,
            )
            log.write_log(log_path, "Evergreen completed successfully, cycle_count incremented")
        else:
            state.update_state(
                phase="failed",
                exit_status=f"error_{returncode}",
            )
            log.write_log(log_path, f"Evergreen failed: {stderr[:200]}")

    elif decision == "dry_run":
        log.write_log(log_path, "Dry-run completed, no evergreen invoked")
        state.update_state(phase="dry_run", exit_status="dry_run")

    else:
        log.write_log(log_path, f"Skipped: {reason}")
        state.update_state(phase="skipped", exit_status="skipped")

    elapsed = time.time() - start_time
    log.end_cycle_log(log_path, "completed", elapsed)

    log.log_message(f"Cycle completed in {elapsed:.1f}s")
    return 0


def show_status() -> int:
    """Display current state."""
    st = state.load_state()
    print("=== Research Loop State ===")
    for key, value in st.items():
        if value is not None:
            print(f"  {key}: {value}")
    return 0


def reset_loop() -> int:
    """Reset the loop state."""
    state.reset_state()
    log.log_message("Loop state reset")
    return 0


def main() -> int:
    """Main entry point for the orchestrator."""
    if len(sys.argv) < 2:
        print("Usage: orchestrator.py <command>")
        print("Commands: cycle, dry-run, status, reset")
        return 1

    command = sys.argv[1]

    if command == "cycle":
        return run_cycle(dry_run=False)
    elif command == "dry-run":
        return run_cycle(dry_run=True)
    elif command == "status":
        return show_status()
    elif command == "reset":
        return reset_loop()
    else:
        print(f"Unknown command: {command}")
        return 1


if __name__ == "__main__":
    sys.exit(main())