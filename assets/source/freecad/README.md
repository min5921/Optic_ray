# FreeCAD 원본

선택적으로 보관할 편집 가능한 `.FCStd` source model을 이곳에 둔다.

권장 절차:

1. 움직이는 부품이나 material 영역마다 별도 body를 사용한다.
2. 특히 scanner pivot을 고려해 의미 있는 origin을 정한다.
3. Simulation body를 binary STL로 `../../meshes/`에 export한다.
4. 대응하는 `.stl.yaml` metadata 파일을 만든다.
5. 3D viewer에서 import된 bounding box, orientation, normal과 pivot을 확인한다.

`.FCStd1` 같은 FreeCAD backup 파일은 무시되며 기본 `.FCStd` 파일은 Git에서 제외되지 않는다.
