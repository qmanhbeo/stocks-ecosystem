#!/usr/bin/env python3
"""
Validate alpha-research-lab notes consistency.

Checks:
- findings/deadends chunk filenames are contiguous 30-wide ranges
- non-tail chunks contain exactly 30 blocks
- headings use strict format (## FXXX: / ## DXXX:)
- IDs are unique (and deadends are contiguous)
- findings.md / deadends.md manifests match actual chunk files
- findings_compact/deadends_compact only reference existing IDs
- anchored session links (findings-xxxxx-xxxxx.md#fNNN / deadends...#dNNN)
  point to the correct chunk file
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Sequence, Tuple


@dataclass
class ChunkAuditResult:
    files: List[Path]
    ids: List[int]
    id_to_locs: Dict[int, List[Tuple[str, int]]]
    issues: List[str]


def _collect_ids(prefix: str, files: Sequence[Path]) -> Tuple[List[int], Dict[int, List[Tuple[str, int]]]]:
    pattern = re.compile(rf"^## {prefix}(\d{{3}}):")
    ids: List[int] = []
    locs: Dict[int, List[Tuple[str, int]]] = {}
    for fp in files:
        for lineno, line in enumerate(fp.read_text(encoding="utf-8").splitlines(), start=1):
            m = pattern.match(line)
            if not m:
                continue
            val = int(m.group(1))
            ids.append(val)
            locs.setdefault(val, []).append((fp.name, lineno))
    return ids, locs


def _audit_chunks(notes_dir: Path, kind: str) -> ChunkAuditResult:
    files = sorted(notes_dir.glob(f"{kind}-*.md"))
    issues: List[str] = []
    if not files:
        return ChunkAuditResult(files=[], ids=[], id_to_locs={}, issues=[f"{kind}: no chunk files found"])

    filename_re = re.compile(rf"{kind}-(\d{{5}})-(\d{{5}})\.md$")
    ranges: List[Tuple[int, int, str]] = []
    for fp in files:
        m = filename_re.match(fp.name)
        if not m:
            issues.append(f"{kind}: bad filename format: {fp.name}")
            continue
        start, end = int(m.group(1)), int(m.group(2))
        ranges.append((start, end, fp.name))

    for i, (start, end, name) in enumerate(ranges):
        if end - start != 29:
            issues.append(f"{kind}: filename range must be width 30: {name}")
        if i > 0 and start != ranges[i - 1][1] + 1:
            issues.append(f"{kind}: filename gap/overlap: {ranges[i - 1][2]} -> {name}")

    prefix = "F" if kind == "findings" else "D"
    ids, id_to_locs = _collect_ids(prefix, files)

    malformed_a = re.compile(rf"^(?:{prefix}\d{{3}}:|## ## {prefix}\d{{3}}:)")
    malformed_b = re.compile(rf"^## {prefix}\d+:")
    proper = re.compile(rf"^## {prefix}\d{{3}}:")

    for fp in files:
        lines = fp.read_text(encoding="utf-8").splitlines()
        block_count = 0
        for lineno, line in enumerate(lines, start=1):
            if proper.match(line):
                block_count += 1
            if (malformed_a.match(line) or malformed_b.match(line)) and not proper.match(line):
                issues.append(f"{kind}: malformed heading at {fp.name}:{lineno}")
        if fp != files[-1] and block_count != 30:
            issues.append(f"{kind}: non-tail chunk must have 30 blocks: {fp.name} has {block_count}")
        if fp == files[-1] and not (1 <= block_count <= 30):
            issues.append(f"{kind}: tail chunk invalid block count: {fp.name} has {block_count}")

    if len(ids) != len(set(ids)):
        dups = [n for n, locs in id_to_locs.items() if len(locs) > 1]
        issues.append(f"{kind}: duplicate IDs: {dups[:20]}")

    if kind == "deadends" and ids:
        existing = set(ids)
        missing = [n for n in range(min(existing), max(existing) + 1) if n not in existing]
        if missing:
            issues.append(f"deadends: missing IDs in contiguous range: {missing[:20]}")

    return ChunkAuditResult(files=files, ids=ids, id_to_locs=id_to_locs, issues=issues)


def _audit_index_manifest(index_path: Path, chunk_kind: str, actual_files: Sequence[Path]) -> List[str]:
    issues: List[str] = []
    if not index_path.exists():
        return [f"missing index file: {index_path}"]
    text = index_path.read_text(encoding="utf-8")
    listed = re.findall(
        rf"\[([^\]]*{chunk_kind}-\d{{5}}-\d{{5}}\.md)\]\(\./[^\)]*\)",
        text,
    )
    expected = [fp.name for fp in actual_files]
    if listed != expected:
        issues.append(f"{index_path.name}: chunk manifest mismatch with actual {chunk_kind}-*.md files")
    return issues


def _audit_compact_refs(compact_path: Path, prefix: str, existing_ids: Sequence[int]) -> List[str]:
    issues: List[str] = []
    if not compact_path.exists():
        return [f"missing compact file: {compact_path}"]
    existing = set(existing_ids)
    text = compact_path.read_text(encoding="utf-8")
    for m in re.finditer(rf"\b{prefix}(\d{{1,3}})\b", text):
        val = int(m.group(1))
        if val not in existing:
            issues.append(f"{compact_path.name}: references missing {prefix}{val:03d}")
            break
    return issues


def _audit_session_anchors(notes_dir: Path, finding_map: Dict[int, str], deadend_map: Dict[int, str]) -> List[str]:
    issues: List[str] = []
    for fp in notes_dir.glob("session_*_log.md"):
        text = fp.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            for m in re.finditer(r"(findings-\d{5}-\d{5}\.md)#f(\d{3})", line):
                file_ref, fid = m.group(1), int(m.group(2))
                expected = finding_map.get(fid)
                if expected and expected != file_ref:
                    issues.append(
                        f"{fp.name}:{lineno}: findings anchor mismatch for F{fid:03d} "
                        f"(ref={file_ref}, expected={expected})"
                    )
            for m in re.finditer(r"(deadends-\d{5}-\d{5}\.md)#d(\d{3})", line, flags=re.IGNORECASE):
                file_ref, did = m.group(1), int(m.group(2))
                expected = deadend_map.get(did)
                if expected and expected != file_ref:
                    issues.append(
                        f"{fp.name}:{lineno}: deadends anchor mismatch for D{did:03d} "
                        f"(ref={file_ref}, expected={expected})"
                    )
    return issues


def run(notes_dir: Path) -> int:
    issues: List[str] = []

    findings = _audit_chunks(notes_dir, "findings")
    deadends = _audit_chunks(notes_dir, "deadends")
    issues.extend(findings.issues)
    issues.extend(deadends.issues)

    issues.extend(_audit_index_manifest(notes_dir / "findings.md", "findings", findings.files))
    issues.extend(_audit_index_manifest(notes_dir / "deadends.md", "deadends", deadends.files))

    issues.extend(_audit_compact_refs(notes_dir / "findings_compact.md", "F", findings.ids))
    issues.extend(_audit_compact_refs(notes_dir / "deadends_compact.md", "D", deadends.ids))

    finding_map = {k: v[0][0] for k, v in findings.id_to_locs.items()}
    deadend_map = {k: v[0][0] for k, v in deadends.id_to_locs.items()}
    issues.extend(_audit_session_anchors(notes_dir, finding_map, deadend_map))

    if issues:
        print(f"NOTES_AUDIT_FAILED ({len(issues)} issues)")
        for item in issues:
            print(f"- {item}")
        return 1

    print("NOTES_AUDIT_OK")
    print(
        f"findings: blocks={len(findings.ids)} unique={len(set(findings.ids))} "
        f"range=F{min(findings.ids):03d}-F{max(findings.ids):03d} chunks={len(findings.files)}"
    )
    print(
        f"deadends: blocks={len(deadends.ids)} unique={len(set(deadends.ids))} "
        f"range=D{min(deadends.ids):03d}-D{max(deadends.ids):03d} chunks={len(deadends.files)}"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate alpha-research-lab notes consistency")
    parser.add_argument(
        "--notes-dir",
        type=Path,
        default=Path("notes"),
        help="Path to notes directory (default: ./notes from alpha-research-lab root)",
    )
    args = parser.parse_args()
    return run(args.notes_dir)


if __name__ == "__main__":
    sys.exit(main())
