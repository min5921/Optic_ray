# Coordinate·placement·STL contract

- 상태: 초기 구현 contract
- 작성일: 2026-06-28

## 1. World coordinate system

Simulator는 오른손 world coordinate system을 사용한다.

- `+x`: 전방, nominal target 방향
- `+y`: 좌측
- `+z`: 상방

모든 내부 길이는 meter, 모든 내부 각도는 radian을 사용한다.

## 2. Vector와 transform convention

- Vector는 column vector다.
- Rotation은 active rotation이다.
- Homogeneous transform은 4×4 matrix다.
- `T_A_from_B`는 frame B로 표현된 coordinate를 frame A로 변환한다.

```text
p_A = T_A_from_B @ p_B
T_world_from_component = T_world_from_assembly @ T_assembly_from_component
```

Direction과 normal에는 rotation block만 적용한다. Normal은 transform 후 다시 normalize한다. Rigid component placement에는 non-uniform scale을 허용하지 않는다.

내부 rotation 표현:

- Normalize된 quaternion `[w, x, y, z]`
- 또는 orthonormal 3×3 rotation matrix

Input boundary에서 Euler angle을 허용할 수 있지만 `euler_order`를 반드시 명시해야 한다. 입력 즉시 내부 quaternion으로 변환한다.

## 3. Component frame

각 component는 다음 frame과 geometry를 정의할 수 있다.

- `component_frame`: 기본 rigid-body frame
- `mechanical_datums`: mount, pivot, mating 또는 measurement reference
- `optical_ports`: beam connection reference
- `surface_frames`: optical 또는 reflective surface reference
- `collision_geometry`: 선택적 mechanical envelope
- `visual_geometry`: 선택적 STL·STEP 표시 geometry

Mechanical datum과 optical port는 서로 다르다. 두 mount를 연결했다고 해서 optical axis가 완벽하게 정렬되는 것은 아니다. 그 관계는 catalog 또는 assembly constraint에 명시해야 한다.

## 4. Optical port convention

Optical port에는 다음 정보가 포함된다.

- 고유 port ID
- Local origin
- Nominal propagation 방향인 local `+z`
- Local `+x/+y` transverse axis
- Reference plane
- Clear aperture
- Input·output·bidirectional role
- 선택적 wavelength·profile·interface constraint

순서가 있는 transmit path에서 output port `+z`와 input port `+z`는 같은 propagation 방향으로 정렬한다.

Port-to-port placement에는 다음 값을 추가할 수 있다.

- 연결된 optical axis 방향의 axial gap
- Port plane의 transverse offset
- Optical axis 둘레의 clocking rotation
- 명시적인 angular misalignment

현재 구현은 다음 transform 순서를 사용한다.

```text
T_world_from_component
  = T_world_from_upstream_port
  @ T_upstream_port_from_target_port
  @ inverse(T_component_from_target_port)
```

`T_upstream_port_from_target_port`의 translation은 upstream port frame에서 `[offset_x, offset_y, axial_gap]`이다. Rotation은 `Rz(clocking) @ Ry(misalignment_y) @ Rx(misalignment_x)` 순서로 적용한다. 이 순서를 변경할 경우 schema version과 regression test를 함께 갱신해야 한다.

## 5. Placement mode

### Absolute

Component transform을 world 또는 assembly frame 기준으로 지정한다.

### Port-to-port

Component input port를 upstream output port에 정렬한 뒤 요청한 gap, offset, clocking과 misalignment를 적용한다.

### Constraint-based

향후 placement solver를 위해 예약한다. 초기 구현은 임의의 CAD 형태 constraint system을 parsing하지만 계산하지 않는다.

### Measured

Measurement 또는 calibration result에서 component transform을 불러온다. Nominal transform과 measured transform은 서로 구분해 유지한다.

## 6. STL import contract

STL은 triangle mesh 형식이므로 unit, material assignment, optical property, component port, pivot 또는 assembly constraint를 신뢰성 있게 저장하지 못한다. 따라서 import하는 모든 STL에는 명시적인 metadata가 필요하다.

초기 STL 규칙:

- Binary STL을 우선한다.
- 파일 하나에는 physical role 하나만 지정한다.
- Target STL 하나에는 기본 material 하나를 지정한다.
- `unit_scale_m`을 반드시 명시한다.
- Identity를 의도적으로 선택한 경우가 아니라면 placement transform을 반드시 명시한다.
- Normal은 policy에 따라 검사 후 repair하거나 거부한다.
- Open·non-manifold mesh는 role에 따라 warning 또는 error를 생성한다.
- Lens STL은 mechanical·visual geometry로만 사용한다.
- Scanner STL에는 pivot과 rotation axis를 명시해야 한다.
- MVP에서는 multi-material model을 여러 STL 파일로 분리해 export한다.

## 7. FreeCAD workflow

권장 project 흐름:

```text
FreeCAD .FCStd master
    ↓ 각 part/body export
binary STL mesh
    + 대응하는 .stl.yaml sidecar
    ↓
simulation asset loader
    ↓
검증된 SI-unit mesh + placement + role + material
```

FreeCAD source 파일은 `assets/source/freecad/`에 보관하고 export한 mesh는 `assets/meshes/`에 둔다.

Export 전 확인 사항:

1. 가능한 경우 model origin을 의미 있는 datum에 둔다.
2. 가능한 경우 scanner origin을 의도한 pivot에 둔다.
3. Project coordinate convention과 일관되게 model을 배향한다.
4. 서로 다른 material 또는 moving part는 별도 body로 export한다.
5. Optical footprint와 intersection accuracy에 충분한 tessellation을 선택한다.
6. Sidecar에 source filename과 revision을 보존한다.
7. Project viewer에서 import한 bounding box와 normal을 확인한다.

FreeCAD는 일반적으로 mechanical dimension을 millimeter로 표현하지만 importer는 STL unit을 추정하지 않는다. Millimeter로 export한 경우 sidecar에 `unit_scale_m: 0.001`을 입력한다.

## 8. Mesh role

- `target`: beam intersection과 material return 계산에 참여한다.
- `scanner_surface`: pivot과 axis를 가진 움직이는 reflective geometry다.
- `optical_mechanical`: visualization·collision에만 사용하며 optical behavior는 별도 prescription 또는 catalog record에서 가져온다.
- `mount`: visualization·collision에만 사용한다.
- `occluder`: visibility와 shadowing에만 사용한다.

## 9. Validation

Import할 때 다음 정보를 보고한다.

- Raw bounding box와 SI-scaled bounding box
- Triangle·vertex 수
- Manifold·open-edge 상태
- Normal orientation 요약
- 선택한 role과 material
- Component transform
- 필요한 경우 scanner pivot·axis
- 누락되었거나 가정한 metadata
- Source path와 content hash

Unit scale, role 또는 placement를 알 수 없는 STL을 warning 없이 받아들이지 않는다.
