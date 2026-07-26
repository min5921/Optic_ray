from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest
import yaml

from lidarsim.assets import load_stl_asset, load_stl_geometry
from lidarsim.beam import BeamState
from lidarsim.config import load_project
from lidarsim.config.schema import SchemaStore
from lidarsim.scene import (
    RayMeshIntersection,
    TriangleMesh,
    intersect_ray_mesh,
    intersect_rectangle_plane,
    world_triangle_mesh_from_asset,
)


def _single_triangle_metadata(mesh_name: str) -> dict:
    half_sqrt = math.sqrt(0.5)
    return {
        "schema_version": 1,
        "asset_id": "test:placed_triangle",
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
            "quaternion_wxyz": [half_sqrt, 0.0, 0.0, half_sqrt],
        },
        "material": {"default_material_ref": "custom:diffuse_gray_020"},
        "validation": {
            "require_closed_mesh": False,
            "normal_policy": "validate",
            "expected_bounds_m": None,
        },
    }


def _beam(origin: tuple[float, float, float], direction: tuple[float, float, float]) -> BeamState:
    return BeamState(
        time_s=0.0,
        origin_m=origin,
        direction=direction,
        transverse_x_axis=(1.0, 0.0, 0.0),
        wavelength_m=1550.0e-9,
        power_w=0.01,
        waist_radius_x_m=0.001,
        waist_radius_y_m=0.001,
    )


def test_ascii_stl_retains_read_only_float64_geometry(tmp_path: Path) -> None:
    path = tmp_path / "triangle_ascii.stl"
    path.write_text(
        """solid triangle
facet normal 0 0 1
  outer loop
    vertex 0 0 0
    vertex 2 0 0
    vertex 0 3 0
  endloop
endfacet
endsolid triangle
""",
        encoding="ascii",
    )

    geometry = load_stl_geometry(path)

    assert geometry.encoding == "ascii"
    assert geometry.triangle_vertices.dtype == np.float64
    assert geometry.geometric_normals.dtype == np.float64
    np.testing.assert_allclose(
        geometry.triangle_vertices,
        [[[0.0, 0.0, 0.0], [2.0, 0.0, 0.0], [0.0, 3.0, 0.0]]],
    )
    np.testing.assert_allclose(geometry.geometric_normals, [[0.0, 0.0, 1.0]])
    assert geometry.valid_triangle_mask.tolist() == [True]
    assert not geometry.triangle_vertices.flags.writeable
    assert not geometry.geometric_normals.flags.writeable
    assert not geometry.valid_triangle_mask.flags.writeable


def test_binary_stl_retains_read_only_float64_geometry(
    tmp_path: Path, write_binary_stl
) -> None:
    triangles = [
        [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        [(0.0, 0.0, 1.0), (0.0, 1.0, 1.0), (1.0, 0.0, 1.0)],
    ]
    path = write_binary_stl(tmp_path / "two_triangles.stl", triangles)

    geometry = load_stl_geometry(path)

    assert geometry.encoding == "binary"
    np.testing.assert_allclose(geometry.triangle_vertices, triangles)
    np.testing.assert_allclose(
        geometry.geometric_normals,
        [[0.0, 0.0, 1.0], [0.0, 0.0, -1.0]],
    )
    assert not geometry.supplied_normals.flags.writeable
    assert not geometry.geometric_normals.flags.writeable


def test_sidecar_scale_rotation_and_translation_create_world_geometry(
    project_root: Path,
    tmp_path: Path,
    write_binary_stl,
) -> None:
    path = write_binary_stl(
        tmp_path / "placed.stl",
        [[(1.0, 0.0, 0.0), (2.0, 0.0, 0.0), (1.0, 1.0, 0.0)]],
    )
    metadata_path = tmp_path / "placed.stl.yaml"
    metadata_path.write_text(
        yaml.safe_dump(_single_triangle_metadata(path.name), sort_keys=False),
        encoding="utf-8",
    )
    project = load_project(project_root / "configs" / "project.yaml")
    schemas = SchemaStore.load(project_root / "schemas")

    asset = load_stl_asset(metadata_path, schemas, catalog=project.catalog)
    mesh = world_triangle_mesh_from_asset(asset)

    np.testing.assert_allclose(
        mesh.triangle_vertices_m,
        [[[1.0, 2.001, 3.0], [1.0, 2.002, 3.0], [0.999, 2.001, 3.0]]],
        atol=1.0e-12,
    )
    np.testing.assert_allclose(mesh.geometric_normals, [[0.0, 0.0, 1.0]])
    assert mesh.asset_id == "test:placed_triangle"
    assert not asset.geometry.triangle_vertices.flags.writeable
    assert not mesh.triangle_vertices_m.flags.writeable


def test_sidecar_rotation_updates_world_geometric_normal(
    project_root: Path,
    tmp_path: Path,
    write_binary_stl,
) -> None:
    path = write_binary_stl(
        tmp_path / "normal_rotation.stl",
        [[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)]],
    )
    metadata = _single_triangle_metadata(path.name)
    half_sqrt = math.sqrt(0.5)
    metadata["placement"]["translation_m"] = [0.0, 0.0, 0.0]
    metadata["placement"]["quaternion_wxyz"] = [half_sqrt, half_sqrt, 0.0, 0.0]
    metadata_path = tmp_path / "normal_rotation.stl.yaml"
    metadata_path.write_text(
        yaml.safe_dump(metadata, sort_keys=False),
        encoding="utf-8",
    )
    project = load_project(project_root / "configs" / "project.yaml")
    schemas = SchemaStore.load(project_root / "schemas")

    asset = load_stl_asset(metadata_path, schemas, catalog=project.catalog)
    mesh = world_triangle_mesh_from_asset(asset)

    np.testing.assert_allclose(
        mesh.geometric_normals,
        [[0.0, -1.0, 0.0]],
        atol=1.0e-12,
    )


def test_intersection_contract_defaults_barycentric_tolerance_for_legacy_callers() -> None:
    result = RayMeshIntersection(
        hit=False,
        status="no_hit",
        miss_reason="legacy_test",
        ray_origin_m=(0.0, 0.0, 0.0),
        ray_direction=(0.0, 0.0, 1.0),
        distance_m=None,
        point_m=None,
        triangle_index=None,
        barycentric=None,
        geometric_normal=None,
        front_face=None,
        face=None,
        tested_triangle_count=1,
        valid_triangle_count=1,
        parallel_epsilon=1.0e-10,
        minimum_distance_m=1.0e-9,
    )

    assert result.barycentric_epsilon == pytest.approx(1.0e-12)


def test_mesh_center_hit_reports_barycentric_normal_and_front_face() -> None:
    mesh = TriangleMesh(
        [[[-1.0, -1.0, 2.0], [1.0, -1.0, 2.0], [0.0, 1.0, 2.0]]]
    )

    result = intersect_ray_mesh((0.0, 0.0, 3.0), (0.0, 0.0, -2.0), mesh)

    assert result.hit
    assert result.status == "hit"
    assert result.distance_m == pytest.approx(1.0)
    assert result.triangle_index == 0
    np.testing.assert_allclose(result.point_m, [0.0, 0.0, 2.0])
    np.testing.assert_allclose(result.barycentric, [0.25, 0.25, 0.5])
    np.testing.assert_allclose(result.geometric_normal, [0.0, 0.0, 1.0])
    assert result.front_face is True
    assert result.face == "front"
    result_dict = result.to_dict()
    assert result_dict["barycentric_epsilon"] == pytest.approx(1.0e-12)
    assert (
        result_dict["face_convention"]
        == "front_when_dot_ray_direction_geometric_normal_is_negative"
    )


def test_mesh_back_face_preserves_winding_normal_and_reports_back() -> None:
    mesh = TriangleMesh(
        [[[-1.0, -1.0, 2.0], [1.0, -1.0, 2.0], [0.0, 1.0, 2.0]]]
    )

    result = intersect_ray_mesh((0.0, 0.0, 1.0), (0.0, 0.0, 1.0), mesh)

    assert result.hit
    np.testing.assert_allclose(result.geometric_normal, [0.0, 0.0, 1.0])
    assert result.front_face is False
    assert result.face == "back"


@pytest.mark.parametrize(
    ("origin", "direction", "expected_status", "expected_reason"),
    [
        (
            (0.0, 0.0, 3.0),
            (1.0, 0.0, 0.0),
            "parallel",
            "ray_parallel_to_all_non_degenerate_triangles",
        ),
        (
            (0.0, 0.0, 3.0),
            (0.0, 0.0, 1.0),
            "behind",
            "triangle_intersections_not_in_positive_ray_direction",
        ),
        (
            (4.0, 4.0, 3.0),
            (0.0, 0.0, -1.0),
            "no_hit",
            "ray_does_not_intersect_any_triangle_bounds",
        ),
    ],
)
def test_mesh_miss_status_is_explicit(
    origin: tuple[float, float, float],
    direction: tuple[float, float, float],
    expected_status: str,
    expected_reason: str,
) -> None:
    mesh = TriangleMesh(
        [[[-1.0, -1.0, 2.0], [1.0, -1.0, 2.0], [0.0, 1.0, 2.0]]]
    )

    result = intersect_ray_mesh(origin, direction, mesh)

    assert not result.hit
    assert result.status == expected_status
    assert result.miss_reason == expected_reason
    assert result.point_m is None
    assert result.triangle_index is None


def test_mesh_closest_hit_skips_farther_and_degenerate_triangles() -> None:
    mesh = TriangleMesh(
        [
            [[-1.0, -1.0, 2.0], [1.0, -1.0, 2.0], [0.0, 1.0, 2.0]],
            [[0.0, 0.0, 0.5], [0.0, 0.0, 0.5], [0.0, 0.0, 0.5]],
            [[-1.0, -1.0, 1.0], [1.0, -1.0, 1.0], [0.0, 1.0, 1.0]],
        ]
    )

    result = intersect_ray_mesh((0.0, 0.0, 0.0), (0.0, 0.0, 1.0), mesh)

    assert result.hit
    assert result.triangle_index == 2
    assert result.distance_m == pytest.approx(1.0)
    assert result.tested_triangle_count == 3
    assert result.valid_triangle_count == 2
    assert mesh.degenerate_triangle_count == 1


def test_all_degenerate_mesh_returns_safe_no_hit() -> None:
    mesh = TriangleMesh(
        [[[0.0, 0.0, 1.0], [0.0, 0.0, 1.0], [0.0, 0.0, 1.0]]]
    )

    result = intersect_ray_mesh((0.0, 0.0, 0.0), (0.0, 0.0, 1.0), mesh)

    assert result.status == "no_hit"
    assert result.miss_reason == "mesh_has_no_non_degenerate_triangles"
    assert result.valid_triangle_count == 0


def test_origin_intersection_is_self_hit_filtered_not_behind() -> None:
    mesh = TriangleMesh(
        [[[-1.0, -1.0, 0.0], [1.0, -1.0, 0.0], [0.0, 1.0, 0.0]]]
    )

    result = intersect_ray_mesh(
        (0.0, 0.0, 0.0),
        (0.0, 0.0, 1.0),
        mesh,
        minimum_distance_m=1.0e-12,
    )

    assert not result.hit
    assert result.status == "self_hit_filtered"
    assert result.miss_reason == "triangle_intersections_at_or_below_minimum_distance"


def test_shared_edge_hit_is_deterministic_and_crack_free() -> None:
    mesh = TriangleMesh(
        [
            [[-1.0, -1.0, 5.0], [-1.0, 1.0, 5.0], [1.0, 1.0, 5.0]],
            [[-1.0, -1.0, 5.0], [1.0, 1.0, 5.0], [1.0, -1.0, 5.0]],
        ]
    )

    result = intersect_ray_mesh((0.0, 0.0, 0.0), (0.0, 0.0, 1.0), mesh)

    assert result.hit
    assert result.triangle_index == 0
    assert result.distance_m == pytest.approx(5.0)
    np.testing.assert_allclose(result.point_m, [0.0, 0.0, 5.0])
    assert result.barycentric is not None
    assert np.all(result.barycentric >= 0.0)
    assert float(np.sum(result.barycentric)) == pytest.approx(1.0)


def test_two_triangle_plane_matches_analytical_rectangle_plane() -> None:
    vertices = np.array(
        [
            [[-1.0, -1.0, 5.0], [-1.0, 1.0, 5.0], [1.0, 1.0, 5.0]],
            [[-1.0, -1.0, 5.0], [1.0, 1.0, 5.0], [1.0, -1.0, 5.0]],
        ],
        dtype=np.float64,
    )
    mesh = TriangleMesh(vertices)
    beam = _beam((0.2, -0.1, 0.0), (0.0, 0.0, 1.0))

    mesh_hit = intersect_ray_mesh(beam.origin_m, beam.direction, mesh)
    rectangle_hit = intersect_rectangle_plane(
        beam,
        target_id="target",
        material_ref="custom:diffuse_gray_020",
        center_m=(0.0, 0.0, 5.0),
        normal=(0.0, 0.0, -1.0),
        width_axis=(1.0, 0.0, 0.0),
        width_m=2.0,
        height_m=2.0,
    )

    assert mesh_hit.hit and rectangle_hit.hit
    assert mesh_hit.distance_m == pytest.approx(
        rectangle_hit.distance_to_target_m,
        abs=1.0e-12,
    )
    np.testing.assert_allclose(mesh_hit.point_m, rectangle_hit.hit_center_m, atol=1.0e-12)
    np.testing.assert_allclose(
        mesh_hit.geometric_normal,
        rectangle_hit.target_normal,
        atol=1.0e-12,
    )
    assert mesh_hit.front_face == rectangle_hit.front_face
