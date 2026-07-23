# 사용자 설정 및 부품 교체 매뉴얼

- 문서 상태: Draft v0.2
- 대상 프로젝트: Custom Beam, Scanner, and Optical Return Simulator
- 기준 설계: `PROJECT_VISION.md` Draft v0.2
- 마지막 갱신: 2026-07-09

## 1. 이 매뉴얼의 목적

이 매뉴얼은 Python source code를 수정하지 않고 다음 조건을 설정하거나 교체하는 방법을 설명한다.

- wavelength와 source power
- point/line/area beam 조건
- collimator, lens, aperture, mirror와 scanner component
- component position/orientation와 optical path
- scanner angle, frequency와 waveform
- FreeCAD에서 만든 STL geometry
- target material과 reflectivity
- receiver aperture/FOV/efficiency
- numerical model과 output
- 여러 wavelength/component/parameter variant 비교

모든 실제 장비값은 versioned YAML configuration과 catalog record에 보관한다. Simulation logic 안에 특정 장비값을 hard-code하지 않는 것이 원칙이다.

## 2. 현재 구현 상태

Phase 0·0.1과 Phase 1 Gaussian Beam Engine이 완료되었다. `lidarsim validate`는 project/scenario/experiment/catalog YAML을 검사하고 단위, 물리 범위, wavelength validity와 참조·배치를 검증한다. `placement`, `inspect-mesh`, `inspect-measurement`, `report`, `view`, `review`로 배치와 입력 contract를 확인할 수 있다. `lidarsim beam`은 active source의 point·elliptical·line Gaussian을 NumPy/float64로 자유공간 전파하고 radius, divergence, q-parameter, second moment와 power-normalized irradiance를 YAML/PNG로 저장한다. Numerical check와 실제 장비 calibration을 구분해 confidence, provenance, paraxial validity와 hardware readiness를 함께 표시한다.

Phase 2의 vertical slice로 `lidarsim optical-train`이 추가되었다. 이 명령은 source에서 ideal thin-lens collimator를 거쳐 scanner mirror에서 정지 반사되고, rectangle-plane target footprint와 첫 Lambertian virtual-aperture estimate까지 free-space propagation, ABCD thin-lens transform, centered circular aperture clipping, static flat-mirror reflection, mirror aperture clipping, catalog power transmission/reflectivity, target hit/footprint와 analytical link budget을 계산한다. 이 값은 동일 scanner/collimator의 역방향 traversal 또는 fiber-coupled power가 아니다. 현재는 `scanner.static_command_angle_rad` 하나를 static pose로 적용해 mirror normal, reflected ray, target hit와 virtual-aperture estimate를 바꿀 수 있다. Phase 3의 첫 helper로 `lidarsim scanner-sweep`이 추가되어 여러 static command angle에서 target hit와 analytical return 변화를 YAML/CSV/PNG로 비교할 수 있다. 이어서 `lidarsim scanner-path`가 추가되어 config의 scanner waveform에서 한 줄의 ideal forward scan path를 시간 샘플로 만들고, 각 sample의 target hit와 virtual-aperture estimate를 계산한다. Dynamic lag, jitter, bidirectional return stroke, calibration table과 실제 scanner dynamics는 아직 적용하지 않는다. 여러 rectangle-plane이 중심 광선을 가로막으면 가장 가까운 하나만 opaque visible target으로 energy에 기여하지만, beam footprint 면적별 부분 가림과 STL occlusion은 아직 없다. Reciprocal return train, single-mode fiber coupling, STL hit detection, non-Lambertian BRDF/BSDF, detector noise, speckle와 coherent FMCW는 아직 구현되지 않았다. `lidarsim run`, `compare`와 calibrated scan radiometry는 아직 구현되지 않았다.

## 3. 주요 파일 위치

```text
Optic_ray_project/
├─ configs/
│  ├─ project.yaml
│  ├─ baseline_1550nm.yaml
│  └─ experiments/
│     └─ component_swap.example.yaml
│
├─ catalog/
│  ├─ components/
│  │  └─ custom/
│  └─ materials/
│     └─ custom/
│
├─ assets/
│  ├─ source/freecad/
│  ├─ meshes/
│  └─ measurements/
│
├─ schemas/
│
└─ docs/
   ├─ PROJECT_VISION.md
   ├─ USER_MANUAL.md
   └─ specs/
```

중요 문서:

- [프로젝트 전체 설계](PROJECT_VISION.md)
- [초기 기준 사양](specs/INITIAL_BASELINE.md)
- [좌표·배치·STL 규칙](specs/COORDINATES_AND_PLACEMENT.md)
- [설정·부품 교체·실험 규칙](specs/CONFIGURATION_AND_EXPERIMENTS.md)
- [정확도·보정 규칙](specs/ACCURACY_AND_CALIBRATION.md)
- [UX workflow](specs/UX_WORKFLOW.md)
- [시뮬레이션 UI 개발 계획](UI_SIMULATION_DASHBOARD.md)
- [에너지·수렴성 규칙](specs/ENERGY_AND_CONVERGENCE.md)
- [측정 데이터 규칙](specs/MEASUREMENT_DATA.md)
- [프로젝트 설정 파일](../configs/project.yaml)
- [기준 설정 파일](../configs/baseline_1550nm.yaml)
- [부품 교체 실험 예제](../configs/experiments/component_swap.example.yaml)
- [STL metadata template](../assets/meshes/mesh_metadata.example.yaml)

## 4. 권장 작업 순서

조건이나 부품을 바꿀 때 baseline 파일을 직접 덮어쓰지 않는 것이 좋다.

1. `configs/project.yaml`에서 catalog/asset 경로와 active baseline을 확인한다.
2. `configs/baseline_1550nm.yaml`을 복사한다.
3. 복사한 파일의 `scenario_id`를 고유하게 변경한다.
4. 필요한 물리 조건이나 `component_ref`만 변경한다.
5. `lidarsim validate`로 units, references, wavelength와 placement를 검사한다.
6. Baseline과 variant를 같은 sampling/seed로 실행한다.
7. 결과 metric의 절대값과 baseline 대비 변화량을 비교한다.
8. 사용한 effective config와 결과를 함께 보존한다.

예시 파일명:

```text
configs/my_1310nm_test.yaml
configs/my_thorlabs_collimator_test.yaml
configs/my_scanner_v2.yaml
```

## 5. 기본 설정 구조

### 5.1 Project file

[`configs/project.yaml`](../configs/project.yaml)은 catalog, asset, measurement, scenario, experiment와 result 경로를 묶는다.

```yaml
project_id: optic_ray_default
catalog_paths:
  - ../catalog/components
  - ../catalog/materials
scenarios:
  - baseline_1550nm.yaml
active_baseline: baseline_1550nm
```

### 5.2 Unit-aware input

사용자 YAML은 compatible unit string을 허용한다.

```yaml
wavelength_m: 1550 nm
optical_power_w: 10 mW
effective_focal_length_m: 20 mm
mechanical_amplitude_rad: 5 deg
frequency_hz: 10 Hz
```

Field suffix `_m`, `_w`, `_rad`, `_hz`는 resolved canonical unit을 뜻한다. Input parser는 compatible unit을 SI/radian으로 변환한다. Unit 없는 number는 canonical SI 값으로 해석되지만 사용자 입력에는 unit string을 권장한다.

### 5.3 Scenario structure

기준 설정은 다음 영역으로 나뉜다.

```yaml
model_purpose: analytical_regression

source:             # wavelength, power, beam parameters
optical_assembly:   # component references, placement, optical paths
scanner:            # motion and timing
scene:              # target geometry and material
receiver:           # aperture, FOV and optical efficiency
simulation:         # model/backend/precision/seed
outputs:            # requested results
```

## 6. Wavelength 변경

[기준 설정](../configs/baseline_1550nm.yaml)의 다음 값을 바꾼다.

```yaml
source:
  element_id: source
  parameter_ownership: scenario_operating_point
  catalog_parameter_policy: match_nominal
  profile_kind: circular_gaussian
  propagation_model: gaussian_m2
  wavelength_m: 1550 nm
```

`scenario_operating_point`는 실제 실행에 쓰는 wavelength, power와 beam 조건은 scenario 값이 authoritative source라는 뜻이다. Component catalog의 값은 부품의 nominal specification·validity·provenance이며 scenario 운전값을 조용히 덮어쓰지 않는다.

예:

```yaml
# 1310 nm
wavelength_m: 1310 nm

# 1064 nm
wavelength_m: 1064 nm

# 905 nm
wavelength_m: 905 nm
```

Wavelength를 변경하면 다음 항목을 함께 확인해야 한다.

- source와 fiber MFD validity
- collimator design wavelength/range
- lens glass/coating data
- mirror/filter transmission 또는 reflectivity
- target material wavelength data
- receiver/detector spectral response

Wavelength만 변경하고 component data를 그대로 사용할 수 없는 경우 warning 또는 validation error가 발생해야 한다.

현재 Phase 0.1 validator는 source와 optical component의 declared wavelength range를 강제하고, target material의 기준 wavelength가 다르면 warning을 낸다. 상세 coating curve, glass dispersion와 detector spectral response 검사는 해당 model이 구현되는 Phase에서 추가한다.

## 7. Source와 Beam 조건 변경

### 7.1 Optical power

```yaml
source:
  optical_power_w: 10 mW
```

예:

```yaml
optical_power_w: 1 mW
optical_power_w: 50 mW
```

### 7.2 Fiber source

```yaml
source:
  type: fiber_gaussian
  profile_kind: circular_gaussian
  propagation_model: gaussian_m2
  mode_field_diameter_m: 10 um
  mode_field_diameter_definition: gaussian_1e2_intensity
  mfd_gaussian_approximation: true
  waist_offset_m: 0 m
  m2_x: 1.0
  m2_y: 1.0
```

실제 fiber를 사용할 때는 제조사와 wavelength에 따른 MFD를 입력한다. NA와 MFD가 모두 있더라도 어느 값을 canonical beam input으로 사용할지 model에 명시해야 한다.

`mode_field_diameter_definition`은 다음 중 하나다.

- `gaussian_1e2_intensity`: MFD를 Gaussian 1/e² intensity diameter로 정의
- `petermann_ii`: Petermann II MFD를 Gaussian-equivalent diameter로 근사
- `manufacturer_unspecified`: 제조사 정의가 명확하지 않음

`petermann_ii` 또는 `manufacturer_unspecified`를 사용하면 approximation warning이 발생한다. 불확도를 알고 있으면 `mode_field_diameter_uncertainty_m`에 입력한다. 현재 Phase 1 report는 이 불확도를 기록하지만 tolerance propagation은 아직 하지 않는다. Gaussian 근사를 허용하지 않을 경우 `mfd_gaussian_approximation: false`로 두고 measured-profile workflow를 사용해야 한다.

Scenario 값을 catalog nominal과 같게 유지할 때는 `catalog_parameter_policy: match_nominal`을 사용한다. Power, wavelength, MFD 등을 의도적으로 바꿀 때는 `explicit_override`로 변경해야 하며 report에 override warning이 남는다.

### 7.3 Free-space measured beam

향후 measured source는 다음 형태로 추가한다.

```yaml
source:
  type: measured_profile
  profile_kind: measured
  propagation_model: measured_transfer
  wavelength_m: 1550 nm
  optical_power_w: 10 mW
  profile_file: assets/measurements/source_profile.csv
```

현재 validator는 measured input contract를 검사하지만 `lidarsim beam`은 measured propagation을 실행하지 않는다.

### 7.4 Beam type 선택

현재 구현:

- point Gaussian
- elliptical Gaussian
- elliptical line Gaussian

향후 구현:

- area top-hat
- measured 2D profile
- Fresnel-propagated field
- Powell/cylindrical-lens-generated line profile

Top-hat이나 실제 Powell line beam을 단순 Gaussian q-parameter model로 해석하지 않는다.

Numerical line-beam 예제:

```powershell
lidarsim beam configs/line_beam_project.example.yaml
```

이 예제는 3.0 mm × 0.25 mm의 1/e² waist radius를 가진 elliptical Gaussian이며 상용 line generator를 뜻하지 않는다.

## 8. Optical component 교체

Component는 catalog ID로 참조한다.

```yaml
- id: collimator
  component_ref: custom:ideal_collimator_f20
```

35 mm focal-length reference로 바꾸려면 ID만 교체한다.

```yaml
component_ref: custom:ideal_collimator_f35
```

관련 catalog:

- [20 mm ideal collimator](../catalog/components/custom/ideal_collimator_f20.yaml)
- [35 mm ideal collimator](../catalog/components/custom/ideal_collimator_f35.yaml)

### 8.1 교체 시 placement policy

부품의 크기와 reference plane이 달라질 수 있으므로 교체 방식도 명시한다.

- `preserve_existing_assembly`: 기존 위치를 유지하고 drop-in 결과를 확인
- `reconnect_ports`: 새 component port 기준으로 다시 연결
- `reoptimize_selected_parameters`: 지정한 gap/alignment 변수만 최적화

자동 재정렬이나 최적화를 조용히 수행하면 안 된다.

### 8.2 교체 시 검사할 항목

- wavelength validity
- input/output port compatibility
- focal/working distance
- clear aperture와 clipping
- coating/transmission
- CAD envelope와 collision
- scanner 또는 mount와의 간섭
- placement reference plane 변화

## 9. 새로운 Custom component 추가

`catalog/components/custom/` 아래에 새로운 YAML record를 만든다.

예시:

```yaml
schema_version: 1
id: custom:my_collimator
component_type: collimator
model_level: paraxial_specification

validity:
  wavelength_range_m: [1500 nm, 1600 nm]

optical:
  model: ideal_thin_lens
  design_wavelength_m: 1550 nm
  effective_focal_length_m: 25 mm
  clear_aperture_diameter_m: 12 mm
  power_transmission: 0.98

ports:
  - id: input
    role: input
    interface_type: free_space
    reference_plane: optical_surface
    origin_local_m: [0.0, 0.0, 0.0]
    propagation_axis_local: [0.0, 0.0, 1.0]
    transverse_x_local: [1.0, 0.0, 0.0]

  - id: output
    role: output
    interface_type: free_space
    reference_plane: optical_surface
    origin_local_m: [0.0, 0.0, 0.0]
    propagation_axis_local: [0.0, 0.0, 1.0]
    transverse_x_local: [1.0, 0.0, 0.0]

provenance:
  type: user_specification
  source: my_design_note
```

그 후 scenario의 `component_ref`를 다음처럼 지정한다.

```yaml
component_ref: custom:my_collimator
```

## 10. Thorlabs 등 상용 component 추가

상용 부품은 manufacturer와 part number가 포함된 stable ID를 사용한다.

```yaml
id: thorlabs:PART_NUMBER
manufacturer: Thorlabs
part_number: PART_NUMBER
revision: null
```

가능한 자료를 함께 기록한다.

- data sheet URL/file
- design wavelength/range
- EFL/BFL/working distance
- clear aperture
- coating/transmission
- surface prescription 또는 Zemax file
- CAD/STL/STEP mechanical geometry
- nominal tolerance
- downloaded date와 file hash

Vendor file이 black-box이면 내부 lens prescription으로 변환했다고 가정하지 않는다. Native fallback model과 vendor/external reference model을 구분한다.

## 11. Component placement 변경

### 11.1 Absolute placement

```yaml
placement:
  mode: absolute
  translation_m: [0.10, 0.00, 0.02]
  quaternion_wxyz: [1.0, 0.0, 0.0, 0.0]
```

### 11.2 Port-to-port placement

```yaml
placement:
  mode: port
  connect_from: source.output
  connect_to: collimator.input
  axial_gap_m: 20 mm
```

추가 가능한 값:

```yaml
transverse_offset_m: [0.0, 0.0]
clocking_rad: 0.0
angular_misalignment_rad: [0.0, 0.0]
```

좌표 규칙은 [좌표·배치 규격](specs/COORDINATES_AND_PLACEMENT.md)을 따른다.

배치 결과 확인:

```powershell
lidarsim placement configs/project.yaml
lidarsim placement configs/project.yaml --write-report results/placement.yaml
```

## 12. Scanner 조건 변경

```yaml
scanner:
  element_id: scan_mirror
  type: one_axis_flat_mirror
  rotation_axis_world: [0.0, 1.0, 0.0]
  static_command_angle_rad: 0 deg
  mechanical_amplitude_rad: 5 deg
  frequency_hz: 10 Hz
  waveform: triangle
  samples_per_line: 101
```

변경할 수 있는 주요 조건:

- mirror/facet component reference
- pivot와 rotation axis
- static command angle
- mechanical angle range
- frequency
- triangle/sinusoidal/raster/custom waveform
- frame/line/pixel timing
- calibration table
- jitter/lag/facet error

현재 구현된 `static_command_angle_rad`는 한 순간의 scanner command angle을 뜻한다. 이 값은 mirror normal과 aperture axes를 `rotation_axis_world` 기준으로 회전시켜 reflected ray와 target hit 위치를 바꾼다. Flat mirror에서는 mechanical angle 변화에 대해 reflected optical angle이 약 2배로 변한다. `optical-train`은 이 정적 pose 하나만 계산하며, frequency 기반 ideal sample은 `scanner-path`에서 계산한다. Dynamic lag와 jitter는 두 명령 모두 아직 계산하지 않는다.

Degree 입력이 허용되는 UI가 생기더라도 effective config에는 radian으로 변환된 값을 저장한다.

여러 정적 angle을 비교할 때는 baseline YAML을 반복해서 직접 수정하지 말고 `scanner-sweep`을 사용한다.

```powershell
# 설정된 mechanical_amplitude_rad 범위를 기본 11개 sample로 sweep
lidarsim scanner-sweep configs/project.yaml

# 원하는 각도만 명시적으로 비교
lidarsim scanner-sweep configs/project.yaml --angles-deg -5 0 5 --output results/scanner_sweep.yaml

# 범위와 sample 수 지정
lidarsim scanner-sweep configs/project.yaml --start-deg -3 --stop-deg 3 --count 7
```

기본 출력:

- `scanner_sweep.yaml`: static sweep report
- `scanner_sweep_table.csv`: spreadsheet용 angle별 핵심 수치
- `scanner_sweep_plot.png`: target local hit 좌표와 estimated received power trend

각 sample은 독립적인 Phase 2 analytical reference run이다. 따라서 `scanner-sweep` 결과는 static angle별 비교에는 유용하지만, 시간 순서, waveform phase, scan velocity, acceleration, galvo/모터 lag, jitter 또는 calibration table을 포함한 scan path로 해석하면 안 된다.

한 줄의 이상적인 scanner path를 보고 싶을 때는 `scanner-path`를 사용한다.

```powershell
# baseline scanner 설정의 triangle waveform에서 한 줄 forward path 생성
lidarsim scanner-path configs/project.yaml --samples 11 --output results/scanner_path.yaml
```

`scanner-path`는 `scanner.waveform`, `mechanical_amplitude_rad`, `frequency_hz`, `samples_per_line`을 읽는다. 현재 지원하는 waveform은 다음과 같다.

- `static`: `static_command_angle_rad`를 모든 sample에 적용
- `triangle`: `-mechanical_amplitude_rad`에서 `+mechanical_amplitude_rad`까지 forward half-period line
- `sinusoidal`: sinusoidal half-cycle의 forward line

출력은 다음을 포함한다.

- sample time
- command angle
- target local hit coordinate
- estimated power on target
- estimated received aperture power
- receiver FOV status
- link loss

이 명령은 ideal command path reference다. 아직 motor/galvo dynamics, lag, jitter, acceleration limit, bidirectional return stroke, calibration table과 실제 encoder measurement는 반영하지 않는다. 따라서 validator와 Phase 0.1 review는 `scan_path`를 “생성 불가”가 아닌 `reference_only` fidelity로 표시한다. `raster` 또는 `custom` waveform을 선택하면 현재 runner가 지원하지 않는다는 별도 warning이 발생한다.

## 13. FreeCAD/STL geometry 사용

### 13.1 권장 파일 흐름

```text
assets/source/freecad/my_part.FCStd
    ↓ FreeCAD export
assets/meshes/my_part.stl
assets/meshes/my_part.stl.yaml
```

### 13.2 Sidecar 만들기

[STL metadata template](../assets/meshes/mesh_metadata.example.yaml)을 복사한다.

```yaml
mesh:
  file: my_target.stl
  unit_scale_m: 0.001

role: target

placement:
  parent_frame: world
  translation_m: [10.0, 0.0, 0.0]
  quaternion_wxyz: [1.0, 0.0, 0.0, 0.0]

material:
  default_material_ref: custom:diffuse_gray_020
```

FreeCAD millimeter export 예제는 `unit_scale_m: 0.001`이지만 importer가 unit을 자동 추측해서는 안 된다.

### 13.3 Scanner STL

```yaml
role: scanner_surface

scanner:
  pivot_local_m: [0.0, 0.0, 0.0]
  rotation_axis_local: [0.0, 1.0, 0.0]
```

가능하면 FreeCAD model origin을 scanner pivot에 맞춘다.

### 13.4 STL 제한

STL에는 다음 정보가 없다.

- 신뢰할 수 있는 unit
- material
- lens glass/coating
- optical port
- scanner pivot/axis
- assembly constraint

따라서 STL만으로 lens focusing을 계산하지 않는다. Lens STL은 mechanical visualization 용도이며 별도의 optical catalog/prescription이 필요하다.

초기에는 material이나 움직임이 다른 body를 separate STL로 export한다.

## 14. Target와 Material 변경

Plane target 예:

```yaml
scene:
  targets:
    - id: target_plane
      geometry:
        type: rectangle_plane
        center_m: [10.0, 0.0, 0.0]
        normal: [-1.0, 0.0, 0.0]
        width_m: 4 m
        height_m: 4 m
      material_ref: custom:diffuse_gray_020
```

STL target 예:

```yaml
geometry:
  type: stl_asset
  metadata_file: assets/meshes/my_target.stl.yaml
```

중요: 현재 `stl_asset`은 unit, bounds, topology, normal, hash와 sidecar metadata 검사까지만 지원한다. Optical train에서는 unsupported target miss로 처리되며 ray-triangle hit, footprint, occlusion과 return power는 아직 계산하지 않는다. CPU STL closest-hit는 `Phase 4.1-M1`에서 구현할 예정이며 상세 Gate는 [`specs/IMPLEMENTATION_AUDIT_2026-07-15.md`](specs/IMPLEMENTATION_AUDIT_2026-07-15.md)를 따른다.

Material는 catalog ID로 교체한다.

```yaml
material_ref: custom:diffuse_gray_020
```

향후 material record에서 변경할 값:

- wavelength-dependent reflectivity
- diffuse/specular/retro ratio
- BRDF/BSDF model
- roughness RMS/correlation length
- refractive index와 absorption

## 15. Receiver 조건 변경

```yaml
receiver:
  architecture: virtual_monostatic
  model_level: virtual_aperture
  position_m: [0.0, 0.0, 0.0]
  direction: [1.0, 0.0, 0.0]
  aperture_diameter_m: 25 mm
  full_fov_rad: 25 deg
  optical_efficiency: 0.80
  detector_model: none
```

`virtual_monostatic/virtual_aperture`는 실제 동일 scanner·collimator 역경로, single-mode fiber mode coupling, duplexer와 detector를 생략한 분석용 aperture다. 기존 field `estimated_received_power_w`와 화면의 `Virtual aperture estimate`는 이 가상 plane의 값이며 fiber에 결합되는 power가 아니다.

현재 `lidarsim optical-train`은 rectangle-plane target hit가 있을 때 `virtual_monostatic/virtual_aperture` receiver에 대한 첫 Lambertian analytical return을 계산한다. 결과는 virtual aperture가 차지하는 solid angle에 기반한 optical power와 해당 plane까지의 link loss이며, 실제 target→same scanner→same collimator→fiber→duplexer→detector 경로를 통과한 calibrated hardware prediction은 아니다.

이 프로젝트에서 목표로 하는 실제 수신 구조는 다음과 같다.

```text
송신: fiber/source → shared collimator → shared scanner mirror → target
수신: target → same scanner mirror → same collimator → same fiber receive mode
      → circulator/coupler → detector 또는 coherent mixer
```

계획된 configuration은 다음 형태다. **현재 schema에는 아직 이 field를 넣으면 안 된다.** Phase 2.4에서 loader/schema와 함께 구현한 뒤 사용할 수 있다.

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

single-mode fiber coupling은 aperture 안으로 들어왔는지만 검사하지 않고 return field와 fiber mode의 overlap, MFD, lateral/angular offset과 focus mismatch를 계산해야 한다. 자세한 구현 contract, output plane과 검증 항목은 [`specs/RECIPROCAL_FIBER_RETURN.md`](specs/RECIPROCAL_FIBER_RETURN.md)를 따른다.

향후 변경 가능한 항목:

- 동일 송수신 fiber 또는 별도 receive fiber
- circulator/coupler/PBS 등의 duplexer architecture
- shared collimator와 scanner element reference
- fiber MFD/NA, lateral/angular/focus offset
- return mirror/collimator aperture와 optical efficiency
- optional bistatic receiver position/orientation, aperture와 FOV
- detector responsivity/noise/bandwidth/saturation
- coherent LO path와 mixer coupling

## 16. Simulation 조건 변경

```yaml
simulation:
  mode: radiometric
  accuracy_mode: relative_design
  backend: numpy
  real_dtype: float64
  random_seed: 0
```

향후 지원할 mode:

- radiometric
- coherent field
- FMCW waveform/range
- tolerance Monte Carlo

CPU `float64/complex128` 결과가 검증 기준이다. GPU/낮은 precision은 별도 비교 test를 통과한 뒤 사용한다.

### 16.1 Accuracy mode

- `relative_design`: 부품과 조건의 상대 비교. 초기 권장값.
- `absolute_radiometric`: 측정·보정 데이터가 있는 절대 power 예측.
- `coherent_fmcw`: phase, speckle와 FMCW waveform/range 예측.

각 결과에는 accuracy mode, confidence, calibration status와 validity warning을 표시한다. 자세한 규칙은 [정확도·보정 계약](specs/ACCURACY_AND_CALIBRATION.md)을 따른다.

## 17. Output 선택

```yaml
outputs:
  - resolved_config
  - run_manifest
  - accuracy_report
  - placement_report
  - beam_envelope
  - scan_path
  - target_footprint
  - received_aperture_power
  - link_budget
  - energy_ledger
  - convergence_report
  - layout_3d
```

필요하지 않은 output은 목록에서 제거할 수 있다. 다만 모든 run은 재현성을 위해 effective config, manifest와 warning을 항상 저장한다.

현재 `scan_path`는 `lidarsim scanner-path`로 생성되지만 ideal forward-line command reference다. Validator의 `reference_only` warning은 명령 실패가 아니라 실제 scanner dynamics·calibration이 포함되지 않았음을 뜻한다. 나머지 현재 지원 output은 각 전용 명령(`report`, `beam`, `optical-train`, `workspace`)에서 생성된다.

현재 `received_aperture_power`와 `link_budget`은 `virtual_monostatic/virtual_aperture` plane까지의 analytical output이다. 향후 reciprocal return train이 구현되면 return mirror, return collimator, fiber coupling과 detector input plane을 분리한 output을 추가한다. 기존 이름을 fiber-coupled power로 해석하지 않는다.

## 18. 여러 조건 비교

[실험 예제](../configs/experiments/component_swap.example.yaml)는 wavelength와 collimator를 동시에 비교한다.

```yaml
sweeps:
  - parameter: source.wavelength_m
    values: [1310 nm, 1550 nm]

  - parameter: optical_assembly.elements[id=collimator].component_ref
    values:
      - custom:ideal_collimator_f20
      - custom:ideal_collimator_f35
```

두 parameter에 값이 각각 두 개이므로 Cartesian experiment는 총 4 runs다.

### 18.1 비교할 수 있는 metric

- output beam radius/divergence
- waist position
- clipping/transmission loss
- footprint size/orientation
- target irradiance
- scan FOV/coverage
- received aperture power
- baseline 대비 absolute/relative delta
- warning와 runtime

### 18.2 공정한 비교

가능하면 다음 조건을 동일하게 유지한다.

- target와 receiver
- placement policy
- scan samples/timing
- numerical precision
- target sampling
- random seed/scatterer map

## 19. 직접 바꾸는 값과 계산되는 값

직접 설정하는 canonical 값:

- wavelength
- source power/waist/MFD/M²
- component reference
- placement
- scanner mechanical angle/frequency
- target geometry/material
- receiver aperture/FOV

자동 계산되는 derived 값:

- optical frequency
- Gaussian divergence/Rayleigh length
- lens 이후 q-parameter
- reflected beam direction
- footprint 크기/방향
- receiver aperture area/solid angle
- received power

같은 물리량을 input과 derived 값으로 동시에 강제하지 않는다. Measured derived value는 validation target 또는 calibrated override로 명시한다.

## 20. CLI

현재 구현된 명령:

```powershell
# Configuration과 catalog reference 검사
lidarsim validate configs/project.yaml

# 검증 및 SI-resolved snapshot 저장
lidarsim validate configs/project.yaml --write-resolved results/resolved_project.yaml

# Active scenario의 component·port world placement 확인
lidarsim placement configs/project.yaml

# Placement report 저장
lidarsim placement configs/project.yaml --write-report results/placement.yaml

# STL sidecar와 실제 geometry 검사
lidarsim inspect-mesh assets/meshes/my_target.stl.yaml

# Measurement metadata와 referenced data 검사
lidarsim inspect-measurement assets/measurements/my_data.measurement.yaml

# Phase 0 manifest·accuracy·energy·convergence report 저장
lidarsim report configs/project.yaml --output results/phase0_report.yaml

# Headless 2D/3D placement PNG 생성
lidarsim view configs/project.yaml --output results/placement.png

# 그림·지원 output·경고·수치 검사를 한 HTML로 생성
lidarsim review configs/project.yaml --output results/phase0_1_review.html

# Phase 1 Gaussian 자유공간 전파·power audit·PNG 생성
lidarsim beam configs/project.yaml

# 전파 거리와 profile plane을 단위 포함 값으로 지정
lidarsim beam configs/project.yaml --z-max-m "100 mm" --profile-distance-m "50 mm"

# Numerical elliptical-Gaussian line-beam 예제
lidarsim beam configs/line_beam_project.example.yaml

# Optical assembly workspace용 3D bench PNG와 scene YAML 생성
lidarsim workspace configs/project.yaml --output results/ui_workspace.png --write-scene results/ui_workspace_scene.yaml

# 추가 dependency 없이 열 수 있는 read-only workspace dashboard 생성
lidarsim dashboard configs/project.yaml --output results/ui_dashboard.html

# Scanner path section까지 포함한 dashboard 생성
lidarsim dashboard configs/project.yaml --output results/ui_dashboard_with_path.html --include-scanner-path --scanner-path-samples 11

# Baseline을 덮어쓰지 않고 scanner mirror 위치 variant 생성
lidarsim placement-variant configs/project.yaml --element scan_mirror --scenario-id mirror_shift --translation-m 0.1 0 0

# Port-to-port collimator gap variant 생성
lidarsim placement-variant configs/project.yaml --element collimator --scenario-id collimator_gap_25mm --axial-gap-m "25 mm"

# Browser parameter·numeric placement workspace 실행
lidarsim ui configs/project.yaml
```

`review` 그림의 scan limit, receiver FOV와 return path는 설정값 기반 기하학 가이드다. 실제 Phase 2.2/2.3 footprint와 received power 값은 `lidarsim optical-train` report에서 확인한다.

`beam` 결과의 radius는 1/e² irradiance radius다. 기본 실행은 `results/phase1/<timestamp>_<scenario>_<hash>/` 아래에 `beam_report.yaml`, `beam_summary.yaml`, `beam.png`를 생성하므로 이전 결과를 덮어쓰지 않는다. YAML report의 첫 `summary`와 `accuracy`에서 전체 상태·신뢰도·보정 여부를 먼저 확인한다. `profile_audit`은 Gaussian tail truncation, base/refined grid quadrature와 grid convergence를 분리한다. `analytical_checks`는 내부 일관성 검사이며 실제 측정 validation이 아니다. 이 명령은 downstream optical component를 적용하지 않는다.

```powershell
# Phase 2 source→collimator→static mirror reflection optical train 계산
lidarsim optical-train configs/project.yaml

# 짧은 alias
lidarsim train configs/project.yaml

# 여러 static scanner command angle에서 target hit와 received power 비교
lidarsim scanner-sweep configs/project.yaml --angles-deg -5 0 5 --output results/scanner_sweep.yaml

# Config의 scanner waveform으로 한 줄 ideal forward scan path 생성
lidarsim scanner-path configs/project.yaml --samples 11 --output results/scanner_path.yaml
```

`optical-train` 결과의 `optical_train.states`에는 source output, collimator input/output, scanner mirror origin과 reflected output의 `BeamState`가 저장된다. `power_ledger`는 free-space, collimator aperture clipping, component transmission, mirror rectangular aperture와 mirror reflectivity를 순서대로 기록한다. `component_reports[].aperture_clip`에서 clear aperture 대비 clipping fraction을 확인하고, `summary.total_transmission`과 `summary.total_loss_w`로 optical train 손실을 빠르게 본다. `target_footprints[]`에는 rectangle-plane 후보 hit, incidence angle, projected Gaussian footprint, 후보 power, 실제 기여 power와 `visibility_status`가 저장된다. 여러 target이 같은 center ray에 걸리면 `visible_nearest` 하나만 실제 power를 가지며 더 먼 target은 `occluded_by_nearer_target`으로 표시된다. `scene_energy_ledger`는 이 후보/기여 구분과 송신 power 초과 여부를 검사한다. `receiver_return`에는 visible target의 Lambertian reflectivity, receiver aperture/FOV 판정, estimated received aperture power와 link loss가 저장된다. 현재 aperture를 지난 뒤의 diffraction/truncated profile shape, mirror edge scattering, polarization, footprint 면적별 부분 occlusion, STL visibility, non-Lambertian BRDF, detector noise와 coherent field sum은 계산하지 않는다.

`scanner-sweep` 결과는 단일 `optical-train` 결과를 angle별로 반복 실행한 요약이다. YAML의 `samples[]`에는 command angle, reflected/final direction, target hit 좌표, target local coordinate, target power, received power, receiver FOV status와 link loss가 들어간다. CSV는 같은 값을 spreadsheet에서 비교하기 위한 경량 table이다. PNG는 angle에 따른 target local hit 위치와 received power 추세를 보여준다. 이 명령은 baseline config를 수정하지 않으며, sample별 `scenario_config_hash`로 angle이 반영된 reference snapshot을 구분한다.

`scanner-path` 결과는 `scanner-sweep`의 angle별 static reference를 시간 순서에 맞게 배열한 한 줄 scan report다. YAML의 `samples[]`에는 `time_s`, `line_position`, command angle과 각 sample의 target/receiver 결과가 들어간다. CSV는 같은 값을 table로 저장하고, PNG는 command angle, target hit 좌표, received power를 시간축에서 보여준다. 이 명령은 “ideal forward-line command path”만 구현하므로 실제 구동기의 lag나 calibration error를 포함하는 full scanner dynamics로 해석하지 않는다.

`workspace`는 optical assembly workspace의 초기 viewer 명령이다. 현재 configuration과 Phase 2.3 report를 읽어 `schema_version: 1`의 strict `ViewportScene`을 만들고 저장 전에 `viewport_scene.schema.json`으로 검증한 뒤, 다음 요소를 3D PNG로 그린다.

- source, collimator, scanner mirror, target, receiver
- component local frame
- input/output port axis
- mirror normal
- reflected ray
- target plane edge
- receiver FOV guide
- beam path와 target hit ray
- target footprint overlay

`--write-scene`으로 저장되는 YAML은 Streamlit, Plotly, Three.js 또는 React frontend가 소비할 data contract다. Streamlit UI에서는 interactive Plotly 3D viewer, component 선택, guide toggle, numeric placement와 첫 `MirrorTargetMate` preview를 지원하지만, `workspace` CLI 명령 자체는 read-only다. Drag/rotate gizmo, undo/redo와 일반 constraint solver는 아직 구현하지 않았다. UI 변경값은 반드시 variant config로 저장되어 CLI에서 재현된다.

`dashboard`는 현재 Phase 2.3 simulation을 한 HTML에서 검토하기 위한 read-only dashboard 명령이다. 기본 실행은 다음 파일을 함께 만든다.

- `ui_dashboard.html`
- `ui_dashboard_phase2_report.yaml`
- `ui_dashboard_viewport_scene.yaml`
- `ui_dashboard_workspace.png`
- `ui_dashboard_optical_train.png`

Dashboard HTML에는 workspace 그림, optical train radius/power 그림, summary, generated file path, component report, power ledger, target footprint, receiver return, warning, assumptions와 raw summary가 포함된다. 외부 server 없이 browser에서 열 수 있도록 PNG는 HTML 안에 base64로 포함한다. 이 파일은 계속 read-only 결과 viewer이며, parameter/placement 편집은 `lidarsim ui`에서 수행한다.

`--include-scanner-path`를 추가하면 같은 dashboard에 ideal forward-line scanner path section을 포함한다. 이때 다음 파일도 함께 저장된다.

- `<dashboard_stem>_scanner_path.yaml`
- `<dashboard_stem>_scanner_path.csv`
- `<dashboard_stem>_scanner_path.png`

이 section은 command angle, target local coordinate, received power trend를 시간축으로 보여준다. 단, motor/galvo dynamics, lag, jitter, bidirectional return stroke와 calibration table이 빠진 ideal reference임을 dashboard 안에서도 명시한다.

`placement-variant`는 numeric placement editor의 첫 CLI helper다. 원본 baseline scenario를 직접 수정하지 않고, active scenario를 복사한 뒤 지정한 element placement만 바꾼 variant scenario와 variant project를 저장한다.

Absolute placement element에서 바꿀 수 있는 값:

- `--translation-m X Y Z`
- `--quaternion-wxyz W X Y Z`

Port placement element에서 바꿀 수 있는 값:

- `--axial-gap-m "25 mm"`
- `--transverse-offset-m "1 mm" "0 mm"`
- `--clocking-rad "2 deg"`
- `--angular-misalignment-rad "0.5 deg" "0 deg"`

주의할 점:

- Absolute placement field와 port placement field를 섞으면 error가 발생한다.
- 생성된 variant project는 `lidarsim validate`, `lidarsim workspace`, `lidarsim dashboard`로 다시 실행할 수 있어야 한다.
- Loader는 project file의 상위 directory에서 repository `schemas/` root를 탐색하므로 `configs/ui_runs/`의 nested variant도 지원한다.
- UI가 생기더라도 baseline을 조용히 덮어쓰지 않고 이 variant 생성 흐름을 사용해야 한다.

### 20.1 Interactive 3D optical bench UI

UI dependency는 core runtime과 분리되어 있다.

```powershell
& .\.venv\Scripts\python.exe -m pip install -e ".[ui]"
& .\.venv\Scripts\python.exe -m lidarsim.cli ui configs/project.yaml

# Browser를 자동으로 열지 않고 port 지정
& .\.venv\Scripts\python.exe -m lidarsim.cli ui configs/project.yaml --headless --port 8765
```

이 방식은 PowerShell에서 `Activate.ps1` 실행이 금지되거나 `lidarsim.exe` launcher가 application-control policy로 차단된 경우에도 사용할 수 있다.

CLI는 Streamlit usage-statistics 수집을 끈 상태로 실행하므로 최초 실행 email 입력 prompt를 띄우지 않는다. 이미 해당 prompt에서 대기 중인 이전 process가 있다면 그 terminal에서 `Ctrl+C`로 종료하고 위 명령을 다시 실행한다.

화면의 왼쪽은 3D optical bench, 오른쪽은 선택한 객체의 inspector다. 3D 영역에서는 다음을 할 수 있다.

- `광학 헤드 확대`: source, collimator와 scanner mirror를 근거리 동일 축척으로 표시하는 기본 보기
- `전체 광로`: scanner에서 target까지의 전체 beam path와 footprint 확인
- `선택 부품 확대`: 선택한 부품의 geometry와 local guide 확인
- 마우스 orbit, zoom과 pan
- component marker 선택 또는 sidebar에서 객체 선택
- optical/port axis, local frame, mirror normal, target plane, receiver FOV guide toggle
- beam path, reflected ray, target hit와 footprint overlay 확인
- 선택 객체의 origin, type, component reference hover 확인

오른쪽 inspector에서 바꿀 수 있는 항목:

- wavelength와 source power
- scanner static command angle, waveform, amplitude, frequency와 samples per line
- target center, normal, width와 height
- receiver position, direction, aperture, full FOV와 optical efficiency
- 선택 component와 같은 type의 catalog reference
- absolute placement의 position·quaternion
- port placement의 axial gap·transverse offset·clocking·angular misalignment

Scanner의 `Static command angle (deg)`가 실제 미러 기계각이다. 값을 바꾸면 pending warning이 나타나며 `변경값 반영 · 시뮬레이션`을 눌러야 reflected ray와 target hit가 다시 계산된다. `고급 설정: 기계 회전축 단위벡터`의 X/Y/Z는 각도가 아니라 회전축 방향이다. 기본 Y축은 `[0, 1, 0]`이며 `[10, 10, 0]`처럼 크기가 1이 아닌 값은 저장할 때 방향을 유지한 채 단위벡터로 정규화한다.

값을 바꾸면 inspector 상단 상태가 `편집값이 아직 3D와 config에 반영되지 않았습니다`로 바뀐다. 이 상태에서는 3D와 power metric이 마지막 실행 결과를 계속 표시한다. 상단의 `변경값 반영 · 시뮬레이션`을 눌러야 현재 편집값을 variant YAML로 저장·검증하고 3D와 metric을 다시 계산한다. 실행 중 active project/scenario YAML을 외부 editor에서 수정한 경우에도 config hash 변화가 감지되면 stale session 결과를 버리고 자동 재계산한다.

현재 pending edit는 선택한 객체 하나만 추적한다. Source 값을 바꾼 뒤 적용하지 않고 mirror 등 다른 객체로 이동하면 이전 입력이 저장 대상에서 빠질 수 있으므로, `UI-S` project-wide draft가 구현되기 전에는 객체를 바꾸기 전에 변경값을 적용하거나 원래 값으로 되돌린다.

같은 작업을 반복 수정할 수 있도록 `같은 ID의 기존 UI variant 덮어쓰기`는 기본으로 켜져 있다. 이 옵션은 `configs/ui_runs/` 아래의 해당 작업 사본만 갱신하며 baseline config는 덮어쓰지 않는다. 이전 variant도 별도로 보존하려면 `Scenario ID`를 새 이름으로 바꾼 뒤 실행한다.

`scan_mirror`를 선택하면 `Mirror → Target 정렬` section이 나타난다. 이 preview는 현재 Phase 2 incident center ray와 target rectangle center를 사용해 ideal reflection law를 만족하는 surface normal을 구하고, 현재 mirror pose 대비 residual과 추천 rotation을 표시한다. `추천 pose를 편집값에 적용`은 browser의 quaternion과 `scanner.rotation_axis_world` 편집값만 바꾸며 파일을 쓰지 않는다. 두 값을 함께 바꾸는 이유는 scanner mount pose를 회전할 때 catalog의 local mechanical axis도 world frame에서 같이 회전해야 하기 때문이다. 그 뒤 `변경값 반영 · 시뮬레이션`을 눌러야 값이 variant YAML에 저장되고 새 beam path가 계산된다. 현재 첫 구현은 absolute placement mirror만 적용할 수 있다.

`변경값 반영 · 시뮬레이션`을 누르면 다음 순서로 실행된다.

```text
browser 입력
→ configs/ui_runs/<scenario>.yaml
→ configs/ui_runs/<scenario>_project.yaml
→ schema/unit/physical/placement validation
→ Phase 2 optical train과 optional ideal scanner path
→ results/ui_runs/<scenario>_<hash>/
```

Validation이 실패하면 잘못된 새 variant file은 rollback한다. 다만 현재는 simulation/render 실패까지 포함한 완전한 atomic transaction이 아니므로, 중요한 기존 variant를 보존하려면 새 Scenario ID를 사용한다. Full rollback은 `UI-S` 범위다. 성공한 project는 다음처럼 CLI에서 재현할 수 있다.

```powershell
lidarsim validate configs/ui_runs/my_variant_project.yaml
lidarsim optical-train configs/ui_runs/my_variant_project.yaml
lidarsim dashboard configs/ui_runs/my_variant_project.yaml --include-scanner-path
```

현재 UI는 interactive viewer와 numeric editor를 결합한 단계다. Plotly point selection은 component marker에 적용되며, 작은 부품을 고르기 어려우면 sidebar `선택 객체`를 사용한다. Drag/rotate gizmo, undo/redo, port/coaxial snap과 persistent constraint list는 후속 UI Phase C~E 범위다. 독립 receiver `LookAtMate`는 실제 shared scanner/collimator/fiber return path와 맞지 않아 우선순위를 내렸고, reciprocal return ray와 fiber port의 coaxial residual을 먼저 구현한다.

다음 명령은 이후 Phase에서 구현할 계획이다.

```powershell

# 한 시나리오 실행
lidarsim run configs/my_scenario.yaml

# Parameter/component experiment 실행
lidarsim compare configs/experiments/my_experiment.yaml

```

CLI와 GUI는 동일한 config/schema/validator를 사용해야 한다.

## 21. 실제 장비 사양으로 교체하는 절차

1. Baseline scenario를 복사한다.
2. 실제 source wavelength/power/MFD 또는 measured profile을 입력한다.
3. 실제 optical component catalog record를 추가한다.
4. FreeCAD source와 exported STL/sidecar를 추가한다.
5. 실제 placement/pivot/axis를 입력한다.
6. Target/material/receiver 사양을 교체한다.
7. Unknown 값은 추측하지 않고 `null` 또는 assumption으로 기록한다.
8. Nominal scenario를 검증한다.
9. Baseline과 실제 scenario를 비교한다.
10. Bench measurement가 생기면 measured/calibrated scenario를 별도로 만든다.

측정 데이터 형식은 [측정 데이터 계약](specs/MEASUREMENT_DATA.md), 수치 안정성은 [에너지·수렴성 계약](specs/ENERGY_AND_CONVERGENCE.md), 전체 사용 흐름은 [UX 계약](specs/UX_WORKFLOW.md)을 따른다.

## 22. 자주 발생할 오류

### STL 크기가 1000배 다름

원인: STL unit이 없거나 FreeCAD mm export를 m로 해석함.

조치: Sidecar의 `unit_scale_m`과 imported bounding box를 확인한다.

### STL normal이 geometry와 다름

원인: Export된 facet normal과 vertex winding으로 다시 계산한 normal이 일치하지 않음.

조치: Phase 0.1의 `normal_policy=repair`는 mismatch를 기록하지만 파일을 자동 수정하지 않는다. FreeCAD 또는 mesh 도구에서 normal을 재계산한 뒤 다시 export하고 `lidarsim inspect-mesh`로 확인한다.

### Component를 바꿨는데 초점이 맞지 않음

원인: `preserve_existing_assembly`가 기존 위치를 유지함.

조치: 새 working distance를 확인하고 `reconnect_ports` 또는 명시적 gap 변경을 사용한다.

### Wavelength만 바꿨더니 warning이 발생함

원인: Lens/coating/material/detector validity range를 벗어남.

조치: 해당 wavelength를 지원하는 catalog data나 component로 함께 교체한다.

### Catalog nominal과 source 값이 다르다는 오류

원인: `catalog_parameter_policy: match_nominal` 상태에서 scenario의 power, wavelength, MFD 또는 M²를 바꿈.

조치: 입력 실수라면 catalog 값으로 되돌린다. 의도한 운전 조건 변경이면 `catalog_parameter_policy: explicit_override`로 바꾸고 report의 override warning을 보존한다.

### Paraxial small-angle warning

원인: Source divergence에서 sin/tan small-angle proxy가 software tolerance를 넘음.

조치: 이 값은 직접적인 실제 오차가 아니라 model validity 경고다. 정확한 장비 예측이 필요하면 measured profile, non-paraxial propagation 또는 bench comparison을 사용한다.

### STL lens가 빛을 굴절시키지 않음

원인: STL은 mechanical geometry일 뿐 optical prescription이 아님.

조치: Ideal/catalog/sequential/measured optical model을 별도로 연결한다.

### 비교 결과가 매번 달라짐

원인: Random seed, scatterer map 또는 sampling이 variant마다 달라짐.

조치: Experiment에서 fixed seed와 shared sampling policy를 사용한다.

## 23. Git과 여러 PC 사용

Git에 보관할 항목:

- configs
- catalog YAML
- documentation
- 허용된 STL/FreeCAD source assets
- small validation data

Git에 넣지 않을 항목:

- generated `outputs/`, `results/`, `artifacts/`
- virtual environment
- credentials
- 재배포가 금지된 vendor files
- 큰 temporary mesh/cache

작업 PC를 바꾸기 전에는 config/catalog/asset 변경을 함께 commit하고 `HANDOFF.md`에 현재 scenario와 다음 작업을 기록한다.
