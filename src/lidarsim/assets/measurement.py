"""Measurement metadata, referenced data와 traceability validation."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pint
import yaml

from lidarsim.config.immutable import deep_freeze, deep_thaw
from lidarsim.config.schema import SchemaStore
from lidarsim.config.units import create_unit_registry
from lidarsim.errors import ConfigFileError, ConfigValidationError, Diagnostic


_NUMERIC_PREFIX = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?")
_UNITS = create_unit_registry()


@dataclass(frozen=True, slots=True)
class MeasurementRecord:
    """검증된 measurement metadata와 exact data content hash."""

    identifier: str
    metadata_path: Path
    data_path: Path
    data_sha256: str
    data: Mapping[str, Any]
    warnings: tuple[Diagnostic, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "measurement_id": self.identifier,
            "metadata_path": str(self.metadata_path),
            "data_path": str(self.data_path),
            "data_sha256": self.data_sha256,
            "metadata": deep_thaw(self.data),
            "warnings": [warning.format() for warning in self.warnings],
        }


def _load_yaml_mapping(path: Path) -> dict[str, Any]:
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigFileError(path, f"Measurement YAML을 읽을 수 없습니다: {exc}") from exc
    if not isinstance(document, dict):
        raise ConfigFileError(path, "Measurement YAML root는 mapping이어야 합니다.")
    return document


def _validate_condition_quantities(
    value: Any,
    *,
    source: str,
    path: str,
    diagnostics: list[Diagnostic],
) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            _validate_condition_quantities(
                child,
                source=source,
                path=child_path,
                diagnostics=diagnostics,
            )
        return
    if isinstance(value, list | tuple):
        for index, child in enumerate(value):
            _validate_condition_quantities(
                child,
                source=source,
                path=f"{path}[{index}]",
                diagnostics=diagnostics,
            )
        return
    if isinstance(value, bool) or value is None:
        return
    if isinstance(value, (int, float)):
        diagnostics.append(
            Diagnostic(
                source=source,
                path=path,
                message="Measurement condition의 숫자에는 명시적인 unit이 필요합니다.",
                hint="예: '1550 nm', '23 degC', '1 m'",
            )
        )
        return
    if isinstance(value, str) and _NUMERIC_PREFIX.match(value.strip()):
        try:
            quantity = _UNITS.Quantity(value)
        except (pint.PintError, ValueError, TypeError) as exc:
            diagnostics.append(
                Diagnostic(
                    source=source,
                    path=path,
                    message=f"Measurement condition unit을 해석할 수 없습니다: {value!r}: {exc}",
                )
            )
            return
        if quantity.dimensionless:
            diagnostics.append(
                Diagnostic(
                    source=source,
                    path=path,
                    message=f"Measurement condition {value!r}에 physical unit이 없습니다.",
                )
            )


def load_measurement(metadata_path: str | Path, schemas: SchemaStore) -> MeasurementRecord:
    """Measurement sidecar와 referenced data file을 검증하고 freeze한다."""

    path = Path(metadata_path).resolve()
    raw = _load_yaml_mapping(path)
    schemas.validate(raw, "measurement.schema.json", source=str(path))
    diagnostics: list[Diagnostic] = []
    warnings: list[Diagnostic] = []
    _validate_condition_quantities(
        raw["conditions"],
        source=str(path),
        path="conditions",
        diagnostics=diagnostics,
    )
    for name, unit_expression in raw["units"].items():
        try:
            _UNITS.Unit(unit_expression)
        except (pint.PintError, ValueError, TypeError) as exc:
            diagnostics.append(
                Diagnostic(
                    source=str(path),
                    path=f"units.{name}",
                    message=f"Unit expression을 해석할 수 없습니다: {unit_expression!r}: {exc}",
                )
            )
    if not raw["units"]:
        warnings.append(
            Diagnostic(
                source=str(path),
                path="units",
                message="Data column unit mapping이 비어 있습니다.",
                hint="숫자 column이 있다면 column name과 unit을 명시하세요.",
                severity="warning",
            )
        )

    data_path = (path.parent / str(raw["data_file"])).resolve()
    try:
        payload = data_path.read_bytes()
    except OSError as exc:
        diagnostics.append(
            Diagnostic(
                source=str(path),
                path="data_file",
                message=f"Referenced measurement data를 읽을 수 없습니다: {data_path}: {exc}",
            )
        )
        payload = b""
    data_hash = hashlib.sha256(payload).hexdigest()
    declared_hash = raw.get("source_hash")
    if declared_hash and str(declared_hash).lower() != data_hash:
        diagnostics.append(
            Diagnostic(
                source=str(path),
                path="source_hash",
                message=f"Declared hash가 data file과 일치하지 않습니다: actual={data_hash}",
            )
        )
    if diagnostics:
        raise ConfigValidationError(diagnostics)
    return MeasurementRecord(
        identifier=str(raw["measurement_id"]),
        metadata_path=path,
        data_path=data_path,
        data_sha256=data_hash,
        data=deep_freeze(raw),
        warnings=tuple(warnings),
    )
