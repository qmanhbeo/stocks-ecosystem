from __future__ import annotations

import hashlib
import tarfile
from datetime import date, datetime
from pathlib import Path

import zstandard as zstd

import backup_data_snapshot as backup


def _read_tar_names(archive_path: Path) -> list[str]:
    names: list[str] = []
    with archive_path.open("rb") as raw:
        dctx = zstd.ZstdDecompressor()
        with dctx.stream_reader(raw) as reader:
            with tarfile.open(fileobj=reader, mode="r|") as tf:
                for member in tf:
                    names.append(member.name)
    return names


def test_snapshot_name_uses_timestamp() -> None:
    assert backup._snapshot_name(datetime(2026, 4, 5, 14, 32, 15)) == "data-snapshot-2026-04-05-143215.tar.zst"


def test_create_snapshot_writes_valid_archive_and_checksum(tmp_path) -> None:
    source_dir = tmp_path / "data"
    (source_dir / "nested").mkdir(parents=True)
    (source_dir / "alpha.txt").write_text("alpha", encoding="utf-8")
    (source_dir / "nested" / "beta.txt").write_text("beta", encoding="utf-8")
    output_dir = tmp_path / "out"

    snapshot = backup._create_snapshot(
        source_dir=source_dir,
        output_dir=output_dir,
        snapshot_at=datetime(2026, 4, 5, 14, 32, 15),
        zstd_level=19,
    )

    assert snapshot.archive_path.name == "data-snapshot-2026-04-05-143215.tar.zst"
    assert snapshot.checksum_path.name == "data-snapshot-2026-04-05-143215.tar.zst.sha256"
    assert snapshot.archive_path.exists()
    assert snapshot.checksum_path.exists()

    names = _read_tar_names(snapshot.archive_path)
    assert "data" in names
    assert "data/alpha.txt" in names
    assert "data/nested" in names
    assert "data/nested/beta.txt" in names

    digest = hashlib.sha256(snapshot.archive_path.read_bytes()).hexdigest()
    assert snapshot.checksum_path.read_text(encoding="utf-8") == f"{digest}  {snapshot.archive_path.name}\n"


def test_prune_local_snapshots_keeps_newest_pairs(tmp_path) -> None:
    root = tmp_path
    for stamp in ["2026-04-01-090000", "2026-04-05-083000", "2026-04-05-151500"]:
        archive = root / f"data-snapshot-{stamp}.tar.zst"
        checksum = root / f"data-snapshot-{stamp}.tar.zst.sha256"
        archive.write_bytes(stamp.encode("utf-8"))
        checksum.write_text(f"{'a' * 64}  {archive.name}\n", encoding="utf-8")
    extra = root / "not-a-snapshot.txt"
    extra.write_text("keep me", encoding="utf-8")

    removed = backup._prune_local_snapshots(root, keep=2)

    assert sorted(p.name for p in removed) == [
        "data-snapshot-2026-04-01-090000.tar.zst",
        "data-snapshot-2026-04-01-090000.tar.zst.sha256",
    ]
    assert not (root / "data-snapshot-2026-04-01-090000.tar.zst").exists()
    assert not (root / "data-snapshot-2026-04-01-090000.tar.zst.sha256").exists()
    assert (root / "data-snapshot-2026-04-05-083000.tar.zst").exists()
    assert (root / "data-snapshot-2026-04-05-151500.tar.zst").exists()
    assert extra.exists()
