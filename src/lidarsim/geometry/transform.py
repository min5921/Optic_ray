"""오른손 좌표계용 불변 rigid transform."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray


FloatArray = NDArray[np.float64]


def _readonly_float_array(value: ArrayLike, shape: tuple[int, ...], *, name: str) -> FloatArray:
    array = np.array(value, dtype=np.float64, copy=True)
    if array.shape != shape:
        raise ValueError(f"{name} shape은 {shape}여야 하지만 {array.shape}입니다.")
    if not np.all(np.isfinite(array)):
        raise ValueError(f"{name}에는 유한한 숫자만 사용할 수 있습니다.")
    array.setflags(write=False)
    return array


def normalize_vector(value: ArrayLike, *, name: str = "vector") -> FloatArray:
    """Vector를 float64 unit vector로 변환한다."""

    vector = np.array(value, dtype=np.float64, copy=True)
    if vector.shape != (3,):
        raise ValueError(f"{name} shape은 (3,)이어야 하지만 {vector.shape}입니다.")
    if not np.all(np.isfinite(vector)):
        raise ValueError(f"{name}에는 유한한 숫자만 사용할 수 있습니다.")
    norm = float(np.linalg.norm(vector))
    if norm <= 1e-15:
        raise ValueError(f"{name}은 zero vector일 수 없습니다.")
    result = vector / norm
    result.setflags(write=False)
    return result


@dataclass(frozen=True, slots=True, eq=False)
class RigidTransform:
    """`T_destination_from_source` convention을 따르는 rigid transform."""

    rotation: FloatArray
    translation_m: FloatArray

    def __post_init__(self) -> None:
        rotation = _readonly_float_array(self.rotation, (3, 3), name="rotation")
        translation = _readonly_float_array(self.translation_m, (3,), name="translation_m")
        gram = rotation.T @ rotation
        if not np.allclose(gram, np.eye(3), rtol=0.0, atol=1e-12):
            raise ValueError("rotation은 orthonormal matrix여야 합니다.")
        determinant = float(np.linalg.det(rotation))
        if not np.isclose(determinant, 1.0, rtol=0.0, atol=1e-12):
            raise ValueError("rotation determinant는 +1이어야 합니다.")
        object.__setattr__(self, "rotation", rotation)
        object.__setattr__(self, "translation_m", translation)

    @classmethod
    def identity(cls) -> "RigidTransform":
        """Identity transform을 반환한다."""

        return cls(np.eye(3, dtype=np.float64), np.zeros(3, dtype=np.float64))

    @classmethod
    def from_quaternion_wxyz(
        cls,
        quaternion_wxyz: ArrayLike,
        translation_m: ArrayLike = (0.0, 0.0, 0.0),
    ) -> "RigidTransform":
        """Normalize한 `[w, x, y, z]` quaternion으로 transform을 만든다."""

        quaternion = np.array(quaternion_wxyz, dtype=np.float64, copy=True)
        if quaternion.shape != (4,):
            raise ValueError(
                f"quaternion_wxyz shape은 (4,)이어야 하지만 {quaternion.shape}입니다."
            )
        if not np.all(np.isfinite(quaternion)):
            raise ValueError("quaternion_wxyz에는 유한한 숫자만 사용할 수 있습니다.")
        norm = float(np.linalg.norm(quaternion))
        if norm <= 1e-15:
            raise ValueError("quaternion_wxyz는 zero quaternion일 수 없습니다.")
        w, x, y, z = quaternion / norm
        rotation = np.array(
            [
                [1.0 - 2.0 * (y * y + z * z), 2.0 * (x * y - z * w), 2.0 * (x * z + y * w)],
                [2.0 * (x * y + z * w), 1.0 - 2.0 * (x * x + z * z), 2.0 * (y * z - x * w)],
                [2.0 * (x * z - y * w), 2.0 * (y * z + x * w), 1.0 - 2.0 * (x * x + y * y)],
            ],
            dtype=np.float64,
        )
        return cls(rotation, translation_m)

    @classmethod
    def from_axis_angle(
        cls,
        axis: ArrayLike,
        angle_rad: float,
        translation_m: ArrayLike = (0.0, 0.0, 0.0),
    ) -> "RigidTransform":
        """오른손 active axis-angle rotation으로 transform을 만든다."""

        unit_axis = normalize_vector(axis, name="axis")
        angle = float(angle_rad)
        if not np.isfinite(angle):
            raise ValueError("angle_rad에는 유한한 숫자만 사용할 수 있습니다.")
        x, y, z = unit_axis
        cosine = float(np.cos(angle))
        sine = float(np.sin(angle))
        one_minus_cosine = 1.0 - cosine
        rotation = np.array(
            [
                [
                    cosine + x * x * one_minus_cosine,
                    x * y * one_minus_cosine - z * sine,
                    x * z * one_minus_cosine + y * sine,
                ],
                [
                    y * x * one_minus_cosine + z * sine,
                    cosine + y * y * one_minus_cosine,
                    y * z * one_minus_cosine - x * sine,
                ],
                [
                    z * x * one_minus_cosine - y * sine,
                    z * y * one_minus_cosine + x * sine,
                    cosine + z * z * one_minus_cosine,
                ],
            ],
            dtype=np.float64,
        )
        return cls(rotation, translation_m)

    @property
    def matrix(self) -> FloatArray:
        """Read-only 4×4 homogeneous matrix를 반환한다."""

        matrix = np.eye(4, dtype=np.float64)
        matrix[:3, :3] = self.rotation
        matrix[:3, 3] = self.translation_m
        matrix.setflags(write=False)
        return matrix

    def inverse(self) -> "RigidTransform":
        """Source와 destination을 바꾼 inverse transform을 반환한다."""

        inverse_rotation = self.rotation.T
        inverse_translation = -(inverse_rotation @ self.translation_m)
        return RigidTransform(inverse_rotation, inverse_translation)

    def __matmul__(self, other: Any) -> "RigidTransform":
        """두 transform을 frame 순서대로 합성한다."""

        if not isinstance(other, RigidTransform):
            return NotImplemented
        rotation = self.rotation @ other.rotation
        translation = self.rotation @ other.translation_m + self.translation_m
        return RigidTransform(rotation, translation)

    def transform_point(self, point: ArrayLike) -> FloatArray:
        """Rotation과 translation을 point에 적용한다."""

        source = _readonly_float_array(point, (3,), name="point")
        result = self.rotation @ source + self.translation_m
        result.setflags(write=False)
        return result

    def transform_direction(self, direction: ArrayLike, *, normalize: bool = False) -> FloatArray:
        """Translation 없이 rotation만 direction에 적용한다."""

        source = _readonly_float_array(direction, (3,), name="direction")
        result = self.rotation @ source
        if normalize:
            return normalize_vector(result, name="transformed direction")
        result.setflags(write=False)
        return result

    def transform_normal(self, normal: ArrayLike) -> FloatArray:
        """Normal에 rotation을 적용하고 다시 normalize한다."""

        return self.transform_direction(normal, normalize=True)

    def almost_equal(self, other: "RigidTransform", *, atol: float = 1e-12) -> bool:
        """두 transform이 지정한 absolute tolerance 안에서 같은지 검사한다."""

        return bool(
            np.allclose(self.rotation, other.rotation, rtol=0.0, atol=atol)
            and np.allclose(self.translation_m, other.translation_m, rtol=0.0, atol=atol)
        )
