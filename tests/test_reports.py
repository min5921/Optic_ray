from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from lidarsim.config import load_project
from lidarsim.config.schema import SchemaStore
from lidarsim.results import build_phase0_report, write_review_html
from lidarsim.visualization import render_placement_view


def test_phase0_report_is_schema_valid_and_does_not_claim_uncomputed_power(
    project_root: Path,
) -> None:
    project = load_project(project_root / "configs" / "project.yaml")
    report = build_phase0_report(
        project,
        created_at=datetime(2026, 6, 29, 0, 0, tzinfo=UTC),
    )
    report_data = report.to_dict()

    SchemaStore.load(project_root / "schemas").validate(
        report_data,
        "phase0_report.schema.json",
        source="test report",
    )
    assert report.manifest.config_hash == project.config_hash
    assert report.manifest.created_at_utc == "2026-06-29T00:00:00Z"
    assert report.accuracy.confidence_level == "comparative"
    assert report.accuracy.calibration_status == "uncalibrated"
    assert report.accuracy.model_purpose == "analytical_regression"
    assert report.accuracy.hardware_readiness == "analytical_only"
    assert report.accuracy.receiver_model == "virtual_monostatic/virtual_aperture"
    assert report.energy_ledger.status == "not_evaluated"
    assert report.energy_ledger.source_power_w == pytest.approx(0.01)
    assert report.energy_ledger.entries == ()
    assert report.energy_ledger.conservation_residual_w is None
    assert report.convergence.overall_status == "warning"
    assert report.placement["elements"]["collimator"]["translation_world_m"] == pytest.approx(
        [0.0, 0.0, -0.08]
    )


def test_phase0_report_records_model_assumptions_and_numerical_checks(
    project_root: Path,
) -> None:
    project = load_project(project_root / "configs" / "project.yaml")

    report = build_phase0_report(project)

    assert report.accuracy.component_model_levels == {
        "source": "ideal",
        "collimator": "paraxial_specification",
        "scan_mirror": "ideal",
    }
    assert any("target target_plane" in assumption for assumption in report.accuracy.assumptions)
    checks = {check.check_id: check for check in report.convergence.checks}
    assert checks["transform_orthonormality"].status == "pass"
    assert checks["transform_determinant"].status == "pass"
    assert checks["port_axis_norm"].status == "pass"
    assert checks["port_angular_alignment"].status == "pass"
    assert checks["beam_physics_convergence"].status == "not_evaluated"


def test_phase0_1_html_review_is_self_contained(
    project_root: Path,
    tmp_path: Path,
) -> None:
    project = load_project(project_root / "configs" / "project.yaml")
    report = build_phase0_report(project)
    image_path = render_placement_view(project, tmp_path / "placement.png", dpi=72)

    result = write_review_html(project, report, image_path, tmp_path / "review.html")

    document = result.read_text(encoding="utf-8")
    assert "Phase 0.1 LiDAR setup review" in document
    assert "analytical_only" in document
    assert "virtual_monostatic/virtual_aperture" in document
    assert "data:image/png;base64," in document
    assert "이 Phase 0.1 review 자체는 배치·설정 검증만 수행" in document
    assert "lidarsim optical-train" in document
    assert "reference_only" in document
