"""Periodic watchdog snapshots for the live PhoBERT forward-looking canary."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import time
from typing import Any

from research_pipelines.news_features.config import get_default_config


REPO_ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_ROOT = REPO_ROOT / "artifacts" / "job_status"
DEFAULT_JOB_STATUS = ARTIFACT_ROOT / "phobert_forward_looking_train.json"
DEFAULT_CURRENT = ARTIFACT_ROOT / "phobert_forward_looking_watchdog_current.json"
DEFAULT_HISTORY = ARTIFACT_ROOT / "phobert_forward_looking_watchdog_history.jsonl"
DEFAULT_COMMAND_SUBSTRING = "research_pipelines.news_features.core.train_phobert_forward_looking"
DEFAULT_TRAINING_MANIFEST = get_default_config().phobert_forward_looking_training_manifest_path()
NVIDIA_SMI = Path("/usr/lib/wsl/lib/nvidia-smi")


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def run_command(argv: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, capture_output=True, text=True, check=False)


def read_meminfo() -> dict[str, int]:
    values: dict[str, int] = {}
    with Path("/proc/meminfo").open("r", encoding="utf-8") as handle:
        for line in handle:
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            parts = value.strip().split()
            if not parts:
                continue
            try:
                values[key] = int(parts[0])
            except ValueError:
                continue
    return values


def collect_system_memory() -> dict[str, Any]:
    meminfo = read_meminfo()
    total_kib = int(meminfo.get("MemTotal", 0))
    available_kib = int(meminfo.get("MemAvailable", 0))
    swap_total_kib = int(meminfo.get("SwapTotal", 0))
    swap_free_kib = int(meminfo.get("SwapFree", 0))
    used_kib = max(total_kib - available_kib, 0)
    return {
        "ram_total_gib": round(total_kib / 1024 / 1024, 2),
        "ram_used_gib": round(used_kib / 1024 / 1024, 2),
        "ram_available_gib": round(available_kib / 1024 / 1024, 2),
        "swap_total_gib": round(swap_total_kib / 1024 / 1024, 2),
        "swap_free_gib": round(swap_free_kib / 1024 / 1024, 2),
    }


def collect_gpu() -> dict[str, Any]:
    if not NVIDIA_SMI.exists():
        return {"available": False}
    query = [
        str(NVIDIA_SMI),
        "--query-gpu=name,memory.total,memory.used,utilization.gpu,temperature.gpu",
        "--format=csv,noheader,nounits",
    ]
    result = run_command(query)
    if result.returncode != 0:
        return {"available": False, "error": result.stderr.strip() or result.stdout.strip()}
    line = next((item.strip() for item in result.stdout.splitlines() if item.strip()), "")
    if not line:
        return {"available": False, "error": "empty_nvidia_smi_output"}
    parts = [part.strip() for part in line.split(",")]
    gpu = {
        "available": True,
        "raw": line,
    }
    if len(parts) >= 5:
        gpu.update(
            {
                "name": parts[0],
                "memory_total_mib": int(parts[1]),
                "memory_used_mib": int(parts[2]),
                "utilization_gpu_pct": int(parts[3]),
                "temperature_c": int(parts[4]),
            }
        )
    return gpu


def collect_process(command_substring: str) -> dict[str, Any]:
    result = run_command(["pgrep", "-af", command_substring])
    if result.returncode != 0:
        return {"running": False, "matches": []}
    matches: list[dict[str, Any]] = []
    for line in result.stdout.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        pid_text, _, command = stripped.partition(" ")
        try:
            pid = int(pid_text)
        except ValueError:
            continue
        ps = run_command(["ps", "-p", str(pid), "-o", "pid=,etime=,pcpu=,pmem=,cmd="])
        if ps.returncode != 0 or not ps.stdout.strip():
            continue
        parts = ps.stdout.strip().split(None, 4)
        if len(parts) < 5:
            continue
        matches.append(
            {
                "pid": int(parts[0]),
                "elapsed": parts[1],
                "cpu_pct": float(parts[2]),
                "mem_pct": float(parts[3]),
                "cmd": parts[4],
            }
        )
    return {"running": bool(matches), "matches": matches}


def safe_stat(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    stat = path.stat()
    return {
        "path": str(path.relative_to(REPO_ROOT)),
        "size_bytes": int(stat.st_size),
        "mtime_epoch": float(stat.st_mtime),
    }


def collect_candidate_state(training_manifest: dict[str, Any]) -> dict[str, Any]:
    candidates = dict(training_manifest.get("candidates") or {})
    current_entry = next(iter(candidates.values()), {})
    output_dir = Path(str(current_entry.get("output_dir", ""))) if current_entry.get("output_dir") else None
    candidate_state_path = output_dir / "candidate_state.json" if output_dir else None
    metrics_path = output_dir / "metrics.json" if output_dir else None
    model_dir = output_dir / "model" if output_dir else None
    state_payload = load_json(candidate_state_path) if candidate_state_path and candidate_state_path.exists() else {}
    epoch_history = list(state_payload.get("epoch_history") or [])
    latest_epoch = dict(epoch_history[-1]) if epoch_history else {}
    latest_val_summary = dict(latest_epoch.get("val_summary") or {})
    latest_val_metrics = dict(latest_val_summary.get("metrics") or {})
    return {
        "candidate_name": state_payload.get("candidate_name") or current_entry.get("candidate_name"),
        "status": state_payload.get("status") or current_entry.get("status"),
        "last_completed_epoch": state_payload.get("last_completed_epoch"),
        "epoch_history_len": len(epoch_history),
        "latest_val_metrics": latest_val_metrics,
        "candidate_state_file": safe_stat(candidate_state_path) if candidate_state_path else None,
        "metrics_file": safe_stat(metrics_path) if metrics_path else None,
        "model_safetensors": safe_stat(model_dir / "model.safetensors") if model_dir else None,
    }


def progress_marker(job_status: dict[str, Any], candidate_state: dict[str, Any]) -> str:
    current_epoch = ((job_status.get("progress") or {}).get("current_epoch"))
    last_completed_epoch = candidate_state.get("last_completed_epoch")
    heartbeat = job_status.get("last_heartbeat")
    safetensors_mtime = ((candidate_state.get("model_safetensors") or {}).get("mtime_epoch"))
    return json.dumps(
        {
            "heartbeat": heartbeat,
            "current_epoch": current_epoch,
            "last_completed_epoch": last_completed_epoch,
            "model_safetensors_mtime": safetensors_mtime,
        },
        sort_keys=True,
    )


def classify_health(
    *,
    job_status: dict[str, Any],
    training_manifest: dict[str, Any],
    process_state: dict[str, Any],
    previous_snapshot: dict[str, Any],
    current_marker: str,
) -> tuple[str, int]:
    status = str(job_status.get("status", "unknown"))
    manifest_status = str(training_manifest.get("status", "unknown"))
    if status in {"complete", "completed"} or manifest_status in {"complete", "completed"}:
        return ("completed", 0)
    if status in {"failed", "error"} or manifest_status in {"failed", "error"}:
        return ("failed", 0)
    if status == "no_winner" or manifest_status == "no_winner":
        return ("completed_no_winner", 0)
    if not process_state.get("running"):
        return ("process_missing", 0)

    previous_marker = str(previous_snapshot.get("progress_marker", ""))
    previous_stale_count = int(previous_snapshot.get("stale_polls", 0) or 0)
    if current_marker != previous_marker:
        return ("healthy_progressing", 0)

    stale_polls = previous_stale_count + 1
    if stale_polls >= 2:
        return ("stalled", stale_polls)
    return ("healthy_slow", stale_polls)


def build_snapshot(command_substring: str, previous_snapshot: dict[str, Any]) -> dict[str, Any]:
    job_status = load_json(DEFAULT_JOB_STATUS)
    config = get_default_config()
    config.ensure_phobert_forward_looking_model_state()
    training_manifest = load_json(DEFAULT_TRAINING_MANIFEST)
    process_state = collect_process(command_substring)
    gpu_state = collect_gpu()
    memory_state = collect_system_memory()
    candidate_state = collect_candidate_state(training_manifest)
    marker = progress_marker(job_status, candidate_state)
    health, stale_polls = classify_health(
        job_status=job_status,
        training_manifest=training_manifest,
        process_state=process_state,
        previous_snapshot=previous_snapshot,
        current_marker=marker,
    )
    return {
        "ts_utc": utc_now(),
        "job": "phobert_forward_looking_watchdog",
        "watch_target": "phobert_forward_looking_train",
        "health": health,
        "stale_polls": stale_polls,
        "progress_marker": marker,
        "process": process_state,
        "job_status": {
            "status": job_status.get("status"),
            "phase": job_status.get("phase"),
            "last_heartbeat": job_status.get("last_heartbeat"),
            "progress": job_status.get("progress"),
            "throughput": job_status.get("throughput"),
        },
        "training_manifest": {
            "status": training_manifest.get("status"),
            "run_id": training_manifest.get("run_id"),
            "winner": training_manifest.get("winner"),
            "candidate_names": list(((training_manifest.get("run_signature") or {}).get("candidate_names") or [])),
        },
        "candidate_state": candidate_state,
        "hardware": {
            "memory": memory_state,
            "gpu": gpu_state,
        },
    }


def should_stop(snapshot: dict[str, Any]) -> bool:
    return snapshot.get("health") in {"completed", "completed_no_winner", "failed", "process_missing"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Periodic watchdog snapshots for the live PhoBERT canary.")
    parser.add_argument("--poll-seconds", type=int, default=600, help="Polling interval in seconds. Defaults to 600.")
    parser.add_argument("--command-substring", default=DEFAULT_COMMAND_SUBSTRING, help="Substring used to find the live job.")
    parser.add_argument("--once", action="store_true", help="Run one poll only and exit.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    DEFAULT_CURRENT.parent.mkdir(parents=True, exist_ok=True)
    while True:
        previous_snapshot = load_json(DEFAULT_CURRENT)
        snapshot = build_snapshot(str(args.command_substring), previous_snapshot)
        write_json(DEFAULT_CURRENT, snapshot)
        append_jsonl(DEFAULT_HISTORY, snapshot)
        print(
            "watchdog snapshot "
            f"health={snapshot['health']} "
            f"phase={snapshot['job_status'].get('phase')} "
            f"candidate={snapshot['candidate_state'].get('candidate_name')} "
            f"epoch={snapshot['candidate_state'].get('last_completed_epoch')} "
            f"gpu={((snapshot['hardware'].get('gpu') or {}).get('utilization_gpu_pct'))}",
            flush=True,
        )
        if args.once or should_stop(snapshot):
            return
        time.sleep(max(int(args.poll_seconds), 1))


if __name__ == "__main__":
    main()
