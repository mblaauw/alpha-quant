import hashlib
from datetime import date
from pathlib import Path

import zstandard


def _fetch_id(source: str, endpoint: str, params: str) -> str:
    raw = f"{source}|{endpoint}|{params}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def vault_path(base: Path, source: str, dt: date, endpoint: str, params: str) -> Path:
    fid = _fetch_id(source, endpoint, params)
    return base / source / str(dt.year) / f"{dt.month:02d}" / f"{dt.day:02d}" / f"{fid}.zst"


def write_blob(base: Path, source: str, dt: date, endpoint: str, params: str, data: bytes) -> str:
    path = vault_path(base, source, dt, endpoint, params)
    path.parent.mkdir(parents=True, exist_ok=True)
    cctx = zstandard.ZstdCompressor()
    compressed = cctx.compress(data)
    path.write_bytes(compressed)
    return path.name.replace(".zst", "")


def read_blob(path: Path) -> bytes:
    dctx = zstandard.ZstdDecompressor()
    return dctx.decompress(path.read_bytes())
