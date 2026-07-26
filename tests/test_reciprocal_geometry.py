from __future__ import annotations

import math

import numpy as np
import pytest

from lidarsim.geometry import RigidTransform
from lidarsim.receiver import ResolvedPlaneFrame, trace_reciprocal_center_ray


SQRT_HALF = math.sqrt(0.5)


def _baseline_planes(
    *,
    mirror_normal: tuple[float, float, float] = (-SQRT_HALF, 0.0, SQRT_HALF),
) -> tuple[ResolvedPlaneFrame, ResolvedPlaneFrame, ResolvedPlaneFrame]:
    mirror = ResolvedPlaneFrame(
        origin_m=np.zeros(3, dtype=np.float64),
        normal=np.asarray(mirror_normal, dtype=np.float64),
        x_axis=np.asarray([0.0, 1.0, 0.0], dtype=np.float64),
    )
    collimator = ResolvedPlaneFrame(
        origin_m=np.asarray([0.0, 0.0, -0.08], dtype=np.float64),
        normal=np.asarray([0.0, 0.0, 1.0], dtype=np.float64),
        x_axis=np.asarray([1.0, 0.0, 0.0], dtype=np.float64),
    )
    fiber = ResolvedPlaneFrame(
        origin_m=np.asarray([0.0, 0.0, -0.10], dtype=np.float64),
        normal=np.asarray([0.0, 0.0, 1.0], dtype=np.float64),
        x_axis=np.asarray([1.0, 0.0, 0.0], dtype=np.float64),
    )
    return mirror, collimator, fiber


def _trace_baseline(
    *,
    mirror: ResolvedPlaneFrame | None = None,
    mirror_width_m: float = 0.02,
    mirror_height_m: float = 0.02,
    collimator: ResolvedPlaneFrame | None = None,
    collimator_diameter_m: float | None = 0.01,
    fiber: ResolvedPlaneFrame | None = None,
):
    default_mirror, default_collimator, default_fiber = _baseline_planes()
    return trace_reciprocal_center_ray(
        target_hit_m=[10.0, 0.0, 0.0],
        transmit_mirror_hit_m=[0.0, 0.0, 0.0],
        transmit_incident_direction=[0.0, 0.0, 1.0],
        mirror_plane=default_mirror if mirror is None else mirror,
        mirror_clear_width_m=mirror_width_m,
        mirror_clear_height_m=mirror_height_m,
        collimator_receive_plane=(
            default_collimator if collimator is None else collimator
        ),
        collimator_receive_axis=[0.0, 0.0, -1.0],
        collimator_clear_aperture_diameter_m=collimator_diameter_m,
        fiber_reference_plane=default_fiber if fiber is None else fiber,
        fiber_receive_axis=[0.0, 0.0, -1.0],
        position_tolerance_m=1.0e-10,
        angular_tolerance_rad=1.0e-10,
    )


def test_exact_retrace_closes_at_mirror_collimator_and_fiber_planes() -> None:
    result = _trace_baseline()

    assert result.status == "pass"
    assert result.terminated is False
    assert result.return_incident_direction == pytest.approx([-1.0, 0.0, 0.0])
    assert result.mirror_hit.intersection.point_m == pytest.approx([0.0, 0.0, 0.0])
    assert result.mirror_hit.aperture_status == "pass"
    assert result.reflected_direction == pytest.approx([0.0, 0.0, -1.0], abs=1e-12)
    assert result.collimator_hit is not None
    assert result.collimator_hit.intersection.point_m == pytest.approx(
        [0.0, 0.0, -0.08], abs=1e-12
    )
    assert result.fiber_hit is not None
    assert result.fiber_hit.intersection.point_m == pytest.approx(
        [0.0, 0.0, -0.10], abs=1e-12
    )
    assert result.closure.maximum_position_residual_m == pytest.approx(0.0, abs=1e-14)
    assert result.closure.maximum_angular_residual_rad == pytest.approx(0.0, abs=1e-14)
    assert result.closure.status == "pass"
    assert result.to_dict()["model"] == "reciprocal_center_ray_geometry"

    with pytest.raises(ValueError):
        result.termination_point_m[0] = 1.0


def test_mirror_perturbation_changes_round_trip_angle_by_twice_mechanical_angle() -> None:
    mirror, _, _ = _baseline_planes()
    perturbation_rad = 1.0e-3
    rotation = RigidTransform.from_axis_angle([0.0, 1.0, 0.0], perturbation_rad)
    perturbed_mirror = ResolvedPlaneFrame(
        origin_m=mirror.origin_m,
        normal=rotation.transform_direction(mirror.normal),
        x_axis=rotation.transform_direction(mirror.x_axis),
    )

    result = _trace_baseline(mirror=perturbed_mirror)

    assert result.terminated is False
    assert result.status == "warning"
    assert result.closure.mirror_angular_residual_rad == pytest.approx(
        2.0 * perturbation_rad,
        rel=1e-9,
    )
    assert result.closure.collimator_angular_residual_rad == pytest.approx(
        2.0 * perturbation_rad,
        rel=1e-9,
    )
    assert result.closure.collimator_lateral_residual_m is not None
    assert result.closure.collimator_lateral_residual_m > 0.0
    assert any("closure residual" in warning for warning in result.warnings)


@pytest.mark.parametrize(
    ("plane", "reason"),
    [
        (
            ResolvedPlaneFrame(
                origin_m=np.asarray([0.0, 0.0, 1.0]),
                normal=np.asarray([0.0, 0.0, 1.0]),
                x_axis=np.asarray([1.0, 0.0, 0.0]),
            ),
            "return_mirror:parallel_to_plane",
        ),
        (
            ResolvedPlaneFrame(
                origin_m=np.asarray([11.0, 0.0, 0.0]),
                normal=np.asarray([1.0, 0.0, 0.0]),
                x_axis=np.asarray([0.0, 1.0, 0.0]),
            ),
            "return_mirror:intersection_behind_ray",
        ),
    ],
)
def test_parallel_or_behind_mirror_terminates_at_target_without_teleport(
    plane: ResolvedPlaneFrame,
    reason: str,
) -> None:
    result = _trace_baseline(mirror=plane)

    assert result.status == "terminated"
    assert result.terminated is True
    assert result.termination_reason == reason
    assert result.termination_point_m == pytest.approx([10.0, 0.0, 0.0])
    assert result.reflected_direction is None
    assert result.collimator_hit is None
    assert result.fiber_hit is None
    assert result.closure.status == "fail"


def test_mirror_aperture_miss_stops_at_actual_hit_without_recentering() -> None:
    mirror = ResolvedPlaneFrame(
        origin_m=np.asarray([0.0, 0.0, 0.0]),
        normal=np.asarray([0.0, 0.0, 1.0]),
        x_axis=np.asarray([1.0, 0.0, 0.0]),
    )
    _, collimator, fiber = _baseline_planes()

    result = trace_reciprocal_center_ray(
        target_hit_m=[1.0, 0.0, 1.0],
        transmit_mirror_hit_m=[0.02, 0.0, 0.0],
        transmit_incident_direction=[0.0, 0.0, -1.0],
        mirror_plane=mirror,
        mirror_clear_width_m=0.01,
        mirror_clear_height_m=0.01,
        collimator_receive_plane=collimator,
        collimator_receive_axis=[0.0, 0.0, -1.0],
        fiber_reference_plane=fiber,
        fiber_receive_axis=[0.0, 0.0, -1.0],
    )

    assert result.terminated is True
    assert result.termination_reason == "return_mirror:outside_clear_aperture"
    assert result.mirror_hit.aperture_status == "miss"
    assert result.mirror_hit.local_x_m == pytest.approx(0.02)
    assert result.termination_point_m == pytest.approx([0.02, 0.0, 0.0])
    assert result.termination_point_m != pytest.approx(mirror.origin_m)
    assert result.collimator_hit is None
    assert result.fiber_hit is None


def test_collimator_aperture_miss_stops_at_actual_plane_intersection() -> None:
    mirror, collimator, fiber = _baseline_planes()
    perturbation = RigidTransform.from_axis_angle([0.0, 1.0, 0.0], 0.02)
    perturbed_mirror = ResolvedPlaneFrame(
        origin_m=mirror.origin_m,
        normal=perturbation.transform_direction(mirror.normal),
        x_axis=perturbation.transform_direction(mirror.x_axis),
    )

    result = _trace_baseline(
        mirror=perturbed_mirror,
        collimator=collimator,
        collimator_diameter_m=1.0e-3,
        fiber=fiber,
    )

    assert result.terminated is True
    assert result.termination_reason == "return_collimator:outside_clear_aperture"
    assert result.collimator_hit is not None
    assert result.collimator_hit.aperture_status == "miss"
    actual_hit = result.collimator_hit.intersection.point_m
    assert actual_hit is not None
    assert result.termination_point_m == pytest.approx(actual_hit)
    assert result.termination_point_m != pytest.approx(collimator.origin_m)
    assert result.fiber_hit is None
