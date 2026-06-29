from __future__ import annotations

import shutil
import struct
from pathlib import Path

import numpy as np
import pytest


@pytest.fixture
def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


@pytest.fixture
def copied_project(tmp_path: Path, project_root: Path) -> Path:
    for name in ("schemas", "configs", "catalog", "assets"):
        shutil.copytree(project_root / name, tmp_path / name)
    return tmp_path / "configs" / "project.yaml"


@pytest.fixture
def write_binary_stl():
    def write(path: Path, triangles) -> Path:
        payload = bytearray(b"Optic Ray test STL".ljust(80, b"\0"))
        payload.extend(struct.pack("<I", len(triangles)))
        for triangle in triangles:
            vertices = np.asarray(triangle, dtype=np.float64)
            normal = np.cross(vertices[1] - vertices[0], vertices[2] - vertices[0])
            norm = float(np.linalg.norm(normal))
            if norm > 0.0:
                normal = normal / norm
            values = [*normal.tolist(), *vertices.reshape(-1).tolist()]
            payload.extend(struct.pack("<12fH", *values, 0))
        path.write_bytes(payload)
        return path

    return write
