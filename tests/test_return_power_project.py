from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
import yaml

from lidarsim.config import load_project
from lidarsim.config.schema import SchemaStore
from lidarsim.optics import propagate_transmitter_train
from lidarsim.receiver import (
    evaluate_project_reciprocal_return,
    evaluate_project_reciprocal_return_power,
)
from lidarsim.results import build_phase2_optical_train_report
from lidarsim.scene import evaluate_target_footprints


def _r2(project):
    train = propagate_transmitter_train(project)
    footprints = evaluate_target_footprints(project, train.final_state.state)
    geometry = evaluate_project_reciprocal_return(project, train, footprints)
    return (
        train,
        footprints,
        geometry,
        evaluate_project_reciprocal_return_power(project, footprints, geometry),
    )


def test_baseline_project_return_power_matches_analytical_reference(
    project_root: Path,
) -> None:
    project = load_project(project_root / "configs" / "project.yaml")
    train, _, _, evaluated = _r2(project)

    assert evaluated.status == "pass"
    assert evaluated.target_hit_residual_m == pytest.approx(0.0, abs=1.0e-15)
    assert evaluated.result is not None
    result = evaluated.result
    assert result.power_at_return_mirror_w == pytest.approx(
        1.8006278445836738e-9,
        rel=1.0e-12,
    )
    assert result.power_at_return_collimator_w == pytest.approx(
        result.power_after_return_mirror_w
    )
    assert result.power_at_fiber_plane_w == pytest.approx(
        1.8006278445836738e-9,
        rel=1.0e-12,
    )
    assert result.target_to_fiber_plane_link_loss_db == pytest.approx(
        67.44574883534182,
        rel=1.0e-12,
    )
    return_apertures = {
        entry.mechanism: entry
        for entry in result.power_ledger
        if entry.mechanism in {
            "return_mirror_aperture",
            "return_collimator_aperture",
        }
    }
    assert return_apertures["return_mirror_aperture"].transmission_fraction == 1.0
    assert return_apertures["return_collimator_aperture"].transmission_fraction == 1.0
    forward_collimator_clip = next(
        entry
        for entry in train.power_ledger
        if entry.mechanism == "circular_aperture_clipping"
    )
    assert forward_collimator_clip.transmission_fraction < 1.0
    assert result.energy_check_status == "pass"


@pytest.mark.parametrize("plane", ["collimator", "fiber"])
def test_actual_return_geometry_miss_zeroes_only_that_plane_and_downstream(
    project_root: Path,
    plane: str,
) -> None:
    project = load_project(project_root / "configs" / "project.yaml")
    _, footprints, geometry, _ = _r2(project)
    assert geometry.path is not None
    path = geometry.path

    if plane == "collimator":
        assert path.collimator_hit is not None
        missed_intersection = replace(
            path.collimator_hit.intersection,
            hit=False,
            miss_reason="parallel",
            distance_m=None,
            point_m=None,
        )
        missed_hit = replace(
            path.collimator_hit,
            intersection=missed_intersection,
            aperture_kind="not_evaluated",
            aperture_status="no_intersection",
            aperture_margin_m=None,
        )
        modified_path = replace(
            path,
            status="terminated",
            terminated=True,
            termination_reason="return_collimator:parallel",
            collimator_hit=missed_hit,
            fiber_hit=None,
        )
    else:
        assert path.fiber_hit is not None
        missed_intersection = replace(
            path.fiber_hit.intersection,
            hit=False,
            miss_reason="parallel",
            distance_m=None,
            point_m=None,
        )
        missed_hit = replace(
            path.fiber_hit,
            intersection=missed_intersection,
            aperture_kind="not_evaluated",
            aperture_status="no_intersection",
            aperture_margin_m=None,
        )
        modified_path = replace(
            path,
            status="terminated",
            terminated=True,
            termination_reason="fiber_reference:parallel",
            fiber_hit=missed_hit,
        )

    modified_geometry = replace(
        geometry,
        status="terminated",
        path=modified_path,
    )
    evaluated = evaluate_project_reciprocal_return_power(
        project,
        footprints,
        modified_geometry,
    )

    assert evaluated.status == "terminated"
    assert evaluated.result is not None
    result = evaluated.result
    assert result.power_at_return_mirror_w > 0.0
    assert result.power_at_return_collimator_w > 0.0
    assert result.power_at_fiber_plane_w == 0.0
    if plane == "collimator":
        assert result.power_after_return_collimator_aperture_w == 0.0
        assert result.termination_reason == "return_collimator_aperture_rejected"
    else:
        assert result.power_after_return_collimator_w > 0.0
        assert result.termination_reason == "fiber_reference_plane_geometry_rejected"


def test_r1_target_hit_mismatch_is_not_silently_replaced(
    project_root: Path,
) -> None:
    project = load_project(project_root / "configs" / "project.yaml")
    _, footprints, geometry, _ = _r2(project)
    assert geometry.path is not None
    shifted = np.array(geometry.path.target_hit_m, dtype=np.float64, copy=True)
    shifted[1] += 1.0e-3
    shifted.setflags(write=False)
    mismatched_geometry = replace(
        geometry,
        path=replace(geometry.path, target_hit_m=shifted),
    )

    evaluated = evaluate_project_reciprocal_return_power(
        project,
        footprints,
        mismatched_geometry,
    )

    assert evaluated.status == "not_evaluated"
    assert evaluated.result is None
    assert evaluated.target_hit_residual_m == pytest.approx(1.0e-3)
    assert evaluated.target_hit_residual_m > evaluated.target_hit_tolerance_m


def test_non_lambertian_material_is_structured_unsupported(
    copied_project: Path,
) -> None:
    material_path = (
        copied_project.parent.parent
        / "catalog"
        / "materials"
        / "custom"
        / "diffuse_gray_020.yaml"
    )
    material = yaml.safe_load(material_path.read_text(encoding="utf-8"))
    material["optical"]["model"] = "unsupported_test_brdf"
    material_path.write_text(
        yaml.safe_dump(material, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

    report = build_phase2_optical_train_report(load_project(copied_project))

    assert report.reciprocal_return["power_status"] == "unsupported_material"
    assert report.reciprocal_return["return_power"] is None
    assert report.summary["power_at_return_mirror_w"] is None
    assert report.summary["power_at_fiber_plane_w"] is None
    SchemaStore.load(copied_project.parent.parent / "schemas").validate(
        report.to_dict(),
        "phase2_optical_train_report.schema.json",
        source="unsupported R2 material report",
    )
