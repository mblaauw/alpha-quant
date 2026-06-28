"""Shared FastAPI dependency helpers."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import Depends

_PROVIDERS: dict[type[Any], Callable[[], Any]] = {}


def service_provider(cls: type[Any]) -> Callable[[], Any]:
    if cls not in _PROVIDERS:

        def _provider() -> Any:
            return cls()

        _PROVIDERS[cls] = _provider
    return _PROVIDERS[cls]


def svc_depends(cls: type[Any]) -> Any:  # noqa: B008
    return Depends(service_provider(cls))
