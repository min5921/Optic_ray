# Simulation asset

이 directory에는 사용자가 제공한 geometry와 관련 metadata를 보관한다.

```text
assets/
├─ source/freecad/   # 선택적으로 보관하는 편집 가능한 FreeCAD 원본
├─ meshes/           # simulator가 읽는 STL 파일
└─ measurements/     # calibration 및 validation dataset
```

규칙:

- 편집 가능한 `.FCStd` 원본과 export한 mesh를 분리한다.
- 움직이는 부품이나 서로 다른 재질 영역은 별도 STL로 export한다.
- 모든 STL 옆에 대응하는 `.stl.yaml` sidecar를 둔다.
- STL geometry에서 lens의 optical performance를 추정하지 않는다.
- 재배포를 금지하는 license가 있는 vendor 파일은 commit하지 않는다.
- 생성된 simulation 결과는 이곳이 아니라 `outputs/` 또는 `results/`에 둔다.

Import contract는 [`../docs/specs/COORDINATES_AND_PLACEMENT.md`](../docs/specs/COORDINATES_AND_PLACEMENT.md)를 참고한다.
