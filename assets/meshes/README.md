# Simulation mesh

Export한 STL mesh와 sidecar metadata를 이곳에 둔다.

예시:

```text
target_panel.stl
target_panel.stl.yaml
scan_mirror.stl
scan_mirror.stl.yaml
```

초기 제한 사항:

- STL 하나에는 role 하나와 기본 material 하나만 지정한다.
- 단위는 sidecar에 반드시 명시한다.
- Placement를 명시적으로 입력한다.
- Scanner mesh에는 pivot과 axis metadata가 필요하다.
- Lens mesh는 mechanical·visual geometry로만 사용한다.

Mesh를 추가할 때 [`mesh_metadata.example.yaml`](mesh_metadata.example.yaml)을 복사해 작성한다.

작성 후 다음 명령으로 sidecar와 실제 geometry를 함께 검증한다.

```powershell
lidarsim inspect-mesh assets/meshes/<mesh-name>.stl.yaml
```

검사 결과에는 encoding, raw·SI bounds, triangle·unique vertex 수, boundary·non-manifold edge, degenerate triangle, facet normal과 SHA-256이 포함된다.
