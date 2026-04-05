"""
Create and upload a dated full-data snapshot of the shared workspace `data/` tree.

This is the backup counterpart to `setup_data.py`.

Features:
- creates `data-snapshot-YYYY-MM-DD.tar.zst`
- writes matching `.sha256`
- uploads both files to a configured Google Drive remote via `rclone`
- prunes old local and remote snapshot pairs, keeping the newest N

Usage:
    python backup_data_snapshot.py --remote-root gdrive:stocks-ecosystem-data-snapshots

Environment:
    DATA_SNAPSHOT_REMOTE_ROOT may be used instead of --remote-root.

Notes:
- The script expects `rclone` to be installed and the remote to be configured.
- The backup source is the workspace-root `data/` directory, not repo-local caches.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tarfile
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import zstandard as zstd


SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = SCRIPT_DIR.parent
DEFAULT_KEEP = 7
DEFAULT_REMOTE_ROOT = "stocks-ecosystem-data-snapshots:project-backup/stock-data-backup/"
SNAPSHOT_DATE_RE = re.compile(r"^data-snapshot-(\d{4}-\d{2}-\d{2})\.tar\.zst$")
SNAPSHOT_CHECKSUM_RE = re.compile(r"^data-snapshot-(\d{4}-\d{2}-\d{2})\.tar\.zst\.sha256$")


@dataclass(frozen=True)
class SnapshotPaths:
    snapshot_date: date
    archive_path: Path
    checksum_path: Path


def _log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def _snapshot_name(snapshot_date: date) -> str:
    return f"data-snapshot-{snapshot_date.isoformat()}.tar.zst"


def _snapshot_paths(output_dir: Path, snapshot_date: date) -> SnapshotPaths:
    archive_name = _snapshot_name(snapshot_date)
    archive_path = output_dir / archive_name
    checksum_path = output_dir / f"{archive_name}.sha256"
    return SnapshotPaths(snapshot_date=snapshot_date, archive_path=archive_path, checksum_path=checksum_path)


def _compute_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_checksum(archive_path: Path, checksum_path: Path) -> None:
    digest = _compute_sha256(archive_path)
    checksum_path.write_text(f"{digest}  {archive_path.name}\n", encoding="utf-8")


def _iter_snapshot_members(source_dir: Path):
    if not source_dir.exists():
        raise FileNotFoundError(f"snapshot source directory does not exist: {source_dir}")
    if not source_dir.is_dir():
        raise RuntimeError(f"snapshot source is not a directory: {source_dir}")
    if source_dir.is_symlink():
        raise RuntimeError(f"refusing to snapshot symlinked source directory: {source_dir}")

    yield source_dir
    for root, dirnames, filenames in os.walk(source_dir, topdown=True, followlinks=False):
        dirnames.sort()
        filenames.sort()
        root_path = Path(root)

        for dirname in dirnames:
            path = root_path / dirname
            if path.is_symlink():
                raise RuntimeError(f"refusing to snapshot symlink entry: {path}")
            yield path

        for filename in filenames:
            path = root_path / filename
            if path.is_symlink():
                raise RuntimeError(f"refusing to snapshot symlink entry: {path}")
            if not path.is_file():
                raise RuntimeError(f"refusing to snapshot non-regular entry: {path}")
            yield path


def _build_archive(source_dir: Path, archive_path: Path, *, zstd_level: int = 9) -> None:
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = archive_path.with_suffix(archive_path.suffix + ".tmp")
    if tmp_path.exists():
        tmp_path.unlink()

    _log(f"building archive {archive_path.name} from {source_dir}")
    compressor = zstd.ZstdCompressor(level=zstd_level, threads=-1)
    with tmp_path.open("wb") as raw:
        with compressor.stream_writer(raw) as compressed:
            with tarfile.open(fileobj=compressed, mode="w|") as tf:
                for path in _iter_snapshot_members(source_dir):
                    arcname = Path("data") if path == source_dir else Path("data") / path.relative_to(source_dir)
                    tf.add(path, arcname=str(arcname), recursive=False)
    tmp_path.replace(archive_path)


def _snapshot_group_date(path: Path) -> date | None:
    m = SNAPSHOT_DATE_RE.fullmatch(path.name)
    if m:
        return date.fromisoformat(m.group(1))
    m = SNAPSHOT_CHECKSUM_RE.fullmatch(path.name)
    if m:
        return date.fromisoformat(m.group(1))
    return None


def _local_snapshot_groups(root: Path) -> dict[date, dict[str, Path]]:
    groups: dict[date, dict[str, Path]] = {}
    for path in root.iterdir():
        snap_date = _snapshot_group_date(path)
        if snap_date is None:
            continue
        bucket = groups.setdefault(snap_date, {})
        if SNAPSHOT_DATE_RE.fullmatch(path.name):
            bucket["archive"] = path
        elif SNAPSHOT_CHECKSUM_RE.fullmatch(path.name):
            bucket["checksum"] = path
    return groups


def _prune_local_snapshots(root: Path, keep: int) -> list[Path]:
    groups = _local_snapshot_groups(root)
    ordered_dates = sorted(groups.keys(), reverse=True)
    removed: list[Path] = []
    for snap_date in ordered_dates[keep:]:
        for path in groups[snap_date].values():
            if path.exists():
                path.unlink()
                removed.append(path)
    return removed


def _remote_join(remote_root: str, filename: str) -> str:
    return remote_root.rstrip("/") + "/" + filename


def _check_rclone_remote(remote_root: str) -> None:
    if shutil.which("rclone") is None:
        raise RuntimeError("rclone is required but was not found on PATH")
    if ":" not in remote_root:
        raise RuntimeError(
            f"invalid remote root '{remote_root}'; expected something like 'gdrive:backups/data'"
        )
    remote_name = remote_root.split(":", 1)[0].strip()
    if not remote_name:
        raise RuntimeError(f"invalid remote root '{remote_root}'")

    result = subprocess.run(
        ["rclone", "listremotes"],
        check=True,
        capture_output=True,
        text=True,
    )
    remotes = {line.strip().rstrip(":") for line in result.stdout.splitlines() if line.strip()}
    if remote_name not in remotes:
        raise RuntimeError(
            f"rclone remote '{remote_name}' is not configured. Run `rclone config` first."
        )


def _run_rclone(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["rclone", *args], check=True, capture_output=True, text=True)


def _upload_snapshot(remote_root: str, snapshot: SnapshotPaths) -> None:
    _log(f"uploading to {remote_root}")
    _run_rclone("mkdir", remote_root)
    _run_rclone("copyto", str(snapshot.archive_path), _remote_join(remote_root, snapshot.archive_path.name))
    _run_rclone("copyto", str(snapshot.checksum_path), _remote_join(remote_root, snapshot.checksum_path.name))


def _remote_snapshot_groups(remote_root: str) -> dict[date, dict[str, str]]:
    result = _run_rclone("lsjson", remote_root)
    entries = json.loads(result.stdout or "[]")
    groups: dict[date, dict[str, str]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("Name") or entry.get("Path") or "").strip()
        snap_date = _snapshot_group_date(Path(name))
        if snap_date is None:
            continue
        bucket = groups.setdefault(snap_date, {})
        if SNAPSHOT_DATE_RE.fullmatch(name):
            bucket["archive"] = name
        elif SNAPSHOT_CHECKSUM_RE.fullmatch(name):
            bucket["checksum"] = name
    return groups


def _prune_remote_snapshots(remote_root: str, keep: int) -> list[str]:
    groups = _remote_snapshot_groups(remote_root)
    ordered_dates = sorted(groups.keys(), reverse=True)
    removed: list[str] = []
    for snap_date in ordered_dates[keep:]:
        for name in groups[snap_date].values():
            _run_rclone("deletefile", _remote_join(remote_root, name))
            removed.append(name)
    return removed


def _create_snapshot(
    *,
    source_dir: Path,
    output_dir: Path,
    snapshot_date: date,
    zstd_level: int,
) -> SnapshotPaths:
    snapshot = _snapshot_paths(output_dir, snapshot_date)
    _build_archive(source_dir, snapshot.archive_path, zstd_level=zstd_level)
    _write_checksum(snapshot.archive_path, snapshot.checksum_path)
    return snapshot


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--source-dir",
        type=Path,
        default=WORKSPACE_ROOT / "data",
        help="Directory to snapshot. Defaults to the shared workspace data tree.",
    )
    ap.add_argument(
        "--output-dir",
        type=Path,
        default=WORKSPACE_ROOT,
        help="Where to write the archive and checksum. Defaults to the workspace root.",
    )
    ap.add_argument(
        "--remote-root",
        type=str,
        default=os.environ.get("DATA_SNAPSHOT_REMOTE_ROOT", DEFAULT_REMOTE_ROOT),
        help=f"rclone destination root like {DEFAULT_REMOTE_ROOT}",
    )
    ap.add_argument(
        "--keep",
        type=int,
        default=DEFAULT_KEEP,
        help="Keep this many newest snapshot pairs locally and on Drive.",
    )
    ap.add_argument(
        "--date",
        type=str,
        default="",
        help="Override the snapshot date (YYYY-MM-DD). Defaults to today.",
    )
    ap.add_argument(
        "--zstd-level",
        type=int,
        default=9,
        help="zstd compression level for the tar.zst archive.",
    )
    ap.add_argument(
        "--no-upload",
        action="store_true",
        help="Build the local snapshot only and skip rclone upload/pruning.",
    )
    args = ap.parse_args()

    if args.keep < 1:
        raise SystemExit("ERROR: --keep must be >= 1")

    if not args.no_upload and not args.remote_root:
        raise SystemExit(
            "ERROR: --remote-root or DATA_SNAPSHOT_REMOTE_ROOT is required unless --no-upload is set"
        )

    if not args.no_upload:
        _check_rclone_remote(args.remote_root)

    snapshot_date = date.fromisoformat(args.date) if args.date else datetime.now().date()
    snapshot = _create_snapshot(
        source_dir=args.source_dir.resolve(),
        output_dir=args.output_dir.resolve(),
        snapshot_date=snapshot_date,
        zstd_level=args.zstd_level,
    )

    if not args.no_upload:
        _upload_snapshot(args.remote_root, snapshot)
        removed_remote = _prune_remote_snapshots(args.remote_root, args.keep)
        if removed_remote:
            _log(f"pruned remote snapshot files: {removed_remote}")

    removed_local = _prune_local_snapshots(args.output_dir.resolve(), args.keep)
    if removed_local:
        _log(f"pruned local snapshot files: {[str(path) for path in removed_local]}")

    _log(
        f"done archive={snapshot.archive_path.name} checksum={snapshot.checksum_path.name} "
        f"keep={args.keep} upload={'yes' if not args.no_upload else 'no'}"
    )


if __name__ == "__main__":
    main()
