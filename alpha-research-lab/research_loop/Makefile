.PHONY: cycle dry-run status reset loop help

MAX_CYCLES ?= 2

help:
	@echo "Research Loop Orchestrator - MVP"
	@echo ""
	@echo "Targets:"
	@echo "  make cycle      - Run one orchestrator cycle (invokes evergreen)"
	@echo "  make dry-run    - Run decision logic WITHOUT invoking opencode"
	@echo "  make status     - Display current saved state"
	@echo "  make reset      - Reset/delete loop state safely"
	@echo "  make loop       - Run bounded loop (MAX_CYCLES=$(MAX_CYCLES), default 2)"
	@echo ""
	@echo "Variables:"
	@echo "  MAX_CYCLES       - Number of cycles for loop (default: 2)"
	@echo ""
	@echo "Files:"
	@echo "  state/loop_state.json - Persistent state"
	@echo "  logs/cycle_*.log      - Per-cycle logs"
	@echo "  logs/loop_*.log       - Loop summary logs"

cycle:
	@echo "Running orchestrator cycle..."
	python3 orchestrator.py cycle

dry-run:
	@echo "Running dry-run (no evergreen invocation)..."
	python3 orchestrator.py dry-run

status:
	@echo "Current state:"
	python3 orchestrator.py status

reset:
	@echo "Resetting loop state..."
	python3 orchestrator.py reset
	@echo "State reset complete"

loop:
	@echo "Running bounded loop (max_cycles=$(MAX_CYCLES))..."
	python3 orchestrator.py loop --max-cycles $(MAX_CYCLES)