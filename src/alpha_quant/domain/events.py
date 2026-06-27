"""Domain event type — simplified to a plain dict (legacy events removed)."""

from typing import Any

DomainEvent = dict[str, Any]
