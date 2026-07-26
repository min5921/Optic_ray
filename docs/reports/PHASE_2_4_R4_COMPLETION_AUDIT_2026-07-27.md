# Phase 2.4-R4 완료 감사 및 후속 보완 보고서

- 작성일: 2026-07-27
- 기준 branch: `main`
- R4 기준 commit: `4659f1b` (`Complete passive detector input boundary R4`)
- 판정: **Phase 2.4-R1~R4 구현 Gate 완료, analytical/reference simulation으로 사용 가능**
- Hardware readiness: `analytical_only`, `uncalibrated`

## 1. 결론

현재 프로젝트는 다음 정적 왕복 광로를 configuration과 report로 재현한다.

```text
source
→ collimator
→ scanner mirror
→ rectangle-plane target
→ same scanner mirror
→ same collimator
→ same single-mode fiber
→ passive circulator/coupler
→ detector optical input plane
```

광학 배치, 실제 plane intersection, aperture pass/miss, 반사 방향, target footprint, Lambertian scalar return power, fiber 정렬 proxy, duplexer loss와 detector 입력 광 파워가 서로 다른 단계와 power plane으로 분리되었다. 계산된 `0 W`와 미평가 `null`, radiometric power와 coherent field도 분리되어 있다.

따라서 현재 구현은 부품·파장·배치·정렬·재질·duplexer transmission을 바꾸며 **이상화된 조건 간 상대 비교와 회귀 검증**을 하는 데 사용할 수 있다.

그러나 다음 결과로 해석하면 안 된다.

- 보정된 실제 장비의 절대 수신 파워
- STL 물체 전체 면적에서 돌아오는 광 파워
- 실제 single-mode fiber의 diffuse-field 결합 효율
- detector photocurrent, SNR, saturation 또는 detection probability
- speckle이 포함된 coherent field
- FMCW beat signal, range FFT/CZT 또는 point cloud

가장 중요한 다음 단계는 `STL center-ray hit`를 `STL full-footprint·양방향 visibility·radiometry`로 확장하는 CPU 기준 구현이다.

## 2. 완료된 단계와 증거

| 단계 | 완료 내용 | 기준 commit |
| --- | --- | --- |
| `UI-S` | project-wide draft, atomic variant 실행, provenance, footprint orientation, UI 설정 연결 | `df66c80` |
| `Phase 2.4-R1` | target→same mirror→collimator→fiber reciprocal center-ray와 closure | `724818c` |
| `Phase 4.1-M1` | CPU/float64 STL nearest positive center-ray closest-hit | `9970ac9` |
| `Phase 2.4-R2` | rectangle Lambertian target→fiber reference plane scalar power ledger | `9ef3333` |
| `Phase 2.4-R3` | `gaussian_alignment_proxy` fiber coupling과 coupled power | `50bcada` |
| `Phase 2.4-R4` | passive duplexer와 detector optical input boundary | `4659f1b` |

R4에서 추가된 핵심 계약은 다음과 같다.

- `power_coupled_into_fiber_w × return_power_transmission`
- power에는 `T`, optional complex field amplitude에는 `sqrt(T)` 적용
- radiometric R3 입력에는 coherent field가 없으므로 R4 field도 `null`
- `pass`, `blocked`, `zero_input`, `not_evaluated`, `fail` 분리
- fiber→detector, target→detector, source→detector loss를 별도 field로 보고
- R3 결과가 현재 project source power를 초과하면 `fail/null`로 종료
- summary, reciprocal section과 nested detector boundary 상태를 strict schema v6로 일치시킴
- Viewport에는 가짜 detector component·ray·beam·field를 만들지 않음

## 3. Baseline 수치 감사

`configs/project.yaml`의 active baseline 결과는 다음과 같다.

| 물리 plane 또는 지표 | 결과 |
| --- | ---: |
| Source optical power | `10 mW` |
| Target power | `9.99997341 mW` |
| Virtual-aperture regression | `2.49999335 nW` |
| Return mirror power | `1.8006278446 nW` |
| Fiber reference-plane power | `1.8006278446 nW` |
| R3 fiber coupling efficiency | `1.0` |
| Coupled-fiber power | `1.8006278446 nW` |
| R4 detector optical input power | `1.8006278446 nW` |
| Fiber→detector loss | `0 dB` |
| Target→detector input loss | `67.4457488353 dB` |
| Source→detector input round-trip loss | `67.4457603829 dB` |

동일한 return power가 여러 plane에서 유지되는 것은 baseline이 이상적인 정렬, `eta_fiber=1`과 `return_power_transmission=1`을 사용하기 때문이다. 실제 제품 예측값이라는 뜻이 아니다. 실제 부품 데이터가 준비되면 mirror/coating, collimator, fiber coupling과 circulator/coupler 손실이 각각 달라져야 한다.

기존 `P_virtual_ap`는 별도 virtual-aperture 회귀값이다. R2/R3/R4의 fiber 또는 detector plane power로 사용하지 않는다.

## 4. 검증 결과

최종 R4 patch에서 다음 검증을 통과했다.

```text
python -m pytest -q
→ 360 passed in 43.04s

python -W error::DeprecationWarning -W error::UserWarning -m pytest -q
→ 360 passed in 42.86s
```

다음 실제 명령도 모두 성공했다.

```text
python -m lidarsim.cli validate configs/project.yaml
python -m lidarsim.cli optical-train configs/project.yaml
python -m lidarsim.cli workspace configs/project.yaml --write-scene ...
python -m lidarsim.cli dashboard configs/project.yaml
```

검증 범위에는 다음 사례가 포함된다.

- Duplexer `T=0`, `0.25`, `1.0`
- 0 W source와 0 W coupled power
- tiny source보다 큰 외부 R3 power 재사용 차단
- R3 `null`, upstream `fail`, valid zero propagation
- field power와 amplitude의 `T`/`sqrt(T)` 관계
- radiometric field가 계속 `null`인지 확인
- report YAML round-trip과 strict schema v6
- status/result/ledger 변조 report 거부
- non-reciprocal receiver의 명시적 `not_evaluated`
- CLI, Streamlit, HTML dashboard의 `0.0`/`None` 구분
- Viewport component 5개와 ray 6개 유지 및 R4 metadata-only 표현

## 5. 현재 정확도 판정

### 5.1 신뢰할 수 있는 범위

- SI/radian으로 resolve된 configuration과 재현 가능한 CLI 실행
- 정적 component placement와 center-ray plane intersection
- ideal thin-lens paraxial q-parameter와 chief-ray transform
- static ideal mirror reflection과 aperture pass/miss
- rectangle-plane의 projected Gaussian footprint
- Lambertian small-footprint scalar power ledger의 내부 일관성
- reciprocal center-ray closure와 각 reference plane의 power 구분
- passive component의 에너지 장부와 0/null/fail 상태

### 5.2 현재 경고

Baseline source의 최대 Gaussian divergence half-angle은 약 `0.0986761 rad`이고 small-angle geometric proxy error는 `3.258e-3`이다. 설정 tolerance `1.0e-3`보다 크므로 전체 결과는 `warning`이다. 이 경고를 숨기거나 tolerance를 느슨하게 바꾸기보다 non-paraxial 또는 measured-profile 경로가 필요한지 검토해야 한다.

또한 R3의 `eta_fiber=1`은 Lambertian diffuse return 전체를 하나의 정렬된 Gaussian mode로 취급한 낙관적 proxy다. 실제 diffuse-field single-mode coupling으로 해석하면 안 된다.

### 5.3 Calibration 판정

현재 component와 material 대부분은 ideal 또는 nominal placeholder다. 측정 데이터 fitting과 독립 validation이 없으므로 `calibrated_hardware`로 승격할 근거가 없다.

## 6. P0 보완 — 실제 수신 파워 신뢰도에 필수

### P0-1. Phase 4.1-M2 — STL full-footprint, visibility와 CPU radiometry

현재 STL은 center ray가 어느 triangle에 맞았는지만 계산한다. 다음 구현이 필요하다.

- Gaussian footprint가 덮는 visible mesh patch 선택
- footprint/triangle clipping 또는 surface quadrature
- 송신과 수신 방향의 양방향 occlusion
- 부분 가림, 완전 가림과 grazing incidence
- brute-force NumPy/float64 기준 구현
- 기준 결과가 확립된 뒤 BVH 가속
- STL triangle geometry와 optical scatterer를 계속 분리

완료 Gate:

- 2-triangle plane과 `rectangle_plane`의 footprint·power parity
- triangle subdivision을 바꿔도 결과가 수렴
- partial/full occlusion analytical case
- brute-force와 BVH hit·power 일치
- quadrature residual과 전체 energy ledger 통과

이 Gate 전에는 “STL target 반환 파워 simulation”이라고 표시하지 않는다.

### P0-2. Reciprocal spatial-mode acceptance

현재 R3 proxy를 실제성이 높은 수신 결합 모델로 교체하거나 병렬 비교해야 한다.

- Fiber fundamental mode를 collimator와 scanner를 통해 target 방향으로 역전파
- Target patch에서 reciprocal mode acceptance 또는 aperture-plane overlap 적분
- Radiometric diffuse power와 coherent scatterer field 경로 분리
- Étendue와 passivity 상한 검사
- Aperture, lateral, angular, focus와 MFD mismatch를 한 경로에서 계산

완료 Gate:

- aligned Gaussian analytical overlap 재현
- 모든 mismatch에 대한 단조 감소
- target patch quadrature 수렴
- radiometric 결과의 coherent field는 항상 `null`
- 현재 `gaussian_alignment_proxy`와 새 모델의 차이를 report에서 비교

### P0-3. Detector electro-optic model

R4 다음에는 detector input power를 전기 신호로 바꾸는 별도 단계가 필요하다.

- Wavelength-dependent responsivity
- Detector/TIA bandwidth
- Dark current
- Shot noise와 thermal/electronic noise
- Saturation, clipping과 ADC 범위
- 모든 stochastic model의 seed 재현성

완료 Gate:

- `I = R(λ)P` 선형 case
- zero-input noise floor
- shot-noise variance와 bandwidth scaling
- saturation threshold와 clipping
- seeded repeated-run equality

구현 전에는 photocurrent, SNR, detection probability와 range precision을 보고하지 않는다.

### P0-4. 실제 부품·재질 데이터와 측정 검증

상용 또는 보유 부품을 교체 비교하려면 다음 metadata가 필요하다.

- 제조사, part number, revision과 원본 문서 hash
- 유효 wavelength, angle, temperature와 polarization 범위
- Source power/M²/waist, fiber MFD/NA
- Collimator prescription 또는 measured black-box transfer
- Mirror coating reflectivity의 wavelength/angle dependence
- Circulator/coupler insertion loss
- Detector responsivity와 saturation
- Material BRDF 측정값
- nominal, tolerance, measured와 fitted 값 구분

Bench 검증 plane은 최소한 source output, collimator output, mirror return, fiber input과 detector input으로 나눈다. Calibration dataset과 독립 validation dataset을 분리하고 blind residual과 uncertainty coverage를 보고해야 한다.

## 7. P1 보완 — 동적·coherent LiDAR로 확장

### P1-1. Scanner dynamics와 timing

- command-to-angle calibration table
- bandwidth, lag, acceleration, hysteresis
- bidirectional return stroke
- seeded jitter와 facet error
- chirp/pixel timestamp 동기화

현재 `scanner-path`는 ideal forward reference이므로 실제 scan uniformity나 frame-rate 성능을 뜻하지 않는다.

### P1-2. BRDF/BSDF, roughness와 고정 scatterer map

- Lambertian, specular, retroreflective와 transmissive lobe
- Hemispherical integral이 reflectivity를 넘지 않는 energy-conserving BRDF
- Mesh tessellation과 독립적인 surface scatterer sampling
- Scan 위치가 바뀌어도 같은 scatterer position/phase map 재사용
- Seed와 roughness correlation contract

Speckle은 반드시 다음 coherent field 합으로 계산한다.

```text
E_rx = sum(A_i * exp(1j * phi_i))
P_rx = abs(E_rx) ** 2
```

Scatterer power를 단순 합산하거나 pixel마다 phase를 새로 생성하지 않는다.

### P1-3. Coherent FMCW와 signal processing

- CPU `complex128` receive field
- Round-trip phase `4πR/λ`
- Chirp delay와 Doppler
- LO/balanced 또는 IQ mixer
- Complex baseband와 window
- FFT/CZT, peak detection과 range conversion

완료 Gate에는 10 m single target, two-target separation, constructive/destructive phase, LO scaling, FFT/CZT parity와 zero-field case가 포함되어야 한다.

## 8. P2 보완 — 광학·UI·성능 고도화

### Optical fidelity

- Sequential thick/aspheric lens prescription
- Refractive-index dispersion
- Aperture diffraction와 scalar Fresnel propagation
- Aberration, PSF와 wavefront
- Coating Fresnel, polarization/Jones 또는 Stokes
- Ghost, multi-bounce와 multipath

STL/STEP는 기계 geometry로 유지하고 optical prescription은 별도 data contract로 입력한다.

### Tolerance와 환경

- Seeded Monte Carlo tolerance analysis
- Correlated assembly errors
- Temperature, vibration와 aging drift
- Measurement uncertainty propagation

### Optical Assembly Workspace

현재 UI는 interactive viewer, numeric placement, variant 저장과 첫 `MirrorTargetMate`까지 지원한다. SolidWorks-like 작업성을 위해 다음이 남아 있다.

- Three.js 기반 custom 3D viewport
- Component picking과 drag/rotate gizmo
- Port-to-port, coaxial, distance, angle와 look-at mate
- Persistent constraint list
- Undo/redo
- STL/STEP face selection
- Multi-run comparison과 tolerance visualization

모든 편집은 계속 YAML variant로 직렬화되고 CLI에서 동일하게 재현되어야 한다.

### Performance

- CPU brute-force/BVH parity를 먼저 확립
- Scene batching과 profiling
- 그 뒤에만 선택적 GPU backend 추가
- GPU precision 변경은 CPU float64/complex128 기준과 metric tolerance로 검증

## 9. 권장 다음 구현 순서

```text
1. Phase 4.1-M2: STL full-footprint + 양방향 occlusion CPU reference
2. Reciprocal spatial-mode acceptance: R3 proxy 보완
3. Detector electro-optic/noise boundary
4. 실제 부품·재질 bench data와 uncertainty validation
5. Calibrated scanner dynamics와 timing
6. BRDF/roughness + 고정 scatterer map
7. Coherent FMCW field + LO/mixer
8. FFT/CZT + range output
9. Sequential/physical optics, multipath와 GPU acceleration
```

사용자 체감과 물리 신뢰도를 함께 높이는 가장 좋은 다음 slice는 **STL target의 실제 footprint와 가림을 CPU reference로 계산하고 현재 UI에 overlay하는 것**이다. 사용자가 보유한 FreeCAD/STL 형상을 실제 장면 분석에 연결하면서도 coherent FMCW보다 먼저 geometry·energy correctness를 검증할 수 있기 때문이다.

## 10. 최종 readiness 선언

| 항목 | 현재 상태 |
| --- | --- |
| Configuration 재현성 | 사용 가능 |
| 정적 optical assembly 비교 | 사용 가능, analytical |
| Rectangle target 상대 비교 | 사용 가능, Lambertian approximation |
| Reciprocal detector-input power | 사용 가능, optimistic analytical reference |
| STL center-ray geometry | 사용 가능 |
| STL full optical return | 미구현 |
| Actual fiber diffuse-mode coupling | 미구현 |
| Detector electrical signal/SNR | 미구현 |
| Calibrated scanner dynamics | 미구현 |
| Speckle/coherent FMCW | 미구현 |
| Calibrated hardware prediction | 증거 부족 |

현재 프로젝트는 기능 데모를 넘어 configuration-driven analytical reference simulator 단계에 도달했다. 다음 품질 상승은 기능 수를 늘리는 것보다 STL 면적 visibility, reciprocal mode physics와 bench calibration evidence를 먼저 확보하는 데서 나온다.
