"""
Legacy full-data snapshot restore from Google Drive.

NOTE: Most of data/ is now tracked directly in git. You do NOT need this script
on a normal clone — just `git pull` gets you the stock/features/FX/indices data.

The only data NOT in git is data/news/ (3.6 GB of cafef JSONL files).
To restore news only:
    python data_tools/fetch_news_archive.py

This script restores the old full data/ snapshot (file ID: 1zy0FHPMMgBPnPPwi9pcE5NXYteabus30).
Use only if you need a complete rebuild from scratch and git data is unavailable.
See notes/data_sources.md for the full data inventory.

Usage:
    python setup_data.py
"""

import subprocess
import sys
import zipfile
from pathlib import Path
GDRIVE_FILE_ID = "1zy0FHPMMgBPnPPwi9pcE5NXYteabus30"
ARCHIVE_NAME = "data_snapshot.zip"
EXTRACT_TO = Path("data")


def ensure_gdown():
    try:
        import gdown  # noqa: F401
    except ImportError:
        print("Installing gdown...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "gdown"])


def download(dest: Path):
    import gdown

    url = f"https://drive.google.com/uc?id={GDRIVE_FILE_ID}"
    print(f"Downloading snapshot from Google Drive -> {dest}")
    gdown.download(url, str(dest), quiet=False)


def extract(archive: Path, target: Path):
    target.mkdir(parents=True, exist_ok=True)
    print(f"Extracting {archive} -> {target}/")
    with zipfile.ZipFile(archive, "r") as zf:
        zf.extractall(target)
    print("Done.")


def main():
    archive = Path(ARCHIVE_NAME)

    ensure_gdown()

    if not archive.exists():
        download(archive)
    else:
        print(f"{archive} already exists, skipping download.")

    extract(archive, EXTRACT_TO)
    archive.unlink()
    print(f"Cleaned up {archive}. Data ready in {EXTRACT_TO}/")


if __name__ == "__main__":
    main()
