"""Active scenario STL target closest-hit evaluation and visibility resolution."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Mapping

from lidarsim.config.paths import find_project_root
from lidarsim.scene.footprint import TargetFootprint
from lidarsim.scene.mesh import (
    RayMeshIntersection,
    TriangleMesh,
    intersect_ray_mesh,
    world_triangle_mesh_from_asset,
)


@dataclass(frozen=True, slots=True, eq=False)
class StlTargetIntersection:
    """One configured ``stl_asset`` target and its center-ray closest hit."""

    target_id: str
    material_ref: str
    asset_material_ref: str
    metadata_file: str
    asset_id: str
    mesh: TriangleMesh
    hit: bool
    status: str
    miss_reason: str | None
    surface_sidedness: str
    intersection: RayMeshIntersection | None
    visibility_status: str
    contributes_to_center_ray_visibility: bool
    occluded_by_target_id: str | None
    footprint_status: str = "not_evaluated"
    radiometry_status: str = "not_evaluated"
    assumptions: tuple[str, ...] = (
        "STL unit scale과 sidecar world placement를 적용한 immutable float64 triangle을 사용합니다.",
        "CPU NumPy Moller-Trumbore center ray의 nearest positive triangle hit만 계산합니다.",
        "STL triangle은 geometry와 geometric normal의 기준이며 optical scatterer가 아닙니다.",
        "M1은 STL full Gaussian footprint clipping과 radiometry를 계산하지 않습니다.",
    )
    warnings: tuple[str, ...] = ()

    @property
    def distance_m(self) -> float | None:
        if self.intersection is None:
            return None
        return self.intersection.distance_m

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_id": self.target_id,
            "material_ref": self.material_ref,
            "asset_material_ref": self.asset_material_ref,
            "geometry_type": "stl_asset",
            "metadata_file": self.metadata_file,
            "asset_id": self.asset_id,
            "mesh": self.mesh.to_dict(),
            "hit": self.hit,
            "status": self.status,
            "miss_reason": self.miss_reason,
            "surface_sidedness": self.surface_sidedness,
            "intersection": (
                None if self.intersection is None else self.intersection.to_dict()
            ),
            "visibility_status": self.visibility_status,
            "contributes_to_center_ray_visibility": (
                self.contributes_to_center_ray_visibility
            ),
            "occluded_by_target_id": self.occluded_by_target_id,
            "footprint_status": self.footprint_status,
            "radiometry_status": self.radiometry_status,
            "assumptions": list(self.assumptions),
            "warnings": list(self.warnings),
        }


def resolve_project_stl_asset(project: Any, geometry: Mapping[str, Any]) -> Any:
    """Resolve a scenario metadata reference to one validated registry asset."""

    asset_ref = geometry.get("asset_ref")
    if asset_ref is not None:
        asset = project.assets.meshes.get(str(asset_ref))
        if asset is None:
            raise ValueError(f"등록되지 않은 stl_asset asset_ref입니다: {asset_ref!r}")
        return asset
    metadata_file = str(geometry.get("metadata_file", ""))
    declared = Path(metadata_file)
    project_root = find_project_root(project.project_path)
    if declared.is_absolute():
        raise ValueError("Legacy metadata_file은 project-root-relative 경로여야 합니다.")
    candidate = (project_root / declared).resolve()
    if not candidate.is_relative_to(project_root):
        raise ValueError("Legacy metadata_file은 project root 밖을 참조할 수 없습니다.")
    matches = [
        asset
        for asset in project.assets.meshes.values()
        if asset.metadata_path.resolve() == candidate
    ]
    if len(matches) != 1:
        raise ValueError(
            "stl_asset metadata_file은 project asset registry의 정확히 한 sidecar를 "
            f"참조해야 합니다: {metadata_file!r}"
        )
    return matches[0]


def evaluate_stl_target_intersections(
    project: Any,
    beam: Any,
    *,
    blocked_reason: str | None = None,
) -> tuple[StlTargetIntersection, ...]:
    """Evaluate every active ``stl_asset`` target without footprint/radiometry."""

    results: list[StlTargetIntersection] = []
    for target in project.active_scenario["scene"]["targets"]:
        geometry = target["geometry"]
        if str(geometry["type"]) != "stl_asset":
            continue
        asset = resolve_project_stl_asset(project, geometry)
        project_root = find_project_root(project.project_path)
        try:
            metadata_file = asset.metadata_path.relative_to(project_root).as_posix()
        except ValueError:
            metadata_file = str(asset.metadata_path)
        mesh = world_triangle_mesh_from_asset(asset)
        target_id = str(target["id"])
        material_ref = str(target["material_ref"])
        asset_material_ref = str(asset.data["material"]["default_material_ref"])
        material = project.catalog[material_ref].data
        sidedness = str(material["optical"].get("surface_sidedness", "two_sided"))
        warnings = [warning.format() for warning in asset.warnings]

        if blocked_reason is not None:
            warnings.append(
                "Upstream optical train termination 때문에 STL center-ray closest-hit를 계산하지 않았습니다."
            )
            results.append(
                StlTargetIntersection(
                    target_id=target_id,
                    material_ref=material_ref,
                    asset_material_ref=asset_material_ref,
                    metadata_file=metadata_file,
                    asset_id=asset.identifier,
                    mesh=mesh,
                    hit=False,
                    status="not_evaluated",
                    miss_reason=f"upstream_optical_train_terminated:{blocked_reason}",
                    surface_sidedness=sidedness,
                    intersection=None,
                    visibility_status="not_evaluated",
                    contributes_to_center_ray_visibility=False,
                    occluded_by_target_id=None,
                    warnings=tuple(warnings),
                )
            )
            continue

        intersection = intersect_ray_mesh(beam.origin_m, beam.direction, mesh)
        accepted = bool(
            intersection.hit
            and (sidedness == "two_sided" or intersection.front_face is True)
        )
        if intersection.hit and not accepted:
            status = "backface_culled"
            miss_reason = "backface_culled"
            warnings.append(
                "Geometric triangle hit는 존재하지만 one_sided material의 back face라 target hit에서 제외했습니다."
            )
        else:
            status = intersection.status
            miss_reason = intersection.miss_reason
        results.append(
            StlTargetIntersection(
                target_id=target_id,
                material_ref=material_ref,
                asset_material_ref=asset_material_ref,
                metadata_file=metadata_file,
                asset_id=asset.identifier,
                mesh=mesh,
                hit=accepted,
                status=status,
                miss_reason=miss_reason,
                surface_sidedness=sidedness,
                intersection=intersection,
                visibility_status="candidate_unresolved" if accepted else "miss",
                contributes_to_center_ray_visibility=False,
                occluded_by_target_id=None,
                warnings=tuple(warnings),
            )
        )
    return tuple(results)


def resolve_mixed_target_visibility(
    footprints: tuple[TargetFootprint, ...],
    stl_intersections: tuple[StlTargetIntersection, ...],
) -> tuple[tuple[TargetFootprint, ...], tuple[StlTargetIntersection, ...]]:
    """Resolve one nearest positive center-ray target across rectangle and STL."""

    candidates: list[tuple[float, str, str]] = []
    for footprint in footprints:
        distance = footprint.intersection.distance_to_target_m
        if (
            footprint.intersection.geometry_type == "rectangle_plane"
            and footprint.hit
            and distance is not None
        ):
            candidates.append((float(distance), footprint.target_id, "rectangle_plane"))
    for result in stl_intersections:
        if result.hit and result.distance_m is not None:
            candidates.append((float(result.distance_m), result.target_id, "stl_asset"))
    if not candidates:
        return footprints, stl_intersections

    _, visible_target_id, visible_geometry_type = min(
        candidates,
        key=lambda item: (item[0], item[1], item[2]),
    )
    resolved_footprints: list[TargetFootprint] = []
    for footprint in footprints:
        if footprint.intersection.geometry_type != "rectangle_plane" or not footprint.hit:
            resolved_footprints.append(footprint)
            continue
        if (
            footprint.target_id == visible_target_id
            and visible_geometry_type == "rectangle_plane"
        ):
            resolved_footprints.append(
                replace(
                    footprint,
                    visibility_status="visible_nearest",
                    contributes_to_scene_energy=True,
                    occluded_by_target_id=None,
                )
            )
            continue
        resolved_footprints.append(
            replace(
                footprint,
                estimated_power_on_target_w=0.0,
                visibility_status="occluded_by_nearer_target",
                contributes_to_scene_energy=False,
                occluded_by_target_id=visible_target_id,
                warnings=(
                    *footprint.warnings,
                    f"Center ray의 더 가까운 target {visible_target_id!r}에 가려져 scene energy contribution을 0으로 둡니다.",
                ),
            )
        )

    resolved_stl: list[StlTargetIntersection] = []
    for result in stl_intersections:
        if not result.hit:
            resolved_stl.append(result)
            continue
        if result.target_id == visible_target_id and visible_geometry_type == "stl_asset":
            resolved_stl.append(
                replace(
                    result,
                    visibility_status="visible_nearest",
                    contributes_to_center_ray_visibility=True,
                    occluded_by_target_id=None,
                )
            )
            continue
        resolved_stl.append(
            replace(
                result,
                visibility_status="occluded_by_nearer_target",
                contributes_to_center_ray_visibility=False,
                occluded_by_target_id=visible_target_id,
                warnings=(
                    *result.warnings,
                    f"Center ray의 더 가까운 target {visible_target_id!r} 뒤에 가려졌습니다.",
                ),
            )
        )
    return tuple(resolved_footprints), tuple(resolved_stl)


__all__ = [
    "StlTargetIntersection",
    "evaluate_stl_target_intersections",
    "resolve_mixed_target_visibility",
    "resolve_project_stl_asset",
]
