"""Component and material catalog loading."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

import yaml

from lidarsim.config.immutable import deep_freeze
from lidarsim.config.physical import validate_catalog_record_physics
from lidarsim.config.schema import SchemaStore
from lidarsim.config.units import resolve_quantities
from lidarsim.errors import ConfigFileError, ConfigValidationError, Diagnostic


@dataclass(frozen=True, slots=True)
class CatalogEntry:
    """One resolved catalog record."""

    identifier: str
    kind: str
    source_path: Path
    data: Mapping[str, Any]

    @property
    def ports(self) -> tuple[Mapping[str, Any], ...]:
        value = self.data.get("ports", ())
        return tuple(value) if isinstance(value, tuple | list) else ()


@dataclass(frozen=True, slots=True)
class Catalog:
    """Immutable component and material lookup."""

    entries: Mapping[str, CatalogEntry]

    def __contains__(self, identifier: str) -> bool:
        return identifier in self.entries

    def __getitem__(self, identifier: str) -> CatalogEntry:
        return self.entries[identifier]

    def count(self, kind: str) -> int:
        return sum(entry.kind == kind for entry in self.entries.values())


def _load_yaml_mapping(path: Path) -> dict[str, Any]:
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigFileError(path, f"Cannot read YAML: {exc}") from exc
    if not isinstance(document, dict):
        raise ConfigFileError(path, "Catalog YAML must contain a mapping at the document root.")
    return document


def load_catalog(paths: Iterable[Path], schemas: SchemaStore) -> Catalog:
    """Load, validate, resolve, and freeze catalog records."""

    entries: dict[str, CatalogEntry] = {}
    diagnostics: list[Diagnostic] = []
    discovered: list[Path] = []

    for root in paths:
        if not root.is_dir():
            diagnostics.append(
                Diagnostic(
                    source=str(root),
                    path="",
                    message="Catalog path does not exist or is not a directory.",
                    hint="Correct catalog_paths in configs/project.yaml.",
                )
            )
            continue
        discovered.extend(sorted(root.rglob("*.yaml")))

    if diagnostics:
        raise ConfigValidationError(diagnostics)

    for path in discovered:
        raw = _load_yaml_mapping(path)
        if "component_type" in raw:
            schema_name = "component.schema.json"
            kind = "component"
        elif "material_type" in raw:
            schema_name = "material.schema.json"
            kind = "material"
        else:
            diagnostics.append(
                Diagnostic(
                    source=str(path),
                    path="",
                    message="Catalog record must declare component_type or material_type.",
                )
            )
            continue

        try:
            schemas.validate(raw, schema_name, source=str(path))
            resolved = resolve_quantities(raw, source=str(path))
            validate_catalog_record_physics(resolved, source=str(path), kind=kind)
        except ConfigValidationError as exc:
            diagnostics.extend(exc.diagnostics)
            continue

        identifier = str(resolved["id"])
        if identifier in entries:
            diagnostics.append(
                Diagnostic(
                    source=str(path),
                    path="id",
                    message=f"Duplicate catalog ID {identifier!r}; first declared in {entries[identifier].source_path}.",
                    hint="Catalog IDs must be globally unique across all configured catalog paths.",
                )
            )
            continue

        entries[identifier] = CatalogEntry(
            identifier=identifier,
            kind=kind,
            source_path=path.resolve(),
            data=deep_freeze(resolved),
        )

    if diagnostics:
        raise ConfigValidationError(diagnostics)
    return Catalog(entries=MappingProxyType(entries))
