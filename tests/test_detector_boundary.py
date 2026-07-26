from __future__ import annotations

import math

import pytest

from lidarsim.receiver.detector_boundary import apply_duplexer_detector_boundary


def _boundary(**overrides):
    values = {
        "power_coupled_into_fiber_w": 2.0e-6,
        "power_on_target_w": 2.0e-3,
        "return_power_transmission": 0.8,
        "duplexer_type": "ideal_circulator",
    }
    values.update(overrides)
    return apply_duplexer_detector_boundary(**values)


def test_unity_transmission_preserves_power_and_has_zero_link_loss() -> None:
    result = _boundary(return_power_transmission=1.0)

    assert result.power_at_detector_input_w == pytest.approx(2.0e-6)
    assert result.power_lost_in_duplexer_w == pytest.approx(0.0)
    assert result.fiber_coupled_to_detector_input_link_loss_db == pytest.approx(0.0)
    assert result.target_to_detector_input_link_loss_db == pytest.approx(30.0)
    assert result.status == "pass"
    assert result.energy_check_status == "pass"


def test_configurable_duplexer_loss_scales_power_and_reports_db() -> None:
    result = _boundary(
        duplexer_type="fiber_coupler",
        return_power_transmission=0.25,
    )

    assert result.power_at_detector_input_w == pytest.approx(0.5e-6)
    assert result.power_lost_in_duplexer_w == pytest.approx(1.5e-6)
    assert result.fiber_coupled_to_detector_input_link_loss_db == pytest.approx(
        -10.0 * math.log10(0.25)
    )
    assert result.target_to_detector_input_link_loss_db == pytest.approx(
        -10.0 * math.log10(0.5e-6 / 2.0e-3)
    )
    assert result.power_ledger[0].mechanism == "duplexer_return_transmission"
    assert result.power_ledger[0].input_plane == "coupled_fiber_mode"
    assert result.power_ledger[0].output_plane == "detector_input_plane"


def test_zero_transmission_blocks_detector_input_with_explicit_status() -> None:
    result = _boundary(return_power_transmission=0.0)

    assert result.power_at_detector_input_w == 0.0
    assert result.power_lost_in_duplexer_w == pytest.approx(2.0e-6)
    assert result.fiber_coupled_to_detector_input_link_loss_db is None
    assert result.target_to_detector_input_link_loss_db is None
    assert result.status == "blocked"
    assert result.power_ledger[0].status == "blocked"
    assert any("0" in warning and "dB" in warning for warning in result.warnings)


def test_zero_input_is_valid_and_does_not_invent_link_loss() -> None:
    result = _boundary(
        power_coupled_into_fiber_w=0.0,
        power_on_target_w=0.0,
        return_power_transmission=0.7,
    )

    assert result.power_at_detector_input_w == 0.0
    assert result.power_lost_in_duplexer_w == 0.0
    assert result.fiber_coupled_to_detector_input_link_loss_db is None
    assert result.target_to_detector_input_link_loss_db is None
    assert result.status == "zero_input"
    assert result.power_ledger[0].status == "zero_input"
    assert result.energy_check_status == "pass"


@pytest.mark.parametrize("transmission", (0.0, 0.17, 1.0))
def test_power_ledger_satisfies_input_minus_loss_equals_output(
    transmission: float,
) -> None:
    result = _boundary(return_power_transmission=transmission)
    entry = result.power_ledger[0]

    assert entry.input_power_w - entry.loss_w == pytest.approx(entry.output_power_w)
    assert entry.output_power_w == pytest.approx(
        entry.input_power_w * entry.transmission_fraction
    )
    assert result.maximum_energy_residual_w <= result.energy_tolerance_w
    assert result.energy_check_status == "pass"


@pytest.mark.parametrize("transmission", (0.0, 0.25, 1.0))
def test_complex_field_amplitude_is_scaled_by_square_root_of_power_transmission(
    transmission: float,
) -> None:
    input_field = 1.0e-3 + 1.0e-3j
    result = _boundary(
        field_at_fiber_output_sqrt_w=input_field,
        return_power_transmission=transmission,
    )

    assert result.field_at_fiber_output_sqrt_w == input_field
    assert result.field_at_detector_input_sqrt_w == pytest.approx(
        math.sqrt(transmission) * input_field
    )
    assert abs(result.field_at_detector_input_sqrt_w) ** 2 == pytest.approx(
        result.power_at_detector_input_w
    )
    payload = result.to_dict()
    assert payload["field_at_fiber_output_sqrt_w"]["power_w"] == pytest.approx(
        result.power_coupled_into_fiber_w
    )
    assert payload["field_at_detector_input_sqrt_w"]["power_w"] == pytest.approx(
        result.power_at_detector_input_w
    )
    assert payload["field_at_detector_input_sqrt_w"][
        "magnitude_sqrt_w"
    ] == pytest.approx(abs(result.field_at_detector_input_sqrt_w))


def test_zero_power_accepts_only_exact_zero_complex_field() -> None:
    result = _boundary(
        power_coupled_into_fiber_w=0.0,
        power_on_target_w=0.0,
        field_at_fiber_output_sqrt_w=0.0j,
        return_power_transmission=0.4,
    )

    assert result.field_at_fiber_output_sqrt_w == 0.0j
    assert result.field_at_detector_input_sqrt_w == 0.0j
    assert result.power_at_detector_input_w == 0.0

    with pytest.raises(ValueError, match=r"abs\(field\)\*\*2"):
        _boundary(
            power_coupled_into_fiber_w=0.0,
            power_on_target_w=0.0,
            field_at_fiber_output_sqrt_w=1.0e-30 + 0.0j,
            energy_tolerance_w=1.0,
        )


def test_zero_target_power_rejects_any_positive_fiber_power() -> None:
    with pytest.raises(ValueError, match="초과"):
        _boundary(
            power_coupled_into_fiber_w=1.0e-30,
            power_on_target_w=0.0,
            energy_tolerance_w=1.0,
        )


@pytest.mark.parametrize(
    "duplexer_type",
    ("ideal_circulator", "fiber_coupler", "free_space_beamsplitter"),
)
def test_supported_duplexer_types_match_scenario_contract(duplexer_type: str) -> None:
    result = _boundary(duplexer_type=duplexer_type)

    assert result.duplexer_type == duplexer_type


@pytest.mark.parametrize("legacy_name", ("circulator", "ideal_coupler", "coupler"))
def test_non_schema_legacy_duplexer_names_are_rejected(legacy_name: str) -> None:
    with pytest.raises(ValueError, match="다음 중 하나"):
        _boundary(duplexer_type=legacy_name)


def test_serialized_link_loss_names_identify_both_reference_planes() -> None:
    payload = _boundary().to_dict()

    assert "fiber_coupled_to_detector_input_link_loss_db" in payload
    assert "target_to_detector_input_link_loss_db" in payload
    assert "fiber_to_detector_link_loss_db" not in payload
    assert "target_to_detector_link_loss_db" not in payload


def test_power_only_api_leaves_field_boundary_explicitly_absent() -> None:
    result = _boundary()

    assert result.field_at_fiber_output_sqrt_w is None
    assert result.field_at_detector_input_sqrt_w is None
    assert result.to_dict()["field_at_detector_input_sqrt_w"] is None
    assert any("photocurrent" in assumption for assumption in result.assumptions)


@pytest.mark.parametrize(
    ("overrides", "match"),
    [
        ({"power_coupled_into_fiber_w": -1.0}, "0 이상"),
        ({"power_coupled_into_fiber_w": math.inf}, "유한"),
        ({"return_power_transmission": -0.1}, "0 이상 1 이하"),
        ({"return_power_transmission": 1.1}, "0 이상 1 이하"),
        ({"return_power_transmission": math.nan}, "유한"),
        ({"duplexer_type": "beamsplitter_unknown"}, "다음 중 하나"),
        ({"detector_model": ""}, "빈 문자열"),
        ({"model_source": " "}, "빈 문자열"),
        ({"energy_tolerance_w": 0.0}, "0보다 큰"),
        ({"power_on_target_w": -1.0}, "0 이상"),
        (
            {
                "power_coupled_into_fiber_w": 2.0e-3,
                "power_on_target_w": 1.0e-3,
            },
            "초과",
        ),
        ({"field_at_fiber_output_sqrt_w": complex(math.inf, 0.0)}, "유한"),
        ({"field_at_fiber_output_sqrt_w": 1.0e-3 + 0.0j}, r"abs\(field\)\*\*2"),
    ],
)
def test_invalid_boundary_inputs_are_rejected(
    overrides: dict[str, object],
    match: str,
) -> None:
    with pytest.raises(ValueError, match=match):
        _boundary(**overrides)
