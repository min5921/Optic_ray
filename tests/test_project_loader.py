from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from lidarsim.config import load_project
from lidarsim.errors import ConfigValidationError


def _read_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _write_yaml(path: Path, value: dict) -> None:
    path.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")


def test_load_repository_project_resolves_and_freezes_config(project_root: Path) -> None:
    project = load_project(project_root / "configs" / "project.yaml")

    assert project.project["project_id"] == "optic_ray_default"
    assert len(project.scenarios) == 1
    assert len(project.experiments) == 1
    assert project.catalog.count("component") == 4
    assert project.catalog.count("material") == 1
    assert len(project.config_hash) == 64

    baseline = project.active_scenario
    assert baseline["source"]["wavelength_m"] == pytest.approx(1.55e-6)
    assert baseline["source"]["optical_power_w"] == pytest.approx(0.01)
    assert baseline["scanner"]["mechanical_amplitude_rad"] == pytest.approx(0.0872664626)
    assert (
        project.experiments["wavelength_and_collimator_comparison"]["sweeps"][0]["values"][0]
        == pytest.approx(1.31e-6)
    )

    with pytest.raises(TypeError):
        baseline["source"]["wavelength_m"] = 1.0


def test_display_preferences_do_not_change_physical_hash(copied_project: Path) -> None:
    before = load_project(copied_project).config_hash
    raw_project = _read_yaml(copied_project)
    raw_project["display_units"]["length"] = "cm"
    raw_project["ui"]["language"] = "en"
    _write_yaml(copied_project, raw_project)

    after = load_project(copied_project).config_hash
    assert after == before


def test_unknown_component_reference_is_rejected(copied_project: Path) -> None:
    scenario_path = copied_project.parent / "baseline_1550nm.yaml"
    scenario = _read_yaml(scenario_path)
    scenario["optical_assembly"]["elements"][1]["component_ref"] = "custom:missing"
    _write_yaml(scenario_path, scenario)

    with pytest.raises(ConfigValidationError) as captured:
        load_project(copied_project)

    assert any(
        diagnostic.path == "optical_assembly.elements[1].component_ref"
        and "Unknown component" in diagnostic.message
        for diagnostic in captured.value.diagnostics
    )


def test_unknown_schema_field_is_rejected(copied_project: Path) -> None:
    scenario_path = copied_project.parent / "baseline_1550nm.yaml"
    scenario = _read_yaml(scenario_path)
    scenario["source"]["typo_power"] = 12
    _write_yaml(scenario_path, scenario)

    with pytest.raises(ConfigValidationError) as captured:
        load_project(copied_project)

    assert any(
        diagnostic.path == "source" and "Additional properties" in diagnostic.message
        for diagnostic in captured.value.diagnostics
    )


def test_invalid_port_reference_is_rejected(copied_project: Path) -> None:
    scenario_path = copied_project.parent / "baseline_1550nm.yaml"
    scenario = _read_yaml(scenario_path)
    scenario["optical_assembly"]["elements"][1]["placement"]["connect_from"] = "source.bad_port"
    _write_yaml(scenario_path, scenario)

    with pytest.raises(ConfigValidationError) as captured:
        load_project(copied_project)

    assert any("has no port 'bad_port'" in item.message for item in captured.value.diagnostics)
