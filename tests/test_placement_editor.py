from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from lidarsim.config import load_project
from lidarsim.geometry import resolve_assembly
from lidarsim.ui import create_placement_variant


def test_create_absolute_placement_variant_validates(copied_project: Path) -> None:
    config_dir = copied_project.parent
    result = create_placement_variant(
        project_path=copied_project,
        element_id="scan_mirror",
        scenario_id="mirror_shift",
        scenario_output=config_dir / "mirror_shift.yaml",
        project_output=config_dir / "mirror_shift_project.yaml",
        translation_m=(0.1, 0.0, 0.0),
    )

    project = load_project(result.project_path)
    assembly = resolve_assembly(project.active_scenario, project.catalog)

    assert result.changed_fields == ("translation_m",)
    assert project.active_scenario["scenario_id"] == "mirror_shift"
    assert assembly["scan_mirror"].T_world_from_component.translation_m.tolist() == pytest.approx(
        [0.1, 0.0, 0.0]
    )


def test_create_port_placement_variant_accepts_unit_strings(
    copied_project: Path,
) -> None:
    config_dir = copied_project.parent
    result = create_placement_variant(
        project_path=copied_project,
        element_id="collimator",
        scenario_id="collimator_gap_25mm",
        scenario_output=config_dir / "collimator_gap_25mm.yaml",
        project_output=config_dir / "collimator_gap_25mm_project.yaml",
        axial_gap_m="25 mm",
    )

    project = load_project(result.project_path)
    assembly = resolve_assembly(project.active_scenario, project.catalog)

    assert result.changed_fields == ("axial_gap_m",)
    assert project.active_scenario["optical_assembly"]["elements"][1]["placement"][
        "axial_gap_m"
    ] == pytest.approx(0.025)
    assert assembly["collimator"].T_world_from_component.translation_m.tolist() == pytest.approx(
        [0.0, 0.0, -0.075]
    )


def test_create_placement_variant_rejects_wrong_mode_edit(
    copied_project: Path,
) -> None:
    config_dir = copied_project.parent
    with pytest.raises(ValueError, match="port placement"):
        create_placement_variant(
            project_path=copied_project,
            element_id="collimator",
            scenario_id="bad_variant",
            scenario_output=config_dir / "bad_variant.yaml",
            project_output=config_dir / "bad_variant_project.yaml",
            translation_m=(0.0, 0.0, 0.0),
        )


def test_placement_variant_project_points_to_only_variant_scenario(
    copied_project: Path,
) -> None:
    config_dir = copied_project.parent
    result = create_placement_variant(
        project_path=copied_project,
        element_id="scan_mirror",
        scenario_id="mirror_z_offset",
        scenario_output=config_dir / "mirror_z_offset.yaml",
        project_output=config_dir / "mirror_z_offset_project.yaml",
        translation_m=(0.0, 0.0, 0.01),
    )

    project_yaml = yaml.safe_load(result.project_path.read_text(encoding="utf-8"))

    assert project_yaml["active_baseline"] == "mirror_z_offset"
    assert project_yaml["experiments"] == []
    assert project_yaml["scenarios"] == ["mirror_z_offset.yaml"]


def test_placement_variant_supports_nested_ui_runs_directory(
    copied_project: Path,
) -> None:
    output_dir = copied_project.parent / "ui_runs"
    result = create_placement_variant(
        project_path=copied_project,
        element_id="scan_mirror",
        scenario_id="nested_mirror_shift",
        scenario_output=output_dir / "nested_mirror_shift.yaml",
        project_output=output_dir / "nested_mirror_shift_project.yaml",
        translation_m=(0.05, 0.0, 0.0),
    )

    project = load_project(result.project_path)
    assembly = resolve_assembly(project.active_scenario, project.catalog)

    assert project.project_path.parent == output_dir
    assert assembly["scan_mirror"].T_world_from_component.translation_m.tolist() == pytest.approx(
        [0.05, 0.0, 0.0]
    )


def test_placement_variant_rejects_project_outside_configs_layout(
    project_root: Path,
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="schemas"):
        create_placement_variant(
            project_path=project_root / "configs" / "project.yaml",
            element_id="scan_mirror",
            scenario_id="bad_layout",
            scenario_output=tmp_path / "bad_layout.yaml",
            project_output=tmp_path / "bad_layout_project.yaml",
            translation_m=(0.0, 0.0, 0.01),
        )
