import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import duckdb
import structlog
import zstandard

logger = structlog.get_logger()


def _compute_fetch_id(source: str, endpoint: str, params: str, ingest_ts: datetime) -> str:
    raw = f"{source}|{endpoint}|{params}|{ingest_ts.isoformat()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _blob_path(base: Path, source: str, dt: date, fetch_id: str) -> Path:
    return base / source / str(dt.year) / f"{dt.month:02d}" / f"{dt.day:02d}" / f"{fetch_id}.zst"


class Vault:
    def __init__(self, base_path: str | Path) -> None:
        self._base = Path(base_path)
        self._manifest_path = self._base / "manifest.db"
        self._base.mkdir(parents=True, exist_ok=True)
        self._conn = duckdb.connect(str(self._manifest_path))
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS manifest ("
            "  fetch_id VARCHAR PRIMARY KEY,"
            "  source VARCHAR NOT NULL,"
            "  endpoint VARCHAR NOT NULL,"
            "  params VARCHAR NOT NULL,"
            "  ingest_ts TIMESTAMP NOT NULL,"
            "  content_hash VARCHAR NOT NULL,"
            "  byte_size BIGINT NOT NULL,"
            "  compressed_size BIGINT NOT NULL,"
            "  dt DATE NOT NULL"
            ")"
        )
        # Dedup: (source, endpoint, content_hash) — identical payloads
        # from the same API endpoint are stored once regardless of fetch time.

    def store(
        self,
        source: str,
        endpoint: str,
        params: str | dict[str, Any],
        data: bytes,
        ingest_ts: datetime | None = None,
    ) -> str:
        if isinstance(params, dict):
            params_str = json.dumps(params, sort_keys=True, separators=(",", ":"))
        else:
            params_str = params

        if ingest_ts is None:
            ingest_ts = datetime.now(UTC)

        content_hash = hashlib.sha256(data).hexdigest()

        existing = self._conn.execute(
            "SELECT fetch_id FROM manifest WHERE source = ? AND endpoint = ? AND content_hash = ?",
            (source, endpoint, content_hash),
        ).fetchone()
        if existing is not None:
            logger.debug("vault_duplicate_skip", source=source, endpoint=endpoint)
            return existing[0]

        fetch_id = _compute_fetch_id(source, endpoint, params_str, ingest_ts)
        cctx = zstandard.ZstdCompressor(level=3)
        compressed = cctx.compress(data)

        dt = ingest_ts.date()
        path = _blob_path(self._base, source, dt, fetch_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(".tmp")

        try:
            tmp_path.write_bytes(compressed)

            self._conn.execute(
                "INSERT INTO manifest (fetch_id, source, endpoint, params, ingest_ts,"
                " content_hash, byte_size, compressed_size, dt)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    fetch_id,
                    source,
                    endpoint,
                    params_str,
                    ingest_ts,
                    content_hash,
                    len(data),
                    len(compressed),
                    dt,
                ),
            )
            self._conn.commit()

            tmp_path.rename(path)
        except BaseException:
            tmp_path.unlink(missing_ok=True)
            raise

        logger.debug(
            "vault_store",
            source=source,
            fetch_id=fetch_id,
            bytes=len(data),
            compressed=len(compressed),
        )
        return fetch_id

    def read(self, fetch_id: str) -> bytes:
        row = self._conn.execute(
            "SELECT source, dt FROM manifest WHERE fetch_id = ?",
            (fetch_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"fetch_id not found in manifest: {fetch_id}")
        source, dt = row
        path = _blob_path(self._base, source, dt, fetch_id)
        dctx = zstandard.ZstdDecompressor()
        return dctx.decompress(path.read_bytes())

    def read_manifest(
        self,
        source: str | None = None,
        start: date | None = None,
        end: date | None = None,
    ) -> list[dict[str, Any]]:
        conditions: list[str] = []
        params: list[Any] = []
        if source is not None:
            conditions.append("source = ?")
            params.append(source)
        if start is not None:
            conditions.append("dt >= ?")
            params.append(start)
        if end is not None:
            conditions.append("dt <= ?")
            params.append(end)

        where = " AND ".join(conditions) if conditions else "1=1"
        rows = self._conn.execute(
            f"SELECT fetch_id, source, endpoint, params, ingest_ts,"
            f" content_hash, byte_size, compressed_size, dt"
            f" FROM manifest WHERE {where}"
            f" ORDER BY ingest_ts DESC",
            params,
        ).fetchall()

        return [
            {
                "fetch_id": r[0],
                "source": r[1],
                "endpoint": r[2],
                "params": r[3],
                "ingest_ts": r[4].isoformat(),
                "content_hash": r[5],
                "byte_size": r[6],
                "compressed_size": r[7],
                "date": str(r[8]),
            }
            for r in rows
        ]

    def dates_for_source(self, source: str) -> set[date]:
        rows = self._conn.execute(
            "SELECT DISTINCT dt FROM manifest WHERE source = ? ORDER BY dt",
            (source,),
        ).fetchall()
        return {r[0] for r in rows}

    def close(self) -> None:
        self._conn.execute("CHECKPOINT")
        self._conn.close()
