"""
Configuration constants for the research loop orchestrator.
"""

import os

REPO_ROOT = os.path.expanduser("~/stocks-ecosystem")
RESEARCH_LAB = os.path.join(REPO_ROOT, "alpha-research-lab")

LIVE_STATE_PATH = os.path.join(RESEARCH_LAB, "notes", "live_state.md")
SESSIONS_COMPACT_PATH = os.path.join(RESEARCH_LAB, "notes", "sessions_compact.md")
FINDINGS_COMPACT_PATH = os.path.join(RESEARCH_LAB, "notes", "findings_compact.md")
DEADENDS_COMPACT_PATH = os.path.join(RESEARCH_LAB, "notes", "deadends_compact.md")

LOOP_STATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state")
LOOP_STATE_FILE = os.path.join(LOOP_STATE_DIR, "loop_state.json")
LOGS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")

OPENCODE_BINARY = "opencode"
OPENCODE_MODEL = None
OPENCODE_TIMEOUT_SECONDS = 1800

PROTECT_2026 = True

STATE_VERSION = "1.0"