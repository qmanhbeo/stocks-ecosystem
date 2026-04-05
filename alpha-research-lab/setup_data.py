"""
Legacy full-data snapshot restore from Google Drive.

NOTE: Most of data/ is now tracked directly in git. You do NOT need this script
on a normal clone — just `git pull` gets you the stock/features/FX/indices data.

The only data NOT in git is data/news/ (3.6 GB of cafef JSONL files).
To restore news only:
    python data_tools/fetch_news_archive.py

This script restores the old full data/ snapshot from the current backup pair:
- data-snapshot-2026-04-05.tar.zst
- data-snapshot-2026-04-05.tar.zst.sha256

The downloaded archive and checksum are kept locally after extraction so reruns
can reuse them without downloading again.

Use only if you need a complete rebuild from scratch and git data is unavailable.
See notes/data_sources.md for the full data inventory.

Usage:
    python setup_data.py
"""

from __future__ import annotations

import hashlib
import re
import subprocess
import sys
import tarfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = SCRIPT_DIR.parent

ARCHIVE_FILE_ID = "1xMHhPaUDPSvx91EMc4P_Br80qboc7fIg"
CHECKSUM_FILE_ID = "1g6_3acA7_0TRrzMcU8NWA8QhOaKHPx-P"
ARCHIVE_NAME = "data-snapshot-2026-04-05.tar.zst"
CHECKSUM_NAME = f"{ARCHIVE_NAME}.sha256"
ARCHIVE_PATH = WORKSPACE_ROOT / ARCHIVE_NAME
CHECKSUM_PATH = WORKSPACE_ROOT / CHECKSUM_NAME
EXTRACT_TO = WORKSPACE_ROOT


def ensure_runtime_dependencies():
    missing: list[str] = []
    try:
        import gdown  # noqa: F401
    except ImportError:
        missing.append("gdown")

    try:
        import zstandard  # noqa: F401
    except ImportError:
        missing.append("zstandard")

    if missing:
        print(f"Installing {', '.join(missing)}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", *missing])


def download(file_id: str, dest: Path, label: str):
    import gdown

    url = f"https://drive.google.com/uc?id={file_id}"
    print(f"Downloading {label} from Google Drive -> {dest}")
    gdown.download(url, str(dest), quiet=False)


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


def main():
    ensure_runtime_dependencies()

    if not ARCHIVE_PATH.exists():
        download(ARCHIVE_FILE_ID, ARCHIVE_PATH, "snapshot archive")
    else:
        print(f"{ARCHIVE_PATH} already exists, skipping download.")

    if not CHECKSUM_PATH.exists():
        download(CHECKSUM_FILE_ID, CHECKSUM_PATH, "snapshot checksum")
    else:
        print(f"{CHECKSUM_PATH} already exists, skipping download.")

    verify_checksum(ARCHIVE_PATH, CHECKSUM_PATH)
    extract(ARCHIVE_PATH, EXTRACT_TO)
    print(
        f"Data ready in {EXTRACT_TO}/. Kept {ARCHIVE_PATH.name} and "
        f"{CHECKSUM_PATH.name} for reuse on future setup runs."
    )


if __name__ == "__main__":
    main()
