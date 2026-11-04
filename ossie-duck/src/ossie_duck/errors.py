"""Error types shared across modules."""

from __future__ import annotations

from .model import OssieError


class QueryError(OssieError):
    """A semantic query could not be resolved or compiled."""
