"""Validated parameter and placement variants for the browser UI."""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from lidarsim.config import load_project
from lidarsim.ui.placement_editor import (
    _apply_placement_updates,
    _ensure_writable,
    _find_active_scenario,
    _load_yaml,
    _quantity_arg,
    _relative_path,
    _relocated_project_paths,
    _validate_variant_project_layout,
)


QuantityInput = str | float | int
_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$")


@dataclass(frozen=True, slots=True)
class SimulationParameterEdits:
    """User-facing operating-point edits preserved with explicit units."""

    wavelength_m: QuantityInput | None = None
    optical_power_w: QuantityInput | None = None
    scanner_static_command_angle_rad: QuantityInput | None = None
    scanner_rotation_axis_world: tuple[float, float, float] | None = None
    scanner_mechanical_amplitude_rad: QuantityInput | None = None
    scanner_frequency_hz: QuantityInput | None = None
    scanner_waveform: str | None = None
    scanner_samples_per_line: int | None = None
    target_id: str | None = None
    target_center_m: tuple[QuantityInput, QuantityInput, QuantityInput] | None = None
    target_normal: tuple[float, float, float] | None = None
    target_width_axis: tuple[float, float, float] | None = None
    target_width_m: QuantityInput | None = None
    target_height_m: QuantityInput | None = None
    receiver_position_m: tuple[QuantityInput, QuantityInput, QuantityInput] | None = None
    receiver_direction: tuple[float, float, float] | None = None
    receiver_aperture_diameter_m: QuantityInput | None = None
    receiver_full_fov_rad: QuantityInput | None = None
    receiver_optical_efficiency: float | None = None


@dataclass(frozen=True, slots=True)
class AssemblyElementEdits:
    """Optional catalog and numeric placement edit for one assembly element."""

    element_id: str
    component_ref: str | None = None
    translation_m: tuple[float, float, float] | None = None
    quaternion_wxyz: tuple[float, float, float, float] | None = None
    axial_gap_m: QuantityInput | None = None
    transverse_offset_m: tuple[QuantityInput, QuantityInput] | None = None
    clocking_rad: QuantityInput | None = None
    angular_misalignment_rad: tuple[QuantityInput, QuantityInput] | None = None


@dataclass(frozen=True, slots=True)
class SimulationVariantResult:
    """Validated variant files and traceability data returned to the UI."""

    scenario_id: str
    scenario_path: Path
    project_path: Path
    config_hash: str
    changed_fields: tuple[str, ...]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "scenario_path": str(self.scenario_path),
            "project_path": str(self.project_path),
            "config_hash": self.config_hash,
            "changed_fields": list(self.changed_fields),
            "warnings": list(self.warnings),
        }


def _target(scenario: dict[str, Any], target_id: str | None) -> dict[str, Any]:
    targets = scenario["scene"]["targets"]
    selected = str(target_id or targets[0]["id"])
    for item in targets:
        if str(item["id"]) == selected:
            return item
    raise ValueError(f"scene target을 찾을 수 없습니다: {selected!r}")


def _set_if_changed(
    mapping: dict[str, Any],
    key: str,
    value: Any | None,
    *,
    path: str,
    changed: list[str],
) -> None:
    if value is None:
        return
    if mapping.get(key) != value:
        mapping[key] = value
        changed.append(path)


def _apply_parameter_edits(
    scenario: dict[str, Any],
    edits: SimulationParameterEdits,
) -> tuple[str, ...]:
    changed: list[str] = []
    source = scenario["source"]
    _set_if_changed(
        source,
        "wavelength_m",
        None if edits.wavelength_m is None else _quantity_arg(edits.wavelength_m),
        path="source.wavelength_m",
        changed=changed,
    )
    _set_if_changed(
        source,
        "optical_power_w",
        None if edits.optical_power_w is None else _quantity_arg(edits.optical_power_w),
        path="source.optical_power_w",
        changed=changed,
    )
    if any(path.startswith("source.") for path in changed):
        _set_if_changed(
            source,
            "catalog_parameter_policy",
            "explicit_override",
            path="source.catalog_parameter_policy",
            changed=changed,
        )

    scanner = scenario["scanner"]
    scanner_values = (
        (
            "static_command_angle_rad",
            edits.scanner_static_command_angle_rad,
            "scanner.static_command_angle_rad",
        ),
        (
            "mechanical_amplitude_rad",
            edits.scanner_mechanical_amplitude_rad,
            "scanner.mechanical_amplitude_rad",
        ),
        ("frequency_hz", edits.scanner_frequency_hz, "scanner.frequency_hz"),
    )
    for key, value, path in scanner_values:
        _set_if_changed(
            scanner,
            key,
            None if value is None else _quantity_arg(value),
            path=path,
            changed=changed,
        )
    _set_if_changed(
        scanner,
        "rotation_axis_world",
        None
        if edits.scanner_rotation_axis_world is None
        else [float(value) for value in edits.scanner_rotation_axis_world],
        path="scanner.rotation_axis_world",
        changed=changed,
    )
    _set_if_changed(
        scanner,
        "waveform",
        edits.scanner_waveform,
        path="scanner.waveform",
        changed=changed,
    )
    _set_if_changed(
        scanner,
        "samples_per_line",
        edits.scanner_samples_per_line,
        path="scanner.samples_per_line",
        changed=changed,
    )

    target_values_requested = any(
        value is not None
        for value in (
            edits.target_center_m,
            edits.target_normal,
            edits.target_width_axis,
            edits.target_width_m,
            edits.target_height_m,
        )
    )
    if target_values_requested:
        target = _target(scenario, edits.target_id)
        geometry = target["geometry"]
        target_prefix = f"scene.targets[{target['id']}].geometry"
        _set_if_changed(
            geometry,
            "center_m",
            None
            if edits.target_center_m is None
            else [_quantity_arg(value) for value in edits.target_center_m],
            path=f"{target_prefix}.center_m",
            changed=changed,
        )
        _set_if_changed(
            geometry,
            "normal",
            None if edits.target_normal is None else [float(value) for value in edits.target_normal],
            path=f"{target_prefix}.normal",
            changed=changed,
        )
        _set_if_changed(
            geometry,
            "width_axis",
            (
                None
                if edits.target_width_axis is None
                else [float(value) for value in edits.target_width_axis]
            ),
            path=f"{target_prefix}.width_axis",
            changed=changed,
        )
        _set_if_changed(
            geometry,
            "width_m",
            None if edits.target_width_m is None else _quantity_arg(edits.target_width_m),
            path=f"{target_prefix}.width_m",
            changed=changed,
        )
        _set_if_changed(
            geometry,
            "height_m",
            None if edits.target_height_m is None else _quantity_arg(edits.target_height_m),
            path=f"{target_prefix}.height_m",
            changed=changed,
        )

    receiver = scenario["receiver"]
    _set_if_changed(
        receiver,
        "position_m",
        None
        if edits.receiver_position_m is None
        else [_quantity_arg(value) for value in edits.receiver_position_m],
        path="receiver.position_m",
        changed=changed,
    )
    _set_if_changed(
        receiver,
        "direction",
        None
        if edits.receiver_direction is None
        else [float(value) for value in edits.receiver_direction],
        path="receiver.direction",
        changed=changed,
    )
    _set_if_changed(
        receiver,
        "aperture_diameter_m",
        None
        if edits.receiver_aperture_diameter_m is None
        else _quantity_arg(edits.receiver_aperture_diameter_m),
        path="receiver.aperture_diameter_m",
        changed=changed,
    )
    _set_if_changed(
        receiver,
        "full_fov_rad",
        None if edits.receiver_full_fov_rad is None else _quantity_arg(edits.receiver_full_fov_rad),
        path="receiver.full_fov_rad",
        changed=changed,
    )
    _set_if_changed(
        receiver,
        "optical_efficiency",
        edits.receiver_optical_efficiency,
        path="receiver.optical_efficiency",
        changed=changed,
    )
    return tuple(changed)


def _restore(path: Path, previous: bytes | None) -> None:
    if previous is None:
        path.unlink(missing_ok=True)
    else:
        path.write_bytes(previous)


def create_simulation_variant(
    *,
    project_path: str | Path,
    scenario_id: str,
    scenario_output: str | Path,
    project_output: str | Path,
    parameter_edits: SimulationParameterEdits,
    element_edits: AssemblyElementEdits | None = None,
    overwrite: bool = False,
) -> SimulationVariantResult:
    """Write, validate and return one reproducible UI simulation variant."""

    source_project_path = Path(project_path).resolve()
    raw_project = _load_yaml(source_project_path)
    _, raw_scenario = _find_active_scenario(raw_project, project_path=source_project_path)
    base_scenario_id = str(raw_scenario["scenario_id"])
    variant_id = str(scenario_id).strip()
    if not _IDENTIFIER_PATTERN.fullmatch(variant_id):
        raise ValueError(
            "scenario_id는 영문/숫자로 시작하고 영문, 숫자, _, ., :, -만 사용할 수 있습니다."
        )

    scenario_path = Path(scenario_output).resolve()
    variant_project_path = Path(project_output).resolve()
    _validate_variant_project_layout(variant_project_path)
    _ensure_writable(scenario_path, overwrite=overwrite)
    _ensure_writable(variant_project_path, overwrite=overwrite)

    scenario = copy.deepcopy(raw_scenario)
    scenario["scenario_id"] = variant_id
    base_description = str(scenario.get("description", ""))
    scenario["description"] = (
        f"{base_description} UI simulation variant of {base_scenario_id}."
    ).strip()
    changed = list(_apply_parameter_edits(scenario, parameter_edits))
    if element_edits is not None:
        changed.extend(
            _apply_placement_updates(
                scenario,
                element_id=element_edits.element_id,
                component_ref=element_edits.component_ref,
                translation_m=element_edits.translation_m,
                quaternion_wxyz=element_edits.quaternion_wxyz,
                axial_gap_m=element_edits.axial_gap_m,
                transverse_offset_m=element_edits.transverse_offset_m,
                clocking_rad=element_edits.clocking_rad,
                angular_misalignment_rad=element_edits.angular_misalignment_rad,
            )
        )
    if not changed:
        raise ValueError("Baseline과 달라진 simulation parameter 또는 placement가 없습니다.")

    variant_project = _relocated_project_paths(
        raw_project,
        old_project_dir=source_project_path.parent,
        new_project_dir=variant_project_path.parent,
    )
    variant_project["project_id"] = f"{raw_project['project_id']}_{variant_id}"
    variant_project["scenarios"] = [
        _relative_path(scenario_path, base_dir=variant_project_path.parent)
    ]
    variant_project["active_baseline"] = variant_id
    variant_project["experiments"] = []

    previous_scenario = scenario_path.read_bytes() if scenario_path.exists() else None
    previous_project = variant_project_path.read_bytes() if variant_project_path.exists() else None
    try:
        scenario_path.write_text(
            yaml.safe_dump(scenario, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        variant_project_path.write_text(
            yaml.safe_dump(variant_project, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        validated = load_project(variant_project_path)
    except Exception:
        _restore(scenario_path, previous_scenario)
        _restore(variant_project_path, previous_project)
        raise

    return SimulationVariantResult(
        scenario_id=variant_id,
        scenario_path=scenario_path,
        project_path=variant_project_path,
        config_hash=validated.config_hash,
        changed_fields=tuple(changed),
        warnings=tuple(item.format() for item in validated.warnings),
    )


__all__ = [
    "AssemblyElementEdits",
    "SimulationParameterEdits",
    "SimulationVariantResult",
    "create_simulation_variant",
]
