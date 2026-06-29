"""외부 geometry package에 의존하지 않는 STL parser와 geometry audit."""

from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from lidarsim.errors import ConfigFileError


FloatArray = NDArray[np.float64]


@dataclass(frozen=True, slots=True)
class MeshAudit:
    """STL geometry에서 계산한 immutable audit 결과."""

    path: Path
    encoding: str
    triangle_count: int
    unique_vertex_count: int
    bounds_raw: FloatArray
    bounds_m: FloatArray
    degenerate_triangle_count: int
    normal_mismatch_count: int
    boundary_edge_count: int
    nonmanifold_edge_count: int
    is_closed: bool
    content_sha256: str

    def __post_init__(self) -> None:
        for field_name in ("bounds_raw", "bounds_m"):
            array = np.array(getattr(self, field_name), dtype=np.float64, copy=True)
            if array.shape != (2, 3):
                raise ValueError(f"{field_name} shape은 (2, 3)이어야 합니다.")
            array.setflags(write=False)
            object.__setattr__(self, field_name, array)

    def to_dict(self) -> dict[str, Any]:
        """YAML·JSON report용 mapping을 반환한다."""

        return {
            "path": str(self.path),
            "encoding": self.encoding,
            "triangle_count": self.triangle_count,
            "unique_vertex_count": self.unique_vertex_count,
            "bounds_raw": self.bounds_raw.tolist(),
            "bounds_m": self.bounds_m.tolist(),
            "degenerate_triangle_count": self.degenerate_triangle_count,
            "normal_mismatch_count": self.normal_mismatch_count,
            "boundary_edge_count": self.boundary_edge_count,
            "nonmanifold_edge_count": self.nonmanifold_edge_count,
            "is_closed": self.is_closed,
            "content_sha256": self.content_sha256,
        }


def _parse_binary(data: bytes, path: Path) -> tuple[FloatArray, FloatArray] | None:
    if len(data) < 84:
        return None
    triangle_count = struct.unpack_from("<I", data, 80)[0]
    expected_size = 84 + triangle_count * 50
    if triangle_count == 0 or expected_size != len(data):
        return None
    record_dtype = np.dtype(
        [
            ("normal", "<f4", (3,)),
            ("vertices", "<f4", (3, 3)),
            ("attribute", "<u2"),
        ]
    )
    try:
        records = np.frombuffer(data, dtype=record_dtype, count=triangle_count, offset=84)
    except ValueError as exc:
        raise ConfigFileError(path, f"Binary STL record를 읽을 수 없습니다: {exc}") from exc
    normals = np.array(records["normal"], dtype=np.float64, copy=True)
    vertices = np.array(records["vertices"], dtype=np.float64, copy=True)
    return normals, vertices


def _parse_ascii(data: bytes, path: Path) -> tuple[FloatArray, FloatArray]:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text = data.decode("ascii")
        except UnicodeDecodeError as exc:
            raise ConfigFileError(path, "Binary 또는 ASCII STL 형식을 판별할 수 없습니다.") from exc

    normals: list[list[float]] = []
    triangles: list[list[list[float]]] = []
    current_normal: list[float] | None = None
    current_vertices: list[list[float]] = []
    try:
        for line_number, line in enumerate(text.splitlines(), start=1):
            fields = line.strip().split()
            if not fields:
                continue
            if len(fields) == 5 and fields[0].lower() == "facet" and fields[1].lower() == "normal":
                current_normal = [float(value) for value in fields[2:5]]
                current_vertices = []
            elif len(fields) == 4 and fields[0].lower() == "vertex":
                if current_normal is None:
                    raise ValueError(f"{line_number}행 vertex가 facet 밖에 있습니다.")
                current_vertices.append([float(value) for value in fields[1:4]])
            elif fields[0].lower() == "endfacet":
                if current_normal is None or len(current_vertices) != 3:
                    raise ValueError(f"{line_number}행 facet은 vertex 3개를 가져야 합니다.")
                normals.append(current_normal)
                triangles.append(current_vertices)
                current_normal = None
                current_vertices = []
    except ValueError as exc:
        raise ConfigFileError(path, f"ASCII STL parsing에 실패했습니다: {exc}") from exc

    if current_normal is not None:
        raise ConfigFileError(path, "ASCII STL의 마지막 facet이 닫히지 않았습니다.")
    if not triangles:
        raise ConfigFileError(path, "ASCII STL에서 triangle을 찾지 못했습니다.")
    return np.asarray(normals, dtype=np.float64), np.asarray(triangles, dtype=np.float64)


def _topology_counts(vertices: FloatArray) -> tuple[int, int, int]:
    flat_vertices = vertices.reshape(-1, 3)
    _, inverse = np.unique(flat_vertices, axis=0, return_inverse=True)
    indexed = inverse.reshape(-1, 3)
    edges = np.concatenate(
        (
            indexed[:, (0, 1)],
            indexed[:, (1, 2)],
            indexed[:, (2, 0)],
        ),
        axis=0,
    )
    edges.sort(axis=1)
    _, counts = np.unique(edges, axis=0, return_counts=True)
    boundary = int(np.count_nonzero(counts == 1))
    nonmanifold = int(np.count_nonzero(counts > 2))
    return int(np.unique(flat_vertices, axis=0).shape[0]), boundary, nonmanifold


def _geometry_counts(normals: FloatArray, vertices: FloatArray) -> tuple[int, int]:
    edge_a = vertices[:, 1] - vertices[:, 0]
    edge_b = vertices[:, 2] - vertices[:, 0]
    cross = np.cross(edge_a, edge_b)
    cross_norm = np.linalg.norm(cross, axis=1)
    extent = float(np.max(np.ptp(vertices.reshape(-1, 3), axis=0)))
    tolerance = max(extent * extent * 1e-12, 1e-30)
    valid = cross_norm > tolerance
    degenerate = int(np.count_nonzero(~valid))

    normal_norm = np.linalg.norm(normals, axis=1)
    supplied_valid = normal_norm > 1e-15
    mismatch = ~supplied_valid
    comparable = valid & supplied_valid
    if np.any(comparable):
        computed_unit = cross[comparable] / cross_norm[comparable, None]
        supplied_unit = normals[comparable] / normal_norm[comparable, None]
        mismatch[comparable] = np.einsum("ij,ij->i", computed_unit, supplied_unit) < 0.999
    return degenerate, int(np.count_nonzero(mismatch))


def inspect_stl(path: str | Path, *, unit_scale_m: float) -> MeshAudit:
    """Binary·ASCII STL을 읽고 scale·topology·normal audit를 수행한다."""

    mesh_path = Path(path).resolve()
    scale = float(unit_scale_m)
    if not np.isfinite(scale) or scale <= 0.0:
        raise ValueError("unit_scale_m은 유한한 양수여야 합니다.")
    try:
        data = mesh_path.read_bytes()
    except OSError as exc:
        raise ConfigFileError(mesh_path, f"STL 파일을 읽을 수 없습니다: {exc}") from exc

    parsed_binary = _parse_binary(data, mesh_path)
    if parsed_binary is not None:
        normals, vertices = parsed_binary
        encoding = "binary"
    else:
        normals, vertices = _parse_ascii(data, mesh_path)
        encoding = "ascii"

    if not np.all(np.isfinite(vertices)) or not np.all(np.isfinite(normals)):
        raise ConfigFileError(mesh_path, "STL에는 유한한 vertex와 normal만 사용할 수 있습니다.")
    bounds_raw = np.stack(
        (np.min(vertices.reshape(-1, 3), axis=0), np.max(vertices.reshape(-1, 3), axis=0))
    )
    unique_vertices, boundary_edges, nonmanifold_edges = _topology_counts(vertices)
    degenerate, normal_mismatch = _geometry_counts(normals, vertices)
    return MeshAudit(
        path=mesh_path,
        encoding=encoding,
        triangle_count=int(vertices.shape[0]),
        unique_vertex_count=unique_vertices,
        bounds_raw=bounds_raw,
        bounds_m=bounds_raw * scale,
        degenerate_triangle_count=degenerate,
        normal_mismatch_count=normal_mismatch,
        boundary_edge_count=boundary_edges,
        nonmanifold_edge_count=nonmanifold_edges,
        is_closed=boundary_edges == 0 and nonmanifold_edges == 0,
        content_sha256=hashlib.sha256(data).hexdigest(),
    )
