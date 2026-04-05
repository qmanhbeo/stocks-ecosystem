from __future__ import annotations

import hashlib

import pytest

import setup_data


def test_parse_expected_sha256_accepts_standard_checksum_line(tmp_path):
    checksum = "a" * 64
    checksum_path = tmp_path / "snapshot.sha256"
    checksum_path.write_text(
        f"{checksum}  data-snapshot-2026-04-05.tar.zst\n",
        encoding="utf-8",
    )

    assert setup_data.parse_expected_sha256(checksum_path) == checksum


def test_verify_checksum_accepts_matching_archive(tmp_path):
    archive_path = tmp_path / "snapshot.tar.zst"
    archive_path.write_bytes(b"archive-bytes")
    checksum_path = tmp_path / "snapshot.tar.zst.sha256"
    digest = hashlib.sha256(b"archive-bytes").hexdigest()
    checksum_path.write_text(f"{digest}  {archive_path.name}\n", encoding="utf-8")

    setup_data.verify_checksum(archive_path, checksum_path)


def test_verify_checksum_rejects_mismatch(tmp_path):
    archive_path = tmp_path / "snapshot.tar.zst"
    archive_path.write_bytes(b"archive-bytes")
    checksum_path = tmp_path / "snapshot.tar.zst.sha256"
    checksum_path.write_text(f"{'b' * 64}  {archive_path.name}\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="SHA256 mismatch"):
        setup_data.verify_checksum(archive_path, checksum_path)
