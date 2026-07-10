# 사용자 정의 빔·광학계·스캐너·광수신 시뮬레이터 설계안

- 상태: Draft v0.2
- 작성일: 2026-06-28
- 기준 단위: SI 단위계, 내부 각도 radian
- 활성 문서: 이 문서가 현재 프로젝트 범위와 개발 순서를 정의한다.
- 원본 자료: `docs/original/coherent-fmcw-lidar-sim-docs/`

## 1. 프로젝트 목적

이 프로젝트의 목적은 사용자가 정의하거나 상용 catalog에서 선택한 광원, collimator, lens, aperture, mirror와 scanner를 실제 공간에 배치하고, 그 광학계를 통과한 빔이 시간에 따라 어디로 진행하는지 계산하는 것이다. 이후 빔이 물체에 만드는 footprint와 irradiance를 구하고, 물체의 형상과 재질에 따라 얼마만큼의 광 파워 또는 coherent field가 수신기로 돌아오는지 예측한다.

최종적으로 다음 질문에 답할 수 있어야 한다.

1. 광원과 collimator를 통과한 빔의 크기, 모양, waist와 발산각은 어떻게 되는가?
2. 상용 또는 사용자 정의 광학 부품을 어떤 위치와 방향으로 배치했는가?
3. 실제 배치 공차와 aperture가 빔 clipping, 정렬과 광 손실에 어떤 영향을 주는가?
4. 사용자가 설계한 scanner가 시간에 따라 빔을 어디로 보내는가?
5. 표적 표면에서 footprint의 위치, 크기, 방향과 세기 분포는 어떻게 되는가?
6. 거리, 입사각, 재질, 거칠기와 receiver 조건에 따라 얼마만큼의 광 파워가 돌아오는가?
7. detector에서 측정 가능한 photocurrent, noise와 SNR은 어느 정도인가?
8. coherent FMCW 모드에서 수신 신호, 거리, 세기와 speckle은 어떻게 나타나는가?

## 2. 전체 데이터 흐름

```text
BeamSource / measured source data
    ↓
ComponentCatalog + OpticalAssembly placement
    ↓
Collimator / Transmitter OpticalTrain
    ↓
BeamState or ray/field representation
    ↓
UserDefinedScanner(t)
    ↓
time-dependent output BeamState
    ↓
Scene intersection and target footprint
    ↓
Material BSDF / BRDF / roughness response
    ↓
Receiver aperture, optics and detector
    ↓
received optical power / coherent electric field / SNR
    ↓
FMCW waveform and FFT (optional coherent mode)
    ↓
3D layout / scan / footprint / link budget / range / intensity / speckle
```

초기 버전은 광 파워 전달을 검증하는 radiometric 모드를 먼저 완성한다. 그 위에 coherent field, speckle과 FMCW signal processing을 추가한다.

## 3. 정확도 계약과 모델 수준

시뮬레이션은 입력 데이터보다 더 정확하다고 주장해서는 안 된다. 모든 부품과 결과는 사용한 모델 수준, 유효 조건, 가정과 불확도를 함께 기록한다.

### 3.1 모델 수준

#### Level 0 — Ideal

- ideal thin lens, mirror, aperture
- analytical 검증과 초기 시스템 구성용
- aberration, 제조 공차와 coating wavelength dependence를 생략

#### Level 1 — Paraxial Specification

- effective focal length
- clear aperture
- design wavelength
- transmission
- Gaussian q-parameter 또는 ABCD propagation

#### Level 2 — Sequential Prescription

- surface radius 또는 sag model
- surface spacing과 center thickness
- glass dispersion
- conic/asphere coefficients
- aperture, coating와 surface decenter/tilt
- sequential ray tracing과 aberration analysis

#### Level 3 — Vendor Black Box

- Zemax black-box 또는 제조사 전용 model
- 내부 prescription을 공개하지 않고 입력과 출력 성능만 제공
- 외부 optical software backend 또는 vendor 결과와의 비교에 사용

#### Level 4 — Measured and Calibrated

- measured beam profile
- measured transmission, wavefront 또는 M²
- scanner angle calibration
- receiver response calibration
- 실제 장비의 보정된 예측에 사용

### 3.2 모든 결과에 필요한 metadata

- model level
- wavelength와 wavelength validity
- nominal/tolerance/measured 값 구분
- data source와 revision
- 적용한 가정
- 경고와 unsupported feature
- estimated uncertainty 또는 sensitivity
- simulation software version과 config hash

### 3.3 결과 정확도 Mode

- `relative_design`: 동일한 기준에서 wavelength/component/placement 변화의 상대 비교
- `absolute_radiometric`: measured/calibrated source, path, material와 receiver data를 사용한 절대 power 예측
- `coherent_fmcw`: phase, coherence, speckle, waveform와 range까지 포함한 예측

모든 report에는 accuracy mode, confidence level, calibration status, model validity와 uncertainty class를 표시한다. 상세 규칙은 [`specs/ACCURACY_AND_CALIBRATION.md`](specs/ACCURACY_AND_CALIBRATION.md)를 따른다.

## 4. 빔 표현과 전파 모델

빔의 공간 형상과 전파 계산법을 서로 분리한다.

### 4.1 SpatialProfile

지원할 profile:

- circular Gaussian
- elliptical Gaussian
- line Gaussian
- rectangular top-hat
- elliptical top-hat
- measured 2D irradiance/field map

포인트 빔은 수학적인 무한히 가는 ray가 아니라 유한한 waist와 발산각을 가진 Gaussian beam preset으로 정의한다. 라인 빔은 두 축의 크기와 발산이 크게 다른 profile이며, 면적 빔은 총 power와 2D irradiance 분포를 함께 보존한다.

### 4.2 PropagationModel

- `gaussian_q`: circular/elliptical Gaussian의 paraxial propagation
- `second_moment`: general astigmatic 또는 measured beam의 moment propagation
- `ray_bundle`: geometrical envelope와 aperture analysis
- `sequential_ray`: lens prescription 기반 ray tracing
- `fresnel_field`: top-hat, diffractive element와 near-field propagation
- `measured_transfer`: 측정한 input-output relation 또는 lookup table

Gaussian q-parameter를 top-hat이나 Powell lens profile에 그대로 적용하지 않는다. 사용한 propagation model의 validity를 결과에 표시한다.

### 4.3 Beam source 입력

- wavelength 또는 spectrum
- optical power
- waist radius/position 또는 measured profile
- M² 또는 second-moment matrix
- source position과 direction
- polarization state
- coherence mode
- optional fiber MFD, NA와 connector

### 4.4 공통 BeamState

- time
- origin과 propagation direction
- local transverse axes
- wavelength/spectrum
- optical power
- spatial profile reference
- propagation model
- x/y beam radius와 divergence
- second-moment/covariance data
- polarization와 coherence state
- optical path length
- accumulated transmission
- source component와 optical path ID

## 5. Collimator 및 송신 광학계

Collimator를 단일 thin lens로 고정하지 않고 model level에 따라 해석한다.

지원 요소:

- free space
- thin/thick/aspheric lens
- fiber collimator
- triplet 또는 multi-element collimator
- aperture/field stop
- flat/curved mirror
- beam expander
- cylindrical/Powell lens
- filter, window와 beamsplitter

Collimator 공통 입력:

- source interface: fiber/free-space/diode/measured
- design wavelength와 valid wavelength range
- effective/back focal length
- clear aperture와 mechanical aperture
- source waist 또는 fiber MFD와 lens 사이 거리
- glass/coating/transmission
- optional surface prescription 또는 vendor model
- nominal alignment와 tolerances

필수 출력:

- element 전후 BeamState
- waist 위치, beam radius와 divergence
- aberration/validity report
- aperture clipping loss
- surface/coating/transmission loss
- beam decenter와 angular error
- 각 광학 요소 이후의 intermediate state

STL/STEP 형상만으로 lens의 focusing이나 collimation을 계산하지 않는다. Mechanical CAD와 optical prescription은 별도 자료로 연결한다.

## 6. 상용 광학 부품 Catalog

Thorlabs 같은 상용 제품은 제조사와 part number를 key로 하는 versioned catalog로 관리한다.

### 6.1 ComponentRecord

```yaml
schema_version: 1
id: thorlabs:TC12FC-1550
manufacturer: Thorlabs
part_number: TC12FC-1550
revision: null

component_type: fiber_collimator
model_level: vendor_blackbox

optical:
  design_wavelength_m: 1550 nm
  wavelength_range_m: null
  effective_focal_length_m: null
  clear_aperture_m: null
  transmission: null

input_port:
  type: fiber
  mode_field_diameter_m: null
  numerical_aperture: null
  connector: FC

models:
  vendor_file: vendor/thorlabs/TC12FC-1550/model.zmx
  fallback_model: gaussian_collimator

mechanical:
  cad_file: vendor/thorlabs/TC12FC-1550/drawing.step
  mounting_interface: null

provenance:
  source_url: null
  downloaded_at: null
  file_sha256: null

tolerances: {}
assumptions: []
```

실제 수치는 자동으로 추측하지 않는다. Data sheet, vendor file 또는 측정값으로 채우고 누락된 값은 `null`과 assumption으로 남긴다.

### 6.2 지원 model 입력

- data sheet specification
- Zemax `.zmx` prescription
- CODE V `.seq`
- vendor black-box model
- measured beam/transmission table
- mechanical STEP/STL/OBJ
- product drawing PDF와 provenance

Black-box file은 자체 engine에서 일반 lens prescription으로 변환했다고 가정하지 않는다. 외부 software에서 실행하거나 vendor 출력과 비교하는 reference model로 취급한다.

### 6.3 Catalog 저장 구조

```text
catalog/
└─ components/
   ├─ thorlabs/
   ├─ edmund/
   └─ custom/

assets/
└─ vendor/
   └─ thorlabs/
      └─ TC12FC-1550/
         ├─ datasheet.pdf
         ├─ model.zmx
         ├─ drawing.step
         └─ measured_profile.csv
```

Vendor license나 재배포 제한이 있는 파일은 private asset 또는 machine-local asset으로 관리하고 catalog에는 path, hash와 provenance만 저장할 수 있어야 한다.

## 7. 사용자 광학계 입력과 부품 배치

광학 설계는 optical prescription, mechanical geometry와 spatial placement를 분리한 뒤 하나의 `OpticalAssembly`에서 연결한다.

### 7.1 좌표계

필수 frame:

- world frame
- assembly frame
- component local frame
- optical input/output port frame
- optical surface frame
- scanner pivot/frame
- target/scene frame
- receiver frame

위치와 방향은 `RigidTransform`으로 표현한다.

```text
RigidTransform = translation_m + rotation
```

내부 rotation은 quaternion 또는 3×3 rotation matrix를 사용한다. 사용자는 Euler angle을 입력할 수 있지만 rotation order를 명시하고 즉시 내부 표현으로 변환한다.

### 7.2 Component optical port

각 부품은 연결 가능한 port를 가진다.

- port ID
- local position
- local optical axis
- local transverse axes
- clear aperture
- accepted beam/interface type
- input/output 또는 bidirectional
- reference plane

예:

```text
fiber.output → collimator.input
collimator.output → fold_mirror.input
fold_mirror.output → scanner.input
scanner.output → scene
scene return → receiver.input
```

### 7.3 배치 방식

#### Absolute placement

- world 또는 assembly frame 기준 translation/rotation
- CAD에서 알고 있는 절대 위치를 입력할 때 사용

#### Port-to-port placement

- 이전 부품 output port와 다음 부품 input port 연결
- axial gap, lateral offset와 clocking angle 입력
- 광축 정렬을 자동 구성

#### Constraint-based placement

- coincident
- concentric
- parallel/perpendicular
- fixed distance
- fixed angle
- look-at/aim-at target
- mount datum alignment

#### Measured placement

- CMM, tracker 또는 camera calibration에서 측정한 transform 입력
- nominal placement와 measured placement를 함께 보관

### 7.4 Native system file

```yaml
schema_version: 1

assemblies:
  transmitter:
    frame: world
    elements:
      - id: source
        type: gaussian_source
        placement:
          mode: absolute
          translation_m: [0.0, 0.0, 0.0]
          quaternion_wxyz: [1.0, 0.0, 0.0, 0.0]

      - id: collimator
        component_ref: thorlabs:TC12FC-1550
        placement:
          mode: port
          connect_from: source.output
          connect_to: collimator.input
          axial_gap_m: 0 mm
          clocking_rad: 0.0

      - id: scan_mirror
        component_ref: custom:scan_mirror_01
        placement:
          mode: absolute
          translation_m: [0.10, 0.0, 0.0]
          euler_rad: [0.0, 0.7853981634, 0.0]
          euler_order: xyz

optical_paths:
  - id: transmit_main
    elements: [source, collimator, scan_mirror]
```

모든 입력은 schema validation, unit conversion과 reference resolution을 거쳐 immutable simulation config로 변환한다.

### 7.5 Optical prescription 입력

정밀 lens 설계는 surface sequence로 입력한다.

```yaml
surfaces:
  - id: front
    surface_type: spherical
    radius_m: 0.025
    thickness_after_m: 0.004
    medium_after: N-BK7
    clear_semi_diameter_m: 0.006
    coating: custom_ar_1550

  - id: back
    surface_type: aspheric
    radius_m: -0.018
    conic: -1.0
    asphere_coefficients: []
    thickness_after_m: 0.020
    medium_after: air
```

필요한 field:

- surface type
- radius 또는 sag function
- thickness/gap
- material와 dispersion
- clear aperture
- conic/asphere coefficients
- coating
- surface decenter/tilt
- tolerance

### 7.6 외부 파일 입력

- `.zmx`: Zemax sequential prescription importer
- `.seq`: CODE V importer
- `.zar/.zprj`: OpticStudio를 통한 unpack/export adapter
- black box: external backend 또는 validation-only model
- STEP: mechanical assembly와 collision envelope
- STL/OBJ/glTF: visualization mesh
- CSV/JSON: surface prescription, measured profile와 calibration

Importer는 읽지 못한 surface, coating, material 또는 coordinate break를 조용히 무시하지 않는다. Unsupported feature report를 생성하고 필요한 경우 import를 실패시킨다.

### 7.7 Sequential path와 non-sequential scene

- source부터 scanner 직전까지는 ordered `OpticalTrain`을 기본으로 한다.
- mirror, beamsplitter와 scanner 이후는 path graph 또는 non-sequential scene으로 확장한다.
- 초기 MVP는 하나의 transmit path와 하나의 receive path를 지원한다.
- 향후 beamsplitter branch, multiple return path와 ghost reflection을 추가한다.

### 7.8 배치 검증

- component ID/port reference 유효성
- mechanical collision과 overlap
- lens surface 또는 gap inversion
- optical axis mismatch
- aperture overfill과 clipping
- beam walk/decenter
- source가 component 뒤를 향하는 잘못된 방향
- disconnected optical path
- wavelength/coating/model validity mismatch
- mount datum과 measured transform 차이

### 7.9 배치 편집 방식

초기에는 YAML과 숫자 입력을 authoritative source로 한다. 3D viewer에서 drag/rotate한 결과는 정확한 transform 값으로 저장한다.

향후 UI 기능:

- component catalog drag-and-drop
- 3D translation/rotation gizmo
- port snap
- distance/angle constraint editor
- component tree와 optical path tree
- undo/redo와 config diff
- selected component의 data source, model level, tolerance 표시

## 8. 사용자 정의 Scanner

Scanner는 특정 제품에 종속되지 않고 geometry, rigid-body kinematics, command와 calibration을 분리한다.

### 8.1 ScannerDefinition

- scanner type
- mirror/facet geometry와 aperture
- zero-position surface normal
- pivot와 rotation axes
- command angle function
- dynamic response와 angular velocity
- reflectivity/coating
- mechanical envelope
- calibration table

### 8.2 ScannerState

시간 `t`마다 다음 상태를 생성한다.

- command angle와 actual angle
- angular velocity/acceleration
- mirror rigid transform와 normal
- input/output beam direction
- output origin와 local beam axes
- active facet 또는 scan segment
- timestamp, frame/line/pixel index

평면 거울의 방향 계산은 다음 벡터 반사식을 기준으로 한다.

```text
D_out = D_in - 2(D_in · N)N
```

작은 각도에서 optical scan angle이 mechanical mirror angle의 약 두 배라는 관계는 검산용으로만 사용한다.

### 8.3 운동 방식

- static mirror
- galvo/raster
- triangle wave
- sinusoidal/resonant
- polygon mirror
- MEMS 2-axis motion
- user-defined angle function
- time-angle calibration CSV

고급 model:

- bandwidth와 phase lag
- settling/overshoot
- jitter와 encoder quantization
- polygon facet angle/tilt error
- thermal drift와 measured calibration

## 9. Scene과 Target Footprint

초기에는 분석 가능한 plane/primitive target으로 검증하고 이후 STL/CAD scene을 추가한다.

장면 계산 결과:

- beam hit point
- surface normal
- transmitter/receiver path length
- incidence/return angle
- visibility와 occlusion
- footprint center
- major/minor radius 또는 polygon
- footprint orientation
- surface irradiance map

비스듬히 입사하면 Gaussian footprint는 입사 평면 방향으로 대략 `1 / cos(theta_incidence)`만큼 증가한다. Grazing angle에서는 유효 각도 제한과 visibility 판정이 필요하다.

STL triangle은 geometry와 normal reference이며 triangle 하나를 optical scatterer 하나로 취급하지 않는다.

## 10. 물체와 재질에 따른 광 반환

### 10.1 Radiometric mode

표면 위 incident irradiance를 `E_i`, BRDF를 `f_r`, receiver 방향의 표면 각도를 `theta_o`라고 하면 작은 표면 `dA`에서 수신되는 power는 다음과 같이 계산한다.

```text
dP_rx = E_i(x, y, wavelength)
        × f_r(omega_i, omega_o, wavelength)
        × cos(theta_o)
        × dA
        × dOmega_rx
        × T_path
        × eta_rx

dOmega_rx ≈ A_rx × cos(theta_rx) / R_rx²
```

`E_i`가 이미 표면 위 irradiance인지 beam-normal plane의 irradiance인지 명확히 구분하여 incidence cosine을 중복 적용하지 않는다.

초기 reflection model:

- Lambertian diffuse
- energy-normalized specular lobe
- mixed diffuse/specular
- retroreflective lobe
- absorbing/low-reflectivity material

Glass, filter와 transparent object에는 BRDF만이 아니라 BSDF/BTDF가 필요하다.

- Fresnel reflection/transmission
- refractive index `n(wavelength)`와 extinction `k(wavelength)`
- Snell refraction
- thickness와 absorption
- coating
- optional multiple internal reflection

재질 model은 energy conservation을 검사하고 diffuse/specular/retro/transmission/absorption의 합이 물리 범위를 벗어나지 않도록 한다.

### 10.2 Coherent mode

각 surface scatterer가 receiver aperture에 기여하는 power를 `P_i`라고 할 때 field amplitude는 `sqrt(P_i)`에 비례한다.

```text
A_i ∝ sqrt(P_i)
phi_i = 2π(R_tx_i + R_rx_i) / wavelength
        + phi_roughness_i
        + phi_material_i
E_rx = Σ A_i exp(j phi_i)
P_rx = |E_rx|²
```

Monostatic 구성에서는 range phase가 `4πR / wavelength`가 된다.

표면 scatterer의 위치와 roughness phase는 전체 scan에서 고정하고 움직이는 footprint가 각 scatterer의 amplitude weight만 변화시킨다. BRDF에서 coherent amplitude를 만드는 과정은 model assumption으로 명시하고 향후 polarization/coherence efficiency를 포함한다.

## 11. Receiver와 Detector Model

초기 구성은 monostatic circular receiver aperture로 한다. 이후 bistatic 구성과 별도 receive optical train을 허용한다.

Receiver optical 입력:

- position/direction와 placement transform
- aperture shape/diameter
- FOV와 field stop
- receive lens prescription
- optical efficiency와 coating
- focal length와 detector size
- optional fiber core/NA/LO mode

Detector 입력:

- responsivity A/W
- electrical bandwidth
- dark current
- NEP 또는 noise model
- gain
- saturation power/current
- ADC range와 sampling rate
- coherent mode의 LO power와 mixer efficiency

계산 단계를 분리한다.

```text
target return
→ power at receiver aperture
→ power after receive optics
→ power at detector/fiber
→ photocurrent or coherent baseband
→ noise and SNR
→ saturation/detection decision
```

필수 결과:

- aperture/FOV/occlusion acceptance
- received optical power
- detector power와 photocurrent
- material/path별 contribution
- SNR, saturation와 detection margin
- coherent field와 optional FMCW signal

## 12. Configuration, Component Swap와 Experiments

이 프로젝트의 물리 조건과 부품 선택은 source code가 아니라 versioned configuration에서 변경한다. 파장, source, collimator, lens, scanner, target material, receiver와 numerical model을 교체한 뒤 동일한 기준 조건에서 결과를 비교할 수 있어야 한다.

Configuration 계층:

```text
schema defaults
→ component catalog
→ optical assembly/system config
→ scenario config
→ experiment overrides
→ validated immutable effective config
```

핵심 규칙:

- 실제 물리값을 code에 하드코딩하지 않는다.
- 각 물리량은 하나의 canonical input을 가지며 derived value는 계산한다.
- assembly는 복사된 부품 값 대신 stable `component_ref`를 사용한다.
- component 교체 시 port, wavelength, aperture, placement compatibility를 검사한다.
- wavelength와 component를 포함한 단일/다중 parameter sweep을 지원한다.
- 비교 variant는 가능한 경우 동일한 geometry, sampling, seed와 output metric을 사용한다.
- 각 run은 fully resolved config, config hash, warning과 provenance를 저장한다.
- GUI와 CLI는 같은 configuration을 읽고 쓴다.
- 사용자 입력은 `1550 nm`, `10 mW`, `20 mm`, `5 deg` 같은 unit-bearing quantity를 허용한다.
- resolved config는 모든 quantity를 canonical SI/radian으로 저장한다.
- `configs/project.yaml`이 catalog/asset/measurement/scenario/experiment 경로와 active baseline을 묶는다.

초기 예제:

- `configs/baseline_1550nm.yaml`
- `configs/experiments/component_swap.example.yaml`
- `configs/project.yaml`

상세 contract는 [`specs/CONFIGURATION_AND_EXPERIMENTS.md`](specs/CONFIGURATION_AND_EXPERIMENTS.md)를 따른다.

## 13. Result Data Model

계산과 visualization을 분리하기 위해 simulation은 renderer가 아닌 structured result를 반환한다.

권장 dimension:

- time/frame/line/pixel
- optical path
- component/surface
- wavelength
- target patch/scatterer
- waveform sample/FFT bin

주요 결과 object:

- `OpticalTrainResult`
- `PlacementValidationResult`
- `BeamPropagationResult`
- `ScannerTrajectoryResult`
- `FootprintResult`
- `LinkBudgetResult`
- `ReceiverResult`
- `FMCWResult`

각 array에는 units, coordinate frame, model level와 provenance를 metadata로 저장한다. 큰 result는 labeled multidimensional dataset과 chunked storage를 사용하고, figure를 계산 결과의 유일한 저장 형태로 사용하지 않는다.

## 14. Visualization과 Analysis UI

Visualization은 개발 후반 기능이 아니라 Phase 0부터 물리 계산과 placement를 검증하는 도구로 사용한다.

### 14.1 화면 구성

```text
┌────────────────┬────────────────────────────┬──────────────────┐
│ Component Tree │ 3D Optical Assembly        │ Selected Item    │
│ Optical Paths  │ beam/scanner/scene/receiver│ spec/model/error │
├────────────────┼────────────────────────────┼──────────────────┤
│ Beam/Profile   │ Scanner/Time Analysis      │ Link Budget/SNR  │
│ x/y/2D/wavefront│ angle/path/dwell/coverage │ W/dBm/dB/margin  │
└────────────────┴────────────────────────────┴──────────────────┘
```

### 14.2 3D optical assembly view

- component CAD/ideal geometry
- component and port coordinate axes
- optical path/chief ray
- Gaussian beam envelope 또는 sampled ray bundle
- aperture와 clipping region
- scanner mirror pose와 scan animation
- target footprint/irradiance overlay
- receiver FOV와 return path
- collision, alignment와 validity warning

부품을 선택하면 다음을 표시한다.

- manufacturer/part number
- data source와 revision
- model level와 assumptions
- placement transform와 constraints
- input/output BeamState
- component loss와 clipping
- tolerance/sensitivity contribution

### 14.3 Beam analysis

- x/y profile와 2D irradiance
- waist/divergence vs distance
- 1/e² contour와 second-moment diameter
- line width/length와 uniformity
- encircled power
- wavefront/spot/ray fan when available

### 14.4 Scanner analysis

- command/actual angle
- angular velocity/acceleration
- 3D scan animation
- target trajectory, dwell time와 pixel density
- FOV coverage와 scan nonlinearity

### 14.5 Return and receiver analysis

- target irradiance map
- W/dBm link-budget waterfall
- component/path/material loss contribution
- received power vs time/pixel/range
- detector photocurrent, noise, SNR와 saturation
- nominal/tolerance/measured result comparison
- FMCW waveform, FFT, range/intensity/speckle image

### 14.6 구현 계층

- Matplotlib: analytical unit test와 static validation plot
- PyVista: 3D assembly, CAD/mesh, beam path와 footprint
- Plotly/Dash: interactive time plot, heatmap, animation과 dashboard
- standalone HTML/PNG/CSV와 structured result export

### 14.7 사용자 Workflow

```text
project 열기
→ baseline scenario 복사
→ wavelength/component/placement 변경
→ unit/reference/compatibility validation
→ run cost 확인
→ 실행/취소/재시도
→ baseline과 variant 비교
→ confidence가 포함된 HTML report export
```

초기 UI는 unit-aware input, guided validation, component search/swap, FreeCAD/STL import preview, progress/cancel, config diff와 report export를 지원하도록 설계한다. 상세 contract는 [`specs/UX_WORKFLOW.md`](specs/UX_WORKFLOW.md)를 따른다.

## 15. 핵심 Software Structure

```text
schemas/             # project/scenario/experiment/catalog/asset validation
configs/             # project, scenario and experiment files
assets/measurements/ # calibration and validation data

src/lidarsim/
├─ config/         # schema, units and immutable simulation config
├─ catalog/        # commercial/custom component records
├─ experiments/    # overrides, sweeps and variant comparison
├─ geometry/       # frames, rigid transforms, ports and constraints
├─ assembly/       # optical component placement and path graph
├─ beam/           # profiles, Gaussian/second-moment/measured beams
├─ optics/         # surfaces, prescriptions, collimators and trains
├─ importers/      # zmx, seq, CAD, CSV and measured data adapters
├─ scanner/        # scanner geometry, dynamics and calibration
├─ scene/          # primitives, STL/CAD, intersection and visibility
├─ footprint/      # projected profile and surface irradiance
├─ materials/      # BRDF/BSDF and material database
├─ scatter/        # fixed scatterers and coherent sum
├─ receiver/       # aperture, receive optics, detector and link budget
├─ fmcw/           # chirp and beat signal
├─ processing/     # FFT, CZT, range and detection
├─ results/        # labeled structured result models and storage
├─ visualization/  # static plots, 3D viewer and dashboard adapters
└─ compute/        # NumPy and optional GPU backend
```

주요 data object:

- `RigidTransform`
- `OpticalPort`
- `ComponentRecord`
- `ComponentInstance`
- `PlacementConstraint`
- `OpticalAssembly`
- `OpticalPath`
- `BeamSourceConfig`
- `BeamState`
- `ScannerDefinition/State`
- `Footprint`
- `Material`
- `Receiver/Detector`
- `SimulationConfig`
- `ExperimentSpec`
- `ParameterSweep`
- `ComparisonResult`
- `AccuracyReport`
- `PowerLedger`
- `ConvergenceReport`
- `MeasurementSet`
- structured result objects

## 16. 개발 단계

### Phase 0 — Contract, Configuration, Coordinate와 Viewer Skeleton

- Python package/test structure
- unit-aware parser와 coordinate convention
- `RigidTransform`, port와 component placement schema
- model level/assumption/provenance contract
- JSON Schema 기반 project/catalog/config/result validation
- `configs/project.yaml` project manager contract
- scenario override와 component-swap experiment contract
- accuracy/confidence/result manifest contract
- energy ledger와 convergence-report skeleton
- guided error message와 FreeCAD/STL preview contract
- minimal 2D/3D placement viewer

완료 조건: 두 개의 ideal optical component를 배치하고 port로 연결한 뒤 config를 저장/재로드하고 3D 위치와 optical axis를 검증한다.

Phase 0 완료 상태 (2026-06-29): Python package/test 구조, unit-aware YAML resolution, JSON Schema project/scenario/experiment/catalog/result validation, catalog/port/scanner 의미 검증, immutable resolved configuration, physical configuration hash, `RigidTransform`, optical port frame, absolute·port-to-port placement resolver, STL·measurement asset registry, accuracy·energy·convergence·manifest report와 headless 2D/3D placement viewer가 구현되었다. Canonical config 저장→재로드 후 hash와 world placement가 유지됨을 확인했다.

Phase 0.1 검수 강화 상태 (2026-06-29): 양수여야 하는 물리량과 wavelength/component validity의 cross-field 검사, scenario가 source 운전값을 소유하는 contract, port `interface_type`·`reference_plane`, `model_purpose`·receiver `model_level`과 hardware readiness를 추가했다. Baseline은 `analytical_regression`이며 ideal thin lens와 `virtual_monostatic/virtual_aperture`를 사용하므로 실제 상용 collimator 또는 수신계의 절대 성능을 예측한다고 주장하지 않는다. Viewer는 mirror zero normal, 기계각의 두 배가 되는 declared optical scan limit, receiver FOV와 return-path guide를 표시하고, `lidarsim review`는 지원 output·경고·수치 검사를 standalone HTML로 만든다. 이 guide들은 Phase 1의 beam propagation이나 Phase 5의 received-power 계산 결과가 아니다. STL `normal_policy=repair`도 현재 자동 수정으로 과장하지 않고 mismatch 기록과 외부 재-export 절차로 제한한다.

### Phase 1 — Beam Engine

- point Gaussian과 elliptical line Gaussian profile
- Gaussian q-parameter와 second-moment propagation
- measured profile input contract
- power normalization
- beam/profile visualization

완료 조건: 분석식과 일치하는 beam radius/divergence/power를 얻고 point/line beam preset을 시각화한다.

Phase 1 완료 상태 (2026-07-04): 불변 `BeamState`, 오른손 local beam frame, circular·elliptical·line Gaussian profile, M² 기반 Rayleigh range·발산·1/e² radius, complex q-parameter, free-space propagation과 second-moment covariance propagation을 NumPy/float64로 구현했다. Irradiance는 `2P/(π w_x w_y)`로 정규화하며 field amplitude weight와 power를 분리한다. Fiber MFD definition과 Gaussian-equivalent 해석, catalog nominal match/explicit override, small-angle paraxial proxy를 명시적으로 검증한다. `phase1_beam_report.schema.json`과 compact summary에는 model purpose, confidence, calibration, hardware readiness, provenance, 가정과 경고를 포함한다. Power audit은 analytical tail truncation, base/refined grid quadrature와 grid convergence를 분리하고 Gaussian/second-moment 비교는 `internal_consistency_only`, 외부 측정 검증은 `not_evaluated`로 표시한다. `lidarsim beam`은 단위 포함 거리와 timestamp run directory를 지원하며 point/line radius·profile PNG를 생성한다. Measured profile은 입력 contract만 제공하며 실제 전파는 아직 지원하지 않는다. Downstream lens·aperture·mirror와 clipping/loss는 Phase 2 범위다.

### Phase 2 — Optical Components, Catalog와 Assembly

- free space, thin lens, aperture와 mirror
- collimator와 fiber source interface
- commercial/custom catalog
- optical surface prescription
- port/absolute placement
- STL mechanical/visual geometry와 sidecar metadata
- clipping/loss report

완료 조건: 상용 또는 custom collimator와 mirror를 배치한 transmitter train이 config에서 재현되고 element별 BeamState와 loss가 표시된다.

Phase 2 vertical slice 상태 (2026-07-10): `src/lidarsim/optics/`에 determinant가 0이 아닌 paraxial `ABCDMatrix`, free-space와 ideal thin-lens q-parameter transform, centered circular aperture clipping, static flat-mirror reflection, rectangular mirror aperture clipping과 transmitter train propagation을 추가했다. Phase 2.2/2.3 확장으로 `rectangle_plane` target 중심 ray hit, projected Gaussian footprint, target에 걸린 power, Lambertian small-footprint receiver aperture power와 link budget을 analytical reference로 계산한다. `lidarsim optical-train`은 active source에서 ideal thin-lens collimator와 catalog base pose에 `scanner.static_command_angle_rad`를 적용한 mirror를 지나 target/receiver까지의 `BeamState`, aperture clipping, catalog power transmission/reflectivity, power ledger, target footprint, receiver return, ABCD 내부 일관성 check와 PNG를 생성한다. 현재는 ideal centered thin lens, centered aperture, static command-angle flat mirror, rectangle-plane target와 virtual Lambertian receiver만 지원하며, truncated aperture diffraction, aberration, decenter/tilt tolerance, commercial vendor black-box execution, STL hit detection, visibility/occlusion, non-Lambertian BRDF/BSDF, detector noise와 coherent FMCW는 아직 계산하지 않는다. 이 Phase 2 report 자체는 한 개의 static pose만 계산하고, ideal time sample은 Phase 3 `scanner-path` report에서 생성한다. x/y waist 위치가 분리되는 astigmatic post-lens beam은 현재 `BeamState` contract로 정확히 표현할 수 없으므로 silent approximation 대신 명시적으로 거부한다.

### Phase 3 — User-defined Scanner

- scanner placement/pivot/axes
- mirror reflection
- raster/triangle/sinusoidal motion
- command vs actual state
- custom function/calibration table

완료 조건: plane target에서 요청한 FOV/trajectory가 생성되고 mirror angle, beam angle와 placement 변화가 검증된다.

Phase 3 reference slice 상태 (2026-07-10): `scanner.static_command_angle_rad`를 mirror normal과 aperture axes에 적용하고, `lidarsim scanner-sweep`으로 여러 정적 mechanical angle의 reflected direction, target hit, target power와 receiver return을 비교한다. `lidarsim scanner-path`는 `static`, `triangle`, `sinusoidal` 설정에서 한 줄의 ideal forward command path를 시간 sample로 만들며 YAML/CSV/PNG와 JSON Schema contract를 제공한다. `static` scanner의 유효한 0 Hz pose도 지원한다. 이 path는 command/reference fidelity이며 실제 motor/galvo lag, jitter, acceleration limit, bidirectional return stroke, `raster`/`custom` trajectory와 calibration table은 아직 구현하지 않았다. 따라서 requested `scan_path` output은 미구현과 구분되는 `reference_only` warning으로 표시한다.

### Phase 4 — Scene Intersection와 Footprint

- plane/primitive intersection
- visibility/occlusion
- point/line footprint projection
- irradiance integration

완료 조건: target에 도달한 power가 clipping/transmission을 제외하면 송신 power와 일관되고 입사각에 따른 footprint 변화가 검증된다.

### Phase 5 — Material과 Receiver Aperture

- diffuse/specular/retro material
- BRDF link budget
- receiver aperture/FOV/receive optics
- material/path contribution report

완료 조건: 거리, aperture, angle, reflectivity와 component/config 변화에 물리적으로 일관된 received-aperture power가 나온다.

### Phase 6 — Integrated Scan, UI와 Tolerance

- frame/line/pixel scan
- interactive 3D assembly와 scan animation
- received-power image와 link-budget dashboard
- wavelength/parameter/component-swap comparison
- placement tolerance/sensitivity/Monte Carlo
- measured scanner/beam calibration comparison
- progress/cancel/cache/retry와 HTML comparison report

완료 조건: 하나의 project/config로 source부터 receiver aperture까지 end-to-end simulation이 실행되고 nominal/tolerance/component-swap 결과를 비교할 수 있다.

### Phase 7 — Coherent FMCW와 Speckle

- fixed scatterer map
- coherent field sum
- FMCW beat signal/FFT/range
- scanner-driven speckle decorrelation

완료 조건: 알려진 target range의 FFT peak가 한 bin 안에 있고 scan 위치에 따른 speckle 변화가 재현된다.

### Phase 8 — Complex CAD, Advanced Physics와 Performance

- STL/STEP complex scene와 multiple optical paths
- constraint-based placement solver와 advanced UI editor
- top-hat/area-beam Fresnel propagation
- `.zmx/.seq` import와 optional OpticStudio adapter
- transparent BSDF, refraction와 ghost paths
- detector photocurrent/noise/SNR/saturation
- measured/catalog material data
- polarization/Fresnel coating model
- atmosphere absorption/scattering/turbulence when requested
- thermal/environmental drift
- batching/optional GPU backend
- fiber/LO coupling
- Doppler, phase noise와 chirp nonlinearity
- large-scene benchmark

## 17. 검증 시나리오

### Phase 0-2: Configuration, Placement와 Beam

1. Unit-bearing input이 canonical SI/radian resolved config로 변환된다.
2. Unknown field, invalid unit와 missing catalog reference가 명확한 error를 만든다.
3. Port-to-port component의 optical axis와 gap이 입력값과 일치한다.
4. Absolute placement 결과가 rigid-transform 분석값과 일치한다.
5. CAD mechanical origin과 optical-port datum 차이가 올바르게 적용된다.
6. Point beam/collimator spot size가 Gaussian 분석식과 일치한다.
7. Aperture overfill에서 clipping warning, power loss와 energy ledger가 일치한다.
8. Baseline과 동일한 variant의 metric delta가 tolerance 안에서 0이다.

### Phase 3-6: Scanner, Target와 Radiometry

9. Line beam을 mirror로 scan하고 line 위치/orientation이 분석값과 일치한다.
10. Receiver aperture를 키우면 expected regime에서 received power가 증가한다.
11. Diffuse, mirror, black material와 retroreflector return이 구분된다.
12. Distance 증가에 따른 power 감소가 선택한 radiometric model과 일치한다.
13. Wavelength/component swap이 effective config, compatibility warning와 comparison report에 추적된다.
14. Mesh/footprint/time sampling을 refine했을 때 selected metric이 수렴한다.
15. Catalog nominal/tolerance/measurement provenance가 result까지 추적된다.

### Phase 7-8: Advanced Physics

16. 같은 seed에서 roughness/speckle/tolerance result가 재현된다.
17. 10 m target FMCW range가 한 range bin 안에 있다.
18. Detector saturation/noise threshold가 analytical case와 일치한다.
19. Area-beam power integral과 Fresnel propagation이 선택한 reference case와 일치한다.
20. CPU/GPU와 precision 변화가 declared metric tolerance를 만족한다.

Energy와 numerical convergence는 [`specs/ENERGY_AND_CONVERGENCE.md`](specs/ENERGY_AND_CONVERGENCE.md)를 따른다.

## 18. Tolerance, Calibration과 Validation

정확한 시스템은 nominal part data만으로 완성되지 않는다.

Tolerance 대상:

- source waist/MFD/power/wavelength
- component position/decenter/tilt/clocking
- focal length, radius, thickness와 refractive index
- clear aperture와 coating transmission
- scanner pivot, zero angle, scale와 dynamic lag
- receiver alignment, aperture와 detector response
- material parameter와 roughness

분석 방식:

- one-at-a-time sensitivity
- tolerance stack
- worst-case bounds
- seeded Monte Carlo
- measured calibration fitting
- vendor output 또는 external optical software와 golden-case comparison

시뮬레이션 결과에는 nominal value뿐 아니라 uncertainty band와 주요 error contributor를 표시한다.

## 19. 물리 및 구현 원칙

- geometry, propagation, radiometry, detector와 coherent signal layer를 분리한다.
- mechanical CAD, optical prescription와 measured data를 구분한다.
- 모든 component placement는 explicit coordinate frame과 transform을 가진다.
- wavelength와 모든 실제 장비/재질/scan parameter는 editable configuration에서 주입한다.
- component 교체는 stable catalog reference와 compatibility validation을 사용한다.
- beam은 항상 유한한 profile과 total optical power를 가진다.
- power, irradiance, radiance와 field amplitude의 units를 구분한다.
- 모든 optical loss와 clipping을 path별로 추적한다.
- unsupported vendor/import feature를 조용히 무시하지 않는다.
- CPU `float64/complex128` 결과를 기준값으로 사용한다.
- 모든 stochastic model은 seed를 받는다.
- GPU는 CPU physics와 regression test가 검증된 뒤 추가한다.
- 큰 계산에서 `[pixels, scatterers, samples]` 전체 배열을 한 번에 만들지 않는다.
- 각 Phase는 analytical test, unit test, visualization과 example config를 함께 완료한다.

## 20. 사용자와 함께 결정할 항목

실제 장비 사양은 아직 결정되지 않았으므로 Phase 0-5 구현과 검증에는 [`specs/INITIAL_BASELINE.md`](specs/INITIAL_BASELINE.md)의 교체 가능한 초기값을 사용한다.

### 확정된 초기 구현 기준

- [x] 1550 nm single-wavelength reference; config에서 변경 가능
- [x] 10 mW, 10 µm MFD, M²=1.0 fiber Gaussian reference
- [x] point Gaussian과 elliptical line Gaussian 우선; area diffraction은 이후
- [x] native Python CPU core; Zemax/CODE V가 없어도 실행
- [x] ideal 20 mm focal-length collimator와 catalog-reference 교체 구조
- [x] absolute/port-to-port placement 우선; full constraint solver는 이후
- [x] one-axis ideal mirror scanner, one transmit path
- [x] 10 m flat Lambertian target
- [x] virtual monostatic 25 mm receiver aperture
- [x] 첫 return 결과는 receiver-aperture optical power와 link budget
- [x] Matplotlib 검증 plot과 PyVista 3D layout 우선
- [x] CPU/float64, 101-sample scan-line 기준
- [x] 모든 물리값과 component 선택은 editable config와 experiment override로 변경

### FreeCAD/STL workflow

- [x] 사용자가 가진 geometry의 초기 교환 형식은 STL
- [x] FreeCAD `.FCStd`는 optional source asset으로 보관
- [x] STL의 unit/role/material/placement/pivot는 `.stl.yaml` sidecar로 보완
- [x] multi-material/moving part는 separate STL로 export
- [x] lens STL은 visualization/mechanical geometry로만 사용

### 실제 장비가 정해지면 교체할 항목

- [ ] 실제 wavelength/spectrum, source model과 measured beam parameters
- [ ] 실제 collimator/lens/mirror/beamsplitter part numbers
- [ ] 실제 scanner STL, pivot, axes, coating, angle/frequency/timing
- [ ] 실제 transmit/receive optical path와 monostatic/bistatic architecture
- [ ] receiver optics, detector와 target material data
- [ ] vendor file의 Git/private/local asset policy
- [ ] 실제 정확도, tolerance, frame/pixel 규모와 runtime 목표
- [ ] OpticStudio/Zemax 또는 bench measurement 비교 가능 여부

## 21. 첫 번째 수직 구현 목표

```text
editable baseline config and component references
→ point/line Gaussian source
→ ideal or catalog-backed thin-lens collimator
→ port-connected one-axis mirror scanner
→ flat diffuse target
→ virtual monostatic circular receiver aperture
→ 3D component layout
→ beam envelope, scan path, footprint, received power and link budget
```

이 경로가 analytical result와 일치한 뒤 sequential prescription, vendor file import, STEP assembly, complex BSDF, coherent FMCW와 GPU 순서로 확장한다.

## 22. 참고 자료

- [ISO 11146-2:2021 — beam width, divergence and propagation ratio](https://www.iso.org/standard/77770.html)
- [Thorlabs Triplet Fiber Optic Collimators/Couplers](https://www.thorlabs.com/newgrouppage9.cfm?objectgroup_id=5124&pn=TC12FC-633)
- [Thorlabs example lens specifications and Zemax files](https://www.thorlabs.com/NewGroupPage9.cfm?ObjectGroup_ID=6509)
- [Ansys OpticStudio Lens Data Editor](https://ansyshelp.ansys.com/public/Views/Secured/Zemax/v25101/en/OpticStudio_User_Guide/OpticStudio_Help/topics/Lens_Data_Editor.html)
- [Ansys OpticStudio Black Box Lens limitations](https://ansyshelp.ansys.com/public/Views/Secured/Zemax/v251/en/OpticStudio_User_Guide/OpticStudio_Help/topics/Black_Box_Lens.html)
- [RayOptics sequential model and Zemax/CODE V import](https://ray-optics.readthedocs.io/en/stable/)
- [NIST BRDF definition](https://math.nist.gov/~FHunt/appearance/brdf.html)
- [CadQuery STEP import/export](https://cadquery.readthedocs.io/en/latest/importexport.html)
- [PyVista 3D visualization](https://docs.pyvista.org/index.html)
- [Plotly animations and Dash integration](https://plotly.com/python/animations/)
- [`specs/INITIAL_BASELINE.md`](specs/INITIAL_BASELINE.md)
- [`specs/COORDINATES_AND_PLACEMENT.md`](specs/COORDINATES_AND_PLACEMENT.md)
- [`specs/CONFIGURATION_AND_EXPERIMENTS.md`](specs/CONFIGURATION_AND_EXPERIMENTS.md)
- [`specs/ACCURACY_AND_CALIBRATION.md`](specs/ACCURACY_AND_CALIBRATION.md)
- [`specs/UX_WORKFLOW.md`](specs/UX_WORKFLOW.md)
- [`specs/ENERGY_AND_CONVERGENCE.md`](specs/ENERGY_AND_CONVERGENCE.md)
- [`specs/MEASUREMENT_DATA.md`](specs/MEASUREMENT_DATA.md)
- [`USER_MANUAL.md`](USER_MANUAL.md)

## 23. v0.2 변경 사항

- spatial profile과 propagation model 분리
- model fidelity/accuracy contract 추가
- commercial component catalog와 provenance 추가
- Zemax/CODE V/vendor black-box import 전략 추가
- mechanical CAD와 optical prescription 분리
- coordinate frame, rigid transform, optical port와 placement constraint 추가
- absolute/port/constraint/measured component placement 추가
- optical path와 assembly validation 추가
- BRDF radiometry 식과 transparent BSDF model 정교화
- detector/SNR/saturation layer 추가
- structured result data model 추가
- 3D placement editor와 analysis dashboard 구체화
- tolerance/calibration/validation 계획 추가
- 개발 순서를 schema/catalog/viewer부터 시작하도록 재구성
- physical parameter와 component 선택을 config-driven experiment로 분리
- wavelength/parameter/component-swap comparison contract와 예제 추가
- FreeCAD/STL asset workflow와 sidecar metadata contract 추가
- 사용자 설정, component 교체와 experiment 비교 manual 추가
- unit-aware input, project manager와 JSON Schema contract 추가
- relative/absolute/coherent accuracy mode와 confidence badge 추가
- measurement/calibration data와 traceability contract 추가
- energy ledger와 numerical convergence contract 추가
- guided wizard, validation UX, progress/cache/report workflow 추가
- Phase별 validation gate로 재구성하고 area/detector 범위 불일치 수정
