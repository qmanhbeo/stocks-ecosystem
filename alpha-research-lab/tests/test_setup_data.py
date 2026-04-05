from __future__ import annotations

import hashlib
import json

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


def test_select_latest_remote_snapshot_prefers_newest_complete_pair(monkeypatch):
    payload = json.dumps(
        [
            {"Name": "data-snapshot-2026-04-04-121500.tar.zst"},
            {"Name": "data-snapshot-2026-04-04-121500.tar.zst.sha256"},
            {"Name": "data-snapshot-2026-04-05-091500.tar.zst"},
            {"Name": "data-snapshot-2026-04-05-091500.tar.zst.sha256"},
            {"Name": "data-snapshot-2026-04-05-143215.tar.zst"},
            {"Name": "data-snapshot-2026-04-05-143215.tar.zst.sha256"},
        ]
    )

    def fake_run(cmd, check=True, capture_output=True, text=True):
        assert cmd == ["rclone", "lsjson", "stocks-ecosystem-data-snapshots:project-backup/stock-data-backup/"]
        return type("Result", (), {"stdout": payload})()

    monkeypatch.setattr(setup_data.subprocess, "run", fake_run)

    archive, checksum = setup_data._select_latest_remote_snapshot(
        "stocks-ecosystem-data-snapshots:project-backup/stock-data-backup/"
    )

    assert archive == "data-snapshot-2026-04-05-143215.tar.zst"
    assert checksum == "data-snapshot-2026-04-05-143215.tar.zst.sha256"


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("data-snapshot-2026-04-05-143215.tar.zst", "data-snapshot-2026-04-05-143215.tar.zst"),
        ("data-snapshot-2026-04-05-143215", "data-snapshot-2026-04-05-143215.tar.zst"),
        ("data-snapshot-2026-04-05-143215.tar.zst.sha256", "data-snapshot-2026-04-05-143215.tar.zst"),
    ],
)
def test_normalize_snapshot_name_accepts_archive_and_stem(raw, expected):
    assert setup_data._normalize_snapshot_name(raw) == expected


def test_normalize_snapshot_name_rejects_bad_value():
    with pytest.raises(ValueError, match="snapshot name must look like"):
        setup_data._normalize_snapshot_name("not-a-snapshot")
