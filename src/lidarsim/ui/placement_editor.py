"""Numeric placement variant helper for UI MVP 0.x."""

from __future__ import annotations

import copy
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True, slots=True)
class PlacementVariantResult:
    """생성된 placement variant file 묶음."""

    scenario_id: str
    element_id: str
    scenario_path: Path
    project_path: Path
    changed_fields: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "element_id": self.element_id,
            "scenario_path": str(self.scenario_path),
            "project_path": str(self.project_path),
            "changed_fields": list(self.changed_fields),
        }


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"YAML을 읽을 수 없습니다: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"YAML root는 mapping이어야 합니다: {path}")
    return data


def _relative_path(target: Path, *, base_dir: Path) -> str:
    return Path(os.path.relpath(target.resolve(), base_dir.resolve())).as_posix()


def _relocated_project_paths(
    raw_project: dict[str, Any],
    *,
    old_project_dir: Path,
    new_project_dir: Path,
) -> dict[str, Any]:
    relocated = copy.deepcopy(raw_project)
    for field in ("catalog_paths", "asset_paths", "measurement_paths"):
        if field not in relocated:
            continue
        relocated[field] = [
            _relative_path(old_project_dir / str(item), base_dir=new_project_dir)
            for item in relocated[field]
        ]
    if "result_root" in relocated:
        relocated["result_root"] = _relative_path(
            old_project_dir / str(relocated["result_root"]),
            base_dir=new_project_dir,
        )
    return relocated


def _quantity_arg(value: str | float | int) -> str | float:
    if isinstance(value, (float, int)):
        return float(value)
    text = str(value)
    try:
        return float(text)
    except ValueError:
        return text


def _find_active_scenario(
    raw_project: dict[str, Any],
    *,
    project_path: Path,
) -> tuple[Path, dict[str, Any]]:
    project_dir = project_path.parent
    active_id = str(raw_project["active_baseline"])
    for entry in raw_project["scenarios"]:
        scenario_path = (project_dir / str(entry)).resolve()
        scenario = _load_yaml(scenario_path)
        if str(scenario.get("scenario_id")) == active_id:
            return scenario_path, scenario
    raise ValueError(f"active_baseline scenario를 찾을 수 없습니다: {active_id!r}")


def _find_element(scenario: dict[str, Any], element_id: str) -> dict[str, Any]:
    for element in scenario["optical_assembly"]["elements"]:
        if str(element["id"]) == element_id:
            return element
    raise ValueError(f"optical_assembly element를 찾을 수 없습니다: {element_id!r}")


def _default_scenario_id(base_scenario_id: str, element_id: str) -> str:
    return f"{base_scenario_id}_{element_id}_placement_variant"


def _default_scenario_path(project_path: Path, scenario_id: str) -> Path:
    return project_path.parent / f"{scenario_id}.yaml"


def _default_project_path(project_path: Path, scenario_id: str) -> Path:
    return project_path.parent / f"{scenario_id}_project.yaml"


def _ensure_writable(path: Path, *, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise ValueError(f"이미 존재하는 파일입니다. 덮어쓰려면 --overwrite를 사용하세요: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)


def _validate_variant_project_layout(project_path: Path) -> None:
    schema_dir = project_path.parent.parent / "schemas"
    if not schema_dir.is_dir():
        raise ValueError(
            "variant project YAML은 부모의 부모에 schemas/가 있는 configs-like directory 아래에 "
            f"저장해야 합니다. 현재 예상 schema directory: {schema_dir}"
        )


def create_placement_variant(
    *,
    project_path: str | Path,
    element_id: str,
    scenario_id: str | None = None,
    scenario_output: str | Path | None = None,
    project_output: str | Path | None = None,
    translation_m: tuple[float, float, float] | None = None,
    quaternion_wxyz: tuple[float, float, float, float] | None = None,
    axial_gap_m: str | float | None = None,
    transverse_offset_m: tuple[str | float, str | float] | None = None,
    clocking_rad: str | float | None = None,
    angular_misalignment_rad: tuple[str | float, str | float] | None = None,
    overwrite: bool = False,
) -> PlacementVariantResult:
    """Active scenario를 복사해 placement만 바꾼 variant scenario/project를 저장한다."""

    source_project_path = Path(project_path).resolve()
    raw_project = _load_yaml(source_project_path)
    _, raw_scenario = _find_active_scenario(raw_project, project_path=source_project_path)
    base_scenario_id = str(raw_scenario["scenario_id"])
    variant_id = scenario_id or _default_scenario_id(base_scenario_id, element_id)
    scenario_path = (
        Path(scenario_output).resolve()
        if scenario_output is not None
        else _default_scenario_path(source_project_path, variant_id).resolve()
    )
    variant_project_path = (
        Path(project_output).resolve()
        if project_output is not None
        else _default_project_path(source_project_path, variant_id).resolve()
    )
    _validate_variant_project_layout(variant_project_path)
    _ensure_writable(scenario_path, overwrite=overwrite)
    _ensure_writable(variant_project_path, overwrite=overwrite)

    scenario = copy.deepcopy(raw_scenario)
    scenario["scenario_id"] = variant_id
    base_description = str(scenario.get("description", ""))
    scenario["description"] = (
        f"{base_description} Placement variant of {base_scenario_id}; "
        f"edited element={element_id}."
    ).strip()
    element = _find_element(scenario, element_id)
    placement = element["placement"]
    mode = str(placement["mode"])
    changed: list[str] = []

    absolute_updates = translation_m is not None or quaternion_wxyz is not None
    port_updates = any(
        item is not None
        for item in (
            axial_gap_m,
            transverse_offset_m,
            clocking_rad,
            angular_misalignment_rad,
        )
    )
    if absolute_updates and mode != "absolute":
        raise ValueError(f"{element_id!r}은 port placement입니다. absolute transform field를 수정할 수 없습니다.")
    if port_updates and mode != "port":
        raise ValueError(f"{element_id!r}은 absolute placement입니다. port placement field를 수정할 수 없습니다.")

    if translation_m is not None:
        placement["translation_m"] = [float(item) for item in translation_m]
        changed.append("translation_m")
    if quaternion_wxyz is not None:
        placement["quaternion_wxyz"] = [float(item) for item in quaternion_wxyz]
        changed.append("quaternion_wxyz")
    if axial_gap_m is not None:
        placement["axial_gap_m"] = _quantity_arg(axial_gap_m)
        changed.append("axial_gap_m")
    if transverse_offset_m is not None:
        placement["transverse_offset_m"] = [_quantity_arg(item) for item in transverse_offset_m]
        changed.append("transverse_offset_m")
    if clocking_rad is not None:
        placement["clocking_rad"] = _quantity_arg(clocking_rad)
        changed.append("clocking_rad")
    if angular_misalignment_rad is not None:
        placement["angular_misalignment_rad"] = [
            _quantity_arg(item) for item in angular_misalignment_rad
        ]
        changed.append("angular_misalignment_rad")
    if not changed:
        raise ValueError("수정할 placement field가 없습니다.")

    variant_project = _relocated_project_paths(
        raw_project,
        old_project_dir=source_project_path.parent,
        new_project_dir=variant_project_path.parent,
    )
    variant_project["project_id"] = f"{raw_project['project_id']}_{variant_id}"
    variant_project["scenarios"] = [_relative_path(scenario_path, base_dir=variant_project_path.parent)]
    variant_project["active_baseline"] = variant_id
    variant_project["experiments"] = []

    scenario_path.write_text(
        yaml.safe_dump(scenario, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    variant_project_path.write_text(
        yaml.safe_dump(variant_project, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return PlacementVariantResult(
        scenario_id=variant_id,
        element_id=element_id,
        scenario_path=scenario_path,
        project_path=variant_project_path,
        changed_fields=tuple(changed),
    )


__all__ = ["PlacementVariantResult", "create_placement_variant"]
