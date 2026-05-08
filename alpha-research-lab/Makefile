.PHONY: loop dry-run status reset check-interrupted recover-interrupted tail help

MAX_CYCLES ?= 2
SESSION_BATCH_SIZE ?= 3

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
	@echo ""
	@echo "Variables:"
	@echo "  MAX_CYCLES         - Number of cycles (default: 2)"
	@echo "  SESSION_BATCH_SIZE - Cycles per session batch (default: 3)"

loop:
	@echo "Running bounded loop (max_cycles=$(MAX_CYCLES), session_batch_size=$(SESSION_BATCH_SIZE))..."
	python3 -u research_loop/orchestrator.py loop --max-cycles $(MAX_CYCLES) --session-batch-size $(SESSION_BATCH_SIZE)

dry-run:
	@echo "Running dry-run (no agent invocation)..."
	python3 -u research_loop/orchestrator.py dry-run --max-cycles $(MAX_CYCLES) --session-batch-size $(SESSION_BATCH_SIZE)

status:
	@echo "Current state:"
	python3 -u research_loop/orchestrator.py status

reset:
	@echo "Resetting loop state..."
	python3 -u research_loop/orchestrator.py reset

check-interrupted:
	@echo "Checking for interrupted runs..."
	python3 -u research_loop/orchestrator.py check-interrupted

recover-interrupted:
	@echo "Recovering from interrupted run..."
	python3 -u research_loop/orchestrator.py recover-interrupted

tail:
	@echo "Tailing latest log file..."
	@ls -t research_loop/logs/cycle_*.log research_loop/logs/loop_*.log 2>/dev/null | head -1 | xargs tail -f