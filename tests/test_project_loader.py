from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from lidarsim.config import load_project
from lidarsim.config.immutable import deep_thaw
from lidarsim.errors import ConfigValidationError
from lidarsim.geometry import resolve_assembly


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
    assert len(project.assets.meshes) == 0
    assert len(project.assets.measurements) == 0
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


def test_cyclic_port_placement_is_rejected_during_project_validation(
    copied_project: Path,
) -> None:
    scenario_path = copied_project.parent / "baseline_1550nm.yaml"
    scenario = _read_yaml(scenario_path)
    scenario["optical_assembly"]["elements"][0]["placement"] = {
        "mode": "port",
        "connect_from": "collimator.output",
        "connect_to": "source.output",
    }
    _write_yaml(scenario_path, scenario)

    with pytest.raises(ConfigValidationError) as captured:
        load_project(copied_project)

    assert any("dependency" in item.message for item in captured.value.diagnostics)


def test_canonical_scenario_save_and_reload_preserves_hash_and_placement(
    copied_project: Path,
) -> None:
    before = load_project(copied_project)
    scenario_path = copied_project.parent / "baseline_1550nm.yaml"
    _write_yaml(scenario_path, deep_thaw(before.active_scenario))

    after = load_project(copied_project)
    assembly = resolve_assembly(after.active_scenario, after.catalog)

    assert after.config_hash == before.config_hash
    assert assembly["collimator"].T_world_from_component.translation_m == pytest.approx(
        (0.0, 0.0, -0.08)
    )


@pytest.mark.parametrize(
    ("path", "value", "message"),
    [
        (("source", "wavelength_m"), "-1550 nm", "0보다 큰 값"),
        (("source", "optical_power_w"), "-10 mW", "0보다 큰 값"),
        (("receiver", "aperture_diameter_m"), "-25 mm", "0보다 큰 값"),
    ],
)
def test_negative_physical_quantities_are_rejected(
    copied_project: Path,
    path: tuple[str, str],
    value: str,
    message: str,
) -> None:
    scenario_path = copied_project.parent / "baseline_1550nm.yaml"
    scenario = _read_yaml(scenario_path)
    scenario[path[0]][path[1]] = value
    _write_yaml(scenario_path, scenario)

    with pytest.raises(ConfigValidationError, match=message):
        load_project(copied_project)


def test_negative_target_size_is_rejected(copied_project: Path) -> None:
    scenario_path = copied_project.parent / "baseline_1550nm.yaml"
    scenario = _read_yaml(scenario_path)
    scenario["scene"]["targets"][0]["geometry"]["width_m"] = "-4 m"
    _write_yaml(scenario_path, scenario)

    with pytest.raises(ConfigValidationError, match="0보다 큰 값"):
        load_project(copied_project)


def test_source_wavelength_outside_catalog_validity_is_rejected(copied_project: Path) -> None:
    scenario_path = copied_project.parent / "baseline_1550nm.yaml"
    scenario = _read_yaml(scenario_path)
    scenario["source"]["wavelength_m"] = "2000 nm"
    _write_yaml(scenario_path, scenario)

    with pytest.raises(ConfigValidationError, match="validity range"):
        load_project(copied_project)


def test_wavelength_outside_downstream_component_validity_is_rejected(
    copied_project: Path,
) -> None:
    component_path = (
        copied_project.parent.parent
        / "catalog"
        / "components"
        / "custom"
        / "ideal_collimator_f20.yaml"
    )
    component = _read_yaml(component_path)
    component["validity"]["wavelength_range_m"] = ["1000 nm", "1400 nm"]
    _write_yaml(component_path, component)

    with pytest.raises(ConfigValidationError, match="element 'collimator'.*validity range"):
        load_project(copied_project)


def test_material_wavelength_mismatch_is_reported(copied_project: Path) -> None:
    material_path = (
        copied_project.parent.parent
        / "catalog"
        / "materials"
        / "custom"
        / "diffuse_gray_020.yaml"
    )
    material = _read_yaml(material_path)
    material["optical"]["wavelength_m"] = "1310 nm"
    _write_yaml(material_path, material)

    project = load_project(copied_project)

    assert any(
        item.path == "scene.targets[0].material_ref"
        and "scenario wavelength" in item.message
        for item in project.warnings
    )


def test_incompatible_port_interfaces_are_rejected(copied_project: Path) -> None:
    source_path = (
        copied_project.parent.parent
        / "catalog"
        / "components"
        / "custom"
        / "baseline_fiber_source.yaml"
    )
    source_record = _read_yaml(source_path)
    source_record["ports"][0]["interface_type"] = "fiber_fc_pc"
    _write_yaml(source_path, source_record)

    with pytest.raises(ConfigValidationError, match="Port interface"):
        load_project(copied_project)


def test_unknown_component_catalog_field_is_rejected(copied_project: Path) -> None:
    component_path = (
        copied_project.parent.parent
        / "catalog"
        / "components"
        / "custom"
        / "ideal_collimator_f20.yaml"
    )
    component = _read_yaml(component_path)
    component["typo_focal_lenght"] = "20 mm"
    _write_yaml(component_path, component)

    with pytest.raises(ConfigValidationError) as captured:
        load_project(copied_project)

    assert any("Additional properties" in item.message for item in captured.value.diagnostics)


def test_scanner_axis_must_lie_in_mirror_surface(copied_project: Path) -> None:
    component_path = (
        copied_project.parent.parent
        / "catalog"
        / "components"
        / "custom"
        / "ideal_scan_mirror_20mm.yaml"
    )
    component = _read_yaml(component_path)
    component["mechanical"]["default_rotation_axis_local"] = component["mechanical"][
        "surface_normal_local"
    ]
    _write_yaml(component_path, component)

    with pytest.raises(ConfigValidationError, match="surface normal과 수직"):
        load_project(copied_project)


def test_circular_profile_requires_equal_axis_parameters(copied_project: Path) -> None:
    scenario_path = copied_project.parent / "baseline_1550nm.yaml"
    scenario = _read_yaml(scenario_path)
    scenario["source"]["m2_y"] = 1.2
    _write_yaml(scenario_path, scenario)

    with pytest.raises(ConfigValidationError, match="x/y waist radius와 M²"):
        load_project(copied_project)


def test_catalog_nominal_mismatch_requires_explicit_override(copied_project: Path) -> None:
    scenario_path = copied_project.parent / "baseline_1550nm.yaml"
    scenario = _read_yaml(scenario_path)
    scenario["source"]["optical_power_w"] = "12 mW"
    _write_yaml(scenario_path, scenario)

    with pytest.raises(ConfigValidationError, match="catalog nominal과 다릅니다"):
        load_project(copied_project)

    scenario["source"]["catalog_parameter_policy"] = "explicit_override"
    _write_yaml(scenario_path, scenario)
    project = load_project(copied_project)
    assert any("명시적으로 override" in item.message for item in project.warnings)


def test_non_gaussian_mfd_definition_is_reported_as_approximation(
    copied_project: Path,
) -> None:
    scenario_path = copied_project.parent / "baseline_1550nm.yaml"
    scenario = _read_yaml(scenario_path)
    scenario["source"]["mode_field_diameter_definition"] = "petermann_ii"
    scenario["source"]["catalog_parameter_policy"] = "explicit_override"
    _write_yaml(scenario_path, scenario)

    project = load_project(copied_project)

    assert any("Gaussian 1/e^2" in item.message for item in project.warnings)
