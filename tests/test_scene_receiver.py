from __future__ import annotations

import math

import pytest

from lidarsim.beam import BeamState
from lidarsim.receiver import estimate_lambertian_receiver_return
from lidarsim.scene import estimate_rectangle_plane_footprint, intersect_rectangle_plane


def _beam(**overrides) -> BeamState:
    values = {
        "time_s": 0.0,
        "origin_m": [0.0, 0.0, 0.0],
        "direction": [1.0, 0.0, 0.0],
        "transverse_x_axis": [0.0, 1.0, 0.0],
        "wavelength_m": 1.55e-6,
        "power_w": 0.01,
        "waist_radius_x_m": 1.0e-3,
        "waist_radius_y_m": 1.0e-3,
        "m2_x": 1.0,
        "m2_y": 1.0,
        "profile_kind": "circular_gaussian",
        "propagation_model": "gaussian_m2",
    }
    values.update(overrides)
    return BeamState(**values)


def _intersection(**overrides):
    values = {
        "beam": _beam(),
        "target_id": "target",
        "material_ref": "custom:diffuse_gray_020",
        "center_m": [10.0, 0.0, 0.0],
        "normal": [-1.0, 0.0, 0.0],
        "width_m": 4.0,
        "height_m": 4.0,
    }
    values.update(overrides)
    beam = values.pop("beam")
    return intersect_rectangle_plane(beam, **values)


def _material() -> dict:
    return {
        "optical": {
            "model": "lambertian",
            "hemispherical_reflectivity": 0.20,
        }
    }


def _receiver(**overrides) -> dict:
    values = {
        "architecture": "virtual_monostatic",
        "position_m": [0.0, 0.0, 0.0],
        "direction": [1.0, 0.0, 0.0],
        "aperture_diameter_m": 0.025,
        "full_fov_rad": math.radians(25.0),
        "optical_efficiency": 0.80,
    }
    values.update(overrides)
    return values


def test_rectangle_plane_center_hit_succeeds() -> None:
    hit = _intersection()

    assert hit.hit is True
    assert hit.hit_center_m == pytest.approx([10.0, 0.0, 0.0])
    assert hit.distance_to_target_m == pytest.approx(10.0)
    assert hit.incidence_angle_rad == pytest.approx(0.0)
    assert hit.local_coordinates_m == pytest.approx([0.0, 0.0])


def test_rectangle_plane_parallel_ray_misses() -> None:
    miss = _intersection(
        beam=_beam(direction=[0.0, 1.0, 0.0], transverse_x_axis=[1.0, 0.0, 0.0])
    )

    assert miss.hit is False
    assert miss.miss_reason == "parallel_to_plane"


def test_rectangle_plane_behind_ray_misses() -> None:
    miss = _intersection(center_m=[-10.0, 0.0, 0.0])

    assert miss.hit is False
    assert miss.miss_reason == "intersection_behind_beam"


def test_rectangle_plane_outside_bounds_misses() -> None:
    miss = _intersection(center_m=[10.0, 2.0, 0.0], width_m=1.0, height_m=1.0)

    assert miss.hit is False
    assert miss.miss_reason == "outside_rectangle_bounds"


def test_rectangle_plane_footprint_reports_power_and_area() -> None:
    beam = _beam()
    footprint = estimate_rectangle_plane_footprint(beam, _intersection(beam=beam))

    assert footprint.hit is True
    assert footprint.projected_footprint_major_radius_m is not None
    assert footprint.projected_footprint_minor_radius_m is not None
    assert footprint.approximate_footprint_area_m2 is not None
    assert footprint.peak_irradiance_w_m2 is not None
    assert footprint.projected_footprint_major_radius_m > 0.0
    assert footprint.projected_footprint_minor_radius_m > 0.0
    assert footprint.approximate_footprint_area_m2 > 0.0
    assert footprint.peak_irradiance_w_m2 > 0.0
    assert footprint.estimated_power_on_target_w == pytest.approx(beam.power_w, rel=1e-10)
    assert footprint.clipped_by_target_bounds is False


def test_oblique_footprint_expands_projected_major_axis() -> None:
    beam = _beam()
    normal = estimate_rectangle_plane_footprint(beam, _intersection(beam=beam))
    oblique_hit = _intersection(
        beam=beam,
        normal=[-math.sqrt(0.5), 0.0, math.sqrt(0.5)],
    )
    oblique = estimate_rectangle_plane_footprint(beam, oblique_hit)

    assert normal.projected_footprint_major_radius_m is not None
    assert oblique.projected_footprint_major_radius_m is not None
    assert oblique.projected_footprint_major_radius_m > normal.projected_footprint_major_radius_m
    assert oblique_hit.incidence_angle_rad == pytest.approx(math.pi / 4.0)


def test_lambertian_receiver_return_is_positive_inside_fov() -> None:
    beam = _beam()
    footprint = estimate_rectangle_plane_footprint(beam, _intersection(beam=beam))

    result = estimate_lambertian_receiver_return(
        footprint=footprint,
        material=_material(),
        receiver=_receiver(),
    )

    assert result.receiver_fov_status == "inside_fov"
    assert result.estimated_received_power_w > 0.0
    assert result.link_loss_db is not None
    assert math.isfinite(result.link_loss_db)
    assert any("fiber-coupled power가 아닙니다" in item for item in result.assumptions)


def test_lambertian_receiver_return_is_zero_outside_fov() -> None:
    beam = _beam()
    footprint = estimate_rectangle_plane_footprint(beam, _intersection(beam=beam))

    result = estimate_lambertian_receiver_return(
        footprint=footprint,
        material=_material(),
        receiver=_receiver(direction=[0.0, 1.0, 0.0]),
    )

    assert result.receiver_fov_status == "outside_fov"
    assert result.estimated_received_power_w == 0.0
    assert result.link_loss_db is None
