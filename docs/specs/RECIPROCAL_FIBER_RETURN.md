# 공용 콜리메이터·단일모드 파이버 왕복 수신 설계

## 1. 목적

이 문서는 이 프로젝트가 최종적으로 계산해야 하는 실제 수신 광로를 정의한다. 기준 구조는 별도의 가상 수신 aperture가 아니라 송신에 사용한 scanner와 collimator를 수신에도 다시 사용하는 monostatic reciprocal optical train이다.

```text
송신
fiber/source
→ shared collimator
→ shared scanner mirror
→ target

수신
target
→ same scanner mirror
→ same collimator
→ receive mode of the same single-mode fiber
→ circulator/coupler
→ detector 또는 coherent mixer
```

따라서 최종 관심량은 단순히 임의의 원형 aperture에 도달한 파워가 아니라 다음 값이다.

- target에서 광학계 방향으로 반환된 파워 또는 field
- return scanner mirror aperture와 반사율을 통과한 파워
- return collimator aperture와 transmission을 통과한 파워
- single-mode fiber mode에 결합되는 효율
- circulator/coupler를 통과한 detector 입력 파워
- coherent mode에서는 fiber에 결합된 complex field와 그 합

## 2. 현재 구현과의 구분

기존 `virtual_monostatic/virtual_aperture` 모델은 target footprint에서 임의의 원형 aperture가 차지하는 solid angle을 사용해 첫 Lambertian return을 계산한다. 이 계산은 현재도 별도의 analytical regression intermediate로 유지한다. Phase 2.4-R1은 이 값과 섞지 않고 다음 geometry를 별도 `reciprocal_return` section에 구현했다.

- configured nearest-visible target hit에서 동일 scanner mirror로 향하는 center ray
- 실제 mirror plane 교차, rectangular clear-aperture center-ray 판정과 ideal 재반사
- collimator receive reference plane의 실제 교차와 circular clear-aperture center-ray 판정
- 실제 collimator hit offset을 사용하는 reverse-oriented paraxial ideal thin-lens chief ray
- source fiber reference plane의 실제 교차
- transmit reference 대비 mirror/collimator/fiber 위치·각도 closure residual
- plane parallel/behind 또는 aperture miss에서 no-teleport 종료
- `ViewportScene`의 target→mirror→collimator→fiber return segment와 residual guide

R1에는 다음 항목이 없었다.

- target radiance를 return mirror acceptance로 적분한 파워
- return mirror reflectivity와 collimator transmission을 연결한 power ledger
- fiber end-face의 mode field
- lateral·angular·focus mismatch에 따른 fiber coupling
- circulator, beamsplitter 또는 2×2 coupler 손실
- detector 또는 coherent mixer

Phase 2.4-R2는 이 가운데 rectangle-plane Lambertian target의 scalar return-power ledger를 구현했다. 계산 조건과 모델은 다음과 같다.

- configured target가 center ray 기준 nearest-visible contributing `rectangle_plane`이어야 한다.
- Material은 `optical.model: lambertian`과 `hemispherical_reflectivity`를 가져야 한다.
- Footprint center와 R1 actual target hit가 기본 `1e-9 m` tolerance 안에서 일치해야 한다.
- R1 mirror/collimator/fiber plane의 실제 intersection을 사용하며, aperture center-ray `pass`는 1, miss/no-intersection은 0으로 매핑한다.
- Forward 송신 Gaussian clipping fraction은 diffuse return의 공간 분포와 같지 않으므로 return aperture transmission으로 재사용하지 않는다.
- Target→mirror acceptance는 small-footprint/small-aperture 근사로 계산한다.

```text
P_return_mirror
≈ P_on_target · reflectivity/π
  · cos(theta_target_to_mirror)
  · [A_mirror · |cos(theta_mirror_incidence)|] / R²
```

그 뒤 return mirror reflectivity와 reverse collimator transmission을 물리적 통과 순서로 적용하고 각 단계의 `input - loss = output`을 독립 ledger로 검사한다. 이 모델은 fiber reference plane에 도달하는 scalar power의 analytical upper-bound/reference이지 Lambertian 광을 하나의 Gaussian receive field로 바꾼 결과가 아니다.

Report의 `estimated_received_power_w`와 `power_at_virtual_aperture_w`는 계속 물리적으로 같은 **virtual aperture 분석용 추정값**이며 R2~R4와 별도다. 이를 `power_coupled_into_fiber_w` 또는 detector power로 해석하면 안 된다. 현재 `reciprocal_return.power_status`, `fiber_coupling_status`, `detector_status`는 각각 R2, R3, R4의 독립 평가 상태를 가진다. R4가 평가되지 않은 architecture나 upstream miss에서는 `detector_boundary: null`과 `detector_status: not_evaluated`를 유지한다.

## 3. 기본 architecture 결정

실제 부품 사양이 정해지기 전의 추천 기본값은 다음과 같다.

- architecture: `reciprocal_single_mode_fiber`
- 송신과 수신은 동일한 scanner mirror와 collimator를 사용한다.
- 수신 mode는 source catalog의 single-mode fiber MFD와 wavelength를 재사용한다.
- 송신광과 수신광의 분리는 configurable ideal circulator를 우선 placeholder로 사용한다.
- circulator의 실제 insertion loss, isolation, polarization dependency는 부품이 정해진 뒤 catalog 또는 measurement로 교체한다.
- 기존 `virtual_monostatic` receiver는 analytical regression용으로만 남긴다.

동일 파이버가 아닌 별도 수신 파이버, fiber array 또는 free-space detector를 사용하게 되면 architecture와 return path를 별도 variant로 만든다. 이 선택은 simulation logic에 hard-code하지 않는다.

## 4. 왕복 기하와 reciprocity

송신 center ray의 mirror 입사 방향을 `d_in`, mirror normal을 `n`이라고 하면 송신 반사 방향은 다음과 같다.

```text
d_out = d_in - 2 (d_in · n) n
```

표적에서 정확히 되돌아오는 center ray가 `-d_out`이면 같은 mirror에서 다시 반사된 방향은 ideal reciprocal case에서 `-d_in`이 된다. 즉, static mirror와 동일한 매질에서는 송신 광로를 역으로 추적한다.

하지만 diffuse target은 한 개의 정확한 역방향 Gaussian beam을 만들지 않는다. target patch 또는 고정 scatterer마다 scanner mirror로 향하는 방향, visibility, aperture acceptance와 field contribution을 평가해야 한다. 따라서 “중심 ray가 되돌아온다”는 검사는 geometry validation이며 전체 반환 파워 모델을 대신하지 않는다.

왕복 geometry report에는 최소한 다음 residual이 필요하다.

- target hit에서 return mirror까지 visibility/intersection 상태
- return ray와 mirror clear aperture 중심의 거리
- mirror 재반사 방향과 collimator receive port axis의 각도
- collimator reference plane에서의 lateral offset
- collimator를 지난 beam/mode와 fiber port의 lateral·angular·focus mismatch
- transmit path와 reverse path의 round-trip closure residual

## 5. 파이버 mode coupling

단일모드 파이버 결합은 aperture에 들어온 파워나 NA 조건만으로 결정하지 않는다. coherent field가 정의된 경우 receive plane에서의 정규화된 mode overlap을 사용한다.

```text
eta_fiber = |∫ E_return(x, y) E_fiber*(x, y) dA|²
            / (∫ |E_return|² dA · ∫ |E_fiber|² dA)
```

```text
P_coupled_into_fiber = P_at_fiber_plane · eta_fiber
```

초기 analytical 구현은 aligned Gaussian-to-Gaussian case에서 시작하고 다음 mismatch를 독립적으로 추가한다.

- mode-field radius mismatch
- lateral offset x/y
- angular offset x/y
- waist/focus 위치 mismatch
- aperture clipping과 optical transmission

Lambertian 또는 rough target의 반환광은 완전한 하나의 Gaussian mode가 아니다. radiometric mode에서는 receive mode를 target 쪽으로 역전파한 spatial acceptance와 target radiance를 적분하는 reciprocity 기반 모델을 사용해야 한다. 작은 footprint 근사는 가능하지만 deterministic Gaussian overlap이라고 과장하지 않는다.

Coherent FMCW 단계에서는 고정된 surface scatterer `i`마다 round-trip phase와 복소 결합 계수 `c_i`를 적용한다.

```text
E_fiber = Σ c_i A_i exp(j phi_i)
P_fiber = |E_fiber|²
```

Field amplitude와 power는 분리하고 scatterer power를 직접 합해 coherent result로 사용하지 않는다.

## 6. Configuration contract

다음 contract는 Phase 2.4-R1에서 scenario schema, semantic validation과 baseline에 구현되었다. `return_path`의 target와 element ID는 실제 active scene/assembly에 존재하고 각각 올바른 역할이어야 하며, 현재 R1은 `reuse_transmit_path: true`만 지원한다.

```yaml
receiver:
  architecture: reciprocal_single_mode_fiber
  model_level: reciprocal_path_reference
  return_path:
    target_ref: target_plane
    scanner_element_id: scan_mirror
    collimator_element_id: collimator
    fiber_element_id: source
    reuse_transmit_path: true
  fiber_coupling:
    model: single_mode_overlap
    mode_field_source: component_catalog
    lateral_offset_m: [0.0, 0.0]
    angular_offset_rad: [0.0, 0.0]
  duplexer:
    type: ideal_circulator
    return_power_transmission: 1.0
  detector_model: none
```

`fiber_coupling`은 R3에서 catalog MFD, R1 actual residual과 configured mismatch를 연결하는 입력이다. R4는 `duplexer.type`과 `return_power_transmission`을 R3 coupled power에 적용하고 detector optical input boundary에서 종료한다. R1/R2는 이 값으로 결합 파워나 detector power를 만들지 않고, R3도 duplexer loss를 적용하지 않는다. `detector_model`은 현재 boundary metadata이며 detector response를 실행하지 않는다. 기존 virtual-aperture 회귀값을 유지하기 위한 `position_m`, `direction`, `aperture_diameter_m`, `full_fov_rad`, `optical_efficiency`도 baseline receiver에 함께 남아 있지만 reciprocal fiber 또는 detector aperture를 뜻하지 않는다.

Component port도 역방향 traversal을 표현해야 한다.

```text
송신: fiber output → collimator input → collimator output → scanner
수신: scanner → collimator output → collimator input → fiber receive mode
```

Port 이름은 광 진행 방향을 고정하는 명령이 아니라 component reference plane과 interface를 식별해야 한다. Reciprocal component는 어느 방향으로 통과해도 같은 component catalog/provenance를 참조한다. R1 baseline의 source output과 collimator input/output port는 `bidirectional`로 정의되어 있다.

## 7. 결과 contract

Strict Phase 2 report schema v6의 `reciprocal_return` section은 R1 geometry, R2 power, R3 coupling과 R4 detector boundary를 분리한다.

- `architecture`, `return_path`, `target_id`
- mirror/collimator/fiber reference plane의 frame, intersection과 local coordinate
- center/expected-point/lateral/aperture residual
- reflected direction과 fiber-bound direction
- termination 상태·사유·실제 종료점
- transmit reference 대비 plane별 위치·각도와 최대 closure residual
- `power_status`, `fiber_coupling_status`, `detector_status`

R2에서 구현된 plane 이름은 다음과 같다.

- `power_at_virtual_aperture_w`: 기존 analytical regression intermediate
- `power_at_return_mirror_w`
- `power_after_return_mirror_aperture_w`
- `power_after_return_mirror_w`
- `power_at_return_collimator_w`
- `power_after_return_collimator_aperture_w`
- `power_after_return_collimator_w`
- `power_at_fiber_plane_w`
- `target_to_fiber_plane_link_loss_db`

R3/R4에서 구현된 이름은 다음과 같다.

- `fiber_coupling_efficiency`
- `power_coupled_into_fiber_w`
- `fiber_plane_to_coupled_mode_loss_db`
- `target_to_fiber_coupled_link_loss_db`
- `return_power_transmission`
- `power_at_detector_input_w`
- `fiber_coupled_to_detector_input_link_loss_db`
- `target_to_detector_input_link_loss_db`
- `source_to_detector_input_round_trip_link_loss_db`

Radiometric R3에서는 mode-shape 진단용 `normalized_field_overlap`만 보존하고 `coherent_field_status: not_provided`, `coupled_field_amplitude_sqrt_w: null`, `field_usable_for_coherent_propagation: false`를 명시한다. R4도 `field_at_fiber_output_sqrt_w: null`, `field_at_detector_input_sqrt_w: null`, `detector_response_status: not_evaluated`를 보고한다. 임의 기준 위상을 붙인 amplitude를 coherent output으로 만들지 않는다.

각 단계는 input, loss, output, mechanism과 source를 갖는 power ledger entry로 남긴다. `link_loss_db`는 어느 두 plane 사이의 값인지 field 이름과 report metadata에 명시한다.

## 8. 구현 순서

### Phase 2.4-R0 — Contract와 정직한 출력

- 목표 architecture와 output plane 정의
- 현재 virtual aperture 결과를 intermediate로 재명명
- reciprocal port traversal과 return-path configuration schema 설계
- UI에 transmit path와 planned return path를 구분해 표시

상태: 완료. Architecture, output plane 이름, virtual-aperture 경고, machine-readable receiver schema, 양방향 fiber/collimator port와 strict reciprocal geometry output schema가 R1에 연결되었다. Planned return guide도 실제 report 기반 return segment로 대체되었다. 파워 plane 확장은 R2~R4에서 진행한다.

### Phase 2-S — R1 선행 안정화 Gate

- calibration evidence 없이 `calibrated` 또는 overall `pass`를 선언하지 않음
- component origin 재중심화 대신 공통 ray-plane/port intersection 사용
- off-axis·tilt·aperture miss를 명시적인 path 상태로 반환
- 여러 target에서 beam power를 중복 합산하지 않는 nearest-visible hit 정책
- schema와 runtime의 zero transmission·zero-power 계약 일치
- scanner axis의 finite/non-zero 의미와 scanner pivot 회전 검증
- target width-axis, material one/two-sided 정책과 quadrature convergence 검증

상태: 2026-07-23 완료. 이 Gate는 R1에서 같은 geometry primitive를 forward/reverse 양쪽에 사용하기 위한 전제 조건이다. UI project-wide draft, atomic variant run과 stable provenance는 다음 `UI-S` Gate에서 닫는다. 상세 ID와 완료 기준은 [`IMPLEMENTATION_AUDIT_2026-07-15.md`](IMPLEMENTATION_AUDIT_2026-07-15.md)를 따른다.

### Phase 2.4-R1 — Reciprocal center-ray geometry

- target hit에서 scanner mirror까지 reverse ray 생성
- 동일 static mirror에서 재반사
- collimator receive reference plane까지 역추적
- aperture center, axis angle과 round-trip closure residual 보고
- return path line을 3D viewport에 overlay

상태: 2026-07-26 완료. Baseline은 configured nearest-visible `target_plane`에서 forward mirror hit를 향해 return ray를 만들고 동일 static mirror에서 재반사한다. Collimator output receive plane의 실제 hit offset에 reverse-oriented paraxial ideal thin-lens law를 적용한 뒤 source fiber reference plane까지 추적한다. Mirror·collimator aperture와 plane intersection miss는 후속 plane으로 재중심화하지 않고 종료한다. Report는 strict `reciprocal_return` section, plane별 residual과 geometry-only `not_evaluated` power 상태를 제공한다. `ViewportScene`은 actual return segment와 closure residual guide를 송신 path와 구분한다. Exact retrace, off-axis reverse lens, target perturbation, 잘못된 path reference, nearest-visible target 불일치, schema/YAML round-trip을 검증했다. Baseline 최대 위치 residual은 약 `1.78e-17 m`, 최대 각도 residual은 `0 rad`다.

### Phase 4.1-M1 — CPU STL target closest-hit MVP

- STL audit parser가 읽은 triangle vertex를 immutable float64 mesh geometry로 보존
- sidecar unit·placement를 적용한 center-ray/triangle intersection
- 최근접 양의 hit point, geometric normal, distance, triangle ID와 front/back face 보고
- 평면 2-triangle STL과 기존 `rectangle_plane`의 hit point·normal·distance 동치 검증
- viewport에 STL mesh와 hit marker overlay
- STL triangle을 optical scatterer 하나로 취급하지 않음

상태: 2026-07-26 완료. Binary/ASCII STL triangle을 immutable NumPy float64로 보존하고 sidecar unit/world placement를 적용한 CPU Möller–Trumbore center-ray nearest positive hit를 구현했다. Stable `geometry.asset_ref`를 권장하며 legacy `metadata_file`은 project-root-relative registry reference로만 허용한다. 현재 strict Phase 2 report schema v4의 `stl_intersections`와 strict `ViewportScene` v2는 hit point, geometric normal, distance, triangle ID/front-back face, mesh/hit overlay와 geometry-only `footprint_status/radiometry_status: not_evaluated`를 구분한다. 평면 2-triangle parity, one-sided backface와 mixed rectangle/STL nearest visibility를 검증했다. BVH, full footprint-area visibility/occlusion, multi-bounce, mesh footprint/radiometry와 coherent scatterer map은 포함하지 않는다. 완료된 R2도 rectangle-plane analytical baseline만 사용하며 STL은 확인된 hit-local geometry와 normal만 제공한다.

### Phase 2.4-R2 — Return optical power ledger

- target radiance에서 mirror가 subtend하는 acceptance 계산
- return mirror aperture와 reflectivity 적용
- collimator clear aperture와 reverse transmission 적용
- 각 plane의 power와 loss를 ledger에 기록
- rectangle-plane analytical case를 첫 기준으로 유지하며 STL closest-hit만으로 mesh 전체 footprint 또는 BRDF 적분이 완료됐다고 표시하지 않음

상태: 2026-07-27 완료. Configured nearest-visible rectangle-plane Lambertian footprint와 R1 actual target hit의 동일성을 먼저 검증하고, 실제 R1 mirror/collimator/fiber plane path가 없는 경우 `not_evaluated`로 남긴다. Target radiance에서 projected mirror clear area가 subtend하는 acceptance를 small-footprint 근사로 계산한 뒤 mirror aperture Gate·reflectivity, collimator aperture Gate·reverse transmission과 fiber-plane intersection Gate를 순차 ledger로 기록한다. R1 center-ray aperture 상태만 binary acceptance로 사용하고 forward Gaussian clipping fraction은 재사용하지 않는다. R2 도입 당시 strict report schema v4, energy residual, aperture rejection, unsupported material/STL, target-hit mismatch, CLI와 Plotly/Matplotlib plane-power 표시를 검증했다. Baseline은 `P_on_target ≈ 9.99997 mW`, `P_return_mirror ≈ P_fiber_plane ≈ 1.80063 nW`, `target_to_fiber_plane_link_loss ≈ 67.4457 dB`다. 별도 virtual aperture regression은 약 `2.49999 nW`다. 후속 R3/R4도 완료했으며 현재 report schema는 v6다.

### Phase 2.4-R3 — Single-mode fiber coupling

- catalog MFD에서 fiber Gaussian receive mode 생성
- aligned Gaussian analytical test
- lateral, angular, mode-size와 focus mismatch 적용
- `fiber_coupling_efficiency`와 `power_coupled_into_fiber_w` 보고
- diffuse target 모델은 reciprocity/mode acceptance 한계를 명시

상태: 2026-07-27 완료. R2 `power_at_fiber_plane_w`를 독립 input plane power로 사용하고, source/fiber catalog의 `gaussian_1e2_intensity` MFD와 R1 fiber-plane actual lateral/angular residual, configured offset 및 optional receive waist offset으로 정규화 scalar Gaussian overlap을 계산한다. Report model은 `gaussian_alignment_proxy`이며 overlap 효율, coupled power, fiber-plane→mode와 target→coupled-mode loss, coupling energy ledger를 strict schema v5에 기록했다. Aligned mode `eta=1`, lateral/angular/MFD/focus mismatch 감소, zero power, unsupported/missing geometry와 schema/YAML round-trip을 검증했다. Baseline은 `eta_fiber ≈ 1`, `P_coupled ≈ 1.80063 nW`, target→coupled-fiber loss `≈ 67.4457 dB`다. 이는 Lambertian diffuse return 전체를 deterministic Gaussian receive mode로 둔 optimistic analytical upper-bound/reference이며 calibrated hardware prediction이 아니다. Radiometric adapter는 coherent field를 생성하거나 R4로 전달하지 않는다. 후속 R4 완료 후 현재 report schema는 v6다.

### Phase 2.4-R4 — Duplexer와 detector boundary

- ideal circulator/coupler placeholder와 configurable transmission
- 실제 catalog 또는 measured insertion loss로 교체 가능한 contract
- detector input plane까지 power ledger 연결
- radiometric 경로에서는 coherent field를 만들지 않는 명시적 null boundary

상태: 2026-07-27 완료. R3 `power_coupled_into_fiber_w`에 configured `return_power_transmission`을 적용하고 `input-loss=output` detector-boundary ledger를 strict Phase 2 report schema v6에 기록한다. `pass`, `blocked`, `zero_input`, `not_evaluated`, `fail`을 분리하며 계산된 0 W와 미평가 `null`을 보존한다. Summary는 detector input power와 fiber→detector, target→detector, source→detector round-trip loss를 서로 다른 reference plane으로 보고한다. CLI, Streamlit, dashboard는 virtual aperture/R2/R3/R4 값을 분리하고, Viewport는 fiber 뒤 비공간 boundary를 새 component/ray/beam/field로 만들지 않고 fiber reference metadata에만 표시한다. Baseline ideal circulator에서는 `P_detector_input ≈ 1.80063 nW`, fiber→detector loss `0 dB`, source→detector round-trip loss `≈ 67.4457 dB`다. 이 결과는 analytical/uncalibrated optical boundary이며 detector responsivity, photocurrent, noise, saturation, coherent mixing과 FMCW는 계산하지 않는다. 다음 Gate는 Phase 2.4 전체 최종 감사와 보완 보고서다.

## 9. 필수 검증

- calibration evidence가 없으면 `calibrated` confidence/hardware readiness 거부
- off-axis lens·mirror에서 component origin으로 순간이동하지 않고 hit, clipping 또는 miss 보고
- 여러 target에서 nearest-visible power와 전체 energy ledger가 송신 power를 중복 사용하지 않음
- zero transmission 또는 완전 aperture rejection에서 유효한 zero-power/terminated path 생성
- scanner axis zero vector 거부와 pivot 기준 회전 분석값 일치
- exact retrace: `-d_out`이 같은 mirror에서 `-d_in`으로 반사되는지 검사
- mirror perturbation: 작은 mirror angle 변화가 round-trip angular residual을 예상대로 바꾸는지 검사
- STL plane parity: 2-triangle plane과 `rectangle_plane`의 nearest hit point·normal·distance 일치
- STL hit selection: behind/parallel miss와 여러 triangle 중 최근접 양의 hit 선택
- aperture rejection: return ray/beam이 mirror 또는 collimator aperture를 벗어나면 결합 파워가 감소하는지 검사
- R2 geometry Gate: footprint center와 R1 target hit가 tolerance 밖이면 power를 계산하지 않는지 검사
- R2 aperture source: forward Gaussian clipping fraction을 diffuse return aperture acceptance로 재사용하지 않는지 검사
- aligned mode: 동일한 정규화 Gaussian mode의 `eta_fiber = 1` 검사
- lateral/angular mismatch: mismatch가 증가하면 coupling이 단조 감소하는지 검사
- MFD mismatch: analytical Gaussian overlap 식과 일치하는지 검사
- zero transmission: mirror, collimator 또는 duplexer transmission이 0이면 detector input power가 0인지 검사
- energy ledger: 모든 단계에서 `input - loss = output` 검사
- coherent field: complex field 합과 power 합을 혼동하지 않는지 검사

## 10. 아직 결정할 실제 장비 정보

- 동일한 single-mode fiber를 송수신에 모두 사용할지, 별도 receive fiber를 사용할지
- circulator, fiber coupler, PBS/QWP 또는 다른 duplexer 구조
- fiber 종류, MFD/NA, connector와 polarization 특성
- collimator part number, focal length, clear aperture, working distance와 insertion loss
- scanner mirror coating, clear aperture, pivot와 실제 angle calibration
- detector 또는 coherent mixer 구성과 LO path
- 실제 정렬 tolerance와 측정 가능한 coupling/reference power plane

사양이 정해지기 전에는 추천 초기값으로 simulation contract를 구현하되 모든 값은 config/catalog로 교체할 수 있어야 한다.

## 11. 현재 한계

이 문서는 목표 물리 구조와 구현 계약을 정리한 것이다. R0, Phase 2-S, UI-S, R1 reciprocal center-ray geometry, Phase 4.1-M1 STL closest-hit와 R2~R4의 rectangle scalar return-power, Gaussian alignment coupling, passive duplexer/detector optical boundary를 구현했다. 다음 Gate는 Phase 2.4 전체 최종 감사와 보완 보고서다. R2~R4는 nearest-visible Lambertian rectangle의 small-footprint analytical reference와 optimistic Gaussian upper-bound이고 STL radiometry, diffuse spatial-mode decomposition, detector response 또는 coherent field를 계산하지 않는다. 기존 virtual aperture 계산은 regression과 수치 비교를 위해 별도로 유지하며 실제 calibrated fiber-coupled hardware prediction을 주장하지 않는다.
