from __future__ import annotations

import math
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml

from lidarsim.beam import BeamState
from lidarsim.config import load_project
from lidarsim.config.schema import SchemaStore
from lidarsim.errors import ConfigValidationError
from lidarsim.optics import (
    ABCDMatrix,
    apply_abcd_to_beam,
    circular_aperture_transmission_fraction,
    interact_flat_mirror,
    propagate_transmitter_train,
    reflect_vector,
    rectangular_mirror_clip,
)
from lidarsim.results import build_phase2_optical_train_report
from lidarsim.visualization import render_optical_train_view


def _beam(**overrides) -> BeamState:
    values = {
        "time_s": 0.0,
        "origin_m": [0.0, 0.0, 0.0],
        "direction": [0.0, 0.0, 1.0],
        "transverse_x_axis": [1.0, 0.0, 0.0],
        "wavelength_m": 1.55e-6,
        "power_w": 0.01,
        "waist_radius_x_m": 5.0e-6,
        "waist_radius_y_m": 5.0e-6,
        "m2_x": 1.0,
        "m2_y": 1.0,
        "profile_kind": "circular_gaussian",
        "propagation_model": "gaussian_m2",
    }
    values.update(overrides)
    return BeamState(**values)


def test_thin_lens_abcd_collimates_source_at_focal_distance() -> None:
    source = _beam()
    before_lens = source.propagate_free_space(0.02)
    after_lens = apply_abcd_to_beam(before_lens, ABCDMatrix.thin_lens(0.02))

    expected_output_waist = 1.55e-6 * 0.02 / (3.141592653589793 * 5.0e-6)
    assert after_lens.distance_from_waist_m == pytest.approx(-0.02)
    assert after_lens.waist_radius_x_m == pytest.approx(expected_output_waist)
    assert after_lens.rayleigh_range_x_m == pytest.approx(0.02**2 / source.rayleigh_range_x_m)


def test_circular_aperture_closed_form_power_fraction() -> None:
    fraction, method = circular_aperture_transmission_fraction(
        aperture_radius_m=2.0e-3,
        beam_radius_x_m=1.0e-3,
        beam_radius_y_m=1.0e-3,
    )

    assert method == "closed_form_circular_gaussian"
    assert fraction == pytest.approx(1.0 - math.exp(-8.0))


def test_flat_mirror_reflection_uses_vector_law() -> None:
    reflected = reflect_vector([0.0, 0.0, 1.0], [-math.sqrt(0.5), 0.0, math.sqrt(0.5)])

    assert reflected == pytest.approx([1.0, 0.0, 0.0], abs=1e-15)


def test_flat_mirror_reflectivity_scales_output_power() -> None:
    beam = _beam(
        power_w=1.0,
        waist_radius_x_m=1.0e-3,
        waist_radius_y_m=1.0e-3,
    )

    interaction = interact_flat_mirror(
        beam,
        surface_origin_m=[0.0, 0.0, 0.0],
        surface_normal=[0.0, 0.0, 1.0],
        aperture_x_axis=[1.0, 0.0, 0.0],
        aperture_y_axis=[0.0, 1.0, 0.0],
        clear_width_m=0.02,
        clear_height_m=0.02,
        power_reflectivity=0.8,
    )

    assert interaction.aperture_clip.status == "pass"
    assert interaction.output_beam.power_w == pytest.approx(0.8, rel=1e-12)
    assert interaction.output_beam.accumulated_transmission == pytest.approx(0.8, rel=1e-12)


def test_zero_transmission_and_reflectivity_produce_valid_zero_power() -> None:
    beam = _beam(power_w=1.0)
    after_lens = apply_abcd_to_beam(
        beam,
        ABCDMatrix.thin_lens(0.02),
        power_transmission=0.0,
    )
    interaction = interact_flat_mirror(
        after_lens,
        surface_origin_m=[0.0, 0.0, 0.0],
        surface_normal=[0.0, 0.0, 1.0],
        aperture_x_axis=[1.0, 0.0, 0.0],
        aperture_y_axis=[0.0, 1.0, 0.0],
        clear_width_m=0.02,
        clear_height_m=0.02,
        power_reflectivity=0.0,
    )

    assert after_lens.power_w == 0.0
    assert interaction.aperture_clip.input_power_w == 0.0
    assert interaction.output_beam.power_w == 0.0
    assert interaction.output_beam.accumulated_transmission == 0.0


def test_flat_mirror_rectangular_aperture_reports_status() -> None:
    small = _beam(waist_radius_x_m=1.0e-3, waist_radius_y_m=1.0e-3)
    large = _beam(waist_radius_x_m=0.10, waist_radius_y_m=0.10)

    small_clip = rectangular_mirror_clip(
        small,
        surface_normal=[0.0, 0.0, 1.0],
        aperture_x_axis=[1.0, 0.0, 0.0],
        aperture_y_axis=[0.0, 1.0, 0.0],
        clear_width_m=0.02,
        clear_height_m=0.02,
    )
    large_clip = rectangular_mirror_clip(
        large,
        surface_normal=[0.0, 0.0, 1.0],
        aperture_x_axis=[1.0, 0.0, 0.0],
        aperture_y_axis=[0.0, 1.0, 0.0],
        clear_width_m=0.02,
        clear_height_m=0.02,
    )

    assert small_clip.status == "pass"
    assert small_clip.transmission_fraction == pytest.approx(1.0, rel=1e-12)
    assert large_clip.status in {"warning", "fail"}
    assert large_clip.transmission_fraction < 1.0


def test_phase2_train_reflects_from_scanner_mirror_with_power_ledger(project_root: Path) -> None:
    project = load_project(project_root / "configs" / "project.yaml")

    train = propagate_transmitter_train(project)

    assert train.optical_path_id == "transmit_main"
    assert train.states[0].label == "source.output"
    assert train.final_state.label == "scan_mirror.reflected"
    assert train.final_state.state.direction == pytest.approx([1.0, 0.0, 0.0], abs=1e-12)
    assert len(train.component_reports) == 2
    assert train.component_reports[0]["model"] == "ideal_thin_lens"
    assert train.component_reports[1]["surface_model"] == "flat_mirror"
    assert train.unsupported_elements == ()
    assert [entry.mechanism for entry in train.power_ledger] == [
        "free_space_propagation",
        "circular_aperture_clipping",
        "component_power_transmission",
        "free_space_propagation",
        "mirror_rectangular_aperture",
        "mirror_reflectivity",
    ]

    collimator_output = train.component_reports[0]["output_beam_state"]
    mirror_clip = train.component_reports[1]["aperture_clip"]
    assert collimator_output["waist_radius_x_m"] == pytest.approx(0.00197352129, rel=1e-8)
    assert train.final_state.state.power_w == pytest.approx(0.01, rel=1e-5)
    assert train.final_state.state.radius_x_m == pytest.approx(0.00197358, rel=1e-4)
    assert mirror_clip["incidence_angle_rad"] == pytest.approx(math.pi / 4.0)
    assert mirror_clip["transmission_fraction"] == pytest.approx(1.0, rel=1e-11)
    assert train.component_reports[1]["incident_direction"] == pytest.approx([0.0, 0.0, 1.0])
    assert train.component_reports[1]["reflected_direction"] == pytest.approx(
        [1.0, 0.0, 0.0],
        abs=1e-12,
    )
    assert train.component_reports[1]["aperture_status"] == "pass"


def test_phase2_zero_component_transmission_is_schema_valid(
    copied_project: Path,
) -> None:
    component_path = (
        copied_project.parent.parent
        / "catalog"
        / "components"
        / "custom"
        / "ideal_collimator_f20.yaml"
    )
    component = yaml.safe_load(component_path.read_text(encoding="utf-8"))
    component["optical"]["power_transmission"] = 0.0
    component_path.write_text(
        yaml.safe_dump(component, sort_keys=False),
        encoding="utf-8",
    )
    project = load_project(copied_project)

    train = propagate_transmitter_train(project)
    report = build_phase2_optical_train_report(project, train)

    assert train.final_state.state.power_w == 0.0
    assert train.total_transmission == 0.0
    assert train.power_ledger[2].transmission_fraction == 0.0
    assert report.summary["final_power_w"] == 0.0
    SchemaStore.load(copied_project.parent.parent / "schemas").validate(
        report.to_dict(),
        "phase2_optical_train_report.schema.json",
        source="zero transmission Phase 2 report",
    )


def test_phase2_rejects_unsupported_second_moment_contract(
    copied_project: Path,
) -> None:
    scenario_path = copied_project.parent / "baseline_1550nm.yaml"
    scenario = yaml.safe_load(scenario_path.read_text(encoding="utf-8"))
    scenario["source"]["propagation_model"] = "second_moment"
    scenario_path.write_text(
        yaml.safe_dump(scenario, sort_keys=False),
        encoding="utf-8",
    )
    project = load_project(copied_project)

    with pytest.raises(ValueError, match="gaussian_m2만 지원"):
        propagate_transmitter_train(project)


def test_nonunit_scenario_directions_preserve_input_and_report_normalization(
    copied_project: Path,
) -> None:
    scenario_path = copied_project.parent / "baseline_1550nm.yaml"
    scenario = yaml.safe_load(scenario_path.read_text(encoding="utf-8"))
    scenario["scanner"]["rotation_axis_world"] = [0.0, 10.0, 0.0]
    scenario["scene"]["targets"][0]["geometry"]["normal"] = [-2.0, 0.0, 0.0]
    scenario["receiver"]["direction"] = [3.0, 0.0, 0.0]
    scenario_path.write_text(
        yaml.safe_dump(scenario, sort_keys=False),
        encoding="utf-8",
    )
    project = load_project(copied_project)

    report = build_phase2_optical_train_report(project)
    mirror = report.optical_train["component_reports"][1]
    target = report.target_footprints[0]["target_intersection"]
    receiver = report.receiver_return["returns"][0]

    assert sum("runtime에서 unit vector" in item.message for item in project.warnings) == 3
    assert mirror["scanner_rotation_axis_input_world"] == pytest.approx([0.0, 10.0, 0.0])
    assert mirror["scanner_rotation_axis_world"] == pytest.approx([0.0, 1.0, 0.0])
    assert target["target_normal_input"] == pytest.approx([-2.0, 0.0, 0.0])
    assert target["target_normal"] == pytest.approx([-1.0, 0.0, 0.0])
    assert receiver["receiver_direction_input"] == pytest.approx([3.0, 0.0, 0.0])
    assert receiver["receiver_direction"] == pytest.approx([1.0, 0.0, 0.0])


def test_multiple_collinear_targets_only_nearest_owns_scene_energy(
    copied_project: Path,
) -> None:
    scenario_path = copied_project.parent / "baseline_1550nm.yaml"
    scenario = yaml.safe_load(scenario_path.read_text(encoding="utf-8"))
    near = scenario["scene"]["targets"][0]
    near["id"] = "near_target"
    near["geometry"]["center_m"] = ["10 m", "0 m", "0 m"]
    far = {
        "id": "far_target",
        "geometry": {
            "type": "rectangle_plane",
            "center_m": ["12 m", "0 m", "0 m"],
            "normal": [-1.0, 0.0, 0.0],
            "width_m": "4 m",
            "height_m": "4 m",
        },
        "material_ref": near["material_ref"],
    }
    scenario["scene"]["targets"] = [far, near]
    scenario_path.write_text(
        yaml.safe_dump(scenario, sort_keys=False),
        encoding="utf-8",
    )
    project = load_project(copied_project)

    report = build_phase2_optical_train_report(project)
    footprints = {
        item["target_id"]: item for item in report.target_footprints
    }
    returns = {
        item["target_id"]: item for item in report.receiver_return["returns"]
    }
    ledger = report.scene_energy_ledger

    assert footprints["near_target"]["visibility_status"] == "visible_nearest"
    assert footprints["near_target"]["contributes_to_scene_energy"] is True
    assert footprints["near_target"]["estimated_power_on_target_w"] > 0.0
    assert footprints["far_target"]["visibility_status"] == "occluded_by_nearer_target"
    assert footprints["far_target"]["occluded_by_target_id"] == "near_target"
    assert footprints["far_target"]["candidate_estimated_power_on_target_w"] > 0.0
    assert footprints["far_target"]["estimated_power_on_target_w"] == 0.0
    assert returns["far_target"]["status"] == "occluded_by_nearer_target"
    assert returns["far_target"]["estimated_received_power_w"] == 0.0
    assert ledger["total_contributing_power_on_target_w"] <= ledger["input_beam_power_w"]
    assert ledger["oversubscription_residual_w"] == 0.0
    assert ledger["status"] == "pass"
    assert report.summary["estimated_power_on_target_w"] == pytest.approx(
        footprints["near_target"]["estimated_power_on_target_w"]
    )


def test_scanner_static_command_angle_steers_reflected_ray(copied_project: Path) -> None:
    scenario_path = copied_project.parent / "baseline_1550nm.yaml"
    scenario = yaml.safe_load(scenario_path.read_text(encoding="utf-8"))
    scenario["scanner"]["static_command_angle_rad"] = "5 deg"
    scenario_path.write_text(yaml.safe_dump(scenario, sort_keys=False), encoding="utf-8")
    project = load_project(copied_project)

    train = propagate_transmitter_train(project)

    expected = [math.cos(math.radians(10.0)), 0.0, -math.sin(math.radians(10.0))]
    mirror_report = train.component_reports[1]
    assert mirror_report["scanner_pose_model"] == "static_command_angle"
    assert mirror_report["scanner_command_angle_rad"] == pytest.approx(math.radians(5.0))
    assert train.final_state.state.direction == pytest.approx(expected, abs=1e-12)
    assert mirror_report["reflected_direction"] == pytest.approx(expected, abs=1e-12)

    report = build_phase2_optical_train_report(project)
    assert report.summary["target_hit_count"] == 1
    assert report.summary["estimated_received_power_w"] > 0.0


def test_phase2_report_is_schema_valid(project_root: Path) -> None:
    project = load_project(project_root / "configs" / "project.yaml")

    report = build_phase2_optical_train_report(
        project,
        created_at=datetime(2026, 7, 8, tzinfo=UTC),
    )

    SchemaStore.load(project_root / "schemas").validate(
        report.to_dict(),
        "phase2_optical_train_report.schema.json",
        source="test Phase 2 optical train report",
    )
    assert report.manifest["created_at_utc"] == "2026-07-08T00:00:00Z"
    assert report.summary["overall_status"] == "warning"
    assert report.summary["q_parameter_status"] == "pass"
    assert report.summary["energy_ledger_status"] == "pass"
    assert report.summary["aperture_status"] == "pass"
    assert report.summary["target_footprint_status"] == "pass"
    assert report.summary["receiver_return_status"] == "pass"
    assert report.summary["target_hit_count"] == 1
    assert report.summary["estimated_power_on_target_w"] == pytest.approx(
        report.summary["final_power_w"]
    )
    assert report.summary["estimated_received_power_w"] > 0.0
    assert report.summary["link_loss_db"] is not None
    assert report.accuracy["scope"].endswith("lambertian_virtual_aperture")
    assert any("fiber 결합" in warning for warning in report.accuracy["warnings"])
    assert any(
        "virtual aperture plane" in assumption
        for assumption in report.receiver_return["assumptions"]
    )
    assert report.analytical_checks["external_validation_status"] == "not_evaluated"


def test_phase2_report_schema_rejects_nested_component_typo(project_root: Path) -> None:
    project = load_project(project_root / "configs" / "project.yaml")
    payload = build_phase2_optical_train_report(project).to_dict()
    payload["optical_train"]["component_reports"][0]["focal_lenght_typo"] = 0.02

    with pytest.raises(ConfigValidationError, match="not valid under any"):
        SchemaStore.load(project_root / "schemas").validate(
            payload,
            "phase2_optical_train_report.schema.json",
            source="invalid Phase 2 report",
        )


def test_phase2_optical_train_view_writes_png(project_root: Path, tmp_path: Path) -> None:
    project = load_project(project_root / "configs" / "project.yaml")
    report = build_phase2_optical_train_report(project)

    result = render_optical_train_view(report, tmp_path / "phase2_train.png", dpi=72)

    assert result.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert result.stat().st_size > 10_000


def test_phase2_report_yaml_round_trip_contains_power_ledger(project_root: Path, tmp_path: Path) -> None:
    project = load_project(project_root / "configs" / "project.yaml")
    report = build_phase2_optical_train_report(project)
    path = tmp_path / "phase2.yaml"
    path.write_text(
        yaml.safe_dump(report.to_dict(), sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))

    assert loaded["report_type"] == "phase2_optical_train"
    assert loaded["optical_train"]["power_ledger"][1]["mechanism"] == "circular_aperture_clipping"
    assert loaded["target_footprints"][0]["hit"] is True
    assert loaded["receiver_return"]["returns"][0]["receiver_fov_status"] == "inside_fov"
