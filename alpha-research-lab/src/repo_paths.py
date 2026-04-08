from __future__ import annotations

from pathlib import Path


LAB_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = LAB_ROOT.parent
DATA_ROOT = WORKSPACE_ROOT / "data"
ARTIFACTS_ROOT = LAB_ROOT / "artifacts"


def lab_path(*parts: str | Path) -> Path:
    path = LAB_ROOT
    for part in parts:
        path = path / Path(part)
    return path


def workspace_path(*parts: str | Path) -> Path:
    path = WORKSPACE_ROOT
    for part in parts:
        path = path / Path(part)
    return path


def data_path(*parts: str | Path) -> Path:
    relative = Path()
    for part in parts:
        relative = relative / Path(part)
    if relative.parts[:1] == ("data",):
        relative = Path(*relative.parts[1:])
    return DATA_ROOT / relative


def resolve_data_path(value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    if path.parts[:1] == ("data",):
        return data_path(path)
    return path


def artifact_path(*parts: str | Path) -> Path:
    return lab_path("artifacts", *parts)


def lab_relative_path(value: str | Path) -> str:
    path = Path(value)
    if path.is_absolute():
        try:
            return str(path.relative_to(LAB_ROOT))
        except ValueError:
            try:
                return str(path.relative_to(WORKSPACE_ROOT))
            except ValueError:
                return str(path)
    return str(path)
