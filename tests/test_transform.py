from __future__ import annotations

import math

import numpy as np
import pytest

from lidarsim.geometry import RigidTransform


def test_rigid_transform_composition_and_inverse() -> None:
    transform = RigidTransform.from_axis_angle(
        (0.0, 0.0, 1.0),
        math.pi / 2.0,
        translation_m=(1.0, 2.0, 3.0),
    )

    assert transform.transform_point((1.0, 0.0, 0.0)) == pytest.approx((1.0, 3.0, 3.0))
    assert transform.transform_direction((1.0, 0.0, 0.0)) == pytest.approx((0.0, 1.0, 0.0))
    assert (transform.inverse() @ transform).almost_equal(RigidTransform.identity())


def test_quaternion_is_normalized_and_uses_wxyz_order() -> None:
    transform = RigidTransform.from_quaternion_wxyz((2.0, 0.0, 0.0, 0.0))

    assert transform.almost_equal(RigidTransform.identity())


def test_transform_arrays_are_immutable() -> None:
    transform = RigidTransform.identity()

    with pytest.raises(ValueError):
        transform.translation_m[0] = 1.0
    with pytest.raises(ValueError):
        transform.rotation[0, 0] = 2.0


def test_reflection_matrix_is_rejected() -> None:
    with pytest.raises(ValueError, match="determinant"):
        RigidTransform(np.diag((-1.0, 1.0, 1.0)), np.zeros(3))


def test_normal_is_renormalized() -> None:
    transform = RigidTransform.from_axis_angle((0.0, 1.0, 0.0), math.pi / 2.0)

    assert transform.transform_normal((0.0, 0.0, 5.0)) == pytest.approx((1.0, 0.0, 0.0))
