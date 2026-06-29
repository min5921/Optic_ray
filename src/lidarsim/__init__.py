"""Optic Ray simulator package."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("optic-ray-sim")
except PackageNotFoundError:  # pragma: no cover - source-tree fallback
    __version__ = "0.1.0"

__all__ = ["__version__"]
