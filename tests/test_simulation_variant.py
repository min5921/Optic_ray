from __future__ import annotations

import math
from pathlib import Path

import pytest

from lidarsim.config import load_project
from lidarsim.errors import ConfigValidationError
from lidarsim.geometry import resolve_assembly
from lidarsim.ui import (
    AssemblyElementEdits,
    SimulationParameterEdits,
    create_simulation_variant,
)


def test_simulation_variant_combines_parameters_and_placement(
    copied_project: Path,
) -> None:
    output_dir = copied_project.parent / "ui_runs"
    result = create_simulation_variant(
        project_path=copied_project,
        scenario_id="ui_target_12m",
        scenario_output=output_dir / "ui_target_12m.yaml",
        project_output=output_dir / "ui_target_12m_project.yaml",
        parameter_edits=SimulationParameterEdits(
            optical_power_w="8 mW",
            scanner_static_command_angle_rad="1 deg",
            scanner_rotation_axis_world=(0.0, 0.999, 0.0447),
            target_id="target_plane",
            target_center_m=("12 m", "0 m", "0 m"),
            target_width_axis=(0.0, 0.0, 1.0),
            receiver_aperture_diameter_m="30 mm",
        ),
        element_edits=AssemblyElementEdits(
            element_id="scan_mirror",
            translation_m=(0.01, 0.0, 0.0),
        ),
    )

    project = load_project(result.project_path)
    scenario = project.active_scenario
    assembly = resolve_assembly(scenario, project.catalog)

    assert result.project_path.parent == output_dir
    assert result.config_hash == project.config_hash
    assert scenario["source"]["optical_power_w"] == pytest.approx(0.008)
    assert scenario["source"]["catalog_parameter_policy"] == "explicit_override"
    assert scenario["scanner"]["static_command_angle_rad"] == pytest.approx(math.radians(1.0))
    assert scenario["scanner"]["rotation_axis_world"] == pytest.approx([0.0, 0.999, 0.0447])
    assert scenario["scene"]["targets"][0]["geometry"]["center_m"] == pytest.approx(
        [12.0, 0.0, 0.0]
    )
    assert scenario["scene"]["targets"][0]["geometry"]["width_axis"] == pytest.approx(
        [0.0, 0.0, 1.0]
    )
    assert scenario["receiver"]["aperture_diameter_m"] == pytest.approx(0.03)
    assert assembly["scan_mirror"].T_world_from_component.translation_m.tolist() == pytest.approx(
        [0.01, 0.0, 0.0]
    )
    assert "source.optical_power_w" in result.changed_fields
    assert any("width_axis" in path for path in result.changed_fields)
    assert any("translation_m" in path for path in result.changed_fields)


def test_simulation_variant_rolls_back_invalid_files(copied_project: Path) -> None:
    output_dir = copied_project.parent / "ui_runs"
    scenario_path = output_dir / "invalid_receiver.yaml"
    project_path = output_dir / "invalid_receiver_project.yaml"

    with pytest.raises(ConfigValidationError, match="optical_efficiency"):
        create_simulation_variant(
            project_path=copied_project,
            scenario_id="invalid_receiver",
            scenario_output=scenario_path,
            project_output=project_path,
            parameter_edits=SimulationParameterEdits(receiver_optical_efficiency=1.5),
        )

    assert not scenario_path.exists()
    assert not project_path.exists()


def test_simulation_variant_can_swap_compatible_component(copied_project: Path) -> None:
    output_dir = copied_project.parent / "ui_runs"
    result = create_simulation_variant(
        project_path=copied_project,
        scenario_id="collimator_f35",
        scenario_output=output_dir / "collimator_f35.yaml",
        project_output=output_dir / "collimator_f35_project.yaml",
        parameter_edits=SimulationParameterEdits(scanner_static_command_angle_rad="0.5 deg"),
        element_edits=AssemblyElementEdits(
            element_id="collimator",
            component_ref="custom:ideal_collimator_f35",
        ),
    )

    project = load_project(result.project_path)

    assert project.active_scenario["optical_assembly"]["elements"][1][
        "component_ref"
    ] == "custom:ideal_collimator_f35"
    assert any("component_ref" in path for path in result.changed_fields)


def test_simulation_variant_requires_a_real_edit(copied_project: Path) -> None:
    output_dir = copied_project.parent / "ui_runs"

    with pytest.raises(ValueError, match="달라진"):
        create_simulation_variant(
            project_path=copied_project,
            scenario_id="no_change",
            scenario_output=output_dir / "no_change.yaml",
            project_output=output_dir / "no_change_project.yaml",
            parameter_edits=SimulationParameterEdits(),
        )


def test_simulation_variant_rejects_unsafe_scenario_id_before_writing(
    copied_project: Path,
) -> None:
    escaped_scenario = copied_project.parent / "escaped.yaml"

    with pytest.raises(ValueError, match="scenario_id"):
        create_simulation_variant(
            project_path=copied_project,
            scenario_id="../escaped",
            scenario_output=escaped_scenario,
            project_output=copied_project.parent / "escaped_project.yaml",
            parameter_edits=SimulationParameterEdits(scanner_static_command_angle_rad="1 deg"),
        )

    assert not escaped_scenario.exists()
    assert not (copied_project.parent / "escaped_project.yaml").exists()
