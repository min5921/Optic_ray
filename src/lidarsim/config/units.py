"""Unit-aware resolution of user-facing configuration quantities."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import pint

from lidarsim.errors import ConfigValidationError, Diagnostic


_TARGET_UNITS: tuple[tuple[str, str], ...] = (
    ("_rad", "radian"),
    ("_hz", "hertz"),
    ("_w", "watt"),
    ("_s", "second"),
    ("_m", "meter"),
)


def create_unit_registry() -> pint.UnitRegistry:
    """Create the project's isolated unit registry."""

    registry = pint.UnitRegistry(autoconvert_offset_to_baseunit=True)
    registry.formatter.default_format = "~P"
    return registry


_UNITS = create_unit_registry()


def target_unit_for_key(key: str) -> str | None:
    """Return the canonical unit implied by a configuration field suffix."""

    key_lower = key.lower()
    for suffix, unit in _TARGET_UNITS:
        if key_lower.endswith(suffix):
            return unit
    return None


def _path_text(path: Sequence[str | int]) -> str:
    text = ""
    for item in path:
        if isinstance(item, int):
            text += f"[{item}]"
        elif text:
            text += f".{item}"
        else:
            text = item
    return text


def _convert_scalar(value: Any, target_unit: str, path: Sequence[str | int], source: str) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return value

    try:
        quantity = _UNITS.Quantity(value)
        return float(quantity.to(target_unit).magnitude)
    except (pint.PintError, ValueError, TypeError) as exc:
        raise ConfigValidationError(
            [
                Diagnostic(
                    source=source,
                    path=_path_text(path),
                    message=f"Cannot convert {value!r} to {target_unit}: {exc}",
                    hint=f"Use a compatible quantity such as '20 mm' or a number already expressed in {target_unit}.",
                )
            ]
        ) from exc


def _resolve_value(
    value: Any,
    *,
    target_unit: str | None,
    path: tuple[str | int, ...],
    source: str,
) -> Any:
    if isinstance(value, Mapping):
        return {
            key: _resolve_value(
                child,
                target_unit=target_unit_for_key(str(key)),
                path=(*path, str(key)),
                source=source,
            )
            for key, child in value.items()
        }

    if isinstance(value, list):
        return [
            _resolve_value(
                child,
                target_unit=target_unit,
                path=(*path, index),
                source=source,
            )
            for index, child in enumerate(value)
        ]

    if target_unit is not None:
        return _convert_scalar(value, target_unit, path, source)
    return value


def resolve_quantities(data: Mapping[str, Any], *, source: str) -> dict[str, Any]:
    """Resolve unit-bearing strings into canonical SI/radian floats."""

    return _resolve_value(data, target_unit=None, path=(), source=source)
