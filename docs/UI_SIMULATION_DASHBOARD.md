# 시뮬레이션 UI와 Optical Assembly Workspace 개발 계획

- 문서 상태: Draft
- 작성일: 2026-07-09
- 대상: Optic Ray simulation을 사용자가 쉽게 배치·정렬·실행·분석하기 위한 로컬 UI
- 기준 구현 상태: Phase 2.3 static optical train, rectangle-plane footprint, Lambertian receiver return

## 1. 최상위 목표 — Optical Assembly Workspace

이 UI의 장기 목표는 단순히 simulation 결과를 보여주는 Streamlit dashboard가 아니다.

최종 목표는 SolidWorks 또는 optical bench software처럼 동작하는 optical assembly workspace다. 사용자는 3D 공간에 source, collimator, lens, mirror, scanner, target, receiver를 배치하고, guideline, snap, mate, constraint를 이용해 광학계를 정렬한 뒤 beam을 쏘고 결과를 시각적으로 확인할 수 있어야 한다.

장기적으로 사용자가 하고 싶은 작업은 다음에 가깝다.

```text
광학 부품 선택
→ 3D 공간에 배치
→ port / optical axis / focal distance / mirror normal 기준으로 정렬
→ beam 발사
→ 반사 방향, target hit, footprint, receiver FOV 확인
→ received power와 link budget 분석
→ variant config로 저장
```

따라서 UI는 두 층으로 나누어 생각한다.

```text
Optical Assembly Workspace
    3D 배치, 정렬, constraint, snapping, optical path visualization

Simulation Dashboard
    validate, run, report, plots, power ledger, footprint, receiver return
```

Simulation dashboard는 필요하지만 충분하지 않다. 사용자가 정말 편하게 쓰려면 “어디에 부품을 놓고 어떻게 정렬했는가”를 직접 보고 수정할 수 있어야 한다.

## 2. 기본 원칙

UI는 물리 engine을 대체하지 않는다. UI는 사용자가 쉽게 조작하는 assembly editor와 experiment dashboard이며, 실제 authoritative source는 여전히 versioned configuration, schema, catalog와 report다.

핵심 원칙은 다음과 같다.

```text
YAML / Schema / CLI = 재현 가능한 물리 engine과 기록
UI = 사용자가 쉽게 조작하는 optical bench workspace
```

UI에서 바꾼 값은 숨겨진 상태로 남으면 안 된다. 모든 placement edit, parameter edit, constraint edit는 configuration으로 serialize되어야 하며, 같은 configuration을 CLI에서 실행했을 때 같은 결과가 나와야 한다.

반드시 지킬 규칙:

1. UI와 CLI는 같은 config/schema/validator를 사용한다.
2. UI가 숨겨진 physical state의 유일한 원본이 되면 안 된다.
3. 모든 placement edit는 config로 저장 가능해야 한다.
4. baseline config를 조용히 덮어쓰지 않는다.
5. warning과 unsupported feature를 숨기지 않는다.
6. analytical reference와 calibrated hardware prediction을 명확히 구분한다.
7. 단위 입력은 UI에서 편하게 받더라도 내부 저장은 SI/radian resolved config를 따른다.
8. output report에는 config hash, timestamp, model scope, assumptions, limitations가 남아야 한다.
9. 생성 결과와 cache는 Git에 추가하지 않는다.
10. UI 기능은 작은 analytical case test를 통과한 뒤 확장한다.

## 3. 현재 계획의 gap

기존 UI Phase 0.1은 read-only/result dashboard에 가깝다.

즉, 다음은 가능하다.

- project config 선택
- validate 실행
- optical-train 실행
- summary metric 표시
- warning 표시
- optical train PNG 표시
- report YAML 확인

하지만 이것만으로는 사용자가 원하는 SolidWorks-like placement workflow를 만족하지 못한다.

UI Phase 0.1이 아직 제공하지 못하는 것:

- component를 3D 공간에서 선택하기
- component를 drag/rotate하기
- position/orientation을 직접 편집하기
- port-to-port snap
- optical axis guideline
- focal distance guideline
- mirror를 target center에 맞게 회전
- receiver를 hit point로 정렬
- placement constraint/mate 목록 관리
- undo/redo
- interactive 3D viewport

따라서 UI 개발은 dashboard만 만들고 끝내면 안 된다. 먼저 현재 결과를 쉽게 보는 dashboard를 만들 수는 있지만, 장기 계획에는 optical assembly workspace phase를 명확히 포함해야 한다.

## 4. 진행 규칙과 첫 구현 순서

UI와 물리 engine은 경쟁 관계가 아니다. UI를 먼저 완성한 뒤 물리를 멈추는 방식도 아니고, 물리 engine만 계속 만든 뒤 마지막에 UI를 붙이는 방식도 아니다.

이 프로젝트는 다음 규칙으로 진행한다.

```text
얇은 optical workspace UI 골격을 먼저 만든다.
그 다음 물리 기능을 하나씩 추가할 때마다 UI에 즉시 연결한다.
```

### 4.1 우선순위 결정 규칙

#### 규칙 1 — 사용자가 볼 수 없는 물리 기능은 반쪽 구현이다

새 물리 기능을 추가하면 최소한 다음 중 하나로 사용자가 확인할 수 있어야 한다.

- YAML report
- PNG/HTML report
- UI metric
- 3D viewport overlay

예를 들어 scanner command angle을 구현하면 report에만 남기지 말고, UI에서도 mirror normal과 reflected ray가 바뀌는 것을 보여줘야 한다.

#### 규칙 2 — UI가 숨겨진 source of truth가 되면 안 된다

UI에서 placement나 parameter를 바꾸더라도 그 값은 반드시 configuration으로 저장 가능해야 한다.

허용되는 흐름:

```text
UI edit
→ config patch 또는 variant config 생성
→ validate
→ simulation
→ structured report
```

금지되는 흐름:

```text
UI 내부 state만 변경
→ 저장 불가
→ CLI 재현 불가
```

#### 규칙 3 — 3D drag보다 numeric placement를 먼저 구현한다

SolidWorks-like editor가 최종 목표라도 처음부터 drag/rotate gizmo를 만들지 않는다.

먼저 numeric placement editor를 구현한다.

- position x/y/z
- orientation
- axial gap
- transverse offset
- angular misalignment
- validate
- save variant config

이 단계가 안정되어야 snapping, constraint, gizmo가 의미를 가진다.

#### 규칙 4 — Viewer와 editor를 분리한다

초기에는 viewer를 먼저 만든다.

```text
Viewer: 현재 config와 simulation 결과를 보여준다.
Editor: 사용자가 config를 바꾼다.
```

첫 MVP는 viewer 중심이지만, source 구조는 editor로 확장 가능하게 만든다.

#### 규칙 5 — 작은 end-to-end vertical slice만 merge한다

각 단계는 작게 끝나야 한다.

좋은 단위:

- 3D bench viewer가 source/collimator/mirror/target/receiver를 표시한다.
- numeric editor가 target distance 하나를 바꾸고 variant config를 저장한다.
- scanner angle 하나가 reflected ray와 target hit를 바꾼다.

나쁜 단위:

- 완성형 CAD editor 전체
- full snapping/constraint/gizmo를 한 번에 구현
- UI와 physics를 동시에 대규모 rewrite

#### 규칙 6 — warning과 limitation을 UI에서 숨기지 않는다

UI는 사용자를 편하게 만들어야 하지만, model fidelity를 과장하면 안 된다.

항상 표시할 것:

- hardware readiness
- calibration status
- analytical/reference 여부
- unsupported output
- assumptions
- limitations

#### 규칙 7 — 기존 CLI와 test를 깨지 않는다

UI가 추가되어도 기존 명령은 계속 동작해야 한다.

- `lidarsim validate`
- `lidarsim placement`
- `lidarsim view`
- `lidarsim review`
- `lidarsim beam`
- `lidarsim optical-train`

UI 기능은 이 명령들을 우회하지 않고 같은 loader, schema, physics function을 사용해야 한다.

### 4.2 결정된 첫 구현 순서

현재 기준으로 결정된 순서는 다음과 같다.

```text
1. Viewport data contract
2. UI MVP 0: 3D optical bench viewer + read-only simulation dashboard
3. Phase 3 scanner command angle physics
4. UI 연결: scanner angle에 따른 reflected ray / target hit 변화
5. Numeric placement editor
6. Guidelines and snapping
7. Constraint / mate system
8. Interactive 3D editor
```

### 4.3 바로 다음 patch의 범위

다음 patch는 UI MVP 0으로 제한한다.

포함:

- optional UI dependency 정책 결정
- `ViewportScene` 계열 dataclass 초안
- 현재 project config에서 viewport scene 생성
- source/collimator/mirror/target/receiver 표시용 data 생성
- optical axis, mirror normal, beam path, reflected ray 생성
- target hit marker, footprint overlay, receiver FOV guide 생성
- read-only summary dashboard

제외:

- drag/rotate gizmo
- snapping
- full constraint solver
- scanner time waveform
- STL hit detection
- coherent FMCW

이 순서로 가면 단순 dashboard가 아니라 optical assembly workspace의 뼈대를 먼저 세우면서도, 현재 구현된 Phase 2.3 simulation을 바로 사용자가 볼 수 있게 만들 수 있다.

### 4.4 현재 구현된 UI MVP 0 slice

이번 구현에서는 무거운 UI framework를 바로 추가하지 않고, optical assembly workspace의 공통 data contract, headless viewer와 self-contained read-only dashboard를 먼저 만들었다.

구현된 범위:

- `ViewportScene` data contract
- `ViewportComponent`
- `ViewportPort`
- `GuideLine`
- `RaySegment`
- `FootprintOverlay`
- 향후 editor용 `PlacementConstraint`
- 향후 editor용 `PlacementEdit`
- 현재 project config와 Phase 2.3 report에서 viewport scene 생성
- source, collimator, scanner mirror, rectangle target, receiver 표시용 component data 생성
- component local frame guide 생성
- port axis guide 생성
- mirror normal guide 생성
- reflected ray guide 생성
- target plane edge guide 생성
- receiver FOV guide 생성
- optical train ray segment와 target hit ray 생성
- target footprint overlay 생성
- `lidarsim workspace` CLI 명령
- workspace PNG 생성
- optional viewport scene YAML 저장
- `lidarsim dashboard` CLI 명령
- Phase 2 report YAML, `ViewportScene` YAML, workspace PNG, optical train PNG와 dashboard HTML 동시 생성
- summary, warning, power ledger, target footprint, receiver return을 HTML에서 표시
- `lidarsim placement-variant` CLI 명령
- absolute placement와 port placement의 numeric edit를 variant scenario/project로 저장
- `lidarsim scanner-sweep` CLI 명령
- 여러 static scanner command angle의 target hit, received power와 link budget trend를 YAML/CSV/PNG로 저장
- `lidarsim scanner-path` CLI 명령
- config의 scanner waveform에서 한 줄 ideal forward path를 시간 sample로 생성하고 target/receiver trend를 YAML/CSV/PNG로 저장
- `lidarsim dashboard --include-scanner-path` 옵션
- read-only dashboard에 scanner path plot과 sample table을 선택적으로 embedding

현재 실행 예:

```powershell
lidarsim workspace configs/project.yaml --output results/ui_workspace.png --write-scene results/ui_workspace_scene.yaml
lidarsim dashboard configs/project.yaml --output results/ui_dashboard.html
lidarsim placement-variant configs/project.yaml --element scan_mirror --scenario-id mirror_shift --translation-m 0.1 0 0
lidarsim scanner-sweep configs/project.yaml --angles-deg -5 0 5 --output results/scanner_sweep.yaml
lidarsim scanner-path configs/project.yaml --samples 11 --output results/scanner_path.yaml
lidarsim dashboard configs/project.yaml --output results/ui_dashboard_with_path.html --include-scanner-path --scanner-path-samples 11
```

중요한 한계:

- 아직 Streamlit process나 interactive web app은 아니다.
- 아직 component picking은 없다.
- 아직 browser UI 형태의 numeric placement editor는 없다.
- 아직 snapping, mate, drag/rotate gizmo는 없다.
- `placement-variant`는 baseline을 덮어쓰지 않고 variant config를 생성한다.
- `scanner-sweep`은 static angle 비교 helper이며 scanner time waveform은 아직 아니다.
- `scanner-path`는 ideal forward-line command path이며 motor dynamics나 calibration table은 아직 아니다.

이번 slice의 의미는 “나중에 어떤 UI를 쓰든 같은 `ViewportScene`과 Phase 2 report를 소비하게 만드는 것”이다. Streamlit, Plotly, Three.js, React frontend는 이 contract 위에 붙이면 된다.

## 5. 현재 바로 시각화할 수 있는 simulation 결과

현재 구현된 simulation path는 다음과 같다.

```text
source
→ Gaussian beam
→ ideal thin-lens collimator
→ static flat scanner mirror reflection
→ rectangle-plane target footprint
→ Lambertian virtual receiver return
→ link budget
```

현재 UI에서 표시 가능한 값:

- validation 상태
- hardware readiness와 calibration status
- source/collimator/mirror/target/receiver 위치
- optical axis
- mirror normal
- static reflected ray
- final beam radius
- final optical power
- power ledger
- mirror incidence angle
- mirror aperture clipping 상태
- target hit 또는 miss
- target hit marker
- target footprint radius와 area
- estimated power on target
- receiver FOV 상태
- estimated received aperture power
- link loss dB
- warnings와 limitations
- optical train PNG
- workspace PNG
- self-contained dashboard HTML
- placement PNG
- report YAML

아직 표시하더라도 계산 결과라고 주장하면 안 되는 항목:

- scanner time-dependent scan path
- STL target hit detection
- occlusion 또는 visibility
- BRDF/BSDF
- diffraction
- detector noise와 saturation
- coherent FMCW signal
- speckle
- FFT/CZT range result

## 6. UI 개발 단계

### UI Phase 0.1 — Read-only Result Dashboard

목표는 현재 Phase 2.3 simulation을 버튼으로 실행하고, 핵심 결과를 사람이 보기 쉬운 dashboard로 표시하는 것이다.

기능:

- project config 선택
- active scenario 표시
- `validate` 실행
- `optical-train` 실행
- summary metric 표시
- warning 표시
- optical train PNG 표시
- workspace PNG 표시
- placement PNG 표시
- report YAML 저장 위치 표시
- raw report 일부 펼쳐보기

현재 완료된 부분:

- CLI 기반 `lidarsim dashboard`는 추가 dependency 없이 self-contained HTML을 생성한다.
- HTML에는 Phase 2 summary, workspace PNG, optical train PNG, component report, power ledger, target footprint, receiver return, warning과 assumption이 표시된다.
- 아직 browser 안에서 button을 눌러 실행하는 Streamlit UI는 아니다.

이 단계는 읽기 중심이다. configuration 편집과 3D placement editing은 최소화한다.

중요한 한계:

- 이 phase는 SolidWorks-like placement editor가 아니다.
- component picking, snapping, constraints, interactive 3D viewport는 아직 없다.
- 사용자가 현재 simulation 결과를 쉽게 확인하는 용도다.

완료 조건:

- 사용자가 CLI 명령을 몰라도 baseline simulation을 실행할 수 있다.
- UI 결과가 `lidarsim optical-train configs/project.yaml` 결과와 일치한다.
- warning과 model limitation을 숨기지 않는다.

### UI Phase A — 3D Optical Bench Viewer

목표는 현재 config의 광학계를 optical bench처럼 3D로 보여주는 것이다. 이 단계는 아직 interactive editor가 아니라 viewer다.

표시할 항목:

- source
- collimator
- mirror
- target
- receiver
- optical axes
- component local frames
- input/output ports
- mirror normal
- target plane
- receiver FOV cone
- beam path
- reflected ray
- target hit marker
- footprint overlay

권장 구현:

- 초기에는 기존 placement 계산과 optical train report를 `ViewportScene`으로 변환한다.
- Matplotlib 3D 또는 Plotly로 시작할 수 있다.
- 정확한 interactive editing보다 “현재 광학계가 어떤 상태인지 보이는 것”을 우선한다.

현재 상태:

- Matplotlib 3D 기반 headless viewer가 `lidarsim workspace`로 구현되었다.
- 현재 config와 Phase 2.3 report에서 optical bench PNG와 YAML scene을 생성한다.
- 향후 Streamlit/Plotly/Three.js viewer는 같은 `ViewportScene`을 재사용한다.

완료 조건:

- 사용자가 source→collimator→mirror→target→receiver 관계를 한 화면에서 이해할 수 있다.
- beam path와 reflected ray가 report 값과 일치한다.
- target hit marker와 footprint overlay가 Phase 2.3 report 값과 일치한다.

### UI Phase B — Numeric Placement Editor

목표는 사용자가 component를 선택하고 숫자로 placement를 수정할 수 있게 하는 것이다.

기능:

- component 선택
- position x/y/z 편집
- orientation 편집
- axial gap 편집
- transverse offset 편집
- angular misalignment 편집
- placement validation 실행
- changed layout을 variant config로 저장
- 수정 전후 placement diff 표시

이 단계는 drag/rotate gizmo 이전의 안전한 편집기다. 3D 조작보다 먼저 numeric editor를 넣으면 config serialization과 validation이 안정된다.

현재 완료된 부분:

- CLI 기반 `lidarsim placement-variant`가 구현되었다.
- Absolute placement element는 `translation_m`, `quaternion_wxyz`를 수정할 수 있다.
- Port placement element는 `axial_gap_m`, `transverse_offset_m`, `clocking_rad`, `angular_misalignment_rad`를 수정할 수 있다.
- 원본 baseline을 덮어쓰지 않고 variant scenario/project YAML을 만든다.
- 생성된 variant project는 `validate`, `workspace`, `dashboard`로 다시 실행할 수 있다.
- 아직 browser 안에서 component를 선택하고 form으로 수정하는 UI는 아니다.

완료 조건:

- 사용자가 collimator gap, mirror 위치, target 거리, receiver 위치를 UI에서 수정할 수 있다.
- 수정 결과가 config로 저장되고 CLI에서 재현된다.
- 잘못된 placement는 schema/physical validation warning 또는 error로 표시된다.

### UI Phase C — Guidelines and Snapping

목표는 사용자가 광학계를 빠르게 정렬할 수 있도록 guideline과 snap helper를 제공하는 것이다.

기능:

- grid guideline
- optical axis guideline
- port axis guideline
- distance ruler
- angle ruler
- snap component to beam axis
- port-to-port snap
- coaxial alignment
- place lens at focal distance
- rotate mirror to hit target center
- align receiver to target hit point

Guideline과 snap은 자동으로 config를 덮어쓰면 안 된다. 사용자에게 preview를 보여주고 적용 여부를 명확히 해야 한다.

완료 조건:

- 사용자가 collimator를 source axis에 맞추고 focal distance에 놓을 수 있다.
- 사용자가 mirror를 target center로 향하게 하는 추천 pose를 preview할 수 있다.
- receiver를 target hit point 방향으로 align할 수 있다.

### UI Phase D — Constraint / Mate System

목표는 SolidWorks assembly mate처럼 반복 가능한 placement relation을 config에 기록하는 것이다.

초기 constraint 후보:

- `PortCoincidentMate`
- `CoaxialMate`
- `DistanceMate`
- `AngleMate`
- `LookAtMate`
- `MirrorTargetMate`
- `ApertureCenterMate`

각 constraint는 다음 정보를 가져야 한다.

- constraint id
- constraint type
- source component/port/frame
- target component/port/frame
- parameter value
- enabled/disabled
- validation status
- residual error

완료 조건:

- constraint 목록을 보고 켜고 끌 수 있다.
- constraint를 적용한 placement가 config에 남는다.
- residual error가 report에 표시된다.

### UI Phase E — Interactive 3D Editor

목표는 사용자가 실제 CAD assembly처럼 component를 선택하고 움직일 수 있게 하는 것이다.

기능:

- component picking
- drag/rotate gizmo
- transform handles
- undo/redo
- guide toggle
- constraint list
- snap preview
- constraint preview
- run simulation from current layout
- save changed layout as variant config

이 단계는 가장 어렵다. Streamlit 기본 widget만으로는 충분하지 않을 수 있으며, custom 3D viewport가 필요할 가능성이 높다.

완료 조건:

- 사용자가 3D viewport에서 mirror를 선택하고 회전할 수 있다.
- beam path가 current layout 기준으로 갱신된다.
- 변경된 layout이 config로 저장되고 CLI로 재현된다.

### UI Phase 0.2 — Basic Parameter Editor

목표는 자주 바꾸는 물리값을 UI에서 수정하고 variant config로 저장한 뒤 simulation을 실행하는 것이다.

초기 노출 parameter:

- wavelength
- source power
- collimator component reference
- mirror clear width / height
- mirror reflectivity
- target distance
- target width / height
- material hemispherical reflectivity
- receiver aperture diameter
- receiver full FOV
- receiver optical efficiency

중요 규칙:

- 원본 baseline file을 직접 덮어쓰지 않는다.
- UI 변경값은 `configs/ui_runs/` 또는 명시적 variant config로 저장한다.
- 결과는 `results/ui_runs/` 또는 timestamp run directory에 저장한다.
- 변경 전후 config diff를 볼 수 있어야 한다.

완료 조건:

- 사용자가 UI에서 target distance나 receiver aperture를 바꿔 received power 변화를 확인할 수 있다.
- 저장된 variant config를 CLI로 다시 실행할 수 있다.

### UI Phase 0.3 — Comparison Dashboard

목표는 여러 조건을 한 번에 실행하고 표로 비교하는 것이다.

예:

```text
target distance = 5 m, 10 m, 20 m
receiver aperture = 10 mm, 25 mm, 50 mm
```

표시할 비교 metric:

- target hit count
- target power
- receiver power
- link loss dB
- clipping loss
- warning count
- baseline 대비 ratio 또는 dB 차이

완료 조건:

- 사용자가 여러 거리·aperture 조합을 비교해 receiver power scaling을 볼 수 있다.
- 모든 run의 config hash와 report path가 남는다.

### UI Phase 1 — Scanner UI

Phase 3 scanner command angle이 구현된 뒤 추가한다. 현재는 첫 조각으로 `scanner.static_command_angle_rad`를 static pose에 적용하는 경로가 구현되었다.

기능:

- mechanical command angle 입력
- mirror normal 표시
- reflected direction 표시
- mechanical angle 대비 optical angle 약 2배 관계 검산
- ±amplitude endpoint 표시
- scan path preview

현재 완료된 부분:

- `scanner.static_command_angle_rad`가 mirror normal과 aperture axes에 적용된다.
- Reflected ray, target hit, footprint와 receiver return이 static command angle에 따라 바뀐다.
- `workspace`와 `dashboard`는 report 기반 mirror normal/reflected ray를 표시하므로 angle 변화가 자동 반영된다.

아직 미구현:

- waveform time sampling
- frequency 기반 scan path
- dynamic lag/jitter
- ±amplitude endpoint batch 계산

완료 조건:

- 사용자가 scanner angle을 바꿨을 때 target hit 위치와 receiver return 변화가 표시된다.

### UI Phase 2 — Scan Line / Scan Frame Dashboard

Phase 3.1 이후 scan samples가 생기면 추가한다.

기능:

- waveform 선택
- samples per line
- scan line plot
- target 위 footprint trajectory
- received power per sample
- simple heatmap 또는 line chart

완료 조건:

- 한 줄 scan에서 received power가 sample index에 따라 표시된다.

## 7. 사용자가 원하는 workflow 기준 MVP

사용자가 원하는 “편하게 쓰는 optical assembly simulation”의 첫 MVP는 단순 dashboard보다 크다.

MVP 범위:

1. project config를 load한다.
2. source, collimator, mirror, target, receiver를 3D에 렌더링한다.
3. optical axes와 mirror normal을 표시한다.
4. 현재 beam path를 표시한다.
5. component를 선택할 수 있다.
6. 선택한 component의 numeric transform을 편집할 수 있다.
7. placement validation을 실행한다.
8. optical train simulation을 실행한다.
9. reflected ray, target hit, footprint, receiver FOV를 overlay한다.
10. 변경된 layout을 variant config로 저장한다.

이 MVP는 다음을 아직 포함하지 않아도 된다.

- drag/rotate gizmo
- full constraint solver
- STL triangle hit detection
- scanner time waveform
- coherent FMCW
- detector noise

즉, 첫 MVP는 “3D로 보고, 숫자로 배치 수정하고, beam 결과를 overlay하고, config로 저장하는 optical bench viewer/editor”다.

## 8. 기술 선택

### Streamlit

Streamlit은 UI Phase 0.1 result dashboard에 적합하다.

장점:

- slider, number input, selectbox, table, image 표시가 쉽다.
- Python simulation engine과 직접 연결하기 좋다.
- 연구·실험용 dashboard를 빠르게 만들 수 있다.
- 사용자가 local browser에서 쉽게 볼 수 있다.

한계:

- SolidWorks-like interactive 3D assembly editor를 만들기에는 기본 widget이 부족하다.
- component picking, transform gizmo, snap preview, constraint editor는 custom component가 필요할 수 있다.

### Streamlit + Matplotlib/Plotly

초기 3D viewer에는 충분히 사용할 수 있다.

적합한 범위:

- Phase A 3D Optical Bench Viewer
- static optical axes
- beam path
- reflected ray
- target hit marker
- receiver FOV guide
- 간단한 orbit/zoom viewer

부족한 범위:

- CAD 수준 component picking
- drag/rotate handle
- constraint preview
- 복잡한 assembly editing

### Custom 3D viewport

SolidWorks-like interactive assembly editing에는 별도의 3D viewport를 계획해야 한다.

후보:

1. Streamlit custom component + Three.js
   - Streamlit workflow를 유지하면서 3D editor만 custom web component로 만든다.
   - Python engine과의 통합이 비교적 쉽다.

2. Separate React + Three.js frontend
   - 장기적으로 가장 유연하다.
   - component picking, gizmo, snapping, constraint list, undo/redo를 제대로 구현하기 좋다.
   - Python backend와 JSON API 또는 file-based config/report contract로 연결한다.

3. PyVista
   - Python 기반 engineering visualization에 적합하다.
   - mesh와 3D geometry inspection에는 강하다.
   - browser-first UI나 CAD-like editor로 발전시키려면 추가 설계가 필요하다.

현재 추천:

```text
UI Phase 0.1: Streamlit
UI Phase A: Streamlit + Plotly 또는 Matplotlib 3D
UI Phase B: Streamlit numeric placement editor
UI Phase C~E: custom 3D viewport 계획 수립
장기 editor: Streamlit custom component + Three.js 또는 React + Three.js
```

물리 engine은 계속 Python/YAML/report 기반으로 유지한다. 3D frontend가 생기더라도 frontend가 물리 계산의 source of truth가 되면 안 된다.

## 9. 권장 source 구조

초기 Streamlit dashboard:

```text
src/lidarsim/ui/
├─ __init__.py
├─ app.py          # Streamlit entrypoint
├─ state.py        # UI 입력값과 config override mapping
├─ runners.py      # validate / optical-train 실행 wrapper
├─ summaries.py    # report에서 핵심 metric 추출
└─ plots.py        # UI 표시용 plot helper
```

Optical assembly workspace layer:

```text
src/lidarsim/ui/assembly/
├─ __init__.py
├─ workspace.py          # workspace state와 config/report 연결
├─ viewport_data.py      # ViewportScene contract 생성
├─ guides.py             # optical axis, grid, ruler, FOV guide 생성
├─ constraints.py        # UI-level placement constraint model
├─ snapping.py           # snap candidate와 preview 계산
└─ placement_editor.py   # numeric placement edit와 validation helper
```

Optional future frontend:

```text
frontend/optic-ray-workspace/
├─ package.json
├─ src/
│  ├─ App.tsx
│  ├─ viewport/
│  │  ├─ OpticalBenchScene.tsx
│  │  ├─ ComponentMesh.tsx
│  │  ├─ TransformGizmo.tsx
│  │  └─ Guides.tsx
│  └─ panels/
│     ├─ ComponentInspector.tsx
│     ├─ ConstraintList.tsx
│     └─ SimulationPanel.tsx
└─ README.md
```

CLI entrypoint는 다음 형태를 목표로 한다.

```powershell
lidarsim ui configs/project.yaml
```

직접 실행도 허용할 수 있다.

```powershell
streamlit run src/lidarsim/ui/app.py
```

## 10. Data contracts

UI와 engine 사이에는 명확한 data contract가 필요하다.

### ViewportScene

3D viewport에 넘기는 전체 scene snapshot.

필드 후보:

- project_id
- scenario_id
- config_hash
- components
- ports
- guides
- rays
- footprints
- receiver_fovs
- warnings

### ViewportComponent

3D 공간의 component 표시 단위.

필드 후보:

- element_id
- component_ref
- component_type
- model_level
- transform_world_from_component
- bounds_m
- display_mesh_ref
- local_frame
- selectable
- editable

### ViewportPort

Optical input/output port 표시 단위.

필드 후보:

- element_id
- port_id
- role
- interface_type
- reference_plane
- origin_world_m
- axis_world
- transverse_x_world
- clear_aperture_m

### GuideLine

Grid, optical axis, ruler, snap preview 등을 표시하기 위한 guide.

필드 후보:

- guide_id
- guide_type
- start_m
- end_m
- color
- label
- enabled
- source

### RaySegment

Beam path와 reflected ray 표시 단위.

필드 후보:

- segment_id
- start_m
- end_m
- direction
- optical_path_id
- source_element_id
- target_element_id
- power_w
- radius_start_m
- radius_end_m
- status

### FootprintOverlay

Target surface 위 footprint 표시 단위.

필드 후보:

- target_id
- hit_center_m
- normal
- major_radius_m
- minor_radius_m
- orientation_axis_world
- area_m2
- power_on_target_w
- clipped_by_target_bounds

### PlacementConstraint

UI와 config에 저장 가능한 placement relation.

필드 후보:

- constraint_id
- constraint_type
- enabled
- source_ref
- target_ref
- parameters
- residual
- status
- warnings

### PlacementEdit

사용자가 수행한 placement 변경 단위.

필드 후보:

- edit_id
- element_id
- edit_type
- before_transform
- after_transform
- source
- timestamp
- validation_status
- serialized_config_patch

## 11. 첫 화면 구성안

왼쪽 sidebar:

```text
Project
- project path
- active scenario

Source
- wavelength
- optical power

Optics
- collimator
- mirror clear width / height
- mirror reflectivity

Target
- distance
- width / height
- material reflectivity

Receiver
- aperture diameter
- full FOV
- optical efficiency

Placement
- selected component
- position x/y/z
- orientation
- axial gap
- transverse offset
- angular misalignment

Actions
- Validate
- Run Simulation
- Save Variant
- Reset Edits
- Open Report Directory
```

오른쪽 main view:

```text
3D Optical Bench
- component geometry / simplified shapes
- local frames
- ports
- optical axes
- mirror normal
- beam path
- reflected ray
- target hit marker
- footprint overlay
- receiver FOV

Status
- overall status
- hardware readiness
- calibration status
- warning list

Beam
- final radius x/y
- final power
- total transmission

Mirror
- incidence angle
- aperture status
- reflectivity loss

Target
- hit / miss
- footprint radius
- footprint area
- power on target

Receiver
- FOV status
- received aperture power
- link loss dB

Files
- report YAML
- variant config YAML
```

## 12. 첫 구현 patch 범위 제안

사용자가 원하는 최종 방향은 optical assembly workspace지만, 첫 patch는 너무 크게 잡지 않는다.

추천 첫 patch:

```text
UI MVP 0 — 3D bench viewer + read-only simulation dashboard
```

이번에 실제로 완료한 첫 patch:

- `src/lidarsim/ui/assembly/viewport_data.py` 추가
- `src/lidarsim/visualization/workspace.py` 추가
- `lidarsim workspace` CLI 추가
- `ViewportScene` YAML 저장 옵션 추가
- source/collimator/mirror/target/receiver 3D 표시
- optical axes 표시
- mirror normal 표시
- beam path와 reflected ray 표시
- target hit marker와 footprint overlay 표시
- receiver FOV guide 표시
- README와 USER_MANUAL에 workspace 실행 방법 추가
- viewport data와 renderer/CLI test 추가

다음 patch로 넘긴 항목:

- `streamlit` optional dependency 추가
- `src/lidarsim/ui/app.py` 추가
- project path 입력 widget
- validate 실행 button
- optical-train 실행 button
- summary metric card 표시
- warning list 표시
- report YAML path 표시

제외:

- drag/rotate gizmo
- full constraint solver
- port-to-port snapping
- component catalog browser
- scanner time dynamics
- scan heatmap
- STL interactive editor
- cloud/server deployment

이렇게 시작하면 단순 dashboard가 아니라 optical assembly workspace의 골격을 처음부터 잡을 수 있다.

## 13. 이후 결정해야 할 사항

- Streamlit dependency를 기본 dependency에 넣을지 optional dependency `ui`로 둘지
- `lidarsim ui` 명령이 Streamlit process를 직접 실행할지, 안내만 출력할지
- 초기 3D viewer를 Matplotlib 3D로 할지 Plotly로 할지
- custom Three.js viewport를 언제 시작할지
- UI에서 variant config 저장 위치를 `configs/ui_runs/`로 할지 `results/ui_runs/configs/`로 할지
- generated UI run 결과를 어느 directory layout으로 관리할지
- 여러 PC에서 UI-generated config를 Git에 올릴지 여부
- placement constraint를 scenario schema에 포함할지 별도 workspace schema로 둘지
- 상용 component catalog browser를 언제 붙일지
- 장기 3D editor를 Streamlit custom component로 유지할지 React frontend로 분리할지

## 14. 추천 다음 작업

1. UI dependency 정책 결정
   - 추천: `streamlit`을 optional dependency `ui`에 추가

2. Viewport data contract 구현
   - `ViewportScene`, `ViewportComponent`, `ViewportPort`, `GuideLine`, `RaySegment`, `FootprintOverlay` dataclass 추가

3. UI MVP 0 구현
   - 3D optical bench viewer와 read-only simulation dashboard를 함께 만든다

4. Numeric placement editor 구현
   - 선택 component의 transform을 숫자로 수정하고 variant config로 저장한다

5. Guidelines and snapping 구현
   - optical axis, port axis, focal distance, mirror target alignment helper를 추가한다

6. Phase 3 scanner command angle 구현
   - scanner UI와 scan path UI의 물리 기반을 마련한다

이 순서가 가장 안전하다. 단순 결과 dashboard만 먼저 만들면 나중에 assembly editor로 확장할 때 구조를 다시 뜯어고칠 수 있다. 처음부터 optical bench workspace를 목표로 data contract와 viewport layer를 분리해 두는 것이 좋다.
