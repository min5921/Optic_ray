"""Top-level project loading, resolution, and semantic validation."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

import yaml

from lidarsim.assets.loader import AssetRegistry, load_asset_registry
from lidarsim.catalog.loader import Catalog, load_catalog
from lidarsim.config.immutable import canonical_hash, deep_freeze, deep_thaw
from lidarsim.config.paths import schema_directory_for_project
from lidarsim.config.physical import validate_scenario_physics
from lidarsim.config.schema import SchemaStore
from lidarsim.config.units import resolve_quantities
from lidarsim.errors import ConfigFileError, ConfigValidationError, Diagnostic
from lidarsim.geometry.placement import resolve_assembly


@dataclass(frozen=True, slots=True)
class ResolvedProject:
    """Validated, SI-resolved, immutable project snapshot."""

    project_path: Path
    project: Mapping[str, Any]
    scenarios: Mapping[str, Mapping[str, Any]]
    experiments: Mapping[str, Mapping[str, Any]]
    catalog: Catalog
    assets: AssetRegistry
    warnings: tuple[Diagnostic, ...]
    config_hash: str

    @property
    def active_scenario(self) -> Mapping[str, Any]:
        """Return the configured active baseline scenario."""

        return self.scenarios[str(self.project["active_baseline"])]

    def to_dict(self) -> dict[str, Any]:
        """Return a serializable resolved snapshot for inspection or export."""

        return {
            "project_path": str(self.project_path),
            "project": deep_thaw(self.project),
            "scenarios": deep_thaw(self.scenarios),
            "experiments": deep_thaw(self.experiments),
            "catalog": {
                identifier: {
                    "kind": entry.kind,
                    "source_path": str(entry.source_path),
                    "data": deep_thaw(entry.data),
                }
                for identifier, entry in self.catalog.entries.items()
            },
            "assets": self.assets.to_dict(),
            "warnings": [
                {
                    "source": item.source,
                    "path": item.path,
                    "message": item.message,
                    "hint": item.hint,
                    "severity": item.severity,
                }
                for item in self.warnings
            ],
            "config_hash": self.config_hash,
        }


def _load_yaml_mapping(path: Path) -> dict[str, Any]:
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigFileError(path, f"Cannot read YAML: {exc}") from exc
    if not isinstance(document, dict):
        raise ConfigFileError(path, "YAML must contain a mapping at the document root.")
    return document


def _resolve_paths(
    values: Sequence[str],
    *,
    base_dir: Path,
    source: Path,
    field: str,
    require_directory: bool,
) -> tuple[Path, ...]:
    resolved: list[Path] = []
    diagnostics: list[Diagnostic] = []
    for index, value in enumerate(values):
        path = (base_dir / value).resolve()
        exists = path.is_dir() if require_directory else path.is_file()
        if not exists:
            expected = "directory" if require_directory else "file"
            diagnostics.append(
                Diagnostic(
                    source=str(source),
                    path=f"{field}[{index}]",
                    message=f"Referenced {expected} does not exist: {path}",
                    hint=f"Correct {field} or create the referenced {expected}.",
                )
            )
        resolved.append(path)
    if diagnostics:
        raise ConfigValidationError(diagnostics)
    return tuple(resolved)


def _port_ids(catalog: Catalog, component_ref: str) -> set[str]:
    if component_ref not in catalog:
        return set()
    return {str(port.get("id")) for port in catalog[component_ref].ports}


def _add_duplicate_diagnostics(
    values: Sequence[Mapping[str, Any]],
    *,
    source: Path,
    path: str,
    diagnostics: list[Diagnostic],
) -> None:
    seen: set[str] = set()
    for index, value in enumerate(values):
        identifier = str(value.get("id", ""))
        if identifier in seen:
            diagnostics.append(
                Diagnostic(
                    source=str(source),
                    path=f"{path}[{index}].id",
                    message=f"Duplicate ID {identifier!r}.",
                    hint="IDs must be unique within their collection.",
                )
            )
        seen.add(identifier)


def _validate_vector(
    value: Sequence[Any],
    *,
    source: Path,
    path: str,
    diagnostics: list[Diagnostic],
) -> None:
    try:
        components = tuple(float(item) for item in value)
    except (TypeError, ValueError):
        return
    if not all(math.isfinite(item) for item in components):
        diagnostics.append(
            Diagnostic(
                source=str(source),
                path=path,
                message="Direction or axis vector must contain only finite values.",
            )
        )
        return
    norm = math.sqrt(sum(item**2 for item in components))
    if norm <= 1e-15:
        diagnostics.append(
            Diagnostic(
                source=str(source),
                path=path,
                message="Direction or axis vector must be non-zero.",
                hint="Provide a three-component vector with a non-zero magnitude.",
            )
        )


def _validate_calibration_evidence(
    scenario: Mapping[str, Any],
    *,
    source: Path,
    assets: AssetRegistry,
    diagnostics: list[Diagnostic],
) -> None:
    """calibrated_hardware label에 필요한 추적 가능한 근거를 검사한다."""

    if str(scenario["model_purpose"]) != "calibrated_hardware":
        return
    evidence = scenario.get("calibration_evidence")
    if not isinstance(evidence, Mapping):
        return

    calibration_ids = tuple(
        str(value) for value in evidence.get("calibration_measurement_ids", ())
    )
    validation_ids = tuple(
        str(value) for value in evidence.get("validation_measurement_ids", ())
    )
    for field, identifiers, expected_role in (
        ("calibration_measurement_ids", calibration_ids, "calibration"),
        ("validation_measurement_ids", validation_ids, "validation"),
    ):
        for index, identifier in enumerate(identifiers):
            record = assets.measurements.get(identifier)
            if record is None:
                diagnostics.append(
                    Diagnostic(
                        source=str(source),
                        path=f"calibration_evidence.{field}[{index}]",
                        message=f"등록되지 않은 measurement ID입니다: {identifier!r}",
                    )
                )
                continue
            actual_role = str(record.data.get("dataset_role", ""))
            if actual_role != expected_role:
                diagnostics.append(
                    Diagnostic(
                        source=str(source),
                        path=f"calibration_evidence.{field}[{index}]",
                        message=(
                            f"Measurement {identifier!r}의 dataset_role은 "
                            f"{expected_role!r}이어야 합니다(현재 {actual_role!r})."
                        ),
                    )
                )
    overlap = sorted(set(calibration_ids) & set(validation_ids))
    if overlap:
        diagnostics.append(
            Diagnostic(
                source=str(source),
                path="calibration_evidence",
                message=(
                    "Calibration과 validation dataset은 독립적이어야 합니다: "
                    + ", ".join(overlap)
                ),
            )
        )

    fitted = evidence.get("fitted_parameter_set")
    if isinstance(fitted, Mapping):
        parameter_path = (source.parent / str(fitted["file"])).resolve()
        try:
            payload = parameter_path.read_bytes()
        except OSError as exc:
            diagnostics.append(
                Diagnostic(
                    source=str(source),
                    path="calibration_evidence.fitted_parameter_set.file",
                    message=f"Fitted parameter set file을 읽을 수 없습니다: {parameter_path}: {exc}",
                )
            )
        else:
            actual_hash = hashlib.sha256(payload).hexdigest()
            if actual_hash.lower() != str(fitted["sha256"]).lower():
                diagnostics.append(
                    Diagnostic(
                        source=str(source),
                        path="calibration_evidence.fitted_parameter_set.sha256",
                        message=(
                            "Fitted parameter set SHA-256이 파일과 일치하지 않습니다: "
                            f"actual={actual_hash}"
                        ),
                    )
                )

    validity = evidence.get("validity")
    if isinstance(validity, Mapping):
        wavelength_range = validity.get("wavelength_range_m")
        if isinstance(wavelength_range, Sequence) and len(wavelength_range) == 2:
            lower, upper = (float(value) for value in wavelength_range)
            wavelength = float(scenario["source"]["wavelength_m"])
            if not all(math.isfinite(value) for value in (lower, upper)):
                diagnostics.append(
                    Diagnostic(
                        source=str(source),
                        path="calibration_evidence.validity.wavelength_range_m",
                        message="Calibration wavelength validity는 유한한 값이어야 합니다.",
                    )
                )
            elif lower <= 0.0 or lower > upper:
                diagnostics.append(
                    Diagnostic(
                        source=str(source),
                        path="calibration_evidence.validity.wavelength_range_m",
                        message="Calibration wavelength validity는 증가하는 양의 범위여야 합니다.",
                    )
                )
            elif not lower <= wavelength <= upper:
                diagnostics.append(
                    Diagnostic(
                        source=str(source),
                        path="calibration_evidence.validity.wavelength_range_m",
                        message=(
                            f"Scenario wavelength {wavelength:.9g} m가 calibration "
                            f"validity [{lower:.9g}, {upper:.9g}] m 밖에 있습니다."
                        ),
                    )
                )

    if str(scenario["simulation"]["accuracy_mode"]) != "absolute_radiometric":
        diagnostics.append(
            Diagnostic(
                source=str(source),
                path="simulation.accuracy_mode",
                message=(
                    "calibrated_hardware에는 accuracy_mode=absolute_radiometric가 필요합니다."
                ),
            )
        )
    if str(scenario["receiver"]["model_level"]) != "calibrated":
        diagnostics.append(
            Diagnostic(
                source=str(source),
                path="receiver.model_level",
                message="calibrated_hardware에는 receiver.model_level=calibrated가 필요합니다.",
            )
        )


def _validate_port_reference(
    reference: str,
    *,
    elements: Mapping[str, Mapping[str, Any]],
    catalog: Catalog,
    source: Path,
    path: str,
    diagnostics: list[Diagnostic],
) -> None:
    element_id, separator, port_id = reference.rpartition(".")
    if not separator or not element_id or not port_id:
        diagnostics.append(
            Diagnostic(
                source=str(source),
                path=path,
                message=f"Invalid port reference {reference!r}.",
                hint="Use the form 'element_id.port_id'.",
            )
        )
        return
    element = elements.get(element_id)
    if element is None:
        diagnostics.append(
            Diagnostic(
                source=str(source),
                path=path,
                message=f"Port reference uses unknown element {element_id!r}.",
            )
        )
        return
    component_ref = str(element["component_ref"])
    if component_ref in catalog and port_id not in _port_ids(catalog, component_ref):
        available_ports = ", ".join(sorted(_port_ids(catalog, component_ref))) or "(none)"
        diagnostics.append(
            Diagnostic(
                source=str(source),
                path=path,
                message=f"Component {component_ref!r} has no port {port_id!r}.",
                hint=f"Available ports: {available_ports}.",
            )
        )


def _validate_scenario(
    scenario: Mapping[str, Any],
    *,
    source: Path,
    catalog: Catalog,
    assets: AssetRegistry,
) -> None:
    diagnostics: list[Diagnostic] = []
    assembly = scenario["optical_assembly"]
    element_list = assembly["elements"]
    _add_duplicate_diagnostics(
        element_list,
        source=source,
        path="optical_assembly.elements",
        diagnostics=diagnostics,
    )
    _add_duplicate_diagnostics(
        assembly["optical_paths"],
        source=source,
        path="optical_assembly.optical_paths",
        diagnostics=diagnostics,
    )
    _add_duplicate_diagnostics(
        scenario["scene"]["targets"],
        source=source,
        path="scene.targets",
        diagnostics=diagnostics,
    )

    elements = {str(item["id"]): item for item in element_list}
    for index, element in enumerate(element_list):
        component_ref = str(element["component_ref"])
        if component_ref not in catalog:
            diagnostics.append(
                Diagnostic(
                    source=str(source),
                    path=f"optical_assembly.elements[{index}].component_ref",
                    message=f"Unknown component catalog ID {component_ref!r}.",
                    hint="Add the component record to a configured catalog path or correct the reference.",
                )
            )
        elif catalog[component_ref].kind != "component":
            diagnostics.append(
                Diagnostic(
                    source=str(source),
                    path=f"optical_assembly.elements[{index}].component_ref",
                    message=f"Catalog ID {component_ref!r} is not a component.",
                )
            )

        placement = element["placement"]
        if placement["mode"] == "port":
            for field in ("connect_from", "connect_to"):
                _validate_port_reference(
                    str(placement[field]),
                    elements=elements,
                    catalog=catalog,
                    source=source,
                    path=f"optical_assembly.elements[{index}].placement.{field}",
                    diagnostics=diagnostics,
                )
            target_element, _, _ = str(placement["connect_to"]).rpartition(".")
            if target_element and target_element != str(element["id"]):
                diagnostics.append(
                    Diagnostic(
                        source=str(source),
                        path=f"optical_assembly.elements[{index}].placement.connect_to",
                        message="connect_to must name a port on the element being placed.",
                    )
                )

    for path_index, optical_path in enumerate(assembly["optical_paths"]):
        for element_index, element_id in enumerate(optical_path["elements"]):
            if str(element_id) not in elements:
                diagnostics.append(
                    Diagnostic(
                        source=str(source),
                        path=(
                            f"optical_assembly.optical_paths[{path_index}]"
                            f".elements[{element_index}]"
                        ),
                        message=f"Optical path uses unknown element {element_id!r}.",
                    )
                )

    scanner = scenario["scanner"]
    scanner_id = str(scanner["element_id"])
    if scanner_id not in elements:
        diagnostics.append(
            Diagnostic(
                source=str(source),
                path="scanner.element_id",
                message=f"Scanner uses unknown element {scanner_id!r}.",
            )
        )
    else:
        component_ref = str(elements[scanner_id]["component_ref"])
        if component_ref in catalog:
            component_type = catalog[component_ref].data.get("component_type")
            if component_type != "scanner_mirror":
                diagnostics.append(
                    Diagnostic(
                        source=str(source),
                        path="scanner.element_id",
                        message=(
                            f"Scanner element component {component_ref!r} has type "
                            f"{component_type!r}, expected 'scanner_mirror'."
                        ),
                    )
                )
    _validate_vector(
        scanner["rotation_axis_world"],
        source=source,
        path="scanner.rotation_axis_world",
        diagnostics=diagnostics,
    )

    for index, target in enumerate(scenario["scene"]["targets"]):
        material_ref = str(target["material_ref"])
        if material_ref not in catalog:
            diagnostics.append(
                Diagnostic(
                    source=str(source),
                    path=f"scene.targets[{index}].material_ref",
                    message=f"Unknown material catalog ID {material_ref!r}.",
                )
            )
        elif catalog[material_ref].kind != "material":
            diagnostics.append(
                Diagnostic(
                    source=str(source),
                    path=f"scene.targets[{index}].material_ref",
                    message=f"Catalog ID {material_ref!r} is not a material.",
                )
            )
        normal = target["geometry"].get("normal")
        if normal is not None:
            _validate_vector(
                normal,
                source=source,
                path=f"scene.targets[{index}].geometry.normal",
                diagnostics=diagnostics,
            )
        width_axis = target["geometry"].get("width_axis")
        if width_axis is not None:
            _validate_vector(
                width_axis,
                source=source,
                path=f"scene.targets[{index}].geometry.width_axis",
                diagnostics=diagnostics,
            )

    _validate_vector(
        scenario["receiver"]["direction"],
        source=source,
        path="receiver.direction",
        diagnostics=diagnostics,
    )
    _validate_calibration_evidence(
        scenario,
        source=source,
        assets=assets,
        diagnostics=diagnostics,
    )
    if diagnostics:
        raise ConfigValidationError(diagnostics)


def _resolve_experiment_quantities(experiment: Mapping[str, Any], *, source: Path) -> dict[str, Any]:
    resolved = dict(experiment)
    resolved_sweeps: list[dict[str, Any]] = []
    for sweep in experiment["sweeps"]:
        sweep_copy = dict(sweep)
        parameter = str(sweep["parameter"])
        field_name = parameter.rsplit(".", 1)[-1]
        wrapped = resolve_quantities({field_name: sweep["values"]}, source=str(source))
        sweep_copy["values"] = wrapped[field_name]
        resolved_sweeps.append(sweep_copy)
    resolved["sweeps"] = resolved_sweeps
    return resolved


def _validate_experiment(
    experiment: Mapping[str, Any],
    *,
    source: Path,
    scenario_paths: Mapping[Path, str],
    catalog: Catalog,
) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = []
    warnings: list[Diagnostic] = []
    base_config = (source.parent / str(experiment["base_config"])).resolve()
    if base_config not in scenario_paths:
        diagnostics.append(
            Diagnostic(
                source=str(source),
                path="base_config",
                message=f"Base config is not one of the project's loaded scenarios: {base_config}",
                hint="Reference a scenario listed in configs/project.yaml.",
            )
        )

    run_count = 1
    for index, sweep in enumerate(experiment["sweeps"]):
        values = sweep["values"]
        if experiment["design"] == "cartesian_grid":
            run_count *= len(values)
        if str(sweep["parameter"]).endswith(".component_ref"):
            for value_index, value in enumerate(values):
                if str(value) not in catalog or catalog[str(value)].kind != "component":
                    diagnostics.append(
                        Diagnostic(
                            source=str(source),
                            path=f"sweeps[{index}].values[{value_index}]",
                            message=f"Unknown component catalog ID {value!r}.",
                        )
                    )

    threshold = int(experiment["execution"]["max_runs_without_confirmation"])
    if run_count > threshold:
        warnings.append(
            Diagnostic(
                source=str(source),
                path="sweeps",
                message=f"Experiment expands to {run_count} runs, above confirmation threshold {threshold}.",
                hint="Require explicit confirmation before execution.",
                severity="warning",
            )
        )
    if diagnostics:
        raise ConfigValidationError(diagnostics)
    return tuple(warnings)


def _physical_hash_payload(
    project: Mapping[str, Any],
    scenarios: Mapping[str, Mapping[str, Any]],
    experiments: Mapping[str, Mapping[str, Any]],
    catalog: Catalog,
    assets: AssetRegistry,
) -> dict[str, Any]:
    physical_project = dict(project)
    physical_project.pop("display_units", None)
    physical_project.pop("ui", None)
    return {
        "project": physical_project,
        "scenarios": scenarios,
        "experiments": experiments,
        "catalog": {identifier: entry.data for identifier, entry in catalog.entries.items()},
        "assets": assets.physical_hash_data(),
    }


def load_project(project_path: str | Path = "configs/project.yaml") -> ResolvedProject:
    """Load a project, rejecting schema, reference, unit, and semantic errors."""

    path = Path(project_path).resolve()
    raw_project = _load_yaml_mapping(path)
    schemas = SchemaStore.load(schema_directory_for_project(path))
    schemas.validate(raw_project, "project.schema.json", source=str(path))

    project_dir = path.parent
    catalog_paths = _resolve_paths(
        raw_project["catalog_paths"],
        base_dir=project_dir,
        source=path,
        field="catalog_paths",
        require_directory=True,
    )
    asset_paths = _resolve_paths(
        raw_project["asset_paths"],
        base_dir=project_dir,
        source=path,
        field="asset_paths",
        require_directory=True,
    )
    measurement_paths = _resolve_paths(
        raw_project.get("measurement_paths", ()),
        base_dir=project_dir,
        source=path,
        field="measurement_paths",
        require_directory=True,
    )
    catalog = load_catalog(catalog_paths, schemas)
    assets = load_asset_registry(asset_paths, measurement_paths, schemas, catalog)

    scenario_files = _resolve_paths(
        raw_project["scenarios"],
        base_dir=project_dir,
        source=path,
        field="scenarios",
        require_directory=False,
    )
    scenarios: dict[str, Mapping[str, Any]] = {}
    scenario_paths: dict[Path, str] = {}
    diagnostics: list[Diagnostic] = []
    warnings: list[Diagnostic] = list(assets.warnings)
    for scenario_path in scenario_files:
        raw_scenario = _load_yaml_mapping(scenario_path)
        try:
            schemas.validate(raw_scenario, "scenario.schema.json", source=str(scenario_path))
            resolved_scenario = resolve_quantities(raw_scenario, source=str(scenario_path))
            _validate_scenario(
                resolved_scenario,
                source=scenario_path,
                catalog=catalog,
                assets=assets,
            )
            scenario_warnings = validate_scenario_physics(
                resolved_scenario,
                source=scenario_path,
                catalog=catalog,
            )
            resolve_assembly(resolved_scenario, catalog, source=str(scenario_path))
        except ConfigValidationError as exc:
            diagnostics.extend(exc.diagnostics)
            continue
        scenario_id = str(resolved_scenario["scenario_id"])
        if scenario_id in scenarios:
            diagnostics.append(
                Diagnostic(
                    source=str(scenario_path),
                    path="scenario_id",
                    message=f"Duplicate scenario ID {scenario_id!r}.",
                )
            )
            continue
        scenarios[scenario_id] = deep_freeze(resolved_scenario)
        scenario_paths[scenario_path] = scenario_id
        warnings.extend(scenario_warnings)

    active_baseline = str(raw_project["active_baseline"])
    if active_baseline not in scenarios and not diagnostics:
        diagnostics.append(
            Diagnostic(
                source=str(path),
                path="active_baseline",
                message=f"Active baseline {active_baseline!r} is not a loaded scenario ID.",
            )
        )

    experiment_files = _resolve_paths(
        raw_project.get("experiments", ()),
        base_dir=project_dir,
        source=path,
        field="experiments",
        require_directory=False,
    )
    experiments: dict[str, Mapping[str, Any]] = {}
    for experiment_path in experiment_files:
        raw_experiment = _load_yaml_mapping(experiment_path)
        try:
            schemas.validate(raw_experiment, "experiment.schema.json", source=str(experiment_path))
            resolved_experiment = _resolve_experiment_quantities(raw_experiment, source=experiment_path)
            warnings.extend(
                _validate_experiment(
                    resolved_experiment,
                    source=experiment_path,
                    scenario_paths=scenario_paths,
                    catalog=catalog,
                )
            )
        except ConfigValidationError as exc:
            diagnostics.extend(exc.diagnostics)
            continue
        experiment_id = str(resolved_experiment["experiment_id"])
        if experiment_id in experiments:
            diagnostics.append(
                Diagnostic(
                    source=str(experiment_path),
                    path="experiment_id",
                    message=f"Duplicate experiment ID {experiment_id!r}.",
                )
            )
            continue
        experiments[experiment_id] = deep_freeze(resolved_experiment)

    if diagnostics:
        raise ConfigValidationError(diagnostics)

    frozen_project = deep_freeze(raw_project)
    frozen_scenarios = MappingProxyType(scenarios)
    frozen_experiments = MappingProxyType(experiments)
    config_hash = canonical_hash(
        _physical_hash_payload(
            frozen_project,
            frozen_scenarios,
            frozen_experiments,
            catalog,
            assets,
        )
    )
    return ResolvedProject(
        project_path=path,
        project=frozen_project,
        scenarios=frozen_scenarios,
        experiments=frozen_experiments,
        catalog=catalog,
        assets=assets,
        warnings=tuple(warnings),
        config_hash=config_hash,
    )
