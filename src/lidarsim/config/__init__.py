"""Configuration loading과 validation public API."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .loader import ResolvedProject

__all__ = ["ResolvedProject", "load_project"]


def __getattr__(name: str) -> Any:
    """Asset/config helper 사이의 import cycle 없이 public API를 lazy load한다."""

    if name in __all__:
        from .loader import ResolvedProject, load_project

        exports = {
            "ResolvedProject": ResolvedProject,
            "load_project": load_project,
        }
        return exports[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
