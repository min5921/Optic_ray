from __future__ import annotations

from dataclasses import replace
import math
from pathlib import Path
from types import MappingProxyType

import numpy as np
import pytest

from lidarsim.config import load_project
from lidarsim.config.immutable import deep_freeze, deep_thaw
from lidarsim.optics import propagate_transmitter_train
from lidarsim.receiver import (
    evaluate_project_reciprocal_return,
    evaluate_project_reciprocal_return_power,
)
from lidarsim.receiver.return_power import estimate_reciprocal_return_power
from lidarsim.results import build_phase2_optical_train_report
from lidarsim.scene import evaluate_target_footprints, resolve_mixed_target_visibility


def _estimate(**overrides):
    values = {
        "power_on_target_w": 0.010,
        "target_reflectivity": 0.20,
        "target_normal": [0.0, 0.0, 1.0],
        "target_hit_m": [0.0, 0.0, 0.0],
        "mirror_hit_m": [0.0, 0.0, 10.0],
        "mirror_surface_normal": [0.0, 0.0, -1.0],
        "mirror_clear_width_m": 0.020,
        "mirror_clear_height_m": 0.010,
        "mirror_aperture_status": "pass",
        "mirror_aperture_transmission_fraction": 0.90,
        "mirror_power_reflectivity": 0.80,
        "collimator_aperture_status": "pass",
        "collimator_aperture_transmission_fraction": 0.95,
        "reverse_collimator_transmission": 0.75,
    }
    values.update(overrides)
    return estimate_reciprocal_return_power(**values)


def _project_return_inputs(project_root: Path):
    project = load_project(project_root / "configs" / "project.yaml")
    train = propagate_transmitter_train(project)
    footprints = evaluate_target_footprints(project, train.final_state.state)
    footprints, _ = resolve_mixed_target_visibility(footprints, ())
    geometry = evaluate_project_reciprocal_return(project, train, footprints)
    assert geometry.path is not None
    return project, footprints, geometry


def test_positive_lambertian_return_power_matches_reference_formula() -> None:
    result = _estimate()

    projected_area = 0.020 * 0.010
    target_to_mirror = 0.010 * 0.20 / math.pi * projected_area / 10.0**2
    expected_fiber_plane = target_to_mirror * 0.90 * 0.80 * 0.95 * 0.75

    assert result.status == "pass"
    assert result.projected_mirror_area_m2 == pytest.approx(projected_area)
    assert result.power_at_return_mirror_w == pytest.approx(target_to_mirror)
    assert result.power_at_return_collimator_w == pytest.approx(
        result.power_after_return_mirror_w
    )
    assert result.power_at_fiber_plane_w == pytest.approx(expected_fiber_plane)
    assert result.power_at_fiber_plane_w > 0.0
    assert result.target_to_fiber_plane_link_loss_db is not None
    assert math.isfinite(result.target_to_fiber_plane_link_loss_db)
    assert [entry.mechanism for entry in result.power_ledger] == [
        "lambertian_target_to_mirror_acceptance",
        "return_mirror_aperture",
        "return_mirror_reflectivity",
        "return_collimator_aperture",
        "reverse_collimator_transmission",
        "fiber_reference_plane_geometry",
    ]
    assert any("Exact spatial aperture" in item for item in result.assumptions)


def test_target_and_mirror_tilt_cosines_are_each_applied_exactly_once() -> None:
    reference = _estimate(
        mirror_aperture_transmission_fraction=1.0,
        mirror_power_reflectivity=1.0,
        collimator_aperture_transmission_fraction=1.0,
        reverse_collimator_transmission=1.0,
    )
    sixty_degree_normal = [math.sqrt(3.0) / 2.0, 0.0, 0.5]
    target_tilted = _estimate(
        target_normal=sixty_degree_normal,
        mirror_aperture_transmission_fraction=1.0,
        mirror_power_reflectivity=1.0,
        collimator_aperture_transmission_fraction=1.0,
        reverse_collimator_transmission=1.0,
    )
    mirror_tilted = _estimate(
        mirror_surface_normal=sixty_degree_normal,
        mirror_aperture_transmission_fraction=1.0,
        mirror_power_reflectivity=1.0,
        collimator_aperture_transmission_fraction=1.0,
        reverse_collimator_transmission=1.0,
    )
    both_tilted = _estimate(
        target_normal=sixty_degree_normal,
        mirror_surface_normal=sixty_degree_normal,
        mirror_aperture_transmission_fraction=1.0,
        mirror_power_reflectivity=1.0,
        collimator_aperture_transmission_fraction=1.0,
        reverse_collimator_transmission=1.0,
    )

    assert target_tilted.target_to_mirror_cosine == pytest.approx(0.5)
    assert target_tilted.power_at_return_mirror_w == pytest.approx(
        reference.power_at_return_mirror_w * 0.5
    )
    assert mirror_tilted.mirror_incidence_cosine == pytest.approx(0.5)
    assert mirror_tilted.projected_mirror_area_m2 == pytest.approx(
        reference.mirror_clear_area_m2 * 0.5
    )
    assert mirror_tilted.power_at_return_mirror_w == pytest.approx(
        reference.power_at_return_mirror_w * 0.5
    )
    assert both_tilted.power_at_return_mirror_w == pytest.approx(
        reference.power_at_return_mirror_w * 0.25
    )


def test_baseline_reciprocal_return_matches_analytical_reference_values() -> None:
    result = _estimate(
        power_on_target_w=0.009999973410842097,
        target_normal=[-1.0, 0.0, 0.0],
        target_hit_m=[10.0, 0.0, 0.0],
        mirror_hit_m=[0.0, 0.0, 0.0],
        mirror_surface_normal=[
            -math.sqrt(0.5),
            0.0,
            math.sqrt(0.5),
        ],
        mirror_clear_width_m=0.020,
        mirror_clear_height_m=0.020,
        mirror_aperture_transmission_fraction=1.0,
        mirror_power_reflectivity=1.0,
        collimator_aperture_transmission_fraction=1.0,
        reverse_collimator_transmission=1.0,
    )

    assert result.projected_mirror_area_m2 == pytest.approx(
        2.82842712474619e-4,
        rel=1.0e-14,
    )
    assert result.target_to_mirror_fraction == pytest.approx(
        1.8006326323142125e-7,
        rel=1.0e-14,
    )
    assert result.power_at_return_mirror_w == pytest.approx(
        1.8006278445836738e-9,
        rel=1.0e-14,
    )
    assert result.power_at_fiber_plane_w == pytest.approx(
        1.8006278445836738e-9,
        rel=1.0e-14,
    )
    assert result.target_to_fiber_plane_link_loss_db == pytest.approx(
        67.44574883534182,
        rel=1.0e-14,
    )


def test_project_baseline_uses_binary_return_apertures_not_forward_clipping(
    project_root: Path,
) -> None:
    report = build_phase2_optical_train_report(
        load_project(project_root / "configs" / "project.yaml")
    )
    result = report.reciprocal_return["return_power"]
    assert result is not None

    forward_aperture_fractions = [
        entry["transmission_fraction"]
        for entry in report.optical_train["power_ledger"]
        if entry["mechanism"]
        in {"circular_aperture_clipping", "mirror_rectangular_aperture"}
    ]
    return_aperture_entries = [
        entry
        for entry in result["power_ledger"]
        if entry["mechanism"]
        in {"return_mirror_aperture", "return_collimator_aperture"}
    ]

    assert any(fraction < 1.0 for fraction in forward_aperture_fractions)
    assert [entry["transmission_fraction"] for entry in return_aperture_entries] == [
        1.0,
        1.0,
    ]
    assert result["power_at_return_mirror_w"] == pytest.approx(
        1.8006278445836738e-9,
        rel=1.0e-14,
    )
    assert result["power_at_fiber_plane_w"] == pytest.approx(
        1.8006278445836738e-9,
        rel=1.0e-14,
    )
    assert result["target_to_fiber_plane_link_loss_db"] == pytest.approx(
        67.44574883534182,
        rel=1.0e-14,
    )


@pytest.mark.parametrize("miss_plane", ["mirror", "collimator", "fiber"])
def test_project_geometry_miss_preserves_upstream_power_without_teleport(
    project_root: Path,
    miss_plane: str,
) -> None:
    project, footprints, geometry = _project_return_inputs(project_root)
    assert geometry.path is not None
    path = geometry.path

    if miss_plane == "mirror":
        path = replace(
            path,
            mirror_hit=replace(path.mirror_hit, aperture_status="miss"),
            terminated=True,
            termination_reason="return_mirror:outside_clear_aperture",
        )
    elif miss_plane == "collimator":
        assert path.collimator_hit is not None
        path = replace(
            path,
            collimator_hit=replace(path.collimator_hit, aperture_status="miss"),
            terminated=True,
            termination_reason="return_collimator:outside_clear_aperture",
        )
    else:
        assert path.fiber_hit is not None
        fiber_miss = replace(
            path.fiber_hit.intersection,
            hit=False,
            miss_reason="parallel_to_plane",
            distance_m=None,
            point_m=None,
        )
        path = replace(
            path,
            fiber_hit=replace(
                path.fiber_hit,
                intersection=fiber_miss,
                aperture_status="no_intersection",
            ),
            terminated=True,
            termination_reason="fiber_reference:parallel_to_plane",
        )

    evaluated = evaluate_project_reciprocal_return_power(
        project,
        footprints,
        replace(geometry, path=path, status="terminated"),
    )
    assert evaluated.status == "terminated"
    assert evaluated.result is not None
    result = evaluated.result
    assert result.energy_check_status == "pass"
    assert result.power_at_return_mirror_w > 0.0
    if miss_plane == "mirror":
        assert result.power_after_return_mirror_aperture_w == 0.0
    elif miss_plane == "collimator":
        assert result.power_at_return_collimator_w > 0.0
        assert result.power_after_return_collimator_aperture_w == 0.0
    else:
        assert result.power_after_return_collimator_w > 0.0
    assert result.power_at_fiber_plane_w == 0.0


def test_project_rejects_mismatched_r1_and_footprint_target_hits(
    project_root: Path,
) -> None:
    project, footprints, geometry = _project_return_inputs(project_root)
    assert geometry.path is not None
    shifted_hit = np.array(geometry.path.target_hit_m, dtype=np.float64, copy=True)
    shifted_hit[1] += 1.0e-3
    shifted_hit.setflags(write=False)
    shifted_geometry = replace(
        geometry,
        path=replace(geometry.path, target_hit_m=shifted_hit),
    )

    evaluated = evaluate_project_reciprocal_return_power(
        project,
        footprints,
        shifted_geometry,
    )

    assert evaluated.status == "not_evaluated"
    assert evaluated.result is None
    assert evaluated.target_hit_residual_m == pytest.approx(1.0e-3)
    assert evaluated.target_hit_residual_m > evaluated.target_hit_tolerance_m


def test_project_non_lambertian_and_stl_targets_remain_not_evaluated(
    project_root: Path,
) -> None:
    project, footprints, geometry = _project_return_inputs(project_root)
    material_ref = str(project.active_scenario["scene"]["targets"][0]["material_ref"])
    material_entry = project.catalog[material_ref]
    material_data = deep_thaw(material_entry.data)
    material_data["optical"]["model"] = "not_implemented_brdf"
    catalog_entries = dict(project.catalog.entries)
    catalog_entries[material_ref] = replace(
        material_entry,
        data=deep_freeze(material_data),
    )
    non_lambertian_project = replace(
        project,
        catalog=replace(
            project.catalog,
            entries=MappingProxyType(catalog_entries),
        ),
    )

    unsupported = evaluate_project_reciprocal_return_power(
        non_lambertian_project,
        footprints,
        geometry,
    )
    assert unsupported.status == "unsupported_material"
    assert unsupported.result is None
    unsupported_report = build_phase2_optical_train_report(non_lambertian_project)
    assert unsupported_report.reciprocal_return["return_power"] is None
    assert unsupported_report.summary["power_at_return_mirror_w"] is None
    assert unsupported_report.summary["power_at_return_collimator_w"] is None
    assert unsupported_report.summary["power_at_fiber_plane_w"] is None

    stl_scenario = deep_thaw(project.active_scenario)
    stl_scenario["scene"]["targets"][0]["geometry"] = {
        "type": "stl_asset",
        "asset_ref": "audit:geometry_only",
    }
    scenarios = dict(project.scenarios)
    scenarios[str(project.project["active_baseline"])] = deep_freeze(stl_scenario)
    stl_project = replace(project, scenarios=MappingProxyType(scenarios))
    stl_result = evaluate_project_reciprocal_return_power(
        stl_project,
        footprints,
        geometry,
    )
    assert stl_result.status == "not_evaluated"
    assert stl_result.geometry_type == "stl_asset"
    assert stl_result.result is None


def test_mirror_center_ray_aperture_rejection_terminates_power_path() -> None:
    result = _estimate(mirror_aperture_status="miss")

    assert result.status == "terminated"
    assert result.termination_reason == "return_mirror_aperture_rejected"
    assert result.power_at_return_mirror_w > 0.0
    assert result.power_after_return_mirror_aperture_w == 0.0
    assert result.power_after_return_mirror_w == 0.0
    assert result.power_at_fiber_plane_w == 0.0
    assert result.power_ledger[1].status == "rejected"


def test_collimator_center_ray_aperture_rejection_terminates_power_path() -> None:
    result = _estimate(collimator_aperture_status="no_intersection")

    assert result.status == "terminated"
    assert result.termination_reason == "return_collimator_aperture_rejected"
    assert result.power_after_return_mirror_w > 0.0
    assert result.power_after_return_collimator_aperture_w == 0.0
    assert result.power_at_fiber_plane_w == 0.0
    assert result.power_ledger[3].status == "rejected"


def test_fiber_reference_plane_miss_terminates_without_teleport() -> None:
    result = _estimate(fiber_plane_status="no_intersection")

    assert result.status == "terminated"
    assert result.termination_reason == "fiber_reference_plane_geometry_rejected"
    assert result.power_after_return_collimator_w > 0.0
    assert result.power_at_fiber_plane_w == 0.0
    assert result.power_ledger[-1].mechanism == "fiber_reference_plane_geometry"
    assert result.power_ledger[-1].status == "rejected"


@pytest.mark.parametrize(
    ("override", "zero_mechanism"),
    [
        ({"target_reflectivity": 0.0}, "lambertian_target_to_mirror_acceptance"),
        ({"mirror_aperture_transmission_fraction": 0.0}, "return_mirror_aperture"),
        ({"mirror_power_reflectivity": 0.0}, "return_mirror_reflectivity"),
        (
            {"collimator_aperture_transmission_fraction": 0.0},
            "return_collimator_aperture",
        ),
        ({"reverse_collimator_transmission": 0.0}, "reverse_collimator_transmission"),
    ],
)
def test_zero_fractional_transmission_is_valid_and_returns_zero(
    override: dict[str, float],
    zero_mechanism: str,
) -> None:
    result = _estimate(**override)

    entry = next(
        item for item in result.power_ledger if item.mechanism == zero_mechanism
    )
    assert entry.transmission_fraction == 0.0
    assert entry.output_power_w == 0.0
    assert result.power_at_fiber_plane_w == 0.0
    assert result.status == "zero_power"


def test_return_power_ledger_conserves_energy_at_every_stage() -> None:
    result = _estimate()

    previous_output = None
    for entry in result.power_ledger:
        if previous_output is not None:
            assert entry.input_power_w == pytest.approx(previous_output, abs=1.0e-18)
        assert entry.input_power_w - entry.loss_w == pytest.approx(
            entry.output_power_w,
            abs=1.0e-18,
        )
        previous_output = entry.output_power_w

    assert result.maximum_energy_residual_w <= result.energy_tolerance_w
    assert result.energy_check_status == "pass"
    assert result.power_at_fiber_plane_w <= result.power_on_target_w
    serialized = result.to_dict()
    assert serialized["energy_check_status"] == "pass"
    assert len(serialized["power_ledger"]) == 6


def test_large_nearby_mirror_is_energy_clamped_with_explicit_warning() -> None:
    result = _estimate(
        target_reflectivity=1.0,
        mirror_hit_m=[0.0, 0.0, 0.01],
        mirror_clear_width_m=10.0,
        mirror_clear_height_m=10.0,
        mirror_aperture_transmission_fraction=1.0,
        mirror_power_reflectivity=1.0,
        collimator_aperture_transmission_fraction=1.0,
        reverse_collimator_transmission=1.0,
    )

    assert result.raw_target_to_mirror_fraction > 1.0
    assert result.target_to_mirror_fraction == 1.0
    assert result.power_at_fiber_plane_w == result.power_on_target_w
    assert any("solid-angle" in warning for warning in result.warnings)


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"power_on_target_w": -1.0}, "power_on_target_w"),
        ({"power_on_target_w": math.nan}, "power_on_target_w"),
        ({"target_reflectivity": 1.01}, "target_reflectivity"),
        ({"mirror_clear_width_m": 0.0}, "mirror_clear_width_m"),
        ({"mirror_power_reflectivity": -0.01}, "mirror_power_reflectivity"),
        ({"reverse_collimator_transmission": 1.01}, "reverse_collimator_transmission"),
        ({"mirror_aperture_status": "unknown"}, "mirror_aperture_status"),
        ({"target_normal": [0.0, 0.0, 0.0]}, "target_normal"),
        ({"mirror_hit_m": [0.0, 0.0, 0.0]}, "서로 다른 점"),
    ],
)
def test_invalid_return_power_inputs_are_rejected(
    override: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        _estimate(**override)
