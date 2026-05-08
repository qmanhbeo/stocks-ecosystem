"""
Orchestrator for the research loop.

This module handles:
- State persistence
- Decision logic (lightweight)
- Invoking the evergreen-research-loop skill
- Bounded loop execution
- Logging
- Clean exit

IMPORTANT: This is NOT the research brain. It wraps around evergreen-research-loop.
"""

import os
import subprocess
import sys
import time
import glob
import re
import argparse
from datetime import datetime
from typing import Tuple, Optional, Dict, Any

import config
import state
import log


DEFAULT_MAX_CYCLES = 2
DEFAULT_SLEEP_SECONDS = 5


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
    Counts lines that look like list items under ## Hypothesis Queue.
    Returns: (exists, rough_item_count)
    """
    if not os.path.exists(config.LIVE_STATE_PATH):
        return False, 0
    try:
        with open(config.LIVE_STATE_PATH, "r") as f:
            content = f.read()

        if "## Hypothesis Queue" not in content:
            return False, 0

        start_idx = content.find("## Hypothesis Queue")
        if start_idx == -1:
            return False, 0

        next_heading = content.find("\n## ", start_idx + 1)
        if next_heading == -1:
            queue_section = content[start_idx:]
        else:
            queue_section = content[start_idx:next_heading]

        list_pattern = r"(?:^|\n)(\s*)(?:[-*]|\d+\.)\s+"
        matches = re.findall(list_pattern, queue_section)
        count = len(matches)

        return True, count
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

    if inspect_info["hypothesis_queue_count"] == 0:
        log.log_message("Warning: Queue section exists but no items detected", "WARN")

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


def invoke_phase(prompt: str, use_continue: bool = False, title: str = None) -> Tuple[int, str, str]:
    """
    Invoke a single phase using opencode run.

    Args:
        prompt: The prompt to send
        use_continue: If True, use --continue to resume last session
        title: Session title for first phase

    Returns: (return_code, stdout, stderr)
    """
    cmd = [config.OPENCODE_BINARY, "run"]

    if use_continue:
        cmd.append("--continue")

    if title:
        cmd.extend(["--title", title])

    cmd.extend(["--dir", "alpha-research-lab"])

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


def load_phase_prompt(phase_name: str) -> str:
    """Load prompt from prompts/ directory."""
    prompt_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompts")
    prompt_path = os.path.join(prompt_dir, f"{phase_name}.md")

    if os.path.exists(prompt_path):
        with open(prompt_path, "r") as f:
            return f.read().strip()

    return f"Run {phase_name} phase."


def run_three_phase_cycle(dry_run: bool = False, stop_on_phase_failure: bool = True) -> Dict[str, Any]:
    """
    Execute one complete cycle with four phases in same session.

    Phase 1: Experiment (experimentor) - fresh session
    Phase 2: Experiment (experimentor) - --continue
    Phase 3: Memory (manh-memory-system) - --continue
    Phase 4: Ideate (bright-mind) - --continue

    Returns: dict with phase results
    """
    start_time = time.time()
    cycle_log_path = log.start_cycle_log()

    log.write_log(cycle_log_path, f"Working directory: {config.REPO_ROOT}")
    log.write_log(cycle_log_path, f"Research lab: {config.RESEARCH_LAB}")

    current_state = state.load_state()
    log.write_log(cycle_log_path, log.format_state_summary(current_state))

    inspect_info = inspect_current_state()
    log.write_log(cycle_log_path, f"Heavy job check: {inspect_info['heavy_job']}")

    if inspect_info["heavy_job"]:
        log.write_log(cycle_log_path, "Heavy job detected, skipping cycle")
        state.update_state(phase="skipped", exit_status="heavy_job", active_cycle_log_path=cycle_log_path)
        return {"skipped": True, "reason": "heavy_job"}

    if dry_run:
        log.write_log(cycle_log_path, "Dry-run mode, no phases executed")
        state.update_state(phase="dry_run", exit_status="dry_run")
        return {"skipped": True, "reason": "dry_run"}

    phases = [
        ("experiment", "experimentor"),
        ("experiment", "experimentor"),
        ("memory", "manh-memory-system"),
        ("ideate", "bright-mind"),
    ]

    results = {}
    success_count = 0

    for idx, (phase_name, skill_name) in enumerate(phases):
        is_first = idx == 0
        use_continue = not is_first

        log.log_message(f"=== Phase {idx + 1}: {phase_name} {'(2nd attempt)' if idx == 1 else ''} ===")

        state.update_state(
            phase=f"running_{phase_name}",
            exit_status="running",
            active_phase=phase_name,
            active_agent=skill_name,
            active_phase_started_at=datetime.now().isoformat(),
            active_phase_log_path=cycle_log_path,
        )

        prompt = load_phase_prompt(phase_name)
        wrapped_prompt = prompt

        log.write_log(cycle_log_path, f"Phase {idx + 1} ({phase_name}): using /{skill_name}")

        returncode, stdout, stderr = invoke_phase(wrapped_prompt, use_continue=use_continue, title=f"cycle-{current_state.get('cycle_count', 0) + 1}" if is_first else None)

        log.write_log(cycle_log_path, f"Phase {idx + 1} return code: {returncode}")

        phase_success = returncode == 0
        results[phase_name] = {
            "returncode": returncode,
            "success": phase_success,
            "output": stdout[:500] if stdout else "",
            "error": stderr[:200] if stderr else "",
        }

        if phase_success:
            success_count += 1
            state.update_state(
                phase=f"completed_{phase_name}",
                exit_status="success",
                last_completed_phase=phase_name,
            )
        else:
            log.write_log(cycle_log_path, f"Phase {phase_name} failed: {stderr[:200]}")
            state.update_state(
                phase=f"failed_{phase_name}",
                exit_status=f"error_{returncode}",
            )

            if stop_on_phase_failure and phase_name == "ideate":
                log.log_message(f"Phase 1 (ideate) failed, stopping cycle", "ERROR")
                break

    elapsed = time.time() - start_time

    if success_count == 4:
        log.log_message("All 4 phases completed successfully", "INFO")
        state.update_state(
            phase="completed",
            exit_status="success",
            real_cycle=True,
            clear_active=True,
            last_completed_at=datetime.now().isoformat(),
        )
        results["cycle_complete"] = True
    elif success_count >= 3:
        log.log_message(f"3/4 phases completed", "WARN")
        state.update_state(
            phase="completed_partial",
            exit_status="partial",
            clear_active=True,
            last_completed_at=datetime.now().isoformat(),
        )
        results["cycle_complete"] = True
    else:
        log.log_message(f"Cycle incomplete: {success_count}/4 phases", "ERROR")
        state.update_state(
            phase="failed",
            exit_status="incomplete",
            clear_active=True,
        )
        results["cycle_complete"] = False

    log.end_cycle_log(cycle_log_path, "completed" if results.get("cycle_complete") else "failed", elapsed)
    log.log_message(f"Cycle completed in {elapsed:.1f}s")

    return results


def run_single_cycle(dry_run: bool = False) -> Tuple[int, str]:
    """
    Execute one complete cycle.

    Returns: (exit_code, decision_made)
    """
    start_time = time.time()

    cycle_log_path = log.start_cycle_log()
    log.write_log(cycle_log_path, f"Working directory: {config.REPO_ROOT}")
    log.write_log(cycle_log_path, f"Research lab: {config.RESEARCH_LAB}")

    current_state = state.load_state()
    log.write_log(cycle_log_path, log.format_state_summary(current_state))

    inspect_info = inspect_current_state()
    log.write_log(cycle_log_path, f"Inspection: {inspect_info}")

    decision, reason = decide_action(inspect_info, dry_run)
    log.write_log(cycle_log_path, f"Decision: {decision} ({reason})")

    state.update_state(phase="decision", decision=decision)

    exit_code = 0

    if decision == "run_evergreen":
        log.write_log(cycle_log_path, "Invoking evergreen-research-loop...")

        active_command = f"{config.OPENCODE_BINARY} run --dir alpha-research-lab --agent evergreen-research-loop --title research-loop-cycle"
        state.update_state(
            phase="running_evergreen",
            exit_status="running",
            active_cycle_started_at=datetime.now().isoformat(),
            active_cycle_log_path=cycle_log_path,
            active_command=active_command,
            active_pid=os.getpid(),
        )

        prompt = build_prompt()
        log.write_log(cycle_log_path, f"Prompt length: {len(prompt)} chars")

        returncode, stdout, stderr = invoke_evergreen(prompt)

        log.write_log(cycle_log_path, f"Return code: {returncode}")

        if returncode == 0:
            state.update_state(
                phase="completed",
                exit_status="success",
                real_cycle=True,
                clear_active=True,
                last_completed_at=datetime.now().isoformat(),
            )
            log.write_log(cycle_log_path, "Evergreen completed successfully, cycle_count incremented")
        else:
            exit_code = returncode
            state.update_state(
                phase="failed",
                exit_status=f"error_{returncode}",
                clear_active=True,
            )
            log.write_log(cycle_log_path, f"Evergreen failed: {stderr[:200]}")

    elif decision == "dry_run":
        log.write_log(cycle_log_path, "Dry-run completed, no evergreen invoked")
        state.update_state(phase="dry_run", exit_status="dry_run")

    else:
        log.write_log(cycle_log_path, f"Skipped: {reason}")
        state.update_state(phase="skipped", exit_status="skipped")
        if decision == "skip_heavy":
            exit_code = 10

    elapsed = time.time() - start_time
    log.end_cycle_log(cycle_log_path, "completed", elapsed)

    log.log_message(f"Cycle completed in {elapsed:.1f}s")

    return exit_code, decision


def run_loop(max_cycles: int = DEFAULT_MAX_CYCLES, sleep_seconds: int = DEFAULT_SLEEP_SECONDS) -> int:
    """
    Execute up to max_cycles bounded passes.

    Returns: exit code
    """
    start_time = time.time()

    loop_log_path = log.start_loop_log(max_cycles)
    log.write_log(loop_log_path, f"Starting bounded loop with max_cycles={max_cycles}")
    log.write_log(loop_log_path, f"Working directory: {config.REPO_ROOT}")

    state.update_state(
        loop_start=True,
        loop_max_cycles=max_cycles,
        loop_completed_cycles=0,
        stop_reason=None,
        active_loop_log_path=loop_log_path,
    )

    completed = 0
    stop_reason = "completed_all"

    try:
        for cycle_num in range(1, max_cycles + 1):
            log.log_message(f"Loop cycle {cycle_num}/{max_cycles}")

            inspect_info = inspect_current_state()

            if inspect_info["heavy_job"]:
                stop_reason = "heavy_job_detected"
                log.log_message(f"Stopping loop: heavy job detected", "WARN")
                break

            cycle_start = time.time()
            exit_code, decision = run_single_cycle(dry_run=False)
            cycle_elapsed = time.time() - cycle_start

            completed += 1

            log.log_message(f"Cycle {cycle_num} decision: {decision}, exit_code: {exit_code}")
            log.log_cycle_to_loop(loop_log_path, cycle_num, decision,
                                  "success" if exit_code == 0 else f"error_{exit_code}",
                                  cycle_elapsed)

            if exit_code != 0:
                stop_reason = f"cycle_{cycle_num}_failed"
                log.log_message(f"Stopping loop: cycle failed with exit_code={exit_code}", "ERROR")
                break

            if decision in ["skip_heavy", "skip_empty_queue"]:
                stop_reason = f"cycle_{cycle_num}_{decision}"
                log.log_message(f"Stopping loop: {decision}", "WARN")
                break

            if cycle_num < max_cycles:
                log.log_message(f"Sleeping {sleep_seconds}s before next cycle...")
                time.sleep(sleep_seconds)

    except KeyboardInterrupt:
        stop_reason = "interrupted"
        log.log_message("Loop interrupted by user", "WARN")
        log.log_cycle_to_loop(loop_log_path, completed + 1, "interrupted", "interrupted", 0)
    except Exception as e:
        stop_reason = f"exception_{type(e).__name__}"
        log.log_message(f"Loop exception: {e}", "ERROR")
        log.log_cycle_to_loop(loop_log_path, completed + 1, "exception", "exception", 0)
    finally:
        total_elapsed = time.time() - start_time

        state.update_state(
            loop_complete=True,
            loop_completed_cycles=completed,
            stop_reason=stop_reason,
            clear_active=True,
        )

        log.end_loop_log(loop_log_path, completed, stop_reason, total_elapsed)
        log.log_message(f"Loop completed: {completed} cycles, stop_reason={stop_reason}, total_time={total_elapsed:.1f}s")

    return 0


def run_cycle(dry_run: bool = False) -> int:
    """
    Execute one complete cycle (single cycle, not loop).

    Returns: exit code
    """
    exit_code, _ = run_single_cycle(dry_run=dry_run)
    return exit_code


def show_status() -> int:
    """Display current state."""
    st = state.load_state()
    print("=== Research Loop State ===")
    for key, value in st.items():
        if value is not None:
            print(f"  {key}: {value}")
    return 0


def check_interrupted() -> int:
    """
    Check if there's a stale interrupted run.

    Returns:
        0 if CLEAR
        1 if RUNNING (active process still running)
        2 if STALE_INTERRUPTED (state shows running but no active process)
    """
    st = state.load_state()

    last_phase = st.get("last_phase", "none")
    last_exit = st.get("last_exit_status", "none")
    active_pid = st.get("active_pid")

    print("=== Interruption Check ===")
    print(f"  last_phase: {last_phase}")
    print(f"  last_exit_status: {last_exit}")
    print(f"  active_pid: {active_pid}")
    print(f"  active_cycle_started_at: {st.get('active_cycle_started_at')}")
    print(f"  active_command: {st.get('active_command')}")

    is_running_phase = last_phase in ["running_evergreen", "running"]
    is_running_exit = last_exit == "running"

    if is_running_phase or is_running_exit:
        if active_pid is not None:
            try:
                os.kill(active_pid, 0)
                print("\nStatus: RUNNING (process still active)")
                return 1
            except OSError:
                pass

        print("\nStatus: STALE_INTERRUPTED (state shows running but no active process)")
        return 2

    print("\nStatus: CLEAR")
    return 0


def recover_interrupted() -> int:
    """
    Recover from an interrupted run.

    Inspects logs and artifacts to determine what happened and update state accordingly.
    Only modifies state if active running state exists (last_phase=running_evergreen or last_exit_status=running).
    Otherwise, just reports warnings without modifying state.
    """
    st = state.load_state()

    last_phase = st.get("last_phase", "none")
    last_exit = st.get("last_exit_status", "none")
    active_cycle_started = st.get("active_cycle_started_at")
    active_cycle_log = st.get("active_cycle_log_path")
    active_loop_log = st.get("active_loop_log_path")

    print("=== Recovery Check ===")

    is_running_phase = last_phase in ["running_evergreen", "running"]
    is_running_exit = last_exit == "running"

    if not is_running_phase and not is_running_exit:
        print("No active interrupted state detected (no running_evergreen phase or running exit status).")

        latest_session_time = None
        latest_session_path = None
        if os.path.exists(config.NOTES_DIR):
            session_files = glob.glob(os.path.join(config.NOTES_DIR, "session_*_log.md"))
            for sf in session_files:
                mtime = os.path.getmtime(sf)
                if latest_session_time is None or mtime > latest_session_time:
                    latest_session_time = mtime
                    latest_session_path = sf

        latest_artifact_time = None
        latest_artifact_path = None
        if os.path.exists(config.RUN_SUMMARIES_DIR):
            artifact_files = glob.glob(os.path.join(config.RUN_SUMMARIES_DIR, "*.json"))
            for af in artifact_files:
                mtime = os.path.getmtime(af)
                if latest_artifact_time is None or mtime > latest_artifact_time:
                    latest_artifact_time = mtime
                    latest_artifact_path = af

        if latest_artifact_time and latest_session_time:
            if latest_artifact_time > latest_session_time:
                print(f"\nWARNING: Most recent artifact is newer than most recent session log:")
                print(f"  Artifact: {latest_artifact_path} ({datetime.fromtimestamp(latest_artifact_time)})")
                print(f"  Session: {latest_session_path} ({datetime.fromtimestamp(latest_session_time)})")
                print("This may indicate an interrupted run that produced artifacts but no session log.")
            else:
                print("\nNo anomaly detected - latest session log is newer than latest artifact.")
        elif latest_artifact_time and not latest_session_time:
            print(f"\nWARNING: Artifacts exist but no session logs found.")
            print(f"  Latest artifact: {latest_artifact_path} ({datetime.fromtimestamp(latest_artifact_time)})")

        print("\nNo state modification - no active running state to recover.")
        return 0

    print(f"Detected interrupted state at: {active_cycle_started}")
    print(f"Active cycle log: {active_cycle_log}")
    print(f"Active loop log: {active_loop_log}")

    latest_session_time = None
    if os.path.exists(config.NOTES_DIR):
        session_files = glob.glob(os.path.join(config.NOTES_DIR, "session_*_log.md"))
        for sf in session_files:
            mtime = os.path.getmtime(sf)
            if latest_session_time is None or mtime > latest_session_time:
                latest_session_time = mtime

    latest_artifact_time = None
    if os.path.exists(config.RUN_SUMMARIES_DIR):
        artifact_files = glob.glob(os.path.join(config.RUN_SUMMARIES_DIR, "*.json"))
        for af in artifact_files:
            mtime = os.path.getmtime(af)
            if latest_artifact_time is None or mtime > latest_artifact_time:
                latest_artifact_time = mtime

    start_time = None
    if active_cycle_started:
        try:
            start_dt = datetime.fromisoformat(active_cycle_started)
            start_time = start_dt.timestamp()
        except Exception:
            pass

    artifact_after_start = False
    session_after_start = False

    if start_time:
        if latest_artifact_time and latest_artifact_time > start_time:
            artifact_after_start = True
            print(f"\nArtifacts exist after start time: {datetime.fromtimestamp(latest_artifact_time)}")
        if latest_session_time and latest_session_time > start_time:
            session_after_start = True
            print(f"Session log exists after start time: {datetime.fromtimestamp(latest_session_time)}")

    print("\nRecovery decision:")

    if artifact_after_start and not session_after_start:
        print("  -> Interrupted: artifacts created but no session log")
        print("  -> Marking state as interrupted_needs_memory")
        state.update_state(
            phase="interrupted_needs_memory",
            exit_status="interrupted",
            stop_reason="interrupted_after_artifact_before_memory",
            clear_active=True,
        )
        return 0
    elif session_after_start:
        print("  -> Interrupted but session log exists")
        print("  -> Marking state as interrupted_recovered")
        state.update_state(
            phase="interrupted_but_session_logged",
            exit_status="interrupted_recovered",
            stop_reason="interrupted_recovered_session_logged",
            clear_active=True,
        )
        return 0
    else:
        print("  -> No artifacts or session logs after start time")
        print("  -> Marking as generic interruption")
        state.update_state(
            phase="interrupted",
            exit_status="interrupted",
            stop_reason="interrupted_no_evidence",
            clear_active=True,
        )
        return 0


def reset_loop() -> int:
    """Reset the loop state."""
    state.reset_state()
    log.log_message("Loop state reset")
    return 0


def run_ideate_phase(dry_run: bool = False) -> int:
    """Run only the ideate (bright-mind) phase."""
    if dry_run:
        print("Dry-run: would run ideate phase")
        return 0

    current_state = state.load_state()
    if check_heavy_job_running():
        print("Heavy job detected, skipping")
        return 1

    cycle_log_path = log.start_cycle_log()
    log.write_log(cycle_log_path, "=== IDEATE PHASE (bright-mind) ===")

    prompt = load_phase_prompt("ideate")
    wrapped_prompt = prompt

    state.update_state(phase="running_ideate", exit_status="running", active_phase="ideate", active_agent="bright-mind")

    returncode, stdout, stderr = invoke_phase(wrapped_prompt, use_continue=False, title="ideate")

    if returncode == 0:
        state.update_state(phase="completed_ideate", exit_status="success")
        log.write_log(cycle_log_path, "Ideate phase completed")
    else:
        state.update_state(phase="failed_ideate", exit_status=f"error_{returncode}")
        log.write_log(cycle_log_path, f"Ideate failed: {stderr[:200]}")

    return returncode


def run_experiment_phase(dry_run: bool = False) -> int:
    """Run only the experiment (experimentor) phase."""
    if dry_run:
        print("Dry-run: would run experiment phase")
        return 0

    current_state = state.load_state()
    cycle_log_path = log.start_cycle_log()
    log.write_log(cycle_log_path, "=== EXPERIMENT PHASE (experimentor) ===")

    prompt = load_phase_prompt("experiment")
    wrapped_prompt = prompt

    state.update_state(phase="running_experiment", exit_status="running", active_phase="experiment", active_agent="experimentor")

    returncode, stdout, stderr = invoke_phase(wrapped_prompt, use_continue=True)

    if returncode == 0:
        state.update_state(phase="completed_experiment", exit_status="success")
        log.write_log(cycle_log_path, "Experiment phase completed")
    else:
        state.update_state(phase="failed_experiment", exit_status=f"error_{returncode}")
        log.write_log(cycle_log_path, f"Experiment failed: {stderr[:200]}")

    return returncode


def run_memory_phase(dry_run: bool = False) -> int:
    """Run only the memory (manh-memory-system) phase."""
    if dry_run:
        print("Dry-run: would run memory phase")
        return 0

    current_state = state.load_state()
    cycle_log_path = log.start_cycle_log()
    log.write_log(cycle_log_path, "=== MEMORY PHASE (manh-memory-system) ===")

    prompt = load_phase_prompt("memory")
    wrapped_prompt = prompt

    state.update_state(phase="running_memory", exit_status="running", active_phase="memory", active_agent="manh-memory-system")

    returncode, stdout, stderr = invoke_phase(wrapped_prompt, use_continue=True)

    if returncode == 0:
        state.update_state(phase="completed_memory", exit_status="success")
        log.write_log(cycle_log_path, "Memory phase completed")
    else:
        state.update_state(phase="failed_memory", exit_status=f"error_{returncode}")
        log.write_log(cycle_log_path, f"Memory failed: {stderr[:200]}")

    return returncode


def run_three_phase(dry_run: bool = False) -> int:
    """Run complete 4-phase cycle."""
    if dry_run:
        experiment_prompt = load_phase_prompt("experiment").split("\n")[0]
        memory_prompt = load_phase_prompt("memory").split("\n")[0]
        ideate_prompt = load_phase_prompt("ideate").split("\n")[0]

        print("Dry-run: would run 4-phase cycle (experiment→experiment→memory→ideate)")
        print(f"Phase 1: opencode run --dir alpha-research-lab --title 'cycle-N'")
        print(f"  Prompt: {experiment_prompt[:80]}...")
        print(f"Phase 2: opencode run --continue --dir alpha-research-lab")
        print(f"  Prompt: {experiment_prompt[:80]}...")
        print(f"Phase 3: opencode run --continue --dir alpha-research-lab")
        print(f"  Prompt: {memory_prompt[:80]}...")
        print(f"Phase 4: opencode run --continue --dir alpha-research-lab")
        print(f"  Prompt: {ideate_prompt[:80]}...")
        return 0

    results = run_three_phase_cycle(dry_run=dry_run)

    if results.get("cycle_complete"):
        return 0
    else:
        return 1


def main() -> int:
    """Main entry point for the orchestrator."""
    parser = argparse.ArgumentParser(description="Research Loop Orchestrator")
    parser.add_argument("command", choices=["cycle", "three-phase", "dry-run", "status", "reset", "loop",
                                            "check-interrupted", "recover-interrupted",
                                            "ideate", "experiment", "memory",
                                            "evergreen-cycle"],
                        help="Command to run")
    parser.add_argument("--max-cycles", type=int, default=DEFAULT_MAX_CYCLES,
                        help=f"Maximum cycles for loop (default: {DEFAULT_MAX_CYCLES})")
    parser.add_argument("--sleep", type=int, default=DEFAULT_SLEEP_SECONDS,
                        help=f"Sleep seconds between cycles (default: {DEFAULT_SLEEP_SECONDS})")

    args = parser.parse_args()

    if args.command == "cycle" or args.command == "three-phase":
        return run_three_phase(dry_run=False)
    elif args.command == "dry-run":
        return run_three_phase(dry_run=True)
    elif args.command == "status":
        return show_status()
    elif args.command == "reset":
        return reset_loop()
    elif args.command == "loop":
        return run_loop(max_cycles=args.max_cycles, sleep_seconds=args.sleep)
    elif args.command == "check-interrupted":
        return check_interrupted()
    elif args.command == "recover-interrupted":
        return recover_interrupted()
    elif args.command == "ideate":
        return run_ideate_phase(dry_run=False)
    elif args.command == "experiment":
        return run_experiment_phase(dry_run=False)
    elif args.command == "memory":
        return run_memory_phase(dry_run=False)
    elif args.command == "evergreen-cycle":
        return run_cycle(dry_run=False)
    else:
        print(f"Unknown command: {args.command}")
        return 1


if __name__ == "__main__":
    sys.exit(main())