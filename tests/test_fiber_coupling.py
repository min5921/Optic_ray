from __future__ import annotations

import cmath
import math

import pytest

from lidarsim.receiver.fiber_coupling import (
    GaussianModeAtPlane,
    estimate_single_mode_fiber_coupling,
)


WAVELENGTH_M = 1.55e-6
MODE_RADIUS_M = 5.0e-6


def _coupling(
    receive_mode: GaussianModeAtPlane,
    fiber_mode: GaussianModeAtPlane | None = None,
    *,
    power_w: float = 0.01,
    input_field_sqrt_w: complex | None = None,
):
    return estimate_single_mode_fiber_coupling(
        available_power_at_fiber_plane_w=power_w,
        wavelength_m=WAVELENGTH_M,
        receive_mode=receive_mode,
        fiber_mode=(
            GaussianModeAtPlane.circular(MODE_RADIUS_M)
            if fiber_mode is None
            else fiber_mode
        ),
        input_field_amplitude_sqrt_w=input_field_sqrt_w,
    )


def test_aligned_identical_modes_have_unit_efficiency_without_inventing_field() -> None:
    mode = GaussianModeAtPlane.circular(MODE_RADIUS_M)

    result = _coupling(mode, mode, power_w=0.04)

    assert result.normalized_field_overlap == pytest.approx(1.0 + 0.0j, abs=1e-15)
    assert result.fiber_coupling_efficiency == pytest.approx(1.0, abs=1e-15)
    assert result.input_field_amplitude_sqrt_w is None
    assert result.coupled_field_amplitude_sqrt_w is None
    assert result.coherent_field_status == "not_provided"
    assert result.power_coupled_into_fiber_w == pytest.approx(0.04)
    assert result.status == "pass"
    assert result.model_scope == "deterministic_gaussian_to_gaussian_only"
    assert result.input_power_interpretation == (
        "power_carried_by_declared_deterministic_gaussian_receive_mode"
    )
    assert any("deterministic Gaussian" in warning for warning in result.warnings)
    assert any("zero phase" in warning for warning in result.warnings)


def test_explicit_coherent_input_preserves_field_power_separation() -> None:
    mode = GaussianModeAtPlane.circular(MODE_RADIUS_M)
    input_field = cmath.rect(math.sqrt(0.04), 0.7)

    result = _coupling(
        mode,
        mode,
        power_w=0.04,
        input_field_sqrt_w=input_field,
    )

    assert result.input_field_amplitude_sqrt_w == pytest.approx(input_field)
    assert result.coupled_field_amplitude_sqrt_w == pytest.approx(input_field)
    assert result.coherent_field_status == "evaluated"
    assert abs(result.coupled_field_amplitude_sqrt_w) ** 2 == pytest.approx(
        result.power_coupled_into_fiber_w,
        rel=1e-14,
    )


def test_mode_field_diameter_uses_gaussian_one_e2_intensity_convention() -> None:
    mode = GaussianModeAtPlane.from_mode_field_diameter((10.0e-6, 12.0e-6))

    assert mode.mode_radius_x_m == pytest.approx(5.0e-6)
    assert mode.mode_radius_y_m == pytest.approx(6.0e-6)
    assert mode.mode_field_diameter_x_m == pytest.approx(10.0e-6)
    assert mode.to_dict()["mode_field_diameter_y_m"] == pytest.approx(12.0e-6)


def test_circular_mode_size_mismatch_matches_analytical_overlap() -> None:
    receive_radius = 8.0e-6
    fiber_radius = 5.0e-6
    receive = GaussianModeAtPlane.circular(receive_radius)
    fiber = GaussianModeAtPlane.circular(fiber_radius)
    expected = (
        2.0
        * receive_radius
        * fiber_radius
        / (receive_radius * receive_radius + fiber_radius * fiber_radius)
    ) ** 2

    result = _coupling(receive, fiber)

    assert result.fiber_coupling_efficiency == pytest.approx(expected, rel=1e-14)
    assert 0.0 <= result.fiber_coupling_efficiency <= 1.0


def test_mode_size_mismatch_is_monotonic_away_from_match_and_symmetric() -> None:
    fiber = GaussianModeAtPlane.circular(MODE_RADIUS_M)
    receive_radii = tuple(
        ratio * MODE_RADIUS_M for ratio in (1.0, 1.25, 2.0, 4.0)
    )
    efficiencies = [
        _coupling(GaussianModeAtPlane.circular(radius), fiber).fiber_coupling_efficiency
        for radius in receive_radii
    ]

    assert efficiencies == sorted(efficiencies, reverse=True)
    receive = GaussianModeAtPlane.circular(2.0 * MODE_RADIUS_M)
    swapped = _coupling(fiber, receive)
    assert swapped.fiber_coupling_efficiency == pytest.approx(
        _coupling(receive, fiber).fiber_coupling_efficiency,
        rel=1e-14,
    )


def test_lateral_mismatch_reduces_coupling_monotonically() -> None:
    offsets = (0.0, 0.25 * MODE_RADIUS_M, 0.75 * MODE_RADIUS_M, MODE_RADIUS_M)
    efficiencies = [
        _coupling(
            GaussianModeAtPlane.circular(
                MODE_RADIUS_M,
                center_offset_m=(offset, 0.0),
            )
        ).fiber_coupling_efficiency
        for offset in offsets
    ]

    assert efficiencies == sorted(efficiencies, reverse=True)
    assert efficiencies[-1] == pytest.approx(math.exp(-1.0), rel=1e-14)


def test_angular_mismatch_reduces_coupling_monotonically() -> None:
    angular_scale = WAVELENGTH_M / (math.pi * MODE_RADIUS_M)
    angles = (0.0, 0.1 * angular_scale, 0.4 * angular_scale, angular_scale)
    efficiencies = [
        _coupling(
            GaussianModeAtPlane.circular(
                MODE_RADIUS_M,
                angular_offset_rad=(angle, 0.0),
            )
        ).fiber_coupling_efficiency
        for angle in angles
    ]

    assert efficiencies == sorted(efficiencies, reverse=True)
    assert efficiencies[-1] == pytest.approx(math.exp(-1.0), rel=1e-14)


def test_combined_lateral_and_angular_overlap_matches_analytical_complex_value() -> None:
    lateral_offset = 0.6 * MODE_RADIUS_M
    angular_offset = 0.35 * WAVELENGTH_M / (math.pi * MODE_RADIUS_M)
    wave_number = math.tau / WAVELENGTH_M
    expected = cmath.exp(
        -lateral_offset**2 / (2.0 * MODE_RADIUS_M**2)
        - (wave_number * MODE_RADIUS_M * angular_offset) ** 2 / 8.0
        + 0.5j * wave_number * lateral_offset * angular_offset
    )
    receive = GaussianModeAtPlane.circular(
        MODE_RADIUS_M,
        center_offset_m=(lateral_offset, 0.0),
        angular_offset_rad=(angular_offset, 0.0),
    )

    result = _coupling(receive)

    assert result.normalized_field_overlap == pytest.approx(expected, rel=1e-14)
    assert result.fiber_coupling_efficiency == pytest.approx(abs(expected) ** 2)


def test_focus_and_wavefront_mismatch_reduce_coupling() -> None:
    waist = GaussianModeAtPlane.from_waist_at_plane(
        MODE_RADIUS_M,
        wavelength_m=WAVELENGTH_M,
    )
    rayleigh_range = math.pi * MODE_RADIUS_M**2 / WAVELENGTH_M
    displaced_focus = GaussianModeAtPlane.from_waist_at_plane(
        MODE_RADIUS_M,
        wavelength_m=WAVELENGTH_M,
        distance_from_waist_m=rayleigh_range,
    )

    aligned = _coupling(waist, waist)
    mismatched = _coupling(displaced_focus, waist)

    assert displaced_focus.mode_radius_x_m == pytest.approx(
        math.sqrt(2.0) * MODE_RADIUS_M
    )
    assert displaced_focus.wavefront_radius_x_m == pytest.approx(2.0 * rayleigh_range)
    assert 0.0 < mismatched.fiber_coupling_efficiency < aligned.fiber_coupling_efficiency


def test_focus_mismatch_reduces_coupling_monotonically_with_waist_distance() -> None:
    fiber = GaussianModeAtPlane.from_waist_at_plane(
        MODE_RADIUS_M,
        wavelength_m=WAVELENGTH_M,
    )
    rayleigh_range = math.pi * MODE_RADIUS_M**2 / WAVELENGTH_M
    distances = tuple(scale * rayleigh_range for scale in (0.0, 0.25, 0.5, 1.0, 2.0))
    efficiencies = [
        _coupling(
            GaussianModeAtPlane.from_waist_at_plane(
                MODE_RADIUS_M,
                wavelength_m=WAVELENGTH_M,
                distance_from_waist_m=distance,
            ),
            fiber,
        ).fiber_coupling_efficiency
        for distance in distances
    ]

    assert efficiencies == sorted(efficiencies, reverse=True)


def test_identical_elliptical_modes_share_unit_overlap_in_common_frame() -> None:
    mode = GaussianModeAtPlane(
        mode_radius_x_m=4.0e-6,
        mode_radius_y_m=7.0e-6,
        center_offset_x_m=1.2e-6,
        center_offset_y_m=-0.8e-6,
        angle_x_rad=2.0e-3,
        angle_y_rad=-1.0e-3,
        wavefront_radius_x_m=0.03,
        wavefront_radius_y_m=-0.05,
    )

    result = _coupling(mode, mode)

    assert result.normalized_field_overlap == pytest.approx(1.0 + 0.0j, abs=1e-14)
    assert result.fiber_coupling_efficiency == pytest.approx(1.0, abs=1e-14)


def test_zero_available_power_without_field_does_not_invent_zero_phase() -> None:
    mode = GaussianModeAtPlane.circular(MODE_RADIUS_M)

    result = _coupling(mode, mode, power_w=0.0)

    assert result.fiber_coupling_efficiency == pytest.approx(1.0)
    assert result.available_power_at_fiber_plane_w == 0.0
    assert result.input_field_amplitude_sqrt_w is None
    assert result.coupled_field_amplitude_sqrt_w is None
    assert result.coherent_field_status == "not_provided"
    assert result.power_coupled_into_fiber_w == 0.0
    assert result.status == "zero_available_power"


def test_explicit_zero_field_is_preserved_as_an_evaluated_coherent_input() -> None:
    mode = GaussianModeAtPlane.circular(MODE_RADIUS_M)

    result = _coupling(mode, mode, power_w=0.0, input_field_sqrt_w=0.0j)

    assert result.input_field_amplitude_sqrt_w == 0.0j
    assert result.coupled_field_amplitude_sqrt_w == 0.0j
    assert result.coherent_field_status == "evaluated"


def test_result_to_dict_keeps_overlap_power_and_optional_field_distinct() -> None:
    input_field = cmath.rect(math.sqrt(0.01), -0.4)
    result = _coupling(
        GaussianModeAtPlane.circular(
            MODE_RADIUS_M,
            center_offset_m=(1.0e-6, -0.5e-6),
            angular_offset_rad=(1.0e-3, 0.0),
        ),
        input_field_sqrt_w=input_field,
    )

    payload = result.to_dict()

    assert payload["normalized_field_overlap"]["magnitude"] == pytest.approx(
        abs(result.normalized_field_overlap)
    )
    assert "power_w" not in payload["normalized_field_overlap"]
    assert payload["input_field_amplitude_sqrt_w"]["power_w"] == pytest.approx(0.01)
    assert payload["coupled_field_amplitude_sqrt_w"]["power_w"] == pytest.approx(
        payload["power_coupled_into_fiber_w"],
        rel=1e-14,
    )
    assert payload["fiber_coupling_efficiency"] == pytest.approx(
        abs(result.normalized_field_overlap) ** 2
    )


def test_result_to_dict_uses_null_for_unavailable_coherent_field() -> None:
    payload = _coupling(GaussianModeAtPlane.circular(MODE_RADIUS_M)).to_dict()

    assert payload["input_field_amplitude_sqrt_w"] is None
    assert payload["coupled_field_amplitude_sqrt_w"] is None
    assert payload["coherent_field_status"] == "not_provided"


@pytest.mark.parametrize(
    ("factory", "match"),
    [
        (lambda: GaussianModeAtPlane.circular(0.0), "0보다 큰"),
        (
            lambda: GaussianModeAtPlane.from_mode_field_diameter((1.0e-5,)),
            "길이 2",
        ),
        (
            lambda: GaussianModeAtPlane.circular(
                MODE_RADIUS_M,
                wavefront_radius_m=0.0,
            ),
            "0일 수 없습니다",
        ),
    ],
)
def test_invalid_mode_contract_is_rejected(factory, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        factory()


def test_negative_available_power_is_rejected() -> None:
    mode = GaussianModeAtPlane.circular(MODE_RADIUS_M)

    with pytest.raises(ValueError, match="0 이상"):
        _coupling(mode, mode, power_w=-1.0)


@pytest.mark.parametrize(
    ("power_w", "input_field", "match"),
    [
        (0.01, complex(math.nan, 0.0), "유한"),
        (0.01, 0.2 + 0.0j, r"abs\(field\)\*\*2"),
        (0.0, 1.0e-30 + 0.0j, r"abs\(field\)\*\*2"),
    ],
)
def test_invalid_or_power_inconsistent_coherent_field_is_rejected(
    power_w: float,
    input_field: complex,
    match: str,
) -> None:
    mode = GaussianModeAtPlane.circular(MODE_RADIUS_M)

    with pytest.raises(ValueError, match=match):
        _coupling(
            mode,
            mode,
            power_w=power_w,
            input_field_sqrt_w=input_field,
        )
