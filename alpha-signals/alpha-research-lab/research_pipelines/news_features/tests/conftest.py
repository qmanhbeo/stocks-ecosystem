from __future__ import annotations

import os
from pathlib import Path
import shutil
import tempfile
import uuid

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]
TEST_TEMP_ROOT = REPO_ROOT / "tests" / ".tmp" / "news_features"
TEST_TEMP_ROOT.mkdir(parents=True, exist_ok=True)
os.environ["TMPDIR"] = str(TEST_TEMP_ROOT)
os.environ["TEMP"] = str(TEST_TEMP_ROOT)
os.environ["TMP"] = str(TEST_TEMP_ROOT)
tempfile.tempdir = str(TEST_TEMP_ROOT)


@pytest.fixture
def tmp_path():
    path = TEST_TEMP_ROOT / f"pytest-{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)
