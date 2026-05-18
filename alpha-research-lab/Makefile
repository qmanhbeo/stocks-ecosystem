.PHONY: loop dry-run status reset check-interrupted recover-interrupted tail notes-audit help

MAX_CYCLES ?= 1
SESSION_BATCH_SIZE ?= 1
VERBOSE ?= 0
HEARTBEAT_SECONDS ?= 30

help:
	@echo "Research Loop Orchestrator (run from alpha-research-lab root)"
	@echo ""
	@echo "Commands:"
	@echo "  make loop               - Run bounded loop (MAX_CYCLES=$(MAX_CYCLES))"
	@echo "  make dry-run           - Show cycle plan without execution"
	@echo "  make status            - Display current state"
	@echo "  make reset             - Reset loop state"
	@echo "  make check-interrupted - Check for stale interrupted runs"
	@echo "  make recover-interrupted - Recover from interrupted run"
	@echo "  make tail              - Tail latest log file"
	@echo "  make notes-audit       - Validate notes chunking/index/anchor consistency"
	@echo ""
	@echo "Variables:"
	@echo "  MAX_CYCLES         - Number of cycles (default: 1)"
	@echo "  SESSION_BATCH_SIZE - Compatibility flag only; values >1 are ignored because each cycle uses a fresh OpenCode session (default: 1)"
	@echo "  VERBOSE            - Enable verbose output (default: 0)"
	@echo "  HEARTBEAT_SECONDS  - Heartbeat interval in seconds (default: 30)"

loop:
	@echo "Running bounded loop (max_cycles=$(MAX_CYCLES), requested_session_batch_size=$(SESSION_BATCH_SIZE), verbose=$(VERBOSE))..."
	@if [ "$(VERBOSE)" = "1" ]; then \
		python3 -u evergreen-research-loop/orchestrator.py loop --max-cycles $(MAX_CYCLES) --session-batch-size $(SESSION_BATCH_SIZE) --verbose --heartbeat-seconds $(HEARTBEAT_SECONDS); \
	else \
		python3 -u evergreen-research-loop/orchestrator.py loop --max-cycles $(MAX_CYCLES) --session-batch-size $(SESSION_BATCH_SIZE) --heartbeat-seconds $(HEARTBEAT_SECONDS); \
	fi

dry-run:
	@echo "Running dry-run (no agent invocation)..."
	@if [ "$(VERBOSE)" = "1" ]; then \
		python3 -u evergreen-research-loop/orchestrator.py dry-run --max-cycles $(MAX_CYCLES) --session-batch-size $(SESSION_BATCH_SIZE) --verbose --heartbeat-seconds $(HEARTBEAT_SECONDS); \
	else \
		python3 -u evergreen-research-loop/orchestrator.py dry-run --max-cycles $(MAX_CYCLES) --session-batch-size $(SESSION_BATCH_SIZE) --heartbeat-seconds $(HEARTBEAT_SECONDS); \
	fi

status:
	@echo "Current state:"
	python3 -u evergreen-research-loop/orchestrator.py status

reset:
	@echo "Resetting loop state..."
	python3 -u evergreen-research-loop/orchestrator.py reset

check-interrupted:
	@echo "Checking for interrupted runs..."
	python3 -u evergreen-research-loop/orchestrator.py check-interrupted

recover-interrupted:
	@echo "Recovering from interrupted run..."
	python3 -u evergreen-research-loop/orchestrator.py recover-interrupted

tail:
	@echo "Tailing latest log file..."
	@ls -t evergreen-research-loop/logs/cycle_*.log evergreen-research-loop/logs/loop_*.log 2>/dev/null | head -1 | xargs tail -f

notes-audit:
	@echo "Running notes consistency audit..."
	python3 -u tools/validate_notes_consistency.py --notes-dir notes
