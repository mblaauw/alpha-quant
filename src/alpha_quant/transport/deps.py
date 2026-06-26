"""Shared FastAPI dependency helpers."""

from __future__ import annotations

from fastapi import Depends


def svc_depends(cls: type) -> type:  # noqa: B008
    return Depends(lambda: cls())
