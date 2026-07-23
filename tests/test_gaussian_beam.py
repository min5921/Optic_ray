from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from lidarsim.beam import (
    BeamState,
    SecondMoment1D,
    build_source_beam,
    divergence_half_angle_rad,
    gaussian_radius_m,
    rayleigh_range_m,
)
from lidarsim.config import load_project
from lidarsim.config.immutable import deep_thaw
from lidarsim.config.schema import SchemaStore
from lidarsim.results import build_phase1_beam_report
from lidarsim.visualization import render_beam_view


def _beam(**overrides) -> BeamState:
    values = {
        "time_s": 0.0,
        "origin_m": [0.0, 0.0, 0.0],
        "direction": [0.0, 0.0, 1.0],
        "transverse_x_axis": [1.0, 0.0, 0.0],
        "wavelength_m": 1.0e-6,
        "power_w": 2.0,
        "waist_radius_x_m": 1.0e-3,
        "waist_radius_y_m": 1.0e-3,
        "m2_x": 1.0,
        "m2_y": 1.0,
        "profile_kind": "circular_gaussian",
        "propagation_model": "gaussian_m2",
    }
    values.update(overrides)
    return BeamState(**values)


def test_gaussian_analytical_divergence_rayleigh_and_radius() -> None:
    wavelength = 1.0e-6
    waist = 1.0e-3
    expected_divergence = wavelength / (np.pi * waist)
    expected_rayleigh = np.pi * waist**2 / wavelength

    assert divergence_half_angle_rad(wavelength, waist) == pytest.approx(expected_divergence)
    assert rayleigh_range_m(wavelength, waist) == pytest.approx(expected_rayleigh)
    assert gaussian_radius_m(expected_rayleigh, wavelength, waist) == pytest.approx(
        waist * np.sqrt(2.0)
    )


def test_m2_increases_divergence_and_decreases_rayleigh_range() -> None:
    ideal_divergence = divergence_half_angle_rad(1.0e-6, 1.0e-3, 1.0)
    degraded_divergence = divergence_half_angle_rad(1.0e-6, 1.0e-3, 2.0)
    ideal_rayleigh = rayleigh_range_m(1.0e-6, 1.0e-3, 1.0)
    degraded_rayleigh = rayleigh_range_m(1.0e-6, 1.0e-3, 2.0)

    assert degraded_divergence == pytest.approx(2.0 * ideal_divergence)
    assert degraded_rayleigh == pytest.approx(0.5 * ideal_rayleigh)


def test_beam_state_builds_right_handed_immutable_frame() -> None:
    beam = _beam(direction=[0.0, 0.0, 2.0], transverse_x_axis=[2.0, 0.0, 0.1])

    assert beam.direction == pytest.approx([0.0, 0.0, 1.0])
    assert np.dot(beam.direction, beam.transverse_x_axis) == pytest.approx(0.0, abs=1e-15)
    assert np.cross(beam.transverse_x_axis, beam.transverse_y_axis) == pytest.approx(
        beam.direction
    )
    with pytest.raises(ValueError):
        beam.origin_m[0] = 1.0


def test_zero_power_beam_state_is_valid_and_has_zero_irradiance() -> None:
    beam = _beam(power_w=0.0)

    profile = beam.sample_profile(grid_size=51)

    assert beam.irradiance(0.0, 0.0) == 0.0
    assert profile.integrated_power_w == 0.0
    assert profile.relative_power_error == 0.0


def test_free_space_propagation_updates_plane_q_and_path_length() -> None:
    beam = _beam()
    propagated = beam.propagate_free_space(0.25)

    assert propagated.origin_m == pytest.approx([0.0, 0.0, 0.25])
    assert propagated.distance_from_waist_m == pytest.approx(0.25)
    assert propagated.optical_path_length_m == pytest.approx(0.25)
    assert propagated.q_x_m.real == pytest.approx(0.25)
    assert propagated.q_x_m.imag == pytest.approx(beam.rayleigh_range_x_m)
    assert beam.origin_m == pytest.approx([0.0, 0.0, 0.0])


def test_second_moment_free_space_matches_gaussian_radius_and_m2() -> None:
    waist = 0.4e-3
    wavelength = 1.55e-6
    m2 = 1.7
    distance = 0.8
    moments = SecondMoment1D.from_waist(waist, wavelength, m2).propagate(distance)

    assert moments.radius_m == pytest.approx(
        gaussian_radius_m(distance, wavelength, waist, m2),
        rel=1e-14,
    )
    assert moments.m2 == pytest.approx(m2, rel=1e-14)


def test_gaussian_irradiance_integrates_to_requested_power() -> None:
    beam = _beam(
        waist_radius_x_m=3.0e-3,
        waist_radius_y_m=0.25e-3,
        profile_kind="line_gaussian",
    )

    profile = beam.sample_profile(distance_m=0.2, grid_size=401, extent_radii=4.0)

    assert profile.integrated_power_w == pytest.approx(beam.power_w, rel=1e-10)
    assert profile.relative_power_error < 1e-9

    with pytest.raises(ValueError, match="홀수"):
        beam.sample_profile(grid_size=100)


def test_field_amplitude_weight_squared_matches_normalized_irradiance() -> None:
    beam = _beam()
    x = np.asarray([0.0, 0.5e-3, 1.0e-3])
    amplitude = beam.amplitude_weight(x, np.zeros_like(x))
    irradiance = beam.irradiance(x, np.zeros_like(x))

    assert irradiance / irradiance[0] == pytest.approx(amplitude**2)


def test_project_source_builds_expected_fiber_waist(project_root: Path) -> None:
    project = load_project(project_root / "configs" / "project.yaml")

    beam = build_source_beam(project)

    assert beam.profile_kind == "circular_gaussian"
    assert beam.waist_radius_x_m == pytest.approx(5.0e-6)
    assert beam.power_w == pytest.approx(0.01)
    assert beam.origin_m == pytest.approx([0.0, 0.0, -0.1])


def test_line_beam_example_loads_as_explicit_numerical_preset(project_root: Path) -> None:
    project = load_project(project_root / "configs" / "line_beam_project.example.yaml")

    beam = build_source_beam(project)

    assert beam.profile_kind == "line_gaussian"
    assert beam.waist_radius_x_m == pytest.approx(3.0e-3)
    assert beam.waist_radius_y_m == pytest.approx(0.25e-3)

    report = build_phase1_beam_report(
        project,
        beam,
        z_max_m=0.02,
        sample_count=11,
        grid_size=51,
    )
    assert report.summary["overall_status"] == "warning"
    assert report.summary["paraxial_validity_status"] == "pass"


def test_phase1_report_is_schema_valid_and_audits_power(project_root: Path) -> None:
    project = load_project(project_root / "configs" / "project.yaml")
    report = build_phase1_beam_report(
        project,
        z_max_m=0.02,
        sample_count=21,
        grid_size=201,
        created_at=datetime(2026, 7, 4, tzinfo=UTC),
    )

    SchemaStore.load(project_root / "schemas").validate(
        report.to_dict(),
        "phase1_beam_report.schema.json",
        source="test Phase 1 report",
    )
    assert report.manifest["created_at_utc"] == "2026-07-04T00:00:00Z"
    assert report.profile_audit["status"] == "pass"
    assert report.profile_audit["grid_convergence_relative_error"] < 1e-12
    assert report.profile_audit["truncation_relative_error"] < 1e-12
    assert report.analytical_checks["status"] == "pass"
    assert report.analytical_checks["check_scope"] == "internal_consistency_only"
    assert report.analytical_checks["external_validation_status"] == "not_evaluated"
    assert report.accuracy["hardware_readiness"] == "analytical_only"
    assert report.accuracy["paraxial_validity"]["status"] == "warning"
    assert report.propagation["samples"][-1]["radius_x_m"] == pytest.approx(
        0.00197352763,
        rel=1e-8,
    )


def test_phase1_beam_view_writes_png(project_root: Path, tmp_path: Path) -> None:
    project = load_project(project_root / "configs" / "project.yaml")
    beam = build_source_beam(project)

    result = render_beam_view(
        beam,
        tmp_path / "beam.png",
        z_max_m=0.02,
        sample_count=21,
        grid_size=101,
        dpi=72,
    )

    assert result.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert result.stat().st_size > 10_000


def test_phase1_report_rejects_unvalidated_low_precision(project_root: Path) -> None:
    project = load_project(project_root / "configs" / "project.yaml")
    scenario = deep_thaw(project.active_scenario)
    scenario["simulation"]["real_dtype"] = "float32"

    with pytest.raises(ValueError, match="numpy, real_dtype=float64"):
        build_phase1_beam_report(
            SimpleNamespace(active_scenario=scenario),
            _beam(),
            z_max_m=0.1,
        )
