from __future__ import annotations

import struct
from pathlib import Path

import numpy as np
import pytest
import yaml

from lidarsim.assets import inspect_stl, load_measurement, load_stl_asset
from lidarsim.config import load_project
from lidarsim.config.schema import SchemaStore
from lidarsim.errors import ConfigValidationError


TETRAHEDRON = [
    [(0, 0, 0), (0, 1, 0), (1, 0, 0)],
    [(0, 0, 0), (1, 0, 0), (0, 0, 1)],
    [(0, 0, 0), (0, 0, 1), (0, 1, 0)],
    [(1, 0, 0), (0, 1, 0), (0, 0, 1)],
]


def _schemas(project_root: Path) -> SchemaStore:
    return SchemaStore.load(project_root / "schemas")


def _mesh_metadata(mesh_name: str, **overrides) -> dict:
    metadata = {
        "schema_version": 1,
        "asset_id": "test:tetrahedron",
        "mesh": {
            "file": mesh_name,
            "format": "stl",
            "binary_preferred": True,
            "unit_scale_m": 0.001,
        },
        "role": "target",
        "placement": {
            "parent_frame": "world",
            "translation_m": [1.0, 2.0, 3.0],
            "quaternion_wxyz": [1.0, 0.0, 0.0, 0.0],
        },
        "material": {"default_material_ref": "custom:diffuse_gray_020"},
        "validation": {
            "require_closed_mesh": True,
            "normal_policy": "validate",
            "expected_bounds_m": [[0.0, 0.0, 0.0], [0.001, 0.001, 0.001]],
        },
    }
    metadata.update(overrides)
    return metadata


def _measurement_metadata(data_name: str, **overrides) -> dict:
    metadata = {
        "schema_version": 1,
        "measurement_id": "lab:test_profile",
        "measurement_type": "source_beam_profile",
        "dataset_role": "validation",
        "data_file": data_name,
        "conditions": {"wavelength": "1550 nm", "distance": "1 m"},
        "instrument": {"model": "test"},
        "uncertainty": {"type": "standard", "value": "1 percent"},
        "coordinate_frame": "measurement_frame",
        "units": {"x": "mm", "irradiance": "W/m^2"},
        "processing": [],
        "source_hash": None,
    }
    metadata.update(overrides)
    return metadata


def test_binary_stl_audit_reports_scaled_bounds_and_closed_topology(
    tmp_path: Path, write_binary_stl
) -> None:
    mesh_path = write_binary_stl(tmp_path / "tetra.stl", TETRAHEDRON)

    audit = inspect_stl(mesh_path, unit_scale_m=0.001)

    assert audit.encoding == "binary"
    assert audit.triangle_count == 4
    assert audit.unique_vertex_count == 4
    np.testing.assert_allclose(
        audit.bounds_m,
        [[0.0, 0.0, 0.0], [0.001, 0.001, 0.001]],
    )
    assert audit.is_closed
    assert audit.boundary_edge_count == 0
    assert audit.nonmanifold_edge_count == 0
    assert audit.degenerate_triangle_count == 0
    assert audit.normal_mismatch_count == 0
    assert len(audit.content_sha256) == 64


def test_ascii_stl_is_supported(tmp_path: Path) -> None:
    mesh_path = tmp_path / "triangle.stl"
    mesh_path.write_text(
        """solid triangle
facet normal 0 0 1
  outer loop
    vertex 0 0 0
    vertex 1 0 0
    vertex 0 1 0
  endloop
endfacet
endsolid triangle
""",
        encoding="ascii",
    )

    audit = inspect_stl(mesh_path, unit_scale_m=1.0)

    assert audit.encoding == "ascii"
    assert audit.triangle_count == 1
    assert not audit.is_closed
    assert audit.boundary_edge_count == 3


def test_stl_sidecar_validates_material_placement_and_expected_bounds(
    project_root: Path, tmp_path: Path, write_binary_stl
) -> None:
    mesh_path = write_binary_stl(tmp_path / "tetra.stl", TETRAHEDRON)
    metadata_path = tmp_path / "tetra.stl.yaml"
    metadata_path.write_text(
        yaml.safe_dump(_mesh_metadata(mesh_path.name), sort_keys=False),
        encoding="utf-8",
    )
    project = load_project(project_root / "configs" / "project.yaml")

    asset = load_stl_asset(metadata_path, _schemas(project_root), catalog=project.catalog)

    assert asset.identifier == "test:tetrahedron"
    assert asset.T_parent_from_mesh.translation_m == pytest.approx((1.0, 2.0, 3.0))
    assert asset.audit.is_closed
    assert asset.warnings == ()


def test_required_closed_mesh_rejects_open_triangle(
    project_root: Path, tmp_path: Path, write_binary_stl
) -> None:
    mesh_path = write_binary_stl(
        tmp_path / "open.stl",
        [[(0, 0, 0), (1, 0, 0), (0, 1, 0)]],
    )
    metadata = _mesh_metadata(mesh_path.name)
    metadata["validation"]["expected_bounds_m"] = None
    metadata_path = tmp_path / "open.stl.yaml"
    metadata_path.write_text(yaml.safe_dump(metadata, sort_keys=False), encoding="utf-8")
    project = load_project(project_root / "configs" / "project.yaml")

    with pytest.raises(ConfigValidationError, match="Closed mesh"):
        load_stl_asset(metadata_path, _schemas(project_root), catalog=project.catalog)


def test_scanner_surface_requires_pivot_and_axis(
    project_root: Path, tmp_path: Path, write_binary_stl
) -> None:
    mesh_path = write_binary_stl(tmp_path / "scanner.stl", TETRAHEDRON)
    metadata = _mesh_metadata(mesh_path.name, role="scanner_surface", scanner=None)
    metadata["validation"]["expected_bounds_m"] = None
    metadata_path = tmp_path / "scanner.stl.yaml"
    metadata_path.write_text(yaml.safe_dump(metadata, sort_keys=False), encoding="utf-8")
    project = load_project(project_root / "configs" / "project.yaml")

    with pytest.raises(ConfigValidationError, match="pivot"):
        load_stl_asset(metadata_path, _schemas(project_root), catalog=project.catalog)


def test_reject_normal_policy_blocks_mismatched_facet_normal(
    project_root: Path, tmp_path: Path, write_binary_stl
) -> None:
    mesh_path = write_binary_stl(tmp_path / "bad_normal.stl", TETRAHEDRON)
    payload = bytearray(mesh_path.read_bytes())
    struct.pack_into("<3f", payload, 84, 0.0, 0.0, 1.0)
    mesh_path.write_bytes(payload)
    metadata = _mesh_metadata(mesh_path.name)
    metadata["validation"]["normal_policy"] = "reject"
    metadata_path = tmp_path / "bad_normal.stl.yaml"
    metadata_path.write_text(yaml.safe_dump(metadata, sort_keys=False), encoding="utf-8")
    project = load_project(project_root / "configs" / "project.yaml")

    with pytest.raises(ConfigValidationError, match="facet normal"):
        load_stl_asset(metadata_path, _schemas(project_root), catalog=project.catalog)


def test_project_loader_discovers_active_stl_sidecars(
    copied_project: Path, write_binary_stl
) -> None:
    mesh_dir = copied_project.parent.parent / "assets" / "meshes"
    mesh_path = write_binary_stl(mesh_dir / "tetra.stl", TETRAHEDRON)
    metadata_path = mesh_dir / "tetra.stl.yaml"
    metadata_path.write_text(
        yaml.safe_dump(_mesh_metadata(mesh_path.name), sort_keys=False),
        encoding="utf-8",
    )

    project = load_project(copied_project)

    assert "test:tetrahedron" in project.assets.meshes
    assert project.assets.meshes["test:tetrahedron"].audit.is_closed


def test_project_loader_discovers_active_measurement_sidecars(copied_project: Path) -> None:
    measurement_dir = copied_project.parent.parent / "assets" / "measurements"
    data_path = measurement_dir / "profile.csv"
    data_path.write_text("x,irradiance\n0,1\n", encoding="utf-8")
    metadata_path = measurement_dir / "profile.measurement.yaml"
    metadata_path.write_text(
        yaml.safe_dump(_measurement_metadata(data_path.name), sort_keys=False),
        encoding="utf-8",
    )

    project = load_project(copied_project)

    assert "lab:test_profile" in project.assets.measurements
    assert len(project.assets.measurements["lab:test_profile"].data_sha256) == 64


def test_measurement_metadata_checks_data_and_units(project_root: Path, tmp_path: Path) -> None:
    data_path = tmp_path / "profile.csv"
    data_path.write_text("x,irradiance\n0,1\n", encoding="utf-8")
    metadata_path = tmp_path / "profile.measurement.yaml"
    metadata_path.write_text(
        yaml.safe_dump(_measurement_metadata(data_path.name), sort_keys=False),
        encoding="utf-8",
    )

    measurement = load_measurement(metadata_path, _schemas(project_root))

    assert measurement.identifier == "lab:test_profile"
    assert measurement.data_path == data_path.resolve()
    assert len(measurement.data_sha256) == 64
    assert measurement.warnings == ()


def test_measurement_numeric_condition_without_unit_is_rejected(
    project_root: Path, tmp_path: Path
) -> None:
    data_path = tmp_path / "profile.csv"
    data_path.write_text("x\n0\n", encoding="utf-8")
    metadata = _measurement_metadata(data_path.name, conditions={"wavelength": 1550})
    metadata_path = tmp_path / "profile.measurement.yaml"
    metadata_path.write_text(yaml.safe_dump(metadata, sort_keys=False), encoding="utf-8")

    with pytest.raises(ConfigValidationError, match="명시적인 unit"):
        load_measurement(metadata_path, _schemas(project_root))


def test_measurement_declared_hash_must_match(project_root: Path, tmp_path: Path) -> None:
    data_path = tmp_path / "profile.csv"
    data_path.write_text("x\n0\n", encoding="utf-8")
    metadata = _measurement_metadata(data_path.name, source_hash="0" * 64)
    metadata_path = tmp_path / "profile.measurement.yaml"
    metadata_path.write_text(yaml.safe_dump(metadata, sort_keys=False), encoding="utf-8")

    with pytest.raises(ConfigValidationError, match="일치하지 않습니다"):
        load_measurement(metadata_path, _schemas(project_root))
