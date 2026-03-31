from __future__ import annotations

from pathlib import Path


LAB_ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS_ROOT = LAB_ROOT / "artifacts"


def lab_path(*parts: str | Path) -> Path:
    path = LAB_ROOT
    for part in parts:
        path = path / Path(part)
    return path


def artifact_path(*parts: str | Path) -> Path:
    return lab_path("artifacts", *parts)


def lab_relative_path(value: str | Path) -> str:
    path = Path(value)
    if path.is_absolute():
        try:
            return str(path.relative_to(LAB_ROOT))
        except ValueError:
            return str(path)
    return str(path)
