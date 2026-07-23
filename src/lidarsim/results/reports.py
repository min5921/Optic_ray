"""Phase 0 run manifest, confidence, energy와 convergence report."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

import numpy as np

from lidarsim import __version__
from lidarsim.config.immutable import deep_thaw
from lidarsim.geometry import AssemblyPlacement, resolve_assembly
from lidarsim.results.accuracy import assess_readiness


@dataclass(frozen=True, slots=True)
class RunManifest:
    project_id: str
    scenario_id: str
    config_hash: str
    created_at_utc: str
    software_version: str
    backend: str
    real_dtype: str
    random_seed: int
    deterministic: bool
    asset_hashes: dict[str, str]


@dataclass(frozen=True, slots=True)
class AccuracyReport:
    accuracy_mode: str
    confidence_level: str
    calibration_status: str
    model_purpose: str
    hardware_readiness: str
    calibration_evidence: dict[str, Any] | None
    receiver_model: str
    component_model_levels: dict[str, str]
    assumptions: tuple[str, ...]
    validity: dict[str, Any]
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EnergyLedger:
    status: str
    source_power_w: float
    entries: tuple[dict[str, Any], ...]
    conservation_residual_w: float | None
    reason: str | None


@dataclass(frozen=True, slots=True)
class ConvergenceCheck:
    check_id: str
    status: str
    metric: str
    value: float | None
    tolerance: float | None
    unit: str | None
    message: str


@dataclass(frozen=True, slots=True)
class ConvergenceReport:
    overall_status: str
    checks: tuple[ConvergenceCheck, ...]


@dataclass(frozen=True, slots=True)
class Phase0Report:
    manifest: RunManifest
    accuracy: AccuracyReport
    energy_ledger: EnergyLedger
    convergence: ConvergenceReport
    placement: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Schema validation과 YAML export용 mapping을 반환한다."""

        return {
            "schema_version": 1,
            "report_type": "phase0_validation",
            "manifest": deep_thaw(asdict(self.manifest)),
            "accuracy": deep_thaw(asdict(self.accuracy)),
            "energy_ledger": deep_thaw(asdict(self.energy_ledger)),
            "convergence": deep_thaw(asdict(self.convergence)),
            "placement": self.placement,
        }


def _confidence_for_mode(mode: str, measurement_count: int) -> tuple[str, str, list[str]]:
    warnings: list[str] = []
    if mode == "relative_design":
        warnings.append("절대 receiver power가 calibration되지 않았습니다.")
        return "comparative", "uncalibrated", warnings
    if mode == "absolute_radiometric":
        if measurement_count == 0:
            warnings.append("Absolute radiometric mode에 필요한 measurement가 없습니다.")
            return "out_of_validity", "uncalibrated", warnings
        warnings.append("Measurement 존재만 확인했으며 독립 validation은 아직 수행하지 않았습니다.")
        return "engineering_estimate", "partially_calibrated", warnings
    warnings.append("Coherent FMCW physics와 phase validation이 아직 구현되지 않았습니다.")
    return "out_of_validity", "uncalibrated", warnings


def _asset_hashes(project: Any) -> dict[str, str]:
    hashes = {
        f"mesh:{identifier}": asset.audit.content_sha256
        for identifier, asset in project.assets.meshes.items()
    }
    hashes.update(
        {
            f"measurement:{identifier}": measurement.data_sha256
            for identifier, measurement in project.assets.measurements.items()
        }
    )
    return hashes


def _accuracy_report(project: Any, assembly: AssemblyPlacement) -> AccuracyReport:
    scenario = project.active_scenario
    mode = str(scenario["simulation"]["accuracy_mode"])
    readiness = assess_readiness(project)
    confidence, calibration, warnings = _confidence_for_mode(
        mode, len(project.assets.measurements)
    )
    if readiness.model_purpose == "calibrated_hardware":
        confidence = readiness.confidence_level
        calibration = readiness.calibration_status
    warnings.extend(readiness.warnings)
    component_levels: dict[str, str] = {}
    assumptions: list[str] = []
    for element in assembly.elements.values():
        record = project.catalog[element.component_ref].data
        level = str(record.get("model_level", "unknown"))
        component_levels[element.element_id] = level
        provenance = record.get("provenance", {})
        provenance_type = str(provenance.get("type", "unknown"))
        if level in {"ideal", "paraxial_specification"}:
            assumptions.append(
                f"{element.element_id}: {level} model, provenance={provenance_type}"
            )
    for target in scenario["scene"]["targets"]:
        material_ref = str(target["material_ref"])
        material = project.catalog[material_ref].data
        assumptions.append(
            f"target {target['id']}: material={material_ref}, model={material.get('model_level', 'unknown')}"
        )
    warnings.extend(item.format() for item in project.warnings)
    receiver = scenario["receiver"]
    return AccuracyReport(
        accuracy_mode=mode,
        confidence_level=confidence,
        calibration_status=calibration,
        model_purpose=readiness.model_purpose,
        hardware_readiness=readiness.hardware_readiness,
        calibration_evidence=readiness.calibration_evidence,
        receiver_model=f"{receiver['architecture']}/{receiver['model_level']}",
        component_model_levels=component_levels,
        assumptions=tuple(assumptions),
        validity={
            "wavelength_m": float(scenario["source"]["wavelength_m"]),
            "scenario": str(scenario["scenario_id"]),
        },
        warnings=tuple(warnings),
    )


def _energy_ledger(project: Any) -> EnergyLedger:
    source_power = float(project.active_scenario["source"]["optical_power_w"])
    return EnergyLedger(
        status="not_evaluated",
        source_power_w=source_power,
        entries=(),
        conservation_residual_w=None,
        reason=(
            "Phase 0에는 beam·radiometry engine이 없으므로 source power만 기록하고 "
            "loss·received power를 계산하지 않습니다."
        ),
    )


def _placement_checks(project: Any, assembly: AssemblyPlacement) -> tuple[ConvergenceCheck, ...]:
    orthonormal_error = 0.0
    determinant_error = 0.0
    axis_norm_error = 0.0
    for element in assembly.elements.values():
        rotation = element.T_world_from_component.rotation
        orthonormal_error = max(
            orthonormal_error,
            float(np.max(np.abs(rotation.T @ rotation - np.eye(3)))),
        )
        determinant_error = max(
            determinant_error,
            abs(float(np.linalg.det(rotation)) - 1.0),
        )
        for port_id in element.ports:
            axis = element.world_from_port(port_id).rotation[:, 2]
            axis_norm_error = max(axis_norm_error, abs(float(np.linalg.norm(axis)) - 1.0))

    alignment_error = 0.0
    alignment_count = 0
    for element_spec in project.active_scenario["optical_assembly"]["elements"]:
        placement = element_spec["placement"]
        if placement["mode"] != "port":
            continue
        angular = placement.get("angular_misalignment_rad", (0.0, 0.0))
        if any(abs(float(value)) > 1e-15 for value in angular):
            continue
        source_element, _, source_port = str(placement["connect_from"]).rpartition(".")
        target_element, _, target_port = str(placement["connect_to"]).rpartition(".")
        source_axis = assembly[source_element].world_from_port(source_port).rotation[:, 2]
        target_axis = assembly[target_element].world_from_port(target_port).rotation[:, 2]
        cosine = float(np.clip(np.dot(source_axis, target_axis), -1.0, 1.0))
        alignment_error = max(alignment_error, math.acos(cosine))
        alignment_count += 1

    checks = [
        ConvergenceCheck(
            check_id="transform_orthonormality",
            status="pass" if orthonormal_error <= 1e-12 else "fail",
            metric="max_abs_RtR_minus_I",
            value=orthonormal_error,
            tolerance=1e-12,
            unit=None,
            message="모든 component rotation의 orthonormality를 검사했습니다.",
        ),
        ConvergenceCheck(
            check_id="transform_determinant",
            status="pass" if determinant_error <= 1e-12 else "fail",
            metric="max_abs_det_R_minus_1",
            value=determinant_error,
            tolerance=1e-12,
            unit=None,
            message="모든 component rotation determinant를 검사했습니다.",
        ),
        ConvergenceCheck(
            check_id="port_axis_norm",
            status="pass" if axis_norm_error <= 1e-12 else "fail",
            metric="max_abs_axis_norm_minus_1",
            value=axis_norm_error,
            tolerance=1e-12,
            unit=None,
            message="모든 optical port axis의 unit norm을 검사했습니다.",
        ),
        ConvergenceCheck(
            check_id="port_angular_alignment",
            status=(
                "pass"
                if alignment_count and alignment_error <= 1e-9
                else "not_applicable"
                if not alignment_count
                else "fail"
            ),
            metric="max_connected_port_axis_angle",
            value=alignment_error if alignment_count else None,
            tolerance=1e-9 if alignment_count else None,
            unit="rad" if alignment_count else None,
            message=(
                f"명시적 angular misalignment가 없는 port connection {alignment_count}개를 검사했습니다."
            ),
        ),
    ]
    return tuple(checks)


def _convergence_report(project: Any, assembly: AssemblyPlacement) -> ConvergenceReport:
    checks = list(_placement_checks(project, assembly))
    if project.assets.meshes:
        closed_count = sum(asset.audit.is_closed for asset in project.assets.meshes.values())
        checks.append(
            ConvergenceCheck(
                check_id="stl_topology_audit",
                status="pass",
                metric="audited_mesh_count",
                value=float(len(project.assets.meshes)),
                tolerance=None,
                unit="mesh",
                message=f"STL {len(project.assets.meshes)}개를 검사했으며 closed mesh는 {closed_count}개입니다.",
            )
        )
    else:
        checks.append(
            ConvergenceCheck(
                check_id="stl_topology_audit",
                status="not_applicable",
                metric="audited_mesh_count",
                value=0.0,
                tolerance=None,
                unit="mesh",
                message="Active STL asset이 없습니다.",
            )
        )
    checks.append(
        ConvergenceCheck(
            check_id="beam_physics_convergence",
            status="not_evaluated",
            metric="beam_metric_delta",
            value=None,
            tolerance=None,
            unit=None,
            message=(
                "Phase 0 report는 beam sampling을 실행하지 않습니다. "
                "Phase 1 검증은 lidarsim beam report에서 확인합니다."
            ),
        )
    )
    if any(check.status == "fail" for check in checks):
        overall = "fail"
    elif any(check.status in {"warning", "not_evaluated"} for check in checks):
        overall = "warning"
    else:
        overall = "pass"
    return ConvergenceReport(overall_status=overall, checks=tuple(checks))


def build_phase0_report(
    project: Any,
    assembly: AssemblyPlacement | None = None,
    *,
    created_at: datetime | None = None,
) -> Phase0Report:
    """현재 project state를 과장 없이 표현한 Phase 0 validation report를 만든다."""

    resolved_assembly = assembly or resolve_assembly(
        project.active_scenario,
        project.catalog,
        source=str(project.project_path),
    )
    scenario = project.active_scenario
    timestamp = created_at or datetime.now(UTC)
    manifest = RunManifest(
        project_id=str(project.project["project_id"]),
        scenario_id=str(scenario["scenario_id"]),
        config_hash=project.config_hash,
        created_at_utc=timestamp.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        software_version=__version__,
        backend=str(scenario["simulation"]["backend"]),
        real_dtype=str(scenario["simulation"]["real_dtype"]),
        random_seed=int(scenario["simulation"]["random_seed"]),
        deterministic=True,
        asset_hashes=_asset_hashes(project),
    )
    return Phase0Report(
        manifest=manifest,
        accuracy=_accuracy_report(project, resolved_assembly),
        energy_ledger=_energy_ledger(project),
        convergence=_convergence_report(project, resolved_assembly),
        placement=resolved_assembly.to_dict(),
    )
