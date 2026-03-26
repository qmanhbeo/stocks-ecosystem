"""
Restore the shared root data/news/ tree from the Google Drive archive.

Root data/news/ is excluded from git (3.6 GB, 3,734 JSONL files).
Everything else in data/ is tracked directly in git.

Usage:
    python data_tools/fetch_news_archive.py

What it does:
    1. Downloads data_news_archive.zip from Google Drive
    2. Extracts it into the workspace root data/news/
    3. Deletes the zip

If data/news/ already exists and is non-empty, the script skips the download
unless you pass --force.

See notes/data_sources.md for the full data inventory.
"""

import argparse
import subprocess
import sys
import zipfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
WORKSPACE_ROOT = REPO_ROOT.parent

# Google Drive file ID for the data/news/ archive
# Archive contains: data/news/cafef/raw/*.jsonl (3,734 files)
GDRIVE_FILE_ID = "1uzE57O1TTb7pMsQuTNtSiTKDgDt723-l"
ARCHIVE_NAME = WORKSPACE_ROOT / "data_news_archive.zip"
NEWS_DIR = WORKSPACE_ROOT / "data" / "news"


def ensure_gdown():
    try:
        import gdown  # noqa: F401
    except ImportError:
        print("Installing gdown...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "gdown"])


def download(dest: Path):
    import gdown
    url = f"https://drive.google.com/uc?id={GDRIVE_FILE_ID}"
    print(f"Downloading news archive from Google Drive -> {dest}")
    gdown.download(url, str(dest), quiet=False)


def extract(archive: Path, target: Path):
    target.mkdir(parents=True, exist_ok=True)
    print(f"Extracting {archive} -> {target.parent}/")
    with zipfile.ZipFile(archive, "r") as zf:
        zf.extractall(target.parent)
    print("Done.")


def main():
    parser = argparse.ArgumentParser(description="Restore root data/news/ from Google Drive")
    parser.add_argument("--force", action="store_true", help="Re-download even if data/news/ exists")
    args = parser.parse_args()

    # Check if already present
    existing = list(NEWS_DIR.rglob("*.jsonl")) if NEWS_DIR.exists() else []
    if existing and not args.force:
        print(f"data/news/ already present ({len(existing):,} JSONL files). Use --force to re-download.")
        return

    ensure_gdown()

    archive = ARCHIVE_NAME
    if not archive.exists():
        download(archive)
    else:
        print(f"{archive} already exists, skipping download.")

    extract(archive, NEWS_DIR)
    archive.unlink()
    print(f"Cleaned up {archive}. News data ready in {NEWS_DIR}/")

    # Verify
    restored = list(NEWS_DIR.rglob("*.jsonl"))
    print(f"Verified: {len(restored):,} JSONL files in data/news/")


if __name__ == "__main__":
    main()
