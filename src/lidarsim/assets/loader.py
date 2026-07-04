"""STL sidecar와 project asset registry loading."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

import numpy as np
import yaml

from lidarsim.assets.measurement import MeasurementRecord, load_measurement
from lidarsim.assets.stl import MeshAudit, inspect_stl
from lidarsim.catalog.loader import Catalog
from lidarsim.config.immutable import deep_freeze, deep_thaw
from lidarsim.config.schema import SchemaStore
from lidarsim.config.units import resolve_quantities
from lidarsim.errors import ConfigFileError, ConfigValidationError, Diagnostic
from lidarsim.geometry.transform import RigidTransform, normalize_vector


@dataclass(frozen=True, slots=True)
class StlAsset:
    """검증된 STL sidecar, placement와 geometry audit."""

    identifier: str
    metadata_path: Path
    mesh_path: Path
    data: Mapping[str, Any]
    T_parent_from_mesh: RigidTransform
    audit: MeshAudit
    warnings: tuple[Diagnostic, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "asset_id": self.identifier,
            "metadata_path": str(self.metadata_path),
            "mesh_path": str(self.mesh_path),
            "metadata": deep_thaw(self.data),
            "transform": {
                "parent_frame": self.data["placement"]["parent_frame"],
                "translation_m": self.T_parent_from_mesh.translation_m.tolist(),
                "rotation_parent_from_mesh": self.T_parent_from_mesh.rotation.tolist(),
            },
            "audit": self.audit.to_dict(),
            "warnings": [warning.format() for warning in self.warnings],
        }


@dataclass(frozen=True, slots=True)
class AssetRegistry:
    """Project가 발견한 immutable STL·measurement asset lookup."""

    meshes: Mapping[str, StlAsset]
    measurements: Mapping[str, MeasurementRecord]
    warnings: tuple[Diagnostic, ...]

    @classmethod
    def empty(cls) -> "AssetRegistry":
        return cls(
            meshes=MappingProxyType({}),
            measurements=MappingProxyType({}),
            warnings=(),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "meshes": {identifier: asset.to_dict() for identifier, asset in self.meshes.items()},
            "measurements": {
                identifier: measurement.to_dict()
                for identifier, measurement in self.measurements.items()
            },
            "warnings": [warning.format() for warning in self.warnings],
        }

    def physical_hash_data(self) -> dict[str, Any]:
        """컴퓨터별 absolute path를 제외한 physical hash payload를 반환한다."""

        return {
            "meshes": {
                identifier: {
                    "metadata": asset.data,
                    "mesh_sha256": asset.audit.content_sha256,
                }
                for identifier, asset in self.meshes.items()
            },
            "measurements": {
                identifier: {
                    "metadata": measurement.data,
                    "data_sha256": measurement.data_sha256,
                }
                for identifier, measurement in self.measurements.items()
            },
        }


def _load_yaml_mapping(path: Path) -> dict[str, Any]:
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigFileError(path, f"STL metadata YAML을 읽을 수 없습니다: {exc}") from exc
    if not isinstance(document, dict):
        raise ConfigFileError(path, "STL metadata YAML root는 mapping이어야 합니다.")
    return document


def _material_diagnostics(
    resolved: Mapping[str, Any],
    *,
    catalog: Catalog | None,
    source: str,
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    material = resolved.get("material")
    if resolved["role"] == "target" and material is None:
        diagnostics.append(
            Diagnostic(
                source=source,
                path="material",
                message="Target STL에는 default material reference가 필요합니다.",
            )
        )
        return diagnostics
    if material is not None and catalog is not None:
        material_ref = str(material["default_material_ref"])
        if material_ref not in catalog:
            diagnostics.append(
                Diagnostic(
                    source=source,
                    path="material.default_material_ref",
                    message=f"알 수 없는 material catalog ID입니다: {material_ref!r}",
                )
            )
        elif catalog[material_ref].kind != "material":
            diagnostics.append(
                Diagnostic(
                    source=source,
                    path="material.default_material_ref",
                    message=f"Catalog ID {material_ref!r}는 material이 아닙니다.",
                )
            )
    return diagnostics


def _scanner_diagnostics(resolved: Mapping[str, Any], *, source: str) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    scanner = resolved.get("scanner")
    if resolved["role"] != "scanner_surface":
        return diagnostics
    if not isinstance(scanner, Mapping):
        return [
            Diagnostic(
                source=source,
                path="scanner",
                message="scanner_surface STL에는 pivot과 rotation axis metadata가 필요합니다.",
            )
        ]
    if scanner.get("pivot_local_m") is None:
        diagnostics.append(
            Diagnostic(
                source=source,
                path="scanner.pivot_local_m",
                message="scanner_surface STL에는 pivot_local_m이 필요합니다.",
            )
        )
    axis = scanner.get("rotation_axis_local")
    if axis is None:
        diagnostics.append(
            Diagnostic(
                source=source,
                path="scanner.rotation_axis_local",
                message="scanner_surface STL에는 rotation_axis_local이 필요합니다.",
            )
        )
    else:
        try:
            normalize_vector(axis, name="scanner.rotation_axis_local")
        except ValueError as exc:
            diagnostics.append(
                Diagnostic(
                    source=source,
                    path="scanner.rotation_axis_local",
                    message=str(exc),
                )
            )
    return diagnostics


def load_stl_asset(
    metadata_path: str | Path,
    schemas: SchemaStore,
    *,
    catalog: Catalog | None = None,
) -> StlAsset:
    """STL sidecar, referenced mesh와 semantic contract를 검증한다."""

    path = Path(metadata_path).resolve()
    raw = _load_yaml_mapping(path)
    schemas.validate(raw, "stl_metadata.schema.json", source=str(path))
    resolved = resolve_quantities(raw, source=str(path))
    diagnostics = _material_diagnostics(resolved, catalog=catalog, source=str(path))
    diagnostics.extend(_scanner_diagnostics(resolved, source=str(path)))
    warnings: list[Diagnostic] = []

    placement = resolved["placement"]
    try:
        transform = RigidTransform.from_quaternion_wxyz(
            placement["quaternion_wxyz"], placement["translation_m"]
        )
    except ValueError as exc:
        diagnostics.append(
            Diagnostic(source=str(path), path="placement", message=str(exc))
        )
        transform = RigidTransform.identity()
    if placement["parent_frame"] != "world":
        warnings.append(
            Diagnostic(
                source=str(path),
                path="placement.parent_frame",
                message=(
                    f"Parent frame {placement['parent_frame']!r}은 standalone inspection에서 "
                    "resolve되지 않습니다."
                ),
                severity="warning",
            )
        )

    mesh_path = (path.parent / str(resolved["mesh"]["file"])).resolve()
    if diagnostics:
        raise ConfigValidationError(diagnostics)
    audit = inspect_stl(mesh_path, unit_scale_m=float(resolved["mesh"]["unit_scale_m"]))

    if resolved["mesh"].get("binary_preferred", False) and audit.encoding != "binary":
        warnings.append(
            Diagnostic(
                source=str(path),
                path="mesh.binary_preferred",
                message="Binary STL이 권장되지만 ASCII STL을 읽었습니다.",
                severity="warning",
            )
        )
    validation = resolved["validation"]
    if validation["require_closed_mesh"] and not audit.is_closed:
        diagnostics.append(
            Diagnostic(
                source=str(path),
                path="validation.require_closed_mesh",
                message=(
                    "Closed mesh가 필요하지만 "
                    f"boundary edge {audit.boundary_edge_count}개와 "
                    f"non-manifold edge {audit.nonmanifold_edge_count}개를 찾았습니다."
                ),
            )
        )
    if audit.degenerate_triangle_count:
        severity = "error" if audit.degenerate_triangle_count == audit.triangle_count else "warning"
        item = Diagnostic(
            source=str(path),
            path="mesh.file",
            message=f"Degenerate triangle {audit.degenerate_triangle_count}개를 찾았습니다.",
            severity=severity,
        )
        if severity == "error":
            diagnostics.append(item)
        else:
            warnings.append(item)
    if audit.normal_mismatch_count:
        normal_policy = validation["normal_policy"]
        item = Diagnostic(
            source=str(path),
            path="validation.normal_policy",
            message=f"Geometry와 일치하지 않는 facet normal {audit.normal_mismatch_count}개를 찾았습니다.",
            hint=(
                "Phase 0.1은 normal mismatch를 기록만 하며 mesh data를 수정하지 않습니다. "
                "현재는 FreeCAD 등에서 normal을 재계산해 다시 export하세요."
                if normal_policy == "repair"
                else None
            ),
            severity="error" if normal_policy == "reject" else "warning",
        )
        if normal_policy == "reject":
            diagnostics.append(item)
        else:
            warnings.append(item)

    expected_bounds = validation.get("expected_bounds_m")
    if expected_bounds is not None and not np.allclose(
        audit.bounds_m,
        np.asarray(expected_bounds, dtype=np.float64),
        rtol=1e-6,
        atol=1e-9,
    ):
        diagnostics.append(
            Diagnostic(
                source=str(path),
                path="validation.expected_bounds_m",
                message=(
                    f"Scaled bounds {audit.bounds_m.tolist()}가 expected bounds "
                    f"{expected_bounds!r}와 일치하지 않습니다."
                ),
                hint="STL export unit, unit_scale_m과 orientation을 확인하세요.",
            )
        )

    source_info = resolved.get("source")
    if isinstance(source_info, Mapping) and source_info.get("file"):
        source_path = (path.parent / str(source_info["file"])).resolve()
        if not source_path.is_file():
            warnings.append(
                Diagnostic(
                    source=str(path),
                    path="source.file",
                    message=f"원본 CAD source file을 찾을 수 없습니다: {source_path}",
                    severity="warning",
                )
            )
    if diagnostics:
        raise ConfigValidationError(diagnostics)
    return StlAsset(
        identifier=str(resolved["asset_id"]),
        metadata_path=path,
        mesh_path=mesh_path,
        data=deep_freeze(resolved),
        T_parent_from_mesh=transform,
        audit=audit,
        warnings=tuple(warnings),
    )


def _active_yaml_files(paths: Iterable[Path], pattern: str) -> list[Path]:
    discovered: list[Path] = []
    for root in paths:
        discovered.extend(
            path
            for path in sorted(root.rglob(pattern))
            if ".example." not in path.name.lower()
        )
    return discovered


def load_asset_registry(
    asset_paths: Iterable[Path],
    measurement_paths: Iterable[Path],
    schemas: SchemaStore,
    catalog: Catalog,
) -> AssetRegistry:
    """Configured path에서 active sidecar를 찾아 validate하고 ID로 index한다."""

    meshes: dict[str, StlAsset] = {}
    measurements: dict[str, MeasurementRecord] = {}
    diagnostics: list[Diagnostic] = []
    warnings: list[Diagnostic] = []

    for path in _active_yaml_files(asset_paths, "*.stl.yaml"):
        try:
            asset = load_stl_asset(path, schemas, catalog=catalog)
        except ConfigValidationError as exc:
            diagnostics.extend(exc.diagnostics)
            continue
        except ConfigFileError as exc:
            diagnostics.append(Diagnostic(source=str(exc.path), path="", message=exc.message))
            continue
        if asset.identifier in meshes:
            diagnostics.append(
                Diagnostic(
                    source=str(path),
                    path="asset_id",
                    message=f"중복 STL asset ID입니다: {asset.identifier!r}",
                )
            )
            continue
        meshes[asset.identifier] = asset
        warnings.extend(asset.warnings)

    for path in _active_yaml_files(measurement_paths, "*.yaml"):
        try:
            measurement = load_measurement(path, schemas)
        except ConfigValidationError as exc:
            diagnostics.extend(exc.diagnostics)
            continue
        except ConfigFileError as exc:
            diagnostics.append(Diagnostic(source=str(exc.path), path="", message=exc.message))
            continue
        if measurement.identifier in measurements:
            diagnostics.append(
                Diagnostic(
                    source=str(path),
                    path="measurement_id",
                    message=f"중복 measurement ID입니다: {measurement.identifier!r}",
                )
            )
            continue
        measurements[measurement.identifier] = measurement
        warnings.extend(measurement.warnings)

    if diagnostics:
        raise ConfigValidationError(diagnostics)
    return AssetRegistry(
        meshes=MappingProxyType(meshes),
        measurements=MappingProxyType(measurements),
        warnings=tuple(warnings),
    )
