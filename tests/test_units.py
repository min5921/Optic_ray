from __future__ import annotations

import math

import pytest

from lidarsim.config.units import resolve_quantities
from lidarsim.errors import ConfigValidationError


def test_resolve_quantities_converts_to_si_and_radians() -> None:
    resolved = resolve_quantities(
        {
            "wavelength_m": "1550 nm",
            "optical_power_w": "10 mW",
            "angle_rad": "5 deg",
            "frequency_hz": "10 Hz",
            "position_m": ["20 mm", 0, "1 m"],
        },
        source="test.yaml",
    )

    assert resolved["wavelength_m"] == pytest.approx(1.55e-6)
    assert resolved["optical_power_w"] == pytest.approx(0.01)
    assert resolved["angle_rad"] == pytest.approx(math.radians(5))
    assert resolved["frequency_hz"] == pytest.approx(10.0)
    assert resolved["position_m"] == pytest.approx([0.02, 0.0, 1.0])


def test_resolve_quantities_reports_incompatible_unit_with_field_path() -> None:
    with pytest.raises(ConfigValidationError) as captured:
        resolve_quantities(
            {"source": {"wavelength_m": "10 mW"}},
            source="bad.yaml",
        )

    diagnostic = captured.value.diagnostics[0]
    assert diagnostic.source == "bad.yaml"
    assert diagnostic.path == "source.wavelength_m"
    assert "Cannot convert" in diagnostic.message
