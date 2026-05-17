#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/manh/stocks-ecosystem/alpha-research-lab"
STATE_JSON="$ROOT/evergreen-research-loop/state/loop_state.json"
LOG_DIR="$ROOT/evergreen-research-loop/logs"
OUT_DIR="$ROOT/evergreen-research-loop/watchdog"
OUT_LOG="$OUT_DIR/watchdog_5m.log"

mkdir -p "$OUT_DIR"

echo "=== watchdog start $(date -Is) ===" >> "$OUT_LOG"

while true; do
  ts="$(date -Is)"
  if [[ -f "$STATE_JSON" ]]; then
    state_line="$(python - <<'PY' "$STATE_JSON"
import json, sys
p = sys.argv[1]
try:
    with open(p, "r", encoding="utf-8") as f:
        s = json.load(f)
except Exception:
    print("null|null|-1|null||")
    raise SystemExit(0)
print("|".join([
    str(s.get("last_phase") or "null"),
    str(s.get("last_exit_status") or "null"),
    str(s.get("cycle_count") if s.get("cycle_count") is not None else -1),
    str(s.get("active_pid") if s.get("active_pid") is not None else "null"),
    str(s.get("active_cycle_log_path") or ""),
    str(s.get("active_phase_started_at") or ""),
]))
PY
)"
    IFS='|' read -r phase exit_status cycle_count active_pid active_cycle_log active_phase_started <<< "$state_line"

    errors=""
    if [[ -n "$active_cycle_log" && -f "$active_cycle_log" ]]; then
      errors="$(rg -n "ERROR|Traceback|Exception|error_|failed" "$active_cycle_log" | tail -n 5 || true)"
    fi

    if [[ "$phase" == running_* && "$active_pid" =~ ^[0-9]+$ ]]; then
      if ps -p "$active_pid" >/dev/null 2>&1; then
        pid_state="alive"
      else
        pid_state="missing"
      fi
    else
      pid_state="na"
    fi

    echo "[$ts] phase=$phase exit=$exit_status cycle=$cycle_count active_pid=$active_pid pid_state=$pid_state started=$active_phase_started" >> "$OUT_LOG"
    if [[ -n "$errors" ]]; then
      echo "[$ts] recent_error_lines:" >> "$OUT_LOG"
      echo "$errors" >> "$OUT_LOG"
    fi
  else
    echo "[$ts] state_missing: $STATE_JSON" >> "$OUT_LOG"
  fi

  sleep 300
done
