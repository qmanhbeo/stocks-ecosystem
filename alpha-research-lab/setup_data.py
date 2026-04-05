"""
Restore the latest full-data snapshot from Google Drive.

NOTE: Most of data/ is now tracked directly in git. You do NOT need this script
on a normal clone — just `git pull` gets you the stock/features/FX/indices data.

The only data NOT in git is data/news/ (3.6 GB of cafef JSONL files).
To restore news only:
    python data_tools/fetch_news_archive.py

This script restores the latest full data/ snapshot pair from the configured
Google Drive backup remote:
- data-snapshot-YYYY-MM-DD-HHMMSS.tar.zst
- data-snapshot-YYYY-MM-DD-HHMMSS.tar.zst.sha256

The downloaded archive and checksum are kept locally after extraction so reruns
can reuse them without downloading again.

Use only if you need a complete rebuild from scratch and git data is unavailable.
See notes/data_sources.md for the full data inventory.

Usage:
    python setup_data.py
    python setup_data.py --snapshot-name data-snapshot-2026-04-05-143215.tar.zst
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tarfile
import shutil
from datetime import date, datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = SCRIPT_DIR.parent

DEFAULT_REMOTE_ROOT = "stocks-ecosystem-data-snapshots:project-backup/stock-data-backup/"
SNAPSHOT_STEM_RE = re.compile(r"^data-snapshot-(\d{4}-\d{2}-\d{2})(?:-(\d{6}))?$")
SNAPSHOT_ARCHIVE_RE = re.compile(r"^(data-snapshot-(\d{4}-\d{2}-\d{2})(?:-(\d{6}))?)\.tar\.zst$")
SNAPSHOT_CHECKSUM_RE = re.compile(r"^(data-snapshot-(\d{4}-\d{2}-\d{2})(?:-(\d{6}))?)\.tar\.zst\.sha256$")
EXTRACT_TO = WORKSPACE_ROOT


def ensure_runtime_dependencies():
    missing: list[str] = []
    try:
        import zstandard  # noqa: F401
    except ImportError:
        missing.append("zstandard")

    if missing:
        print(f"Installing {', '.join(missing)}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", *missing])


def parse_expected_sha256(checksum_path: Path) -> str:
    content = checksum_path.read_text(encoding="utf-8").strip()
    match = re.search(r"\b([0-9a-fA-F]{64})\b", content)
    if match is None:
        raise RuntimeError(f"Could not find a SHA256 digest in {checksum_path}")
    return match.group(1).lower()


def compute_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_checksum(archive: Path, checksum_path: Path):
    expected = parse_expected_sha256(checksum_path)
    actual = compute_sha256(archive)
    if actual != expected:
        raise RuntimeError(
            f"SHA256 mismatch for {archive.name}: expected {expected}, got {actual}"
        )
    print(f"Verified SHA256 for {archive.name}.")


def _is_within_directory(base: Path, target: Path) -> bool:
    try:
        target.relative_to(base)
        return True
    except ValueError:
        return False


def extract(archive: Path, target: Path):
    import zstandard as zstd

    target = target.resolve()
    target.mkdir(parents=True, exist_ok=True)
    print(f"Extracting {archive} -> {target}/")

    with archive.open("rb") as compressed:
        dctx = zstd.ZstdDecompressor()
        with dctx.stream_reader(compressed) as reader:
            with tarfile.open(fileobj=reader, mode="r|") as tf:
                for member in tf:
                    destination = (target / member.name).resolve()
                    if not _is_within_directory(target, destination):
                        raise RuntimeError(f"Refusing to extract outside {target}: {member.name}")
                    if member.islnk() or member.issym():
                        raise RuntimeError(f"Refusing to extract archive link entry: {member.name}")
                    tf.extract(member, path=target)
    print("Done.")


def _check_rclone_available() -> None:
    if shutil.which("rclone") is None:
        raise RuntimeError("rclone is required but was not found on PATH")


def _snapshot_sort_key_from_stem(stem: str) -> datetime | None:
    m = SNAPSHOT_STEM_RE.fullmatch(stem)
    if not m:
        return None
    day = date.fromisoformat(m.group(1))
    time_part = m.group(2)
    if time_part:
        return datetime.strptime(f"{m.group(1)}-{time_part}", "%Y-%m-%d-%H%M%S")
    return datetime.combine(day, datetime.min.time())


def _select_latest_remote_snapshot(remote_root: str) -> tuple[str, str]:
    result = subprocess.run(
        ["rclone", "lsjson", remote_root],
        check=True,
        capture_output=True,
        text=True,
    )
    entries = json.loads(result.stdout or "[]")
    groups: dict[str, dict[str, str | datetime]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("Name") or entry.get("Path") or "").strip()
        stem_match = SNAPSHOT_ARCHIVE_RE.fullmatch(name) or SNAPSHOT_CHECKSUM_RE.fullmatch(name)
        if not stem_match:
            continue
        stem = stem_match.group(1)
        sort_key = _snapshot_sort_key_from_stem(stem)
        if sort_key is None:
            continue
        bucket = groups.setdefault(stem, {"sort_key": sort_key})
        if SNAPSHOT_ARCHIVE_RE.fullmatch(name):
            bucket["archive"] = name
        elif SNAPSHOT_CHECKSUM_RE.fullmatch(name):
            bucket["checksum"] = name

    if not groups:
        raise RuntimeError(f"no snapshots found in remote root '{remote_root}'")

    ordered = sorted(groups.items(), key=lambda item: item[1]["sort_key"], reverse=True)
    for stem, bucket in ordered:
        archive = bucket.get("archive")
        checksum = bucket.get("checksum")
        if isinstance(archive, str) and isinstance(checksum, str):
            return archive, checksum
    raise RuntimeError(f"no complete archive/checksum pair found in remote root '{remote_root}'")


def _normalize_snapshot_name(snapshot_name: str) -> str:
    value = snapshot_name.strip()
    if not value:
        raise ValueError("snapshot name must not be empty")
    if value.endswith(".tar.zst.sha256"):
        value = value[: -len(".sha256")]
    elif not value.endswith(".tar.zst"):
        value = value + ".tar.zst"
    if SNAPSHOT_ARCHIVE_RE.fullmatch(value):
        return value
    raise ValueError(
        "snapshot name must look like data-snapshot-YYYY-MM-DD-HHMMSS.tar.zst "
        "or the same stem without .tar.zst"
    )


def _download_remote_file(remote_root: str, name: str, dest: Path) -> None:
    remote_path = remote_root.rstrip("/") + "/" + name
    print(f"Downloading {name} from Google Drive -> {dest}")
    subprocess.run(["rclone", "copyto", remote_path, str(dest)], check=True)


def main():
    ensure_runtime_dependencies()

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--snapshot-name",
        type=str,
        default="",
        help=(
            "Restore a specific snapshot run instead of the newest one. "
            "Accepts the archive name or stem, e.g. data-snapshot-2026-04-05-143215.tar.zst."
        ),
    )
    args = parser.parse_args()

    _check_rclone_available()
    remote_root = os.environ.get("DATA_SNAPSHOT_REMOTE_ROOT", DEFAULT_REMOTE_ROOT)

    if args.snapshot_name:
        archive_name = _normalize_snapshot_name(args.snapshot_name)
        checksum_name = f"{archive_name}.sha256"
    else:
        archive_name, checksum_name = _select_latest_remote_snapshot(remote_root)
    archive_path = WORKSPACE_ROOT / archive_name
    checksum_path = WORKSPACE_ROOT / checksum_name

    if not archive_path.exists():
        _download_remote_file(remote_root, archive_name, archive_path)
    else:
        print(f"{archive_path} already exists, skipping download.")

    if not checksum_path.exists():
        _download_remote_file(remote_root, checksum_name, checksum_path)
    else:
        print(f"{checksum_path} already exists, skipping download.")

    verify_checksum(archive_path, checksum_path)
    extract(archive_path, EXTRACT_TO)
    print(
        f"Data ready in {EXTRACT_TO}/. Kept {archive_path.name} and "
        f"{checksum_path.name} for reuse on future setup runs."
    )


if __name__ == "__main__":
    main()
