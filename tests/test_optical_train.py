from __future__ import annotations

import math
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml

from lidarsim.beam import BeamState
from lidarsim.config import load_project
from lidarsim.config.schema import SchemaStore
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
    assert report.analytical_checks["external_validation_status"] == "not_evaluated"


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
