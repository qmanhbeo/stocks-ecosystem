.PHONY: cycle dry-run status reset loop check-interrupted recover-interrupted ideate experiment memory evergreen-cycle help tail

MAX_CYCLES ?= 1
SESSION_BATCH_SIZE ?= 1
VERBOSE ?= 0
HEARTBEAT_SECONDS ?= 30

help:
	@echo "Research Loop Orchestrator"
	@echo ""
	@echo "Cycle Flow:"
	@echo "  make cycle              - Run one fresh-session cycle (experiment→experiment→memory→ideate→handoff)"
	@echo "  make ideate             - Run only Phase 1 (bright-mind)"
	@echo "  make experiment        - Run only Phase 2 (experimentor)"
	@echo "  make memory            - Run only Phase 3 (manh-memory-system)"
	@echo ""
	@echo "Legacy:"
	@echo "  make evergreen-cycle   - Run old single evergreen call"
	@echo ""
	@echo "Utilities:"
	@echo "  make dry-run            - Run decision logic WITHOUT invoking opencode"
	@echo "  make status             - Display current saved state"
	@echo "  make reset              - Reset/delete loop state safely"
	@echo "  make loop               - Run bounded loop (MAX_CYCLES=$(MAX_CYCLES), default 1)"
	@echo "  make check-interrupted  - Check for stale interrupted runs"
	@echo "  make recover-interrupted - Recover from an interrupted run"
	@echo "  make tail               - Tail -f latest cycle/loop log"
	@echo ""
	@echo "Variables:"
	@echo "  MAX_CYCLES       - Number of cycles for loop (default: 1)"
	@echo "  SESSION_BATCH_SIZE - Compatibility flag only; values >1 are ignored because each cycle uses a fresh OpenCode session (default: 1)"
	@echo "  VERBOSE          - Enable verbose output (default: 0)"
	@echo "  HEARTBEAT_SECONDS - Heartbeat interval in seconds (default: 30)"
	@echo ""
	@echo "Files:"
	@echo "  state/loop_state.json - Persistent state"
	@echo "  logs/cycle_*.log      - Per-cycle logs"
	@echo "  logs/loop_*.log       - Loop summary logs"
	@echo "  prompts/              - Phase prompt templates"

cycle:
	@echo "Running fresh-session cycle (experiment→experiment→memory→ideate→handoff)..."
	python3 -u orchestrator.py cycle

ideate:
	@echo "Running Phase 1: Ideate (bright-mind)..."
	@echo "WARNING: Standalone ideate starts a fresh session and records its session id in state"
	python3 -u orchestrator.py ideate

experiment:
	@echo "Running Phase 2: Experiment (experimentor)..."
	@echo "WARNING: Standalone experiment reuses active_session_id from loop state"
	@echo "Only use after a fresh phase created that session, or use make cycle instead"
	python3 -u orchestrator.py experiment

memory:
	@echo "Running Phase 3: Memory (manh-memory-system)..."
	@echo "WARNING: Standalone memory reuses active_session_id from loop state"
	@echo "Only use after a fresh phase created that session, or use make cycle instead"
	python3 -u orchestrator.py memory

dry-run:
	@echo "Running dry-run (no agent invocation)..."
	@if [ "$(VERBOSE)" = "1" ]; then \
		python3 -u orchestrator.py dry-run --max-cycles $(MAX_CYCLES) --session-batch-size $(SESSION_BATCH_SIZE) --verbose --heartbeat-seconds $(HEARTBEAT_SECONDS); \
	else \
		python3 -u orchestrator.py dry-run --max-cycles $(MAX_CYCLES) --session-batch-size $(SESSION_BATCH_SIZE) --heartbeat-seconds $(HEARTBEAT_SECONDS); \
	fi

status:
	@echo "Current state:"
	python3 -u orchestrator.py status

reset:
	@echo "Resetting loop state..."
	python3 -u orchestrator.py reset
	@echo "State reset complete"

loop:
	@echo "Running bounded loop (max_cycles=$(MAX_CYCLES), requested_session_batch_size=$(SESSION_BATCH_SIZE), verbose=$(VERBOSE))..."
	@if [ "$(VERBOSE)" = "1" ]; then \
		python3 -u orchestrator.py loop --max-cycles $(MAX_CYCLES) --session-batch-size $(SESSION_BATCH_SIZE) --verbose --heartbeat-seconds $(HEARTBEAT_SECONDS); \
	else \
		python3 -u orchestrator.py loop --max-cycles $(MAX_CYCLES) --session-batch-size $(SESSION_BATCH_SIZE) --heartbeat-seconds $(HEARTBEAT_SECONDS); \
	fi

check-interrupted:
	@echo "Checking for interrupted runs..."
	python3 -u orchestrator.py check-interrupted

recover-interrupted:
	@echo "Recovering from interrupted run..."
	python3 -u orchestrator.py recover-interrupted

evergreen-cycle:
	@echo "Running legacy evergreen cycle..."
	python3 -u orchestrator.py evergreen-cycle

tail:
	@echo "Tailing latest log file..."
	@ls -t logs/cycle_*.log logs/loop_*.log 2>/dev/null | head -1 | xargs tail -f
