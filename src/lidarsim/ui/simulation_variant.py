"""Validated parameter and placement variants for the browser UI."""

from __future__ import annotations

import copy
import difflib
import os
import re
import tempfile
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
class ProjectDraftEntry:
    """한 UI 객체에서 아직 적용하지 않은 parameter/placement 변경."""

    object_id: str
    parameter_edits: SimulationParameterEdits = SimulationParameterEdits()
    element_edits: AssemblyElementEdits | None = None

    @property
    def has_changes(self) -> bool:
        return (
            self.parameter_edits != SimulationParameterEdits()
            or self.element_edits is not None
        )


@dataclass(frozen=True, slots=True)
class ProjectDraft:
    """현재 적용 config를 기준으로 여러 객체의 변경을 보존하는 불변 draft."""

    base_project_path: Path
    base_config_hash: str
    entries: tuple[ProjectDraftEntry, ...] = ()

    @classmethod
    def for_project(cls, project: Any) -> ProjectDraft:
        return cls(
            base_project_path=Path(project.project_path).resolve(),
            base_config_hash=str(project.config_hash),
        )

    @property
    def has_changes(self) -> bool:
        return bool(self.entries)

    @property
    def changed_object_ids(self) -> tuple[str, ...]:
        return tuple(entry.object_id for entry in self.entries)

    def matches_project(self, project: Any) -> bool:
        return (
            self.base_project_path == Path(project.project_path).resolve()
            and self.base_config_hash == str(project.config_hash)
        )

    def with_object_edits(
        self,
        object_id: str,
        *,
        parameter_edits: SimulationParameterEdits = SimulationParameterEdits(),
        element_edits: AssemblyElementEdits | None = None,
    ) -> ProjectDraft:
        object_key = str(object_id)
        replacement = ProjectDraftEntry(
            object_id=object_key,
            parameter_edits=parameter_edits,
            element_edits=element_edits,
        )
        retained = tuple(entry for entry in self.entries if entry.object_id != object_key)
        entries = (
            retained
            if not replacement.has_changes
            else tuple(sorted((*retained, replacement), key=lambda entry: entry.object_id))
        )
        return ProjectDraft(
            base_project_path=self.base_project_path,
            base_config_hash=self.base_config_hash,
            entries=entries,
        )

    def without_object(self, object_id: str) -> ProjectDraft:
        return self.with_object_edits(str(object_id))

    def discard(self) -> ProjectDraft:
        return ProjectDraft(
            base_project_path=self.base_project_path,
            base_config_hash=self.base_config_hash,
        )


@dataclass(frozen=True, slots=True)
class ProjectDraftPreview:
    """File을 쓰지 않고 계산한 project-wide draft diff."""

    changed_object_ids: tuple[str, ...]
    changed_fields: tuple[str, ...]
    config_diff: str


@dataclass(frozen=True, slots=True)
class VariantIdentity:
    """UI variant 계보에서 사용하는 재현 가능한 config identity."""

    project_id: str
    scenario_id: str
    config_hash: str
    project_description: str
    scenario_description: str

    def to_dict(self) -> dict[str, str]:
        return {
            "project_id": self.project_id,
            "scenario_id": self.scenario_id,
            "config_hash": self.config_hash,
            "project_description": self.project_description,
            "scenario_description": self.scenario_description,
        }


@dataclass(frozen=True, slots=True)
class VariantProvenance:
    """최초 baseline, 직전 parent와 생성 variant를 분리한 sidecar contract."""

    baseline: VariantIdentity
    parent: VariantIdentity
    variant: VariantIdentity

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "baseline": self.baseline.to_dict(),
            "parent": self.parent.to_dict(),
            "variant": self.variant.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class SimulationVariantResult:
    """Validated variant files and traceability data returned to the UI."""

    scenario_id: str
    scenario_path: Path
    project_path: Path
    provenance_path: Path
    config_hash: str
    changed_object_ids: tuple[str, ...]
    changed_fields: tuple[str, ...]
    provenance: VariantProvenance
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "scenario_path": str(self.scenario_path),
            "project_path": str(self.project_path),
            "provenance_path": str(self.provenance_path),
            "config_hash": self.config_hash,
            "changed_object_ids": list(self.changed_object_ids),
            "changed_fields": list(self.changed_fields),
            "provenance": self.provenance.to_dict(),
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


def _unique(values: list[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


def _apply_project_draft(
    scenario: dict[str, Any],
    draft: ProjectDraft,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    changed_fields: list[str] = []
    changed_objects: list[str] = []
    for entry in draft.entries:
        entry_changes = list(_apply_parameter_edits(scenario, entry.parameter_edits))
        if entry.element_edits is not None:
            edits = entry.element_edits
            entry_changes.extend(
                _apply_placement_updates(
                    scenario,
                    element_id=edits.element_id,
                    component_ref=edits.component_ref,
                    translation_m=edits.translation_m,
                    quaternion_wxyz=edits.quaternion_wxyz,
                    axial_gap_m=edits.axial_gap_m,
                    transverse_offset_m=edits.transverse_offset_m,
                    clocking_rad=edits.clocking_rad,
                    angular_misalignment_rad=edits.angular_misalignment_rad,
                )
            )
        if entry_changes:
            changed_objects.append(entry.object_id)
            changed_fields.extend(entry_changes)
    return _unique(changed_fields), _unique(changed_objects)


def preview_project_draft(
    project_path: str | Path,
    draft: ProjectDraft,
) -> ProjectDraftPreview:
    """현재 config와 draft의 unified YAML diff를 file write 없이 만든다."""

    source_project_path = Path(project_path).resolve()
    project = load_project(source_project_path)
    if not draft.matches_project(project):
        raise ValueError(
            "Draft base가 현재 project와 다릅니다. 현재 config에서 draft를 다시 시작하세요."
        )
    raw_project = _load_yaml(source_project_path)
    _, raw_scenario = _find_active_scenario(raw_project, project_path=source_project_path)
    edited_scenario = copy.deepcopy(raw_scenario)
    changed_fields, changed_objects = _apply_project_draft(edited_scenario, draft)
    before = yaml.safe_dump(raw_scenario, sort_keys=False, allow_unicode=True).splitlines()
    after = yaml.safe_dump(edited_scenario, sort_keys=False, allow_unicode=True).splitlines()
    diff = "\n".join(
        difflib.unified_diff(
            before,
            after,
            fromfile=f"applied/{raw_scenario['scenario_id']}.yaml",
            tofile="draft/pending.yaml",
            lineterm="",
        )
    )
    return ProjectDraftPreview(
        changed_object_ids=changed_objects,
        changed_fields=changed_fields,
        config_diff=diff,
    )


def _provenance_path_for_project(project_path: Path) -> Path:
    stem = project_path.stem
    base = stem[:-8] if stem.endswith("_project") else stem
    return project_path.with_name(f"{base}_provenance.yaml")


def _identity(
    project: Any,
    raw_project: dict[str, Any],
    raw_scenario: dict[str, Any],
) -> VariantIdentity:
    return VariantIdentity(
        project_id=str(raw_project["project_id"]),
        scenario_id=str(raw_scenario["scenario_id"]),
        config_hash=str(project.config_hash),
        project_description=str(raw_project.get("description", "")),
        scenario_description=str(raw_scenario.get("description", "")),
    )


def _identity_from_dict(data: Any, *, name: str) -> VariantIdentity:
    if not isinstance(data, dict):
        raise ValueError(f"UI variant provenance {name} identity는 object여야 합니다.")
    required = {
        "project_id",
        "scenario_id",
        "config_hash",
        "project_description",
        "scenario_description",
    }
    if set(data) != required:
        raise ValueError(
            f"UI variant provenance {name} identity field가 올바르지 않습니다: "
            f"{sorted(data)}"
        )
    config_hash = str(data["config_hash"])
    if not re.fullmatch(r"[0-9a-f]{64}", config_hash):
        raise ValueError(f"UI variant provenance {name}.config_hash가 올바르지 않습니다.")
    return VariantIdentity(
        project_id=str(data["project_id"]),
        scenario_id=str(data["scenario_id"]),
        config_hash=config_hash,
        project_description=str(data["project_description"]),
        scenario_description=str(data["scenario_description"]),
    )


def _load_variant_provenance(project_path: Path) -> VariantProvenance | None:
    path = _provenance_path_for_project(project_path)
    if not path.is_file():
        return None
    data = _load_yaml(path)
    if set(data) != {"schema_version", "baseline", "parent", "variant"}:
        raise ValueError(f"UI variant provenance field가 올바르지 않습니다: {path}")
    if data["schema_version"] != 1:
        raise ValueError(f"지원하지 않는 UI variant provenance schema입니다: {path}")
    return VariantProvenance(
        baseline=_identity_from_dict(data["baseline"], name="baseline"),
        parent=_identity_from_dict(data["parent"], name="parent"),
        variant=_identity_from_dict(data["variant"], name="variant"),
    )


def _atomic_write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.staging-",
        dir=path.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _atomic_write_yaml(path: Path, data: dict[str, Any]) -> None:
    _atomic_write_bytes(
        path,
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True).encode("utf-8"),
    )


def _restore(path: Path, previous: bytes | None) -> None:
    if previous is None:
        path.unlink(missing_ok=True)
    else:
        _atomic_write_bytes(path, previous)


def create_simulation_variant(
    *,
    project_path: str | Path,
    scenario_id: str,
    scenario_output: str | Path,
    project_output: str | Path,
    parameter_edits: SimulationParameterEdits | None = None,
    element_edits: AssemblyElementEdits | None = None,
    draft: ProjectDraft | None = None,
    overwrite: bool = False,
) -> SimulationVariantResult:
    """Write, validate and return one reproducible UI simulation variant."""

    source_project_path = Path(project_path).resolve()
    source_project = load_project(source_project_path)
    raw_project = _load_yaml(source_project_path)
    _, raw_scenario = _find_active_scenario(raw_project, project_path=source_project_path)
    parent_identity = _identity(source_project, raw_project, raw_scenario)
    source_provenance = _load_variant_provenance(source_project_path)
    baseline_identity = (
        parent_identity if source_provenance is None else source_provenance.baseline
    )
    variant_id = str(scenario_id).strip()
    if not _IDENTIFIER_PATTERN.fullmatch(variant_id):
        raise ValueError(
            "scenario_id는 영문/숫자로 시작하고 영문, 숫자, _, ., :, -만 사용할 수 있습니다."
        )

    scenario_path = Path(scenario_output).resolve()
    variant_project_path = Path(project_output).resolve()
    provenance_path = _provenance_path_for_project(variant_project_path)
    _validate_variant_project_layout(variant_project_path)
    _ensure_writable(scenario_path, overwrite=overwrite)
    _ensure_writable(variant_project_path, overwrite=overwrite)
    _ensure_writable(provenance_path, overwrite=overwrite)

    scenario = copy.deepcopy(raw_scenario)
    scenario["scenario_id"] = variant_id
    scenario["description"] = (
        f"{baseline_identity.scenario_description} "
        f"UI simulation variant {variant_id}."
    ).strip()
    if draft is not None:
        if parameter_edits not in (None, SimulationParameterEdits()) or element_edits is not None:
            raise ValueError("Project draft와 단일-object edit를 동시에 지정할 수 없습니다.")
        if not draft.matches_project(source_project):
            raise ValueError(
                "Draft base가 현재 project와 다릅니다. 현재 config에서 draft를 다시 시작하세요."
            )
        changed_fields, changed_objects = _apply_project_draft(scenario, draft)
    else:
        edits = parameter_edits or SimulationParameterEdits()
        changed = list(_apply_parameter_edits(scenario, edits))
        changed_objects_list: list[str] = []
        if any(path.startswith("source.") for path in changed):
            changed_objects_list.append(str(raw_scenario["source"]["element_id"]))
        if any(path.startswith("scanner.") for path in changed):
            changed_objects_list.append(str(raw_scenario["scanner"]["element_id"]))
        if any(path.startswith("scene.targets[") for path in changed):
            changed_objects_list.append(
                str(edits.target_id or raw_scenario["scene"]["targets"][0]["id"])
            )
        if any(path.startswith("receiver.") for path in changed):
            changed_objects_list.append("receiver")
        if element_edits is not None:
            placement_changes = list(
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
            if placement_changes:
                changed_objects_list.append(element_edits.element_id)
                changed.extend(placement_changes)
        changed_fields = _unique(changed)
        changed_objects = _unique(changed_objects_list)
    if not changed_fields:
        raise ValueError("Baseline과 달라진 simulation parameter 또는 placement가 없습니다.")

    variant_project = _relocated_project_paths(
        raw_project,
        old_project_dir=source_project_path.parent,
        new_project_dir=variant_project_path.parent,
    )
    variant_project["project_id"] = f"{baseline_identity.project_id}_{variant_id}"
    variant_project["description"] = (
        f"{baseline_identity.project_description} "
        f"UI simulation variant {variant_id}."
    ).strip()
    variant_project["scenarios"] = [
        _relative_path(scenario_path, base_dir=variant_project_path.parent)
    ]
    variant_project["active_baseline"] = variant_id
    variant_project["experiments"] = []

    previous_scenario = scenario_path.read_bytes() if scenario_path.exists() else None
    previous_project = variant_project_path.read_bytes() if variant_project_path.exists() else None
    previous_provenance = provenance_path.read_bytes() if provenance_path.exists() else None
    try:
        _atomic_write_yaml(scenario_path, scenario)
        _atomic_write_yaml(variant_project_path, variant_project)
        validated = load_project(variant_project_path)
        variant_identity = _identity(validated, variant_project, scenario)
        provenance = VariantProvenance(
            baseline=baseline_identity,
            parent=parent_identity,
            variant=variant_identity,
        )
        _atomic_write_yaml(provenance_path, provenance.to_dict())
    except Exception:
        _restore(scenario_path, previous_scenario)
        _restore(variant_project_path, previous_project)
        _restore(provenance_path, previous_provenance)
        raise

    return SimulationVariantResult(
        scenario_id=variant_id,
        scenario_path=scenario_path,
        project_path=variant_project_path,
        provenance_path=provenance_path,
        config_hash=validated.config_hash,
        changed_object_ids=changed_objects,
        changed_fields=changed_fields,
        provenance=provenance,
        warnings=tuple(item.format() for item in validated.warnings),
    )


__all__ = [
    "AssemblyElementEdits",
    "ProjectDraft",
    "ProjectDraftEntry",
    "ProjectDraftPreview",
    "SimulationParameterEdits",
    "SimulationVariantResult",
    "VariantIdentity",
    "VariantProvenance",
    "create_simulation_variant",
    "preview_project_draft",
]
