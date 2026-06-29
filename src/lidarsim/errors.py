"""User-facing diagnostics and configuration errors."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True, slots=True)
class Diagnostic:
    """One actionable validation diagnostic."""

    source: str
    path: str
    message: str
    hint: str | None = None
    severity: str = "error"

    def format(self) -> str:
        location = self.source
        if self.path:
            location = f"{location}:{self.path}"
        text = f"{self.severity.upper()} {location}\n  {self.message}"
        if self.hint:
            text += f"\n  Fix: {self.hint}"
        return text


class ConfigError(Exception):
    """Base class for configuration failures."""


class ConfigValidationError(ConfigError):
    """A collection of schema or semantic validation errors."""

    def __init__(self, diagnostics: Iterable[Diagnostic]):
        self.diagnostics = tuple(diagnostics)
        if not self.diagnostics:
            raise ValueError("ConfigValidationError requires at least one diagnostic")
        super().__init__("\n".join(item.format() for item in self.diagnostics))


class ConfigFileError(ConfigError):
    """A configuration file could not be read or parsed."""

    def __init__(self, path: Path, message: str):
        self.path = path
        self.message = message
        super().__init__(f"ERROR {path}\n  {message}")
