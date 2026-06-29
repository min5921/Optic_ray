"""Immutable snapshots and canonical hashing helpers."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from types import MappingProxyType
from typing import Any


def deep_freeze(value: Any) -> Any:
    """Recursively freeze mappings and sequences."""

    if isinstance(value, Mapping):
        return MappingProxyType({str(key): deep_freeze(child) for key, child in value.items()})
    if isinstance(value, list | tuple):
        return tuple(deep_freeze(child) for child in value)
    return value


def deep_thaw(value: Any) -> Any:
    """Convert a frozen value into JSON/YAML-serializable containers."""

    if isinstance(value, Mapping):
        return {str(key): deep_thaw(child) for key, child in value.items()}
    if isinstance(value, tuple):
        return [deep_thaw(child) for child in value]
    return value


def canonical_hash(value: Any) -> str:
    """Return a stable SHA-256 hash of a resolved configuration value."""

    encoded = json.dumps(
        deep_thaw(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
