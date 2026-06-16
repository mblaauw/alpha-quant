from __future__ import annotations

import hashlib
from pathlib import Path


def compute_manifest_hash(fixture_path: str | Path) -> str:
    base = Path(fixture_path)
    if not base.exists():
        return ""

    files: list[Path] = sorted(base.rglob("*")) if base.is_dir() else [base]

    hasher = hashlib.sha256()
    for f in files:
        if not f.is_file():
            continue
        rel = str(f.relative_to(base.parent) if base.is_dir() else f.name)
        hasher.update(rel.encode())
        hasher.update(f.read_bytes())

    return hasher.hexdigest()


def verify_fixture_integrity(fixture_path: str | Path, expected_hash: str) -> bool:
    actual = compute_manifest_hash(fixture_path)
    if not expected_hash or not actual:
        return False
    return actual == expected_hash
