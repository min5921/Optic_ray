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
- Nearest-visible rectangle-plane Lambertian target의 R1 geometry-gated scalar return-power ledger
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

현재 `estimated_received_power_w`와 `P_virtual_ap`는 virtual aperture plane의 분석용 중간값이다. 이 값 자체는 동일 scanner·collimator의 reverse traversal을 포함하지 않으며 R2 reciprocal return ledger 및 R3 fiber coupling과 별도로 유지한다. R3는 `gaussian_alignment_proxy`까지 구현했지만 duplexer와 detector loss는 포함하지 않는다.

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

2026-07-26 UI-S checkpoint:

- `UI-S-01` 완료: 불변 project-wide draft가 여러 객체의 변경을 보존하고 변경 객체·field·unified YAML diff와 discard/apply 상태를 표시한다.
- `UI-S-02` 완료: config/provenance snapshot과 staging result directory를 하나의 transaction으로 다루며 render 강제 실패 후에도 기존 variant와 result bundle이 byte-for-byte 유지됨을 검증했다.
- `UI-S-03` 완료: baseline/parent/variant identity를 provenance sidecar에 분리하고 반복 저장에서 project ID와 description이 누적되지 않는다.
- `UI-S-04` 완료: footprint metric eigensystem이 right-handed major/minor local·world axis를 반환하고 report, viewport contract와 두 renderer가 같은 축을 사용한다.
- `UI-S-05` 완료: `result_root`, `ui.language`, `ui.autosave_drafts`와 `display_units.power`를 연결했다. 고정 단위를 사용하는 나머지 editor는 해당 제한을 화면에 warning으로 밝힌다.
- UI-S Gate 완료 후 Phase 2.4-R1 reciprocal center-ray report/viewport 통합을 진행했으며, 완료 상태는 아래 3.4절에 기록한다.

`UI-S`는 `Phase 2-S0/S1`과 병행할 수 있지만, `S1-GEO-01` 완료 전에는 UI numeric placement를 물리적으로 정확한 assembly editor라고 표시하지 않는다.

### 3.4 Phase 2.4-R1 — Reciprocal center-ray geometry

| ID | 문제 | 영향 | 완료 조건 |
| --- | --- | --- | --- |
| `R1-CONFIG-01` | 실제 receiver architecture와 동일 scanner/collimator/fiber return path를 machine-readable하게 지정할 수 없다. | 가상 aperture와 실제 공용 광학계 수신 구조가 config에서 구분되지 않는다. | `reciprocal_single_mode_fiber`, target/scanner/collimator/fiber reference와 bidirectional port를 strict schema·semantic validation으로 연결한다. |
| `R1-GEO-01` | Target hit에서 동일 mirror·collimator·fiber로 되돌아가는 실제 center-ray 교차가 없다. | 배치·scanner angle 변경이 return alignment와 miss에 어떻게 영향을 주는지 검증할 수 없다. | Nearest-visible configured target에서 actual mirror/collimator/fiber reference plane을 순서대로 교차하고 parallel/behind/aperture miss는 no-teleport 종료한다. |
| `R1-LENS-01` | Collimator 이후 return ray를 직선 연장하거나 forward incident의 부호만 뒤집으면 off-axis exact retrace가 깨진다. | Decenter·tilt 조건에서 fiber plane hit와 angular residual이 잘못된다. | 실제 collimator hit offset에 reverse-oriented paraxial ideal thin-lens chief-ray law를 적용하고 off-axis analytical retrace test를 통과한다. |
| `R1-REPORT-01` | Return geometry, power와 fiber coupling 상태가 한 결과처럼 보일 수 있다. | Geometry 통과를 실제 수신 파워 계산 완료로 오해할 수 있다. | Strict `reciprocal_return` section에서 plane별 hit/closure와 `power_status`, `fiber_coupling_status`, `detector_status: not_evaluated`를 분리한다. Virtual aperture는 regression intermediate로 유지한다. |
| `R1-UI-01` | Planned return guide만으로는 실제 hit/miss와 closure residual을 확인할 수 없다. | UI가 simulation 결과가 아닌 설정 가이드를 실제 광로처럼 보일 수 있다. | `ViewportScene`에 `propagation_role: return` actual segment, nullable geometry-only power와 residual guide를 추가하고 termination 뒤 segment를 만들지 않는다. |

2026-07-26 완료:

- Baseline receiver를 `reciprocal_single_mode_fiber`로 전환하고 `return_path.target_ref`, scanner/collimator/fiber element reference, `reuse_transmit_path`와 R3/R4 placeholder를 strict schema로 검증한다. Source와 collimator port는 bidirectional traversal을 명시한다.
- Nearest-visible target가 configured target와 다르면 암묵적으로 대체하지 않고 `not_evaluated`로 보고한다.
- Target→same mirror→collimator receive plane→fiber reference plane을 actual intersection으로 추적한다. Mirror rectangular aperture와 collimator circular aperture miss, parallel/behind ray는 실제 종료점에서 멈춘다.
- Reverse collimator는 actual receive-plane hit offset을 사용하는 paraxial ideal thin-lens law를 적용한다. Baseline exact retrace의 최대 위치 residual은 약 `1.78e-17 m`, 최대 각도 residual은 `0 rad`다.
- Strict Phase 2 report/schema와 `ViewportScene` contract에 reciprocal path, closure check, actual return `RaySegment`와 residual guide를 추가했다. Geometry-only segment의 power는 `null`이며 R1의 power/fiber/detector status는 `not_evaluated`다.
- Phase 2.4-R1 Gate 완료. 다음 활성 단계는 `Phase 4.1-M1` CPU STL target closest-hit MVP다.

### 3.5 Phase 4.1-M1 — CPU STL target closest-hit MVP

2026-07-26 완료했다. MVP 범위와 구현 결과는 다음과 같다.

- binary/ASCII STL triangle vertex를 immutable float64 mesh data로 보존
- sidecar placement와 unit scale을 적용해 world-space triangle 생성
- CPU center-ray/triangle intersection과 nearest positive hit 선택
- hit point, geometric normal, triangle index, distance와 front/back face 보고
- M1 도입 당시 strict Phase 2 report schema v3, 현재 R2 확장 schema v4의 `stl_intersections`와 strict `ViewportScene` v2 계약
- Plotly/Matplotlib viewport에 STL mesh, hit marker와 geometric normal 표시
- material은 mesh/region 단위로 연결
- 평면을 이루는 2-triangle STL과 기존 `rectangle_plane`의 hit point·normal·distance가 tolerance 안에서 일치하는 analytical test
- stable `geometry.asset_ref` 권장, legacy project-root-relative `metadata_file` 호환과 semantic validation
- rectangle/STL 혼합 target 중 center-ray 기준 nearest visible hit 하나 선택

이 단계에서는 BVH, GPU, mesh diffraction, edge scattering, full footprint clipping, occlusion graph와 coherent scatterer sampling을 구현하지 않는다. STL triangle은 geometry와 normal의 기준일 뿐 optical scatterer 하나로 취급하지 않는다.

Gate 결과:

- Binary/ASCII STL triangle을 immutable NumPy float64로 보존하고 degenerate triangle을 hit 후보에서 제외한다.
- CPU Möller–Trumbore reference가 nearest positive hit, barycentric coordinate, winding 기반 geometric normal, distance, triangle ID와 front/back face를 보고하며 parallel/behind/self-hit/no-hit를 구분한다.
- Sidecar `unit_scale_m`과 world placement를 실제 world triangle에 적용한다. Target role, scenario/sidecar material 일치와 `parent_frame: world`를 검증한다.
- 2-triangle plane parity, one-sided backface, mixed rectangle/STL nearest visibility, strict report/viewport schema, CLI report와 Plotly/Matplotlib overlay를 검증했다.
- Phase 4.1-M1 Gate 완료 후 `Phase 2.4-R2` return optical power ledger와 `Phase 2.4-R3` Gaussian alignment coupling까지 순서대로 완료했다. 현재 활성 단계는 R4다.

### 3.6 Phase 2.4-R2 — Return optical power ledger

| ID | 문제 | 영향 | 완료 조건 |
| --- | --- | --- | --- |
| `R2-SOURCE-01` | 기존 virtual aperture 값을 shared scanner/collimator return power로 재사용할 수 있다. | 서로 다른 수신 plane과 aperture geometry를 같은 물리량으로 오해한다. | Virtual aperture regression을 유지하되 R2는 별도 `reciprocal_return.return_power`와 명시적 plane 이름을 사용한다. |
| `R2-GEO-01` | Power 계산이 R1 actual hit/miss와 독립이면 return ray가 aperture를 놓쳐도 파워가 후속 plane으로 이동할 수 있다. | 배치 오차와 target mismatch가 수신 파워에 반영되지 않는다. | Nearest-visible configured rectangle footprint, R1 target-hit 일치와 mirror/collimator/fiber actual intersection을 Gate로 사용한다. |
| `R2-APERTURE-01` | Forward Gaussian clipping fraction을 diffuse return aperture fraction으로 재사용할 위험이 있다. | 송신 Gaussian과 Lambertian 반환광의 공간 분포를 혼동한다. | R1 center-ray aperture pass는 1, miss/no-intersection은 0으로만 매핑하고 forward clipping fraction은 재사용하지 않는다. |
| `R2-LEDGER-01` | Target radiance, mirror reflectivity와 reverse collimator transmission 사이의 plane별 energy 추적이 없다. | 손실의 출처와 target→fiber-plane link loss를 검수할 수 없다. | Small-footprint Lambertian target→projected mirror acceptance 뒤 mirror/collimator loss를 순차 ledger로 기록하고 모든 entry의 `input-loss=output`을 검사한다. |
| `R2-SCOPE-01` | STL closest-hit가 생긴 뒤 mesh radiometry도 구현된 것으로 오해할 수 있다. | Geometry-only triangle hit를 실제 mesh return power로 과장한다. | R2는 `rectangle_plane + lambertian`만 평가하고 STL/지원하지 않는 재질은 명시적인 `not_evaluated`/`unsupported_material`로 남긴다. |

2026-07-27 완료:

- Configured nearest-visible contributing rectangle footprint와 R1 actual target hit가 기본 `1e-9 m` tolerance 안에서 일치할 때만 R2를 평가한다.
- Target radiometric normal의 emission cosine과 mirror projected-area cosine을 서로 다른 항으로 각각 한 번 적용한다.
- R1 mirror/collimator center-ray aperture와 fiber-plane intersection을 no-teleport Gate로 사용한다. Forward transmitter clipping ledger는 R2에 재사용하지 않는다.
- Return mirror incident/after-aperture/after-reflection, return collimator incident/after-aperture/after-transmission과 fiber reference plane을 순서대로 기록한다. Strict Phase 2 report schema는 v4다.
- Plotly/Matplotlib/CLI/Streamlit/dashboard는 `P_virtual_ap`와 `P_return_mirror`/`P_fiber_plane`을 분리한다. 계산된 0 W와 미평가 `null`도 구분한다.
- Baseline은 `P_on_target ≈ 9.99997 mW`, `P_return_mirror ≈ P_fiber_plane ≈ 1.80063 nW`, `target_to_fiber_plane_link_loss ≈ 67.4457 dB`다. Virtual aperture regression은 약 `2.49999 nW`다.
- Phase 2.4-R2 Gate 완료. 후속 R3 완료 상태는 아래 3.7절에 기록한다.

### 3.7 Phase 2.4-R3 — Single-mode fiber coupling proxy

| ID | 문제 | 영향 | 완료 조건 |
| --- | --- | --- | --- |
| `R3-MODE-01` | Fiber reference plane power만 있고 catalog MFD와의 mode overlap이 없다. | Aperture 통과 power를 single-mode fiber coupled power로 오해할 수 있다. | 정규화 Gaussian receive/fiber mode overlap으로 `eta_fiber`와 coupled power를 별도 계산한다. |
| `R3-ALIGN-01` | R1 actual lateral/angular residual과 사용자가 지정한 mismatch가 coupling에 연결되지 않는다. | Placement 변경이 fiber 결합 결과에 반영되지 않는다. | 같은 right-handed receive frame에서 actual residual과 configured offset을 결합하고 lateral/angular/MFD/focus mismatch test를 통과한다. |
| `R3-FIELD-01` | Radiometric Lambertian power에 임의 위상을 붙여 coherent field처럼 전달할 위험이 있다. | 이후 FMCW에서 물리적으로 존재하지 않는 phase coherence를 주장할 수 있다. | Normalized overlap은 shape 진단으로만 보고하고 coherent field/status/사용 가능 여부를 명시적으로 분리한다. |
| `R3-SCOPE-01` | Diffuse target power 전체를 하나의 Gaussian mode로 처리하면 실제 결합을 과대평가할 수 있다. | 결과가 calibrated hardware prediction처럼 보일 수 있다. | Model을 `gaussian_alignment_proxy`로 명시하고 Lambertian upper-bound/reference, uncalibrated 상태와 미구현 spatial-mode decomposition을 경고한다. |
| `R3-UI-01` | Fiber-plane power와 coupled power가 화면에서 같은 plane 값처럼 보일 수 있다. | R2/R3 loss 경계와 0/null 의미가 사라진다. | CLI/Streamlit/dashboard는 R2 plane power, R3 효율·coupled power·loss를 별도 표시하고 Viewport는 새 ray/field 없이 fiber reference metadata만 추가한다. |

2026-07-27 완료:

- Source/fiber catalog의 `gaussian_1e2_intensity` MFD, optional receive MFD/waist offset과 R1 actual residual을 사용하는 NumPy/float64 normalized scalar Gaussian overlap을 구현했다.
- `reciprocal_return.fiber_coupling`과 summary에 `fiber_coupling_efficiency`, `power_coupled_into_fiber_w`, `fiber_plane_to_coupled_mode_loss_db`, `target_to_fiber_coupled_link_loss_db`를 strict Phase 2 report schema v5로 추가했다.
- Radiometric adapter는 `coherent_field_status: not_provided`, `coupled_field_amplitude_sqrt_w: null`, `field_usable_for_coherent_propagation: false`를 보고한다. 임의 기준 위상의 normalized overlap은 coherent output이 아니다.
- CLI/Streamlit/dashboard에서 virtual aperture, R2 fiber-plane power와 R3 coupled power를 분리하고 계산된 `0.0`과 미평가 `null`을 구분한다. Viewport는 기존 R2 return ray power를 유지하고 fiber residual point metadata에만 R3를 표시한다.
- Aligned `eta=1`, lateral/angular/MFD/focus mismatch 단조 감소, zero power, unsupported/missing R1/R2 input, coupling energy ledger, schema/YAML과 UI/CLI를 검증했다.
- Baseline은 `eta_fiber ≈ 1`, `P_coupled ≈ 1.80063 nW`, target→coupled-fiber loss `≈ 67.4457 dB`다. 이 값은 Lambertian diffuse-return optimistic upper-bound/reference이며 calibrated hardware prediction이 아니다.
- Phase 2.4-R3 Gate 완료. 다음 활성 단계는 `Phase 2.4-R4` duplexer와 detector boundary다.

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

2026-07-27 현재 `Phase 2-S0`, `Phase 2-S1`, `UI-S`, `Phase 2.4-R1`, `Phase 4.1-M1`, `Phase 2.4-R2`와 `Phase 2.4-R3`를 순서대로 완료했다. R2는 nearest-visible Lambertian rectangle과 actual R1 geometry Gate를 사용한 target→fiber reference-plane scalar power ledger를, R3는 명시적인 Gaussian alignment proxy를 strict report/UI에 연결했다. 활성 Gate는 `Phase 2.4-R4`다.

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
- Virtual aperture, R2 fiber-plane power, R3 coupled power와 R4 detector power를 서로 다른 output plane으로 표시한다.
- Radiometric mode의 arbitrary-phase overlap 또는 amplitude를 coherent output이라고 표시하지 않는다.
- 각 단계의 analytical test, schema, CLI report와 viewport 표현이 함께 맞아야 완료다.

## 8. 관련 문서

- `docs/PROJECT_VISION.md`
- `docs/specs/RECIPROCAL_FIBER_RETURN.md`
- `docs/specs/ACCURACY_AND_CALIBRATION.md`
- `docs/specs/ENERGY_AND_CONVERGENCE.md`
- `docs/UI_SIMULATION_DASHBOARD.md`
- `docs/USER_MANUAL.md`
- `HANDOFF.md`
