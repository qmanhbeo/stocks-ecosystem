"""Runtime defaults and CUDA diagnostics for local-only PhoBERT operations."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from research_pipelines.news_features.config import NewsFeaturesConfig, get_default_config

WSL_CUDA_LIB_DIR = Path("/usr/lib/wsl/lib")
ALLOW_CPU_OVERRIDE_ENV = "NEWS_FEATURES_ALLOW_CPU"


def _path_exists(path: Path) -> bool:
    return path.exists()


def _prepend_env_path(key: str, directory: Path) -> bool:
    value = str(directory)
    existing = os.environ.get(key, "")
    parts = [segment for segment in existing.split(":") if segment]
    if value in parts:
        return False
    os.environ[key] = f"{value}:{existing}" if existing else value
    return True


def _is_wsl_runtime() -> bool:
    try:
        content = Path("/proc/version").read_text(encoding="utf-8", errors="ignore").lower()
    except OSError:
        return False
    return "microsoft" in content or "wsl" in content


def cuda_runtime_diagnostics(torch) -> dict[str, object]:
    path_value = os.environ.get("PATH", "")
    ld_library_path_value = os.environ.get("LD_LIBRARY_PATH", "")
    return {
        "is_wsl": _is_wsl_runtime(),
        "wsl_cuda_lib_dir": str(WSL_CUDA_LIB_DIR),
        "wsl_cuda_lib_dir_exists": _path_exists(WSL_CUDA_LIB_DIR),
        "dxg_visible": _path_exists(Path("/dev/dxg")),
        "path_has_wsl_cuda_lib": str(WSL_CUDA_LIB_DIR) in path_value.split(":"),
        "ld_library_path_has_wsl_cuda_lib": str(WSL_CUDA_LIB_DIR) in ld_library_path_value.split(":"),
        "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
        "cuda_available": bool(torch.cuda.is_available()),
        "cuda_device_count": int(torch.cuda.device_count()),
        "cuda_version": getattr(torch.version, "cuda", None),
    }


def apply_local_transformers_runtime_defaults(
    config: Optional[NewsFeaturesConfig] = None,
) -> dict[str, str]:
    config = config or get_default_config()
    applied: dict[str, str] = {}

    if _path_exists(WSL_CUDA_LIB_DIR):
        if _prepend_env_path("PATH", WSL_CUDA_LIB_DIR):
            applied["PATH"] = os.environ["PATH"]
        if _prepend_env_path("LD_LIBRARY_PATH", WSL_CUDA_LIB_DIR):
            applied["LD_LIBRARY_PATH"] = os.environ["LD_LIBRARY_PATH"]

    prefer_local = bool(config.phobert_prefer_local_files) or bool(config.phobert_forward_looking_prefer_local_files)
    if not prefer_local:
        return applied

    for key, value in {
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
    }.items():
        if os.environ.get(key) is None:
            os.environ[key] = value
            applied[key] = value
    return applied


def ensure_expected_cuda_runtime(
    torch,
    *,
    context: str,
    allow_cpu_override_env: str = ALLOW_CPU_OVERRIDE_ENV,
) -> None:
    if str(os.environ.get(allow_cpu_override_env, "")).strip().lower() in {"1", "true", "yes", "on"}:
        return

    diagnostics = cuda_runtime_diagnostics(torch)
    if bool(diagnostics.get("cuda_available")):
        return

    if not bool(diagnostics.get("is_wsl")) or not bool(diagnostics.get("wsl_cuda_lib_dir_exists")):
        return

    details = json.dumps(diagnostics, ensure_ascii=False, sort_keys=True)
    if not bool(diagnostics.get("dxg_visible")):
        raise RuntimeError(
            f"{context} expected CUDA on this WSL workstation but /dev/dxg is not visible in this session. "
            f"This usually means the command is running inside a restricted sandbox or container that hides the GPU. "
            f"Run it from your normal shell or outside the sandbox, or set {allow_cpu_override_env}=1 to allow CPU fallback. "
            f"Diagnostics: {details}"
        )

    raise RuntimeError(
        f"{context} found WSL CUDA runtime files and /dev/dxg, but PyTorch still reports CUDA unavailable. "
        f"Check the active Python environment and driver/runtime compatibility, or set {allow_cpu_override_env}=1 to allow CPU fallback. "
        f"Diagnostics: {details}"
    )
