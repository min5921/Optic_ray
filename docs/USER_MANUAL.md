# 사용자 설정 및 부품 교체 매뉴얼

- 문서 상태: Draft v0.1
- 대상 프로젝트: Custom Beam, Scanner, and Optical Return Simulator
- 기준 설계: `PROJECT_VISION.md` Draft v0.2
- 작성일: 2026-06-28

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

Phase 0가 완료되었다. `lidarsim validate`는 project/scenario/experiment/catalog YAML을 JSON Schema로 검사하고, 명시 단위를 SI/radian 값으로 변환하며, component/material/port/scanner 참조와 placement dependency를 의미적으로 검증한다. 검증된 구성은 변경 불가능한 snapshot과 재현 가능한 SHA-256 hash로 만들어진다. `lidarsim placement`는 active scenario의 absolute·port-to-port placement를 world transform으로 계산한다. `inspect-mesh`와 `inspect-measurement`는 실제 STL·measurement sidecar 및 referenced file을 검사한다. `report`는 confidence·energy·convergence 상태를 저장하고 `view`는 2D/3D placement PNG를 만든다.

`lidarsim run`, `compare`와 실제 beam·radiometry 계산은 Phase 1 이후 구현한다. 현재 단계에서는 설정을 수정한 뒤 반드시 `lidarsim validate configs/project.yaml`을 실행한다.

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
5. Planned validator로 units, references, wavelength와 placement를 검사한다.
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
  wavelength_m: 1550 nm
```

예:

```yaml
# 1310 nm
wavelength_m: 1310 nm

# 1064 nm
wavelength_m: 1064 nm

# 905 nm
wavelength_m: 905 nm
```

Wavelength를 변경하면 validator가 다음 항목을 함께 확인해야 한다.

- source와 fiber MFD validity
- collimator design wavelength/range
- lens glass/coating data
- mirror/filter transmission 또는 reflectivity
- target material wavelength data
- receiver/detector spectral response

Wavelength만 변경하고 component data를 그대로 사용할 수 없는 경우 warning 또는 validation error가 발생해야 한다.

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
  mode_field_diameter_m: 10 um
  m2_x: 1.0
  m2_y: 1.0
```

실제 fiber를 사용할 때는 제조사와 wavelength에 따른 MFD를 입력한다. NA와 MFD가 모두 있더라도 어느 값을 canonical beam input으로 사용할지 model에 명시해야 한다.

### 7.3 Free-space measured beam

향후 measured source는 다음 형태로 추가한다.

```yaml
source:
  type: measured_profile
  wavelength_m: 1550 nm
  optical_power_w: 10 mW
  profile_file: assets/measurements/source_profile.csv
  reference_plane_m: [0.0, 0.0, 0.0]
```

### 7.4 Beam type 선택

초기 구현:

- point Gaussian
- elliptical line Gaussian

향후 구현:

- area top-hat
- measured 2D profile
- Fresnel-propagated field
- Powell/cylindrical-lens-generated line profile

Top-hat이나 실제 Powell line beam을 단순 Gaussian q-parameter model로 해석하지 않는다.

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

optical:
  model: ideal_thin_lens
  design_wavelength_m: 1550 nm
  effective_focal_length_m: 25 mm
  clear_aperture_diameter_m: 12 mm
  power_transmission: 0.98

ports:
  - id: input
    role: input
    origin_local_m: [0.0, 0.0, 0.0]
    propagation_axis_local: [0.0, 0.0, 1.0]
    transverse_x_local: [1.0, 0.0, 0.0]

  - id: output
    role: output
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
  mechanical_amplitude_rad: 5 deg
  frequency_hz: 10 Hz
  waveform: triangle
  samples_per_line: 101
```

변경할 수 있는 주요 조건:

- mirror/facet component reference
- pivot와 rotation axis
- mechanical angle range
- frequency
- triangle/sinusoidal/raster/custom waveform
- frame/line/pixel timing
- calibration table
- jitter/lag/facet error

Degree 입력이 허용되는 UI가 생기더라도 effective config에는 radian으로 변환된 값을 저장한다.

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
  position_m: [0.0, 0.0, 0.0]
  direction: [1.0, 0.0, 0.0]
  aperture_diameter_m: 25 mm
  full_fov_rad: 25 deg
  optical_efficiency: 0.80
  detector_model: none
```

초기 결과는 receiver aperture에 도달한 optical power다.

향후 변경 가능한 항목:

- monostatic/bistatic architecture
- receiver position/orientation
- aperture size/shape
- FOV
- receive lens train
- optical efficiency
- detector responsivity/noise/bandwidth/saturation
- fiber/LO coupling

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
```

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

### Component를 바꿨는데 초점이 맞지 않음

원인: `preserve_existing_assembly`가 기존 위치를 유지함.

조치: 새 working distance를 확인하고 `reconnect_ports` 또는 명시적 gap 변경을 사용한다.

### Wavelength만 바꿨더니 warning이 발생함

원인: Lens/coating/material/detector validity range를 벗어남.

조치: 해당 wavelength를 지원하는 catalog data나 component로 함께 교체한다.

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
