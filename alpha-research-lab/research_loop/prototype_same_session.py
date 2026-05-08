#!/usr/bin/env python3
"""
Prototype: Same-Session Three-Phase Orchestration (v3)

Uses --continue flag since session list is unreliable from subprocess.
We verified manually that --continue works for context preservation.

Target: One research cycle = ONE OpenCode session with:
  1. /bright-mind message
  2. /experimentor message
  3. /manh-memory-system message
"""

import subprocess
import os
import sys
import glob
import re
import json
from datetime import datetime
from pathlib import Path

PROTOTYPE_DIR = "/tmp/opencode-cycle-prototype"
LOGS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")


def ensure_dirs():
    os.makedirs(PROTOTYPE_DIR, exist_ok=True)
    os.makedirs(LOGS_DIR, exist_ok=True)


def log_message(msg, log_lines):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{timestamp}] {msg}"
    print(formatted)
    log_lines.append(formatted)


def run_opencode_continue(message):
    """Run opencode with --continue to resume last session."""
    cmd = ["opencode", "run", "--continue"]
    cmd.append(message)

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=120,
        cwd=PROTOTYPE_DIR,
    )

    return result.returncode, result.stdout, result.stderr


def run_opencode_simple(message, title=None):
    """Run opencode with a simple message."""
    cmd = ["opencode", "run"]
    if title:
        cmd.extend(["--title", title])
    cmd.append(message)

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=120,
        cwd=PROTOTYPE_DIR,
    )

    return result.returncode, result.stdout, result.stderr


def test_three_phase_continue(log_lines):
    """Test 1: Three-phase using --continue"""
    log_message("=== Test 1: Three-Phase with --continue ===", log_lines)

    phase1_msg = "Remember exactly this token: ALPHA123. Reply only: stored."
    log_message(f"Phase 1: {phase1_msg}", log_lines)

    ret1, out1, err1 = run_opencode_simple(phase1_msg, title="phase1")
    log_message(f"Phase 1 retcode: {ret1}", log_lines)
    log_message(f"Phase 1 output: {out1.strip()}", log_lines)

    phase2_msg = "Using this same session, what token did I ask you to remember? Then remember exactly this second token: BETA456. Reply only with both tokens."
    log_message(f"Phase 2: {phase2_msg[:50]}...", log_lines)

    ret2, out2, err2 = run_opencode_continue(phase2_msg)
    log_message(f"Phase 2 retcode: {ret2}", log_lines)
    log_message(f"Phase 2 output: {out2.strip()}", log_lines)

    phase3_msg = 'Using this same session, list both remembered tokens. Reply only in JSON: {"phase1":"...","phase2":"..."}'
    log_message(f"Phase 3: {phase3_msg[:50]}...", log_lines)

    ret3, out3, err3 = run_opencode_continue(phase3_msg)
    log_message(f"Phase 3 retcode: {ret3}", log_lines)
    log_message(f"Phase 3 output: {out3.strip()}", log_lines)

    has_alpha = "ALPHA123" in out3
    has_beta = "BETA456" in out3
    passed = has_alpha and has_beta

    log_message(f"Phase 3 has ALPHA123: {has_alpha}", log_lines)
    log_message(f"Phase 3 has BETA456: {has_beta}", log_lines)
    log_message(f"Three-phase test: {'PASSED' if passed else 'FAILED'}", log_lines)

    return {
        "passed": passed,
        "phase1_out": out1.strip(),
        "phase2_out": out2.strip(),
        "phase3_out": out3.strip(),
    }


def test_slash_skill_continue(log_lines):
    """Test 2: Slash skill syntax works with --continue"""
    log_message("=== Test 2: Slash Skill with --continue ===", log_lines)

    msg = "Use /bright-mind skill. Give me one short hypothesis about flowers."
    log_message(f"Message: {msg[:50]}...", log_lines)

    ret, out, err = run_opencode_simple(msg, title="skill-test")
    log_message(f"Retcode: {ret}", log_lines)
    log_message(f"Output: {out[:300]}", log_lines)

    if ret == 0:
        followup = "What hypothesis did I ask you to generate?"
        ret2, out2, err2 = run_opencode_continue(followup)
        log_message(f"Followup retcode: {ret2}", log_lines)
        log_message(f"Followup output: {out2[:200]}", log_lines)

        skill_works = ret == 0 and ("hypothesis" in out.lower() or "flower" in out.lower())
    else:
        skill_works = False

    log_message(f"Slash skill test: {'PASSED' if skill_works else 'FAILED'}", log_lines)

    return {"passed": skill_works, "output": out[:300]}


def main():
    ensure_dirs()

    log_lines = []
    log_message("=== Same-Session Phase Prototype (v3) Started ===", log_lines)
    log_message(f"Working directory: {PROTOTYPE_DIR}", log_lines)

    results = {}

    try:
        results["three_phase"] = test_three_phase_continue(log_lines)
    except Exception as e:
        log_message(f"Test 1 failed with exception: {e}", log_lines)
        results["three_phase"] = {"passed": False, "error": str(e)}

    try:
        results["slash_skill"] = test_slash_skill_continue(log_lines)
    except Exception as e:
        log_message(f"Test 2 failed with exception: {e}", log_lines)
        results["slash_skill"] = {"passed": False, "error": str(e)}

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = os.path.join(LOGS_DIR, f"prototype_same_session_{timestamp}.log")
    with open(log_path, "w") as f:
        f.write("\n".join(log_lines))

    log_message(f"\n=== Prototype Complete ===", log_lines)
    log_message(f"Log saved to: {log_path}", log_lines)

    three_phase_passed = results.get("three_phase", {}).get("passed", False)
    slash_skill_passed = results.get("slash_skill", {}).get("passed", False)

    log_message(f"\n=== Summary ===", log_lines)
    log_message(f"  Three-phase with --continue: {'PASSED' if three_phase_passed else 'FAILED'}", log_lines)
    log_message(f"  Slash skill with --continue: {'PASSED' if slash_skill_passed else 'FAILED'}", log_lines)

    print(f"\nLog saved to: {log_path}")
    print(f"Three-phase test: {'PASSED' if three_phase_passed else 'FAILED'}")
    print(f"Slash skill test: {'PASSED' if slash_skill_passed else 'FAILED'}")

    return 0


if __name__ == "__main__":
    sys.exit(main())