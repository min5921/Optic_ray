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
    propagate_transmitter_train,
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


def test_phase2_train_reaches_scanner_input_with_lens_and_power_ledger(project_root: Path) -> None:
    project = load_project(project_root / "configs" / "project.yaml")

    train = propagate_transmitter_train(project)

    assert train.optical_path_id == "transmit_main"
    assert train.states[0].label == "source.output"
    assert train.final_state.label == "scan_mirror.origin"
    assert len(train.component_reports) == 1
    assert train.component_reports[0]["model"] == "ideal_thin_lens"
    assert train.unsupported_elements[0]["component_type"] == "scanner_mirror"
    assert [entry.mechanism for entry in train.power_ledger] == [
        "free_space_propagation",
        "circular_aperture_clipping",
        "component_power_transmission",
        "free_space_propagation",
    ]

    collimator_output = train.component_reports[0]["output_beam_state"]
    assert collimator_output["waist_radius_x_m"] == pytest.approx(0.00197352129, rel=1e-8)
    assert train.final_state.state.power_w == pytest.approx(0.01, rel=1e-5)
    assert train.final_state.state.radius_x_m == pytest.approx(0.00197358, rel=1e-4)


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
