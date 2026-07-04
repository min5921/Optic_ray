"""Catalog optical port의 local coordinate frame."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np

from lidarsim.geometry.transform import RigidTransform, normalize_vector


@dataclass(frozen=True, slots=True)
class OpticalPort:
    """Component local frame에 정의된 optical connection port."""

    identifier: str
    role: str
    interface_type: str
    reference_plane: str
    T_component_from_port: RigidTransform

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "OpticalPort":
        """Validated catalog mapping에서 오른손 port frame을 만든다."""

        identifier = str(data["id"])
        role = str(data["role"])
        if role not in {"input", "output", "bidirectional"}:
            raise ValueError(f"지원하지 않는 optical port role입니다: {role!r}")
        interface_type = str(data.get("interface_type", "unspecified"))
        reference_plane = str(data.get("reference_plane", "unspecified"))

        z_axis = normalize_vector(data["propagation_axis_local"], name=f"{identifier}.z axis")
        x_candidate = np.array(data["transverse_x_local"], dtype=np.float64, copy=True)
        if x_candidate.shape != (3,) or not np.all(np.isfinite(x_candidate)):
            raise ValueError(f"{identifier}.transverse_x_local은 유한한 vec3여야 합니다.")
        x_projected = x_candidate - float(np.dot(x_candidate, z_axis)) * z_axis
        x_axis = normalize_vector(x_projected, name=f"{identifier}.x axis")
        y_axis = normalize_vector(np.cross(z_axis, x_axis), name=f"{identifier}.y axis")
        rotation = np.column_stack((x_axis, y_axis, z_axis))
        transform = RigidTransform(rotation, data["origin_local_m"])
        return cls(
            identifier=identifier,
            role=role,
            interface_type=interface_type,
            reference_plane=reference_plane,
            T_component_from_port=transform,
        )
