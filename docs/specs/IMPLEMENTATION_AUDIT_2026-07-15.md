# 구현 검수와 활성 개발 순서 — 2026-07-15

- 상태: 현재 구현을 기준으로 승인된 보완 목록과 개발 순서
- 적용 범위: Phase 2 analytical optical train, Phase 3 scanner reference, Streamlit Optical Assembly Workspace
- 기준 문서: `docs/PROJECT_VISION.md`
- 상세 수신 구조: `docs/specs/RECIPROCAL_FIBER_RETURN.md`

## 1. 문서 목적

이 문서는 2026-07-15에 수행한 코드·물리·UI·설정·문서 검수 결과를 이후 세션에서도 동일하게 참조하기 위한 작업 기준이다. 단순한 아이디어 목록이 아니라 각 문제의 영향, 수정 단계와 완료 조건을 정의한다.

현재 baseline은 분석용 회귀 계산으로 사용할 수 있지만, 임의의 3D 배치와 실제 수신 하드웨어를 정확히 예측하는 단계는 아니다. 특히 부품의 transverse offset·tilt, 여러 target, STL target과 reciprocal fiber return을 실제 장비 결과처럼 해석하지 않는다.

## 2. 검수 시점의 확인된 기준

다음 항목은 baseline analytical case에서 일관되게 동작한다.

- Gaussian beam의 M², q-parameter, radius와 irradiance 정규화
- free-space와 ideal thin-lens ABCD transform
- ideal flat-mirror vector reflection
- centered circular aperture와 projected rectangular mirror aperture power 적분
- rectangle-plane center-ray hit와 projected Gaussian footprint 적분
- Lambertian small-footprint virtual-aperture 근사
- YAML configuration, report schema, power ledger와 CLI 재현
- static scanner angle sweep와 ideal scanner command path reference
- Plotly optical bench, numeric variant editor와 `MirrorTargetMate` preview

2026-07-15 검증 결과는 다음과 같다.

```text
python -m pytest -q
→ 139 passed

python -W error::DeprecationWarning -W error::UserWarning -m pytest -q
→ 139 passed
```

현재 `estimated_received_power_w`와 `P_virtual_ap`는 virtual aperture plane의 분석용 중간값이다. 동일 scanner·collimator의 reverse traversal, single-mode fiber mode overlap, duplexer와 detector loss를 포함하지 않는다.

## 3. 등록된 문제와 완료 조건

### 3.1 Phase 2-S0 — 신뢰도·계약 안정화

| ID | 문제 | 영향 | 완료 조건 |
| --- | --- | --- | --- |
| `S0-ACC-01` | `model_purpose`만으로 `calibrated`를 선언할 수 있고 물리 경고가 overall status에 충분히 반영되지 않는다. | 측정 근거가 없어도 실제 장비 보정 결과처럼 보일 수 있다. | calibration dataset, fitted parameter set, independent validation과 validity range가 없으면 `calibrated`를 금지한다. 미구현 핵심 경로와 accuracy warning은 overall을 최소 `warning`으로 만든다. |
| `S0-POWER-01` | Schema는 transmission·reflectivity 0을 허용하지만 runtime `BeamState`와 optical transform은 zero power를 거부한다. | 완전 차단 aperture와 zero-transmission 검증을 표현할 수 없다. | 유효한 zero-power state 또는 명시적인 terminated-path result를 지원하고 schema/runtime/test가 같은 범위를 사용한다. |
| `S0-ENERGY-01` | 여러 target에 동일 beam power를 각각 적용한 뒤 scene total로 합산한다. | target 합계가 송신 파워를 초과해도 energy check가 통과할 수 있다. | visibility/closest-hit 전에는 target별 독립 후보값으로 표시하고 scene energy total로 합산하지 않는다. 단일 center ray에서는 nearest visible hit만 power ledger에 포함한다. |
| `S0-CONFIG-01` | Scenario의 scanner axis, target normal과 receiver direction에 zero-vector·normalization 의미 검증이 부족하다. | YAML validation은 통과하지만 simulation에서 실패하거나 의도와 다른 회전축을 사용할 수 있다. | 모든 방향 벡터를 load 단계에서 finite/non-zero로 검사하고, unit-vector normalization 여부와 원래 입력을 report에 기록한다. |
| `S0-SCHEMA-01` | 일부 component/material/report 중첩 object와 `ViewportScene` 계약이 느슨하거나 schema가 없다. | 오타가 조용히 통과하고 향후 Three.js frontend 계약이 흔들릴 수 있다. | 현재 엔진이 소비하는 필드는 strict schema로 검증하고 `ViewportScene`에 `schema_version`과 JSON Schema를 추가한다. |
| `S0-MODEL-01` | `second_moment`를 선택해도 downstream optical train은 q-ABCD 경로만 사용하거나 astigmatic 상태를 거부한다. | 라인 빔의 end-to-end 부품 교체 비교가 제한된다. | 지원 조합을 validation에서 명확히 제한하고, 지원 시에는 x/y 또는 covariance 전파를 report까지 일관되게 유지한다. |

2026-07-23 중간 checkpoint:

- `S0-ACC-01` 완료: `calibrated_hardware`는 해시로 검증한 fitted parameter file, 역할이 분리된 calibration/validation measurement, wavelength validity, absolute-radiometric mode와 calibrated receiver가 모두 있어야 한다. 공통 readiness 판정을 Phase 0/1/2 report가 사용하며 accuracy warning은 overall을 최소 `warning`으로 만든다.
- `S0-POWER-01` 완료: `BeamState`, ABCD transmission, mirror clipping/reflectivity와 Phase 2 schema가 0 W를 같은 유효 상태로 처리한다.
- `S0-CONFIG-01` 완료: scenario 방향 벡터를 load 단계에서 finite/non-zero 검사하고 non-unit 입력은 warning과 함께 정규화한다. Scanner, target, receiver report에는 원래 입력과 정규화된 vector를 함께 기록한다.
- `S0-MODEL-01` 완료: Phase 2 q-ABCD optical train은 `gaussian_m2`만 명시적으로 지원하며 `second_moment`를 암묵적으로 q 경로에 넣지 않는다.
- `S0-ENERGY-01` 완료: 여러 rectangle-plane 후보 hit를 모두 보존하되 단일 center ray에서 가장 가까운 positive hit 하나만 opaque visible target으로 scene energy와 receiver return에 기여한다. `scene_energy_ledger`가 후보/기여 power와 oversubscription residual을 구분한다.
- `S0-SCHEMA-01` 완료: 현재 실행 경로의 component/material 중첩 optical field와 Phase 2 report를 strict schema로 검증한다. `ViewportScene`은 `schema_version: 1`과 별도 `viewport_scene.schema.json`을 가지며 CLI/UI runner가 저장 전에 검증한다.
- Phase 2-S0 Gate 완료. 후속 Phase 2-S1 Gate도 2026-07-23에 완료했다.

### 3.2 Phase 2-S1 — 실제 배치 geometry 안정화

| ID | 문제 | 영향 | 완료 조건 |
| --- | --- | --- | --- |
| `S1-GEO-01` | 현재 train은 부품까지 축상 거리만 전파하고 transverse error는 경고한 뒤 collimator·mirror origin으로 beam을 재배치한다. | UI에서 입력한 offset·tilt가 실제 miss, clipping과 방향 변화에 반영되지 않는다. | 공통 ray-plane/port intersection으로 실제 hit point를 계산한다. 평면을 벗어나거나 aperture를 놓치면 teleport하지 않고 miss/terminated 상태를 반환한다. |
| `S1-GEO-02` | Scanner catalog pivot이 static rotation geometry에 적용되지 않는다. | 실제 mirror pivot과 surface plane이 떨어진 경우 scan path가 틀린다. | catalog/placement pivot을 world frame으로 변환하고 command angle 회전을 pivot 기준으로 적용한다. |
| `S1-TARGET-01` | Rectangle target은 normal 주위 roll을 명시할 수 없고 backside 양면 가정과 return cosine 처리가 일치하지 않는다. | 직사각형 target 방향과 뒷면 return 해석이 모호하다. | target width axis 또는 quaternion contract를 추가하고 one-sided/two-sided material 정책을 geometry와 radiometry에서 동일하게 적용한다. |
| `S1-NUM-01` | Mirror aperture와 target footprint quadrature에 refined-order convergence 판정이 없다. | 극단적인 clipping과 grazing incidence에서 수치 오차를 신뢰하기 어렵다. | base/refined order 결과와 relative residual을 report하고 tolerance 초과 시 warning/fail을 반환한다. |

2026-07-23 geometry checkpoint:

- `S1-GEO-01` 완료: 공통 float64 ray-plane 교차를 collimator와 scanner mirror에 적용했다. 실제 positive hit까지 전파하며 component origin으로 beam을 재배치하지 않는다. 평면 평행·뒤쪽 교차·clear aperture center-ray miss는 원래 광로에서 명시적인 `terminated` 0 W 상태와 `component_geometric_miss` ledger를 만든다.
- Off-axis collimator는 실제 interaction point와 aperture center의 local decenter를 사용해 projected circular aperture를 적분하고, ideal paraxial thin-lens chief-ray slope 변화를 적용한다.
- `S1-GEO-02` 완료: scanner command rotation은 catalog `mechanical.pivot_local_m`을 world frame으로 변환한 pivot을 기준으로 surface origin, normal과 rectangular aperture axes를 함께 회전한다.
- Baseline, 1 mm collimator decenter, 20 mm aperture miss와 nonzero scanner pivot analytical regression을 통과했다.
- `S1-TARGET-01` 완료: rectangle `geometry.width_axis`가 normal 주위 roll을 결정한다. Normal·width axis는 직교 검증하며 width×height=normal인 right-handed frame을 보고한다. Material `optical.surface_sidedness`의 `one_sided`는 backface를 차단하고 `two_sided`는 입사면 쪽 radiometric normal을 geometry와 Lambertian return에서 동일하게 사용한다.
- `S1-NUM-01` 완료: mirror rectangular aperture와 target footprint Gauss-Legendre 적분은 base/refined order 결과, relative residual, tolerance와 convergence status를 report한다. 최종 power에는 refined 결과를 사용하고 tolerance 초과는 `warning`이다.
- Phase 2-S1 Gate 완료. 다음 활성 단계는 `UI-S`다.

### 3.3 UI-S — 편집·시각화 안정화

| ID | 문제 | 영향 | 완료 조건 |
| --- | --- | --- | --- |
| `UI-S-01` | 현재 선택 객체 하나의 pending edit만 수집한다. | 객체를 바꾸면 적용하지 않은 다른 객체의 편집이 누락될 수 있다. | project 전체 draft patch를 session에서 보존하고, 변경 객체 목록·config diff·discard/apply 상태를 표시한다. |
| `UI-S-02` | Variant를 먼저 덮어쓴 뒤 simulation을 실행한다. | simulation 또는 rendering 실패 시 이전 작업 variant가 이미 바뀔 수 있다. | 임시 파일에서 write→load→validate→simulate→render를 완료한 뒤 원자적으로 replace한다. 실패하면 기존 variant/result를 유지한다. |
| `UI-S-03` | 반복 저장 때 현재 variant가 다시 base가 되어 description과 project ID가 누적된다. | provenance가 길어지고 원래 baseline을 추적하기 어렵다. | 최초 baseline identity와 parent variant를 별도 필드로 유지하고 ID/description은 반복 적용해도 안정적이어야 한다. |
| `UI-S-04` | 3D footprint 장축 방향이 실제 projection eigenvector가 아니라 target width axis에 고정된다. | 경사 입사에서 footprint 크기는 맞아도 화면 방향이 틀릴 수 있다. | 물리 계산이 major/minor world axis를 반환하고 viewport가 같은 축을 사용한다. |
| `UI-S-05` | `result_root`, `display_units`, `ui.language` 등 일부 project UI 설정이 화면에 반영되지 않는다. | config를 바꿔도 UI 동작이 재현되지 않는다. | 지원 설정을 실제 UI에 연결하고, 아직 지원하지 않는 설정은 validation 또는 명시적 warning으로 표시한다. |

`UI-S`는 `Phase 2-S0/S1`과 병행할 수 있지만, `S1-GEO-01` 완료 전에는 UI numeric placement를 물리적으로 정확한 assembly editor라고 표시하지 않는다.

### 3.4 Phase 4.1-M1 — CPU STL target closest-hit MVP

현재 STL은 parser·unit·bounds·topology·normal·hash·sidecar metadata 검사까지만 지원한다. `stl_asset`은 target hit 계산에서 unsupported다.

MVP 범위는 다음으로 제한한다.

- binary/ASCII STL triangle vertex를 immutable float64 mesh data로 보존
- sidecar placement와 unit scale을 적용해 world-space triangle 또는 acceleration input 생성
- CPU center-ray/triangle intersection과 nearest positive hit 선택
- hit point, geometric normal, triangle index, distance와 front/back face 보고
- Plotly viewport에 STL mesh와 hit marker 표시
- material은 mesh/region 단위로 연결
- 평면을 이루는 2-triangle STL과 기존 `rectangle_plane`의 hit point·normal·distance가 tolerance 안에서 일치하는 analytical test

이 단계에서는 BVH, GPU, mesh diffraction, edge scattering, full footprint clipping, occlusion graph와 coherent scatterer sampling을 구현하지 않는다. STL triangle은 geometry와 normal의 기준일 뿐 optical scatterer 하나로 취급하지 않는다.

## 4. 승인된 활성 구현 순서

| 순서 | 단계 | 핵심 산출물 | 다음 단계 Gate |
| ---: | --- | --- | --- |
| 1 | `Phase 2-S0` | calibration gate, zero-power 계약, multi-target energy 정책, vector/schema 검증 | 신뢰도·계약 regression 통과 |
| 2 | `Phase 2-S1` | 공통 ray-plane/port intersection, no-teleport miss, scanner pivot, target orientation | offset·tilt analytical case 통과 |
| 3 | `UI-S` | project-wide draft, atomic variant run, stable provenance, 정확한 footprint orientation | 실패 rollback과 다중 객체 편집 test 통과 |
| 4 | `Phase 2.4-R1` | target→same mirror→collimator receive plane→fiber port reciprocal center ray와 closure residual | exact retrace와 perturbed alignment test 통과 |
| 5 | `Phase 4.1-M1` | CPU STL nearest hit, normal, mesh/hit viewport | 2-triangle plane parity test 통과 |
| 6 | `Phase 2.4-R2` | target radiance→return mirror/collimator power ledger | aperture rejection과 energy ledger 통과 |
| 7 | `Phase 2.4-R3` | single-mode fiber overlap과 coupled power | aligned `eta=1`, mismatch 단조 감소 test 통과 |
| 8 | `Phase 2.4-R4` | circulator/coupler와 detector input plane | zero transmission과 detector boundary test 통과 |
| 9 | 후속 단계 | calibrated scanner dynamics, BRDF/BSDF, detector noise, coherent FMCW, advanced constraint editor | 각 Phase validation gate 적용 |

`UI-S`의 코드 작업은 `Phase 2-S0/S1`과 병렬로 진행할 수 있다. 그러나 Git checkpoint와 완료 선언은 위 Gate 순서를 따른다. R1 결과가 생기면 같은 patch 또는 바로 다음 UI patch에서 return `RaySegment`, aperture residual과 fiber-port alignment overlay를 추가한다.

## 5. 현재 사용자 variant 처리

`configs/ui_runs/baseline_1550nm_ui_variant.yaml`과 대응 project 파일은 사용자 생성 작업물이므로 자동 삭제하거나 baseline으로 승격하지 않는다.

현재 기록된 `scanner.rotation_axis_world: [10, 10, 0]`은 각도가 아니라 방향 벡터다. Runtime에서는 약 `[0.7071, 0.7071, 0]`으로 정규화되므로, 사용자가 Y축 회전을 의도했다면 `[0, 1, 0]`으로 별도 검토해야 한다. `S0-CONFIG-01`이 구현되기 전까지 validation 통과를 사용자 의도 확인으로 간주하지 않는다.

## 6. 단계 공통 검증 규칙

각 단계가 끝날 때 최소한 다음을 실행한다.

```powershell
& .\.venv\Scripts\python.exe -m pytest -q
& .\.venv\Scripts\python.exe -W error::DeprecationWarning -W error::UserWarning -m pytest -q
& .\.venv\Scripts\python.exe -m lidarsim.cli validate .\configs\project.yaml
```

물리 또는 report가 바뀌면 관련 analytical case, schema round-trip과 CLI output을 함께 검증한다. UI가 바뀌면 Streamlit AppTest, variant rollback과 CLI 재현을 함께 검증한다. 검증 결과와 남은 한계는 `HANDOFF.md`에 기록한다.

## 7. 완료 선언 규칙

- 경고만 추가하고 잘못된 물리 동작을 유지한 상태를 완료로 보지 않는다.
- `calibrated`는 측정·fitting·독립 validation evidence가 있을 때만 허용한다.
- 여러 target의 후보 결과와 실제 visible energy contribution을 구분한다.
- UI는 config/report를 우회하는 별도 물리 상태를 소유하지 않는다.
- STL hit가 구현되기 전에는 STL simulation 가능이라고 표시하지 않는다.
- Fiber overlap이 구현되기 전에는 virtual aperture power를 fiber-coupled power라고 표시하지 않는다.
- 각 단계의 analytical test, schema, CLI report와 viewport 표현이 함께 맞아야 완료다.

## 8. 관련 문서

- `docs/PROJECT_VISION.md`
- `docs/specs/RECIPROCAL_FIBER_RETURN.md`
- `docs/specs/ACCURACY_AND_CALIBRATION.md`
- `docs/specs/ENERGY_AND_CONVERGENCE.md`
- `docs/UI_SIMULATION_DASHBOARD.md`
- `docs/USER_MANUAL.md`
- `HANDOFF.md`
