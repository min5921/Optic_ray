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

현재 `virtual_monostatic/virtual_aperture` 모델은 target footprint에서 임의의 원형 aperture가 차지하는 solid angle을 사용해 첫 Lambertian return을 계산한다. 이 모델에는 다음 항목이 없다.

- target에서 scanner mirror로 돌아오는 경로 교차
- return mirror clear aperture와 reflectivity
- scanner pose에 따른 송수신 reciprocity residual
- collimator의 역방향 traversal
- fiber end-face의 mode field
- lateral·angular·focus mismatch에 따른 fiber coupling
- circulator, beamsplitter 또는 2×2 coupler 손실
- detector 또는 coherent mixer

그러므로 현재 report의 `estimated_received_power_w`는 기존 schema를 위한 field 이름이며 물리적으로는 **virtual aperture에서의 분석용 추정값**이다. 이를 `power_coupled_into_fiber_w` 또는 detector power로 해석하면 안 된다. 이 값은 새 왕복 모델을 검증할 때 비교용 intermediate/reference로만 유지한다.

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

## 6. 계획된 configuration contract

다음 예시는 목표 contract이며 현재 schema가 아직 허용하는 설정은 아니다. Phase 2.4 구현 시 schema, catalog와 loader를 함께 추가한다.

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

Component port도 역방향 traversal을 표현해야 한다.

```text
송신: fiber output → collimator input → collimator output → scanner
수신: scanner → collimator output → collimator input → fiber receive mode
```

Port 이름은 광 진행 방향을 고정하는 명령이 아니라 component reference plane과 interface를 식별해야 한다. reciprocal component는 어느 방향으로 통과해도 같은 component catalog/provenance를 참조한다.

## 7. 계획된 결과 contract

새 보고서에서는 서로 다른 plane의 파워를 한 field에 섞지 않는다.

- `power_at_virtual_aperture_w`: 기존 analytical regression intermediate
- `power_at_return_mirror_w`
- `return_mirror_transmission`
- `power_after_return_mirror_w`
- `power_at_return_collimator_w`
- `return_collimator_transmission`
- `power_at_fiber_plane_w`
- `fiber_coupling_efficiency`
- `power_coupled_into_fiber_w`
- `duplexer_return_transmission`
- `power_at_detector_input_w`
- `target_to_fiber_link_loss_db`
- `round_trip_link_loss_db`

각 단계는 input, loss, output, mechanism과 source를 갖는 power ledger entry로 남긴다. `link_loss_db`는 어느 두 plane 사이의 값인지 field 이름과 report metadata에 명시한다.

## 8. 구현 순서

### Phase 2.4-R0 — Contract와 정직한 출력

- 목표 architecture와 output plane 정의
- 현재 virtual aperture 결과를 intermediate로 재명명
- reciprocal port traversal과 return-path configuration schema 설계
- UI에 transmit path와 planned return path를 구분해 표시

상태: architecture, output plane 이름과 virtual-aperture 경고는 문서·report에 반영되었다. Reciprocal path를 machine-readable하게 표현할 receiver schema, 양방향 fiber/collimator port와 return output schema는 아직 남아 있다.

### Phase 2-S — R1 선행 안정화 Gate

- calibration evidence 없이 `calibrated` 또는 overall `pass`를 선언하지 않음
- component origin 재중심화 대신 공통 ray-plane/port intersection 사용
- off-axis·tilt·aperture miss를 명시적인 path 상태로 반환
- 여러 target에서 beam power를 중복 합산하지 않는 nearest-visible hit 정책
- schema와 runtime의 zero transmission·zero-power 계약 일치
- scanner axis의 finite/non-zero 의미와 scanner pivot 회전 검증
- UI project-wide draft, atomic variant run과 stable provenance

이 Gate는 R1에서 같은 geometry primitive를 forward/reverse 양쪽에 사용하기 위한 전제 조건이다. 상세 ID와 완료 기준은 [`IMPLEMENTATION_AUDIT_2026-07-15.md`](IMPLEMENTATION_AUDIT_2026-07-15.md)를 따른다.

### Phase 2.4-R1 — Reciprocal center-ray geometry

- target hit에서 scanner mirror까지 reverse ray 생성
- 동일 static mirror에서 재반사
- collimator receive reference plane까지 역추적
- aperture center, axis angle과 round-trip closure residual 보고
- return path line을 3D viewport에 overlay

### Phase 4.1-M1 — CPU STL target closest-hit MVP

- STL audit parser가 읽은 triangle vertex를 immutable float64 mesh geometry로 보존
- sidecar unit·placement를 적용한 center-ray/triangle intersection
- 최근접 양의 hit point, geometric normal, distance, triangle ID와 front/back face 보고
- 평면 2-triangle STL과 기존 `rectangle_plane`의 hit point·normal·distance 동치 검증
- viewport에 STL mesh와 hit marker overlay
- STL triangle을 optical scatterer 하나로 취급하지 않음

이 단계는 R1 이후, R2 전에 수행한다. BVH, full visibility/occlusion, multi-bounce, mesh footprint clipping과 coherent scatterer map은 포함하지 않는다. R2는 우선 rectangle-plane analytical baseline을 유지하고, STL은 확인된 hit-local geometry와 normal만 제공한다.

### Phase 2.4-R2 — Return optical power ledger

- target radiance에서 mirror가 subtend하는 acceptance 계산
- return mirror aperture와 reflectivity 적용
- collimator clear aperture와 reverse transmission 적용
- 각 plane의 power와 loss를 ledger에 기록
- rectangle-plane analytical case를 첫 기준으로 유지하며 STL closest-hit만으로 mesh 전체 footprint 또는 BRDF 적분이 완료됐다고 표시하지 않음

### Phase 2.4-R3 — Single-mode fiber coupling

- catalog MFD에서 fiber Gaussian receive mode 생성
- aligned Gaussian analytical test
- lateral, angular, mode-size와 focus mismatch 적용
- `fiber_coupling_efficiency`와 `power_coupled_into_fiber_w` 보고
- diffuse target 모델은 reciprocity/mode acceptance 한계를 명시

### Phase 2.4-R4 — Duplexer와 detector boundary

- ideal circulator/coupler placeholder와 configurable transmission
- 실제 catalog 또는 measured insertion loss로 교체 가능한 contract
- detector input plane까지 power ledger 연결
- coherent FMCW 단계가 사용할 complex field boundary 정의

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

이 문서는 목표 물리 구조와 구현 계약을 정리한 것이다. 현재는 R0의 정직한 output 표기 일부만 반영되어 있고, Phase 2-S 안정화, R1 reverse mirror/collimator center ray, Phase 4.1-M1 STL closest-hit, R2 return power ledger, R3 fiber mode overlap, R4 duplexer와 detector는 아직 구현되어 있지 않다. 기존 virtual aperture 계산을 유지하는 이유는 regression과 수치 비교를 위한 것이며 실제 fiber-coupled hardware prediction을 주장하기 위한 것이 아니다.
