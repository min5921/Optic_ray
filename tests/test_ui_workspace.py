from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import yaml

from lidarsim.config import load_project
from lidarsim.config.schema import SchemaStore
from lidarsim.errors import ConfigValidationError
from lidarsim.results import build_phase2_optical_train_report
from lidarsim.ui import (
    SimulationParameterEdits,
    build_viewport_scene,
    create_simulation_variant,
)
from lidarsim.ui.assembly.plotly_viewport import _footprint_coordinates
from lidarsim.ui.assembly.plotly_viewport import build_interactive_viewport_figure
from lidarsim.visualization import render_viewport_scene
from lidarsim.visualization.workspace import _draw_rays, _footprint_polygon


def _reciprocal_hit(
    plane_id: str,
    point_m: list[float],
    expected_center_m: list[float],
    *,
    aperture_status: str = "pass",
) -> dict[str, object]:
    return {
        "plane_id": plane_id,
        "frame": {"origin_m": expected_center_m},
        "intersection": {"hit": True, "point_m": point_m},
        "lateral_residual_m": float(np.linalg.norm(np.asarray(point_m) - expected_center_m)),
        "aperture_status": aperture_status,
    }


def _report_with_reciprocal_path(
    project: object,
    *,
    path: dict[str, object],
) -> dict[str, object]:
    payload = build_phase2_optical_train_report(project).to_dict()  # type: ignore[arg-type]
    payload["reciprocal_return"] = {
        "model": "reciprocal_shared_optical_train",
        "status": path["status"],
        "architecture": "reciprocal_single_mode_fiber",
        "return_path": {
            "scanner_element_id": "scan_mirror",
            "collimator_element_id": "collimator",
            "fiber_element_id": "source",
        },
        "target_id": "target_plane",
        "path": path,
        "power_status": "not_evaluated",
        "fiber_coupling_status": "not_evaluated",
        "detector_status": "not_evaluated",
        "assumptions": ["center ray only"],
        "warnings": ["R1 geometry-only"],
    }
    return payload


def _exact_reciprocal_path() -> dict[str, object]:
    return {
        "model": "reciprocal_center_ray_geometry",
        "status": "pass",
        "terminated": False,
        "termination_reason": None,
        "termination_point_m": [0.0, 0.0, -0.10],
        "target_hit_m": [10.0, 0.0, 0.0],
        "mirror_hit": _reciprocal_hit("return_mirror", [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]),
        "collimator_hit": _reciprocal_hit(
            "return_collimator",
            [0.0, 0.0, -0.08],
            [0.0, 0.0, -0.08],
        ),
        "fiber_hit": _reciprocal_hit(
            "fiber_reference",
            [0.0, 0.0, -0.10],
            [0.0, 0.0, -0.10],
        ),
        "closure": {
            "mirror_angular_residual_rad": 0.0,
            "collimator_angular_residual_rad": 0.0,
            "fiber_angular_residual_rad": 0.0,
        },
        "warnings": [],
    }


def _attach_r2_return_power(
    report: dict[str, object],
    *,
    mirror_power_w: float = 1.8e-9,
    after_mirror_power_w: float = 1.6e-9,
    fiber_plane_power_w: float = 1.5e-9,
) -> None:
    reciprocal = report["reciprocal_return"]
    assert isinstance(reciprocal, dict)
    reciprocal["power_status"] = "pass" if fiber_plane_power_w > 0.0 else "zero_power"
    reciprocal["return_power"] = {
        "status": reciprocal["power_status"],
        "power_at_return_mirror_w": mirror_power_w,
        "power_after_return_mirror_w": after_mirror_power_w,
        "power_at_fiber_plane_w": fiber_plane_power_w,
        "warnings": ["R2 analytical scalar power"],
    }


def _attach_r3_fiber_coupling(
    report: dict[str, object],
    *,
    efficiency: float = 0.64,
    coupled_power_w: float = 9.6e-10,
) -> None:
    reciprocal = report["reciprocal_return"]
    assert isinstance(reciprocal, dict)
    reciprocal["fiber_coupling_status"] = "pass"
    reciprocal["fiber_coupling"] = {
        "model": "gaussian_alignment_proxy",
        "status": "pass",
        "available_power_at_fiber_plane_w": 1.5e-9,
        "fiber_coupling_efficiency": efficiency,
        "power_coupled_into_fiber_w": coupled_power_w,
        "fiber_plane_to_coupled_mode_loss_db": 1.938200260161128,
        "target_to_fiber_coupled_link_loss_db": 70.17728766960431,
        "coherent_field_status": "not_provided",
        "coupled_field_amplitude_sqrt_w": None,
        "field_usable_for_coherent_propagation": False,
        "warnings": ["R3 diffuse-return Gaussian upper-bound/reference"],
    }


def _attach_r4_detector_boundary(
    report: dict[str, object],
    *,
    detector_power_w: float = 4.8e-10,
) -> None:
    reciprocal = report["reciprocal_return"]
    assert isinstance(reciprocal, dict)
    reciprocal["detector_status"] = "pass" if detector_power_w > 0.0 else "blocked"
    reciprocal["detector_boundary"] = {
        "model": "passive_duplexer_detector_input_boundary",
        "model_scope": "analytical_optical_boundary_only",
        "hardware_readiness": "uncalibrated",
        "status": reciprocal["detector_status"],
        "duplexer_type": "fiber_coupler",
        "detector_model": "none",
        "return_power_transmission": 0.5,
        "power_coupled_into_fiber_w": 9.6e-10,
        "power_at_detector_input_w": detector_power_w,
        "fiber_coupled_to_detector_input_link_loss_db": 3.010299956639812,
        "target_to_detector_input_link_loss_db": 73.18758762624412,
        "source_to_detector_input_round_trip_link_loss_db": 73.18758762624412,
        "detector_response_status": "not_evaluated",
        "field_at_fiber_output_sqrt_w": None,
        "field_at_detector_input_sqrt_w": None,
        "coherent_field_status": "not_provided",
        "field_usable_for_coherent_propagation": False,
        "warnings": ["R4 analytical detector optical boundary only"],
    }


def test_viewport_scene_contains_optical_bench_objects(project_root: Path) -> None:
    project = load_project(project_root / "configs" / "project.yaml")

    scene = build_viewport_scene(project)

    component_ids = {component.element_id for component in scene.components}
    assert {"source", "collimator", "scan_mirror", "target_plane", "receiver"} <= component_ids
    assert len(scene.ports) >= 3
    assert any(guide.guide_type == "component_local_frame" for guide in scene.guides)
    assert any(guide.guide_type == "port_axis" for guide in scene.guides)
    assert any(guide.guide_type == "mirror_normal" for guide in scene.guides)
    assert any(guide.guide_type == "target_plane_edge" for guide in scene.guides)
    assert any(guide.guide_type == "receiver_fov" for guide in scene.guides)
    assert any(ray.status == "target_hit" for ray in scene.rays)
    assert len(scene.footprints) == 1


def test_baseline_r2_power_and_r3_coupling_use_distinct_viewport_contracts(
    project_root: Path,
) -> None:
    project = load_project(project_root / "configs" / "project.yaml")
    report = build_phase2_optical_train_report(project)

    scene = build_viewport_scene(project, report=report)
    return_rays = [ray for ray in scene.rays if ray.propagation_role == "return"]

    assert [ray.plane_power_name for ray in return_rays] == [
        "power_at_return_mirror_w",
        "power_after_return_mirror_w",
        "power_at_fiber_plane_w",
    ]
    assert [ray.power_w for ray in return_rays] == pytest.approx(
        [
            report.reciprocal_return["return_power"]["power_at_return_mirror_w"],
            report.reciprocal_return["return_power"]["power_after_return_mirror_w"],
            report.reciprocal_return["return_power"]["power_at_fiber_plane_w"],
        ]
    )
    assert return_rays[0].power_w == pytest.approx(
        report.summary["power_at_return_mirror_w"]
    )
    assert return_rays[-1].power_w == pytest.approx(
        report.summary["power_at_fiber_plane_w"]
    )
    fiber_guide = next(
        guide
        for guide in scene.guides
        if guide.guide_id.endswith("fiber_hit_residual")
    )
    assert fiber_guide.metadata["fiber_coupling_model"] == "gaussian_alignment_proxy"
    assert fiber_guide.metadata["fiber_coupling_efficiency"] == pytest.approx(
        report.summary["fiber_coupling_efficiency"]
    )
    assert fiber_guide.metadata["power_coupled_into_fiber_w"] == pytest.approx(
        report.summary["power_coupled_into_fiber_w"]
    )
    assert fiber_guide.metadata["coherent_field_status"] == "not_provided"
    assert fiber_guide.metadata["field_usable_for_coherent_propagation"] is False


def test_viewport_scene_round_trips_as_yaml(project_root: Path) -> None:
    project = load_project(project_root / "configs" / "project.yaml")
    scene = build_viewport_scene(project)

    payload = yaml.safe_load(yaml.safe_dump(scene.to_dict(), sort_keys=False))

    assert payload["project_id"] == "optic_ray_default"
    assert payload["schema_version"] == 2
    assert payload["meshes"] == []
    assert payload["mesh_hits"] == []
    assert payload["scenario_id"] == "baseline_1550nm"
    assert payload["model_scope"] == (
        "source_to_static_mirror_rectangle_or_stl_center_ray_target_lambertian_virtual_aperture_"
        "and_reciprocal_center_ray_geometry_and_return_power_ledger_"
        "and_gaussian_alignment_proxy_and_passive_detector_input_boundary"
    )
    assert payload["placement_edits"] == []
    assert payload["constraints"] == []


def test_viewport_scene_is_strict_schema_valid(project_root: Path) -> None:
    project = load_project(project_root / "configs" / "project.yaml")
    payload = build_viewport_scene(project).to_dict()
    schemas = SchemaStore.load(project_root / "schemas")

    schemas.validate(
        payload,
        "viewport_scene.schema.json",
        source="test viewport scene",
    )
    payload["components"][0]["typo_origin"] = [0.0, 0.0, 0.0]
    with pytest.raises(ConfigValidationError, match="Additional properties"):
        schemas.validate(
            payload,
            "viewport_scene.schema.json",
            source="invalid viewport scene",
        )


def test_viewport_component_frames_match_physical_directions(project_root: Path) -> None:
    project = load_project(project_root / "configs" / "project.yaml")
    scene = build_viewport_scene(project)
    components = {component.element_id: component for component in scene.components}

    target_rotation = np.asarray(
        components["target_plane"].rotation_world_from_component,
        dtype=np.float64,
    )
    receiver_rotation = np.asarray(
        components["receiver"].rotation_world_from_component,
        dtype=np.float64,
    )

    assert target_rotation[:, 2] == pytest.approx([-1.0, 0.0, 0.0])
    assert target_rotation[:, 0] == pytest.approx([0.0, -1.0, 0.0])
    assert target_rotation[:, 1] == pytest.approx([0.0, 0.0, 1.0])
    assert np.linalg.det(target_rotation) == pytest.approx(1.0)
    assert receiver_rotation[:, 2] == pytest.approx([1.0, 0.0, 0.0])
    assert np.linalg.det(receiver_rotation) == pytest.approx(1.0)
    assert components["receiver"].component_type == "virtual_aperture_regression_intermediate"
    assert components["receiver"].display_role == "virtual_aperture_reference"


def test_not_evaluated_reciprocal_section_does_not_claim_geometry_overlay(
    project_root: Path,
) -> None:
    project = load_project(project_root / "configs" / "project.yaml")
    report = build_phase2_optical_train_report(project).to_dict()
    reciprocal = report["reciprocal_return"]
    assert isinstance(reciprocal, dict)
    reciprocal["status"] = "not_evaluated"
    reciprocal["path"] = None

    scene = build_viewport_scene(project, report=report)

    assert not any(ray.propagation_role == "return" for ray in scene.rays)
    assert not any("return overlay는" in warning for warning in scene.warnings)


def test_workspace_renderer_writes_png(project_root: Path, tmp_path: Path) -> None:
    project = load_project(project_root / "configs" / "project.yaml")
    scene = build_viewport_scene(project)
    output_path = tmp_path / "workspace.png"

    result = render_viewport_scene(scene, output_path, dpi=72)

    assert result == output_path.resolve()
    payload = output_path.read_bytes()
    assert payload.startswith(b"\x89PNG\r\n\x1a\n")
    assert len(payload) > 10_000


def test_reciprocal_exact_path_builds_three_geometry_only_return_segments(
    project_root: Path,
) -> None:
    project = load_project(project_root / "configs" / "project.yaml")
    report = _report_with_reciprocal_path(project, path=_exact_reciprocal_path())

    scene = build_viewport_scene(project, report=report)
    return_rays = [ray for ray in scene.rays if ray.propagation_role == "return"]

    assert len(return_rays) == 3
    assert [(ray.start_m, ray.end_m) for ray in return_rays] == [
        ((10.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
        ((0.0, 0.0, 0.0), (0.0, 0.0, -0.08)),
        ((0.0, 0.0, -0.08), (0.0, 0.0, -0.10)),
    ]
    assert all(ray.power_w is None for ray in return_rays)
    assert all(ray.plane_power_name is None for ray in return_rays)
    assert all(ray.status == "return_propagated" for ray in return_rays)
    residual_guides = [
        guide for guide in scene.guides if guide.guide_type == "return_hit_residual"
    ]
    assert len(residual_guides) == 3
    assert all(guide.metadata["geometry_only"] is True for guide in residual_guides)
    assert all(guide.start_m == guide.end_m for guide in residual_guides)
    with pytest.raises(TypeError):
        residual_guides[0].metadata["plane_id"] = "mutated"  # type: ignore[index]
    assert any("geometry-only" in warning for warning in scene.warnings)
    transmit_rays = [ray for ray in scene.rays if ray.propagation_role == "transmit"]
    assert transmit_rays[0].plane_power_name == report["optical_train"]["states"][0]["label"]
    assert transmit_rays[0].power_w is not None


def test_reciprocal_terminated_path_stops_at_last_actual_hit_without_teleport(
    project_root: Path,
) -> None:
    project = load_project(project_root / "configs" / "project.yaml")
    path = _exact_reciprocal_path()
    collimator_point = [0.003, 0.0, -0.08]
    path.update(
        {
            "status": "terminated",
            "terminated": True,
            "termination_reason": "return_collimator:outside_clear_aperture",
            "termination_point_m": collimator_point,
            "collimator_hit": _reciprocal_hit(
                "return_collimator",
                collimator_point,
                [0.0, 0.0, -0.08],
                aperture_status="miss",
            ),
            # A malformed downstream record must not make the viewport teleport past termination.
            "fiber_hit": _reciprocal_hit(
                "fiber_reference",
                [9.0, 9.0, 9.0],
                [0.0, 0.0, -0.10],
            ),
        }
    )
    report = _report_with_reciprocal_path(project, path=path)

    scene = build_viewport_scene(project, report=report)
    return_rays = [ray for ray in scene.rays if ray.propagation_role == "return"]

    assert len(return_rays) == 2
    assert return_rays[-1].end_m == pytest.approx(collimator_point)
    assert return_rays[-1].status == "return_terminated"
    assert all(ray.end_m != pytest.approx([9.0, 9.0, 9.0]) for ray in return_rays)


@pytest.mark.parametrize("results_wrapper", [False, True])
def test_reciprocal_results_wrapper_is_accepted_without_changing_coordinates(
    project_root: Path,
    results_wrapper: bool,
) -> None:
    project = load_project(project_root / "configs" / "project.yaml")
    report = _report_with_reciprocal_path(project, path=_exact_reciprocal_path())
    section = report["reciprocal_return"]
    assert isinstance(section, dict)
    path = section.pop("path")
    section["results"] = {"path": path} if results_wrapper else {"primary": path}

    scene = build_viewport_scene(project, report=report)
    return_rays = [ray for ray in scene.rays if ray.propagation_role == "return"]

    assert len(return_rays) == 3
    assert return_rays[-1].end_m == pytest.approx([0.0, 0.0, -0.10])


def test_reciprocal_viewport_serializes_and_validates_strict_schema(
    project_root: Path,
) -> None:
    project = load_project(project_root / "configs" / "project.yaml")
    report = _report_with_reciprocal_path(project, path=_exact_reciprocal_path())
    payload = yaml.safe_load(
        yaml.safe_dump(build_viewport_scene(project, report=report).to_dict(), sort_keys=False)
    )

    SchemaStore.load(project_root / "schemas").validate(
        payload,
        "viewport_scene.schema.json",
        source="R1 reciprocal viewport",
    )
    return_rays = [ray for ray in payload["rays"] if ray["propagation_role"] == "return"]
    assert len(return_rays) == 3
    assert all(ray["power_w"] is None for ray in return_rays)


def test_r2_return_plane_power_maps_to_actual_segments_and_preserves_zero(
    project_root: Path,
) -> None:
    project = load_project(project_root / "configs" / "project.yaml")
    report = _report_with_reciprocal_path(project, path=_exact_reciprocal_path())
    _attach_r2_return_power(
        report,
        mirror_power_w=1.8e-9,
        after_mirror_power_w=1.6e-9,
        fiber_plane_power_w=0.0,
    )

    scene = build_viewport_scene(project, report=report)
    return_rays = [ray for ray in scene.rays if ray.propagation_role == "return"]

    assert [ray.plane_power_name for ray in return_rays] == [
        "power_at_return_mirror_w",
        "power_after_return_mirror_w",
        "power_at_fiber_plane_w",
    ]
    assert [ray.power_w for ray in return_rays] == pytest.approx([1.8e-9, 1.6e-9, 0.0])
    assert all(ray.radius_start_m is None for ray in return_rays)
    assert all(ray.radius_end_m is None for ray in return_rays)
    assert any("R2 return overlay" in warning for warning in scene.warnings)
    assert not any("R1 return overlay" in warning for warning in scene.warnings)

    payload = scene.to_dict()
    SchemaStore.load(project_root / "schemas").validate(
        payload,
        "viewport_scene.schema.json",
        source="R2 reciprocal power viewport",
    )
    serialized_return = [
        ray for ray in payload["rays"] if ray["propagation_role"] == "return"
    ]
    assert serialized_return[-1]["power_w"] == 0.0


def test_r3_coupling_is_fiber_reference_metadata_without_fake_ray_or_field(
    project_root: Path,
) -> None:
    project = load_project(project_root / "configs" / "project.yaml")
    report = _report_with_reciprocal_path(project, path=_exact_reciprocal_path())
    _attach_r2_return_power(report)
    _attach_r3_fiber_coupling(report)

    scene = build_viewport_scene(project, report=report)
    return_rays = [ray for ray in scene.rays if ray.propagation_role == "return"]
    fiber_guides = [
        guide
        for guide in scene.guides
        if guide.guide_id.endswith("fiber_hit_residual")
    ]

    assert len(return_rays) == 3
    assert return_rays[-1].power_w == pytest.approx(1.5e-9)
    assert return_rays[-1].plane_power_name == "power_at_fiber_plane_w"
    assert len(fiber_guides) == 1
    assert fiber_guides[0].metadata["fiber_coupling_model"] == (
        "gaussian_alignment_proxy"
    )
    assert fiber_guides[0].metadata["fiber_coupling_efficiency"] == pytest.approx(
        0.64
    )
    assert fiber_guides[0].metadata["power_coupled_into_fiber_w"] == pytest.approx(
        9.6e-10
    )
    assert fiber_guides[0].metadata["coherent_field_status"] == "not_provided"
    assert fiber_guides[0].metadata["field_usable_for_coherent_propagation"] is False
    assert "P_coupled=9.6e-10 W" in fiber_guides[0].label
    assert any("새 ray/beam/field를 만들지 않습니다" in item for item in scene.warnings)
    assert any("calibrated hardware prediction이 아닙니다" in item for item in scene.warnings)

    SchemaStore.load(project_root / "schemas").validate(
        scene.to_dict(),
        "viewport_scene.schema.json",
        source="R3 fiber coupling viewport metadata",
    )


def test_r4_detector_boundary_is_metadata_without_fake_component_ray_or_field(
    project_root: Path,
) -> None:
    project = load_project(project_root / "configs" / "project.yaml")
    report = _report_with_reciprocal_path(project, path=_exact_reciprocal_path())
    _attach_r2_return_power(report)
    _attach_r3_fiber_coupling(report)
    _attach_r4_detector_boundary(report)

    scene = build_viewport_scene(project, report=report)
    return_rays = [ray for ray in scene.rays if ray.propagation_role == "return"]
    fiber_guide = next(
        guide
        for guide in scene.guides
        if guide.guide_id.endswith("fiber_hit_residual")
    )

    assert len(return_rays) == 3
    assert return_rays[-1].power_w == pytest.approx(1.5e-9)
    assert not any(
        component.component_type == "detector_boundary"
        for component in scene.components
    )
    assert fiber_guide.metadata["detector_boundary_model"] == (
        "passive_duplexer_detector_input_boundary"
    )
    assert fiber_guide.metadata["power_at_detector_input_w"] == pytest.approx(
        4.8e-10
    )
    assert fiber_guide.metadata["detector_response_status"] == "not_evaluated"
    assert fiber_guide.metadata["detector_coherent_field_status"] == "not_provided"
    assert (
        fiber_guide.metadata["detector_field_usable_for_coherent_propagation"]
        is False
    )
    assert any("비공간 optical boundary" in item for item in scene.warnings)
    assert any("component, ray, beam 또는 field" in item for item in scene.warnings)

    SchemaStore.load(project_root / "schemas").validate(
        scene.to_dict(),
        "viewport_scene.schema.json",
        source="R4 detector boundary viewport metadata",
    )


def test_reciprocal_coordinates_and_styles_match_plotly_and_matplotlib(
    project_root: Path,
    tmp_path: Path,
) -> None:
    project = load_project(project_root / "configs" / "project.yaml")
    report = _report_with_reciprocal_path(project, path=_exact_reciprocal_path())
    scene = build_viewport_scene(project, report=report)
    expected = [ray for ray in scene.rays if ray.propagation_role == "return"]

    figure = build_interactive_viewport_figure(scene)
    return_guides = [trace for trace in figure.data if trace.name == "return hit residual"]
    assert len(return_guides) == 1
    assert return_guides[0].mode == "lines+markers"
    plotly_return = [trace for trace in figure.data if trace.legendgroup == "return_path"]
    assert len(plotly_return) == len(expected)
    for trace, ray in zip(plotly_return, expected, strict=True):
        assert trace.x == pytest.approx((ray.start_m[0], ray.end_m[0]))
        assert trace.y == pytest.approx((ray.start_m[1], ray.end_m[1]))
        assert trace.z == pytest.approx((ray.start_m[2], ray.end_m[2]))
        assert trace.line.dash == "dash"
        assert trace.name == "Reciprocal return (geometry-only)"

    class _RecordingAxis:
        def __init__(self) -> None:
            self.lines: list[tuple[tuple[object, ...], dict[str, object]]] = []

        def plot(self, *args: object, **kwargs: object) -> None:
            self.lines.append((args, kwargs))

    axis = _RecordingAxis()
    _draw_rays(axis, scene.to_dict())
    matplotlib_return = [line for line in axis.lines if line[1].get("color") == "#0ea5e9"]
    assert len(matplotlib_return) == len(expected)
    for (args, kwargs), ray in zip(matplotlib_return, expected, strict=True):
        assert args[0] == pytest.approx([ray.start_m[0], ray.end_m[0]])
        assert args[1] == pytest.approx([ray.start_m[1], ray.end_m[1]])
        assert args[2] == pytest.approx([ray.start_m[2], ray.end_m[2]])
        assert kwargs["linestyle"] == "--"

    output = render_viewport_scene(scene, tmp_path / "r1_zero_residual_guides.png", dpi=72)
    assert output.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def test_r2_return_power_labels_match_plotly_and_matplotlib(
    project_root: Path,
) -> None:
    project = load_project(project_root / "configs" / "project.yaml")
    report = _report_with_reciprocal_path(project, path=_exact_reciprocal_path())
    _attach_r2_return_power(report)
    scene = build_viewport_scene(project, report=report)
    expected = [ray for ray in scene.rays if ray.propagation_role == "return"]

    figure = build_interactive_viewport_figure(scene)
    plotly_return = [trace for trace in figure.data if trace.legendgroup == "return_path"]
    assert len(plotly_return) == 3
    for trace, ray in zip(plotly_return, expected, strict=True):
        assert trace.name == "Reciprocal return (analytical power)"
        assert ray.plane_power_name in trace.hovertemplate
        assert f"{ray.power_w:.6g} W" in trace.hovertemplate
        assert "return beam radius: not evaluated" in trace.hovertemplate

    class _RecordingAxis:
        def __init__(self) -> None:
            self.lines: list[tuple[tuple[object, ...], dict[str, object]]] = []
            self.labels: list[str] = []

        def plot(self, *args: object, **kwargs: object) -> None:
            self.lines.append((args, kwargs))

        def text2D(self, *args: object, **kwargs: object) -> None:
            self.labels.append(str(args[2]))

    axis = _RecordingAxis()
    _draw_rays(axis, scene.to_dict())
    return_lines = [line for line in axis.lines if line[1].get("color") == "#0ea5e9"]
    assert len(return_lines) == 3
    assert return_lines[0][1]["label"] == "Reciprocal return (analytical power)"
    assert axis.labels == [
        "R2 reciprocal plane power\n"
        + "\n".join(
            f"{ray.plane_power_name}: {float(ray.power_w):.3g} W" for ray in expected
        )
    ]


def test_rotated_oblique_footprint_axes_flow_from_physics_to_both_renderers(
    copied_project: Path,
) -> None:
    incidence_angle = np.pi / 4.0
    target_normal = np.array(
        [-np.cos(incidence_angle), 0.0, np.sin(incidence_angle)],
        dtype=np.float64,
    )
    projected_incidence = np.array(
        [np.sin(incidence_angle), 0.0, np.cos(incidence_angle)],
        dtype=np.float64,
    )
    target_roll = np.pi / 3.0
    width_axis = (
        np.cos(target_roll) * np.array([0.0, 1.0, 0.0], dtype=np.float64)
        + np.sin(target_roll) * projected_incidence
    )
    output_dir = copied_project.parent / "ui_runs"
    variant = create_simulation_variant(
        project_path=copied_project,
        scenario_id="rotated_oblique_footprint",
        scenario_output=output_dir / "rotated_oblique_footprint.yaml",
        project_output=output_dir / "rotated_oblique_footprint_project.yaml",
        parameter_edits=SimulationParameterEdits(
            target_id="target_plane",
            target_normal=tuple(float(value) for value in target_normal),
            target_width_axis=tuple(float(value) for value in width_axis),
        ),
    )
    project = load_project(variant.project_path)
    report = build_phase2_optical_train_report(project)
    scene = build_viewport_scene(project, report=report)
    footprint_report = report.target_footprints[0]
    overlay = scene.footprints[0]

    schemas = SchemaStore.load(copied_project.parent.parent / "schemas")
    schemas.validate(
        report.to_dict(),
        "phase2_optical_train_report.schema.json",
        source="rotated oblique phase2 report",
    )
    schemas.validate(
        scene.to_dict(),
        "viewport_scene.schema.json",
        source="rotated oblique viewport scene",
    )

    assert np.asarray(overlay.major_axis_world) == pytest.approx(
        footprint_report["projected_footprint_major_axis_world"]
    )
    assert np.asarray(overlay.minor_axis_world) == pytest.approx(
        footprint_report["projected_footprint_minor_axis_world"]
    )
    assert overlay.orientation_axis_world == overlay.major_axis_world
    assert abs(float(np.dot(overlay.major_axis_world, projected_incidence))) == pytest.approx(1.0)
    assert np.cross(overlay.major_axis_world, overlay.minor_axis_world) == pytest.approx(
        target_normal,
        abs=1.0e-12,
    )

    center = np.asarray(overlay.hit_center_m, dtype=np.float64)
    expected_major_point = (
        center + overlay.major_radius_m * np.asarray(overlay.major_axis_world)
    )
    expected_minor_point = (
        center + overlay.minor_radius_m * np.asarray(overlay.minor_axis_world)
    )
    plotly_points = _footprint_coordinates(overlay, samples=5)
    matplotlib_points = _footprint_polygon(overlay.to_dict(), samples=4)
    assert plotly_points[0] == pytest.approx(expected_major_point)
    assert plotly_points[1] == pytest.approx(expected_minor_point)
    assert matplotlib_points[0] == pytest.approx(expected_major_point)
    assert matplotlib_points[1] == pytest.approx(expected_minor_point)
