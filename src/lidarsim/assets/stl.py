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


@dataclass(frozen=True, slots=True, eq=False)
class MeshGeometry:
    """STL에서 읽은 immutable triangle geometry.

    ``triangle_vertices``와 ``supplied_normals``는 STL mesh frame의 원본 단위를
    유지한다. ``geometric_normals``는 facet normal을 신뢰하지 않고 vertex winding으로
    계산한 unit normal이며, degenerate triangle에는 zero vector가 들어간다.
    """

    path: Path
    encoding: str
    triangle_vertices: FloatArray
    supplied_normals: FloatArray
    geometric_normals: FloatArray
    valid_triangle_mask: NDArray[np.bool_]
    content_sha256: str

    def __post_init__(self) -> None:
        vertices = np.array(self.triangle_vertices, dtype=np.float64, copy=True)
        if vertices.ndim != 3 or vertices.shape[1:] != (3, 3) or vertices.shape[0] == 0:
            raise ValueError("triangle_vertices shape은 (N, 3, 3), N > 0이어야 합니다.")
        if not np.all(np.isfinite(vertices)):
            raise ValueError("triangle_vertices에는 유한한 숫자만 사용할 수 있습니다.")
        triangle_count = vertices.shape[0]

        supplied = np.array(self.supplied_normals, dtype=np.float64, copy=True)
        geometric = np.array(self.geometric_normals, dtype=np.float64, copy=True)
        valid = np.array(self.valid_triangle_mask, dtype=np.bool_, copy=True)
        if supplied.shape != (triangle_count, 3):
            raise ValueError("supplied_normals shape은 (N, 3)이어야 합니다.")
        if geometric.shape != (triangle_count, 3):
            raise ValueError("geometric_normals shape은 (N, 3)이어야 합니다.")
        if valid.shape != (triangle_count,):
            raise ValueError("valid_triangle_mask shape은 (N,)이어야 합니다.")
        if not np.all(np.isfinite(supplied)) or not np.all(np.isfinite(geometric)):
            raise ValueError("STL normal에는 유한한 숫자만 사용할 수 있습니다.")
        if np.any(valid):
            valid_norms = np.linalg.norm(geometric[valid], axis=1)
            if not np.allclose(valid_norms, 1.0, rtol=0.0, atol=1e-12):
                raise ValueError("유효한 geometric_normals는 unit vector여야 합니다.")
        if np.any(~valid) and not np.allclose(
            geometric[~valid], 0.0, rtol=0.0, atol=0.0
        ):
            raise ValueError("Degenerate triangle의 geometric normal은 zero vector여야 합니다.")
        if self.encoding not in {"ascii", "binary"}:
            raise ValueError("encoding은 'ascii' 또는 'binary'여야 합니다.")
        if len(self.content_sha256) != 64:
            raise ValueError("content_sha256은 64자리 SHA-256 hex digest여야 합니다.")

        for array in (vertices, supplied, geometric, valid):
            array.setflags(write=False)
        object.__setattr__(self, "path", Path(self.path).resolve())
        object.__setattr__(self, "triangle_vertices", vertices)
        object.__setattr__(self, "supplied_normals", supplied)
        object.__setattr__(self, "geometric_normals", geometric)
        object.__setattr__(self, "valid_triangle_mask", valid)

    @property
    def triangle_count(self) -> int:
        return int(self.triangle_vertices.shape[0])

    @property
    def degenerate_triangle_count(self) -> int:
        return int(np.count_nonzero(~self.valid_triangle_mask))

    def to_dict(self) -> dict[str, Any]:
        """큰 vertex payload를 제외한 geometry contract 요약을 반환한다."""

        return {
            "path": str(self.path),
            "encoding": self.encoding,
            "triangle_count": self.triangle_count,
            "degenerate_triangle_count": self.degenerate_triangle_count,
            "vertex_dtype": str(self.triangle_vertices.dtype),
            "geometric_normal_source": "triangle_vertex_winding",
            "content_sha256": self.content_sha256,
        }


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
    geometric_normals, valid = _compute_geometric_normals(vertices)
    degenerate = int(np.count_nonzero(~valid))

    normal_norm = np.linalg.norm(normals, axis=1)
    supplied_valid = normal_norm > 1e-15
    mismatch = ~supplied_valid
    comparable = valid & supplied_valid
    if np.any(comparable):
        supplied_unit = normals[comparable] / normal_norm[comparable, None]
        mismatch[comparable] = (
            np.einsum("ij,ij->i", geometric_normals[comparable], supplied_unit) < 0.999
        )
    return degenerate, int(np.count_nonzero(mismatch))


def _compute_geometric_normals(
    vertices: FloatArray,
) -> tuple[FloatArray, NDArray[np.bool_]]:
    """Vertex winding으로 unit normal과 non-degenerate mask를 계산한다."""

    edge_a = vertices[:, 1] - vertices[:, 0]
    edge_b = vertices[:, 2] - vertices[:, 0]
    cross = np.cross(edge_a, edge_b)
    cross_norm = np.linalg.norm(cross, axis=1)
    extent = float(np.max(np.ptp(vertices.reshape(-1, 3), axis=0)))
    tolerance = max(extent * extent * 1e-12, 1e-30)
    valid = cross_norm > tolerance
    geometric_normals = np.zeros_like(cross, dtype=np.float64)
    geometric_normals[valid] = cross[valid] / cross_norm[valid, None]
    return geometric_normals, valid


def load_stl_geometry(path: str | Path) -> MeshGeometry:
    """Binary·ASCII STL triangle을 손실 없이 float64 geometry로 읽는다."""

    mesh_path = Path(path).resolve()
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
    geometric_normals, valid = _compute_geometric_normals(vertices)
    return MeshGeometry(
        path=mesh_path,
        encoding=encoding,
        triangle_vertices=vertices,
        supplied_normals=normals,
        geometric_normals=geometric_normals,
        valid_triangle_mask=valid,
        content_sha256=hashlib.sha256(data).hexdigest(),
    )


def inspect_mesh_geometry(geometry: MeshGeometry, *, unit_scale_m: float) -> MeshAudit:
    """이미 읽은 STL geometry에서 기존 audit contract를 계산한다."""

    scale = float(unit_scale_m)
    if not np.isfinite(scale) or scale <= 0.0:
        raise ValueError("unit_scale_m은 유한한 양수여야 합니다.")
    vertices = geometry.triangle_vertices
    bounds_raw = np.stack(
        (np.min(vertices.reshape(-1, 3), axis=0), np.max(vertices.reshape(-1, 3), axis=0))
    )
    unique_vertices, boundary_edges, nonmanifold_edges = _topology_counts(vertices)
    degenerate, normal_mismatch = _geometry_counts(geometry.supplied_normals, vertices)
    return MeshAudit(
        path=geometry.path,
        encoding=geometry.encoding,
        triangle_count=geometry.triangle_count,
        unique_vertex_count=unique_vertices,
        bounds_raw=bounds_raw,
        bounds_m=bounds_raw * scale,
        degenerate_triangle_count=degenerate,
        normal_mismatch_count=normal_mismatch,
        boundary_edge_count=boundary_edges,
        nonmanifold_edge_count=nonmanifold_edges,
        is_closed=boundary_edges == 0 and nonmanifold_edges == 0,
        content_sha256=geometry.content_sha256,
    )


def inspect_stl(path: str | Path, *, unit_scale_m: float) -> MeshAudit:
    """Binary·ASCII STL을 읽고 scale·topology·normal audit를 수행한다."""

    return inspect_mesh_geometry(
        load_stl_geometry(path),
        unit_scale_m=unit_scale_m,
    )
