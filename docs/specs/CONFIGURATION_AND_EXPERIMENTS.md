# Configuration·부품 교체·Experiment contract

- 상태: 초기 구현 contract
- 작성일: 2026-06-28

## 1. 목표

Simulator에서 다음 질문에 쉽게 답할 수 있어야 한다.

- Wavelength를 바꾸면 무엇이 달라지는가?
- Collimator, lens, mirror, scanner, target material 또는 receiver를 바꾸면 무엇이 달라지는가?
- 어떤 component나 parameter가 beam size, clipping, scan coverage, return power 또는 SNR을 지배하는가?
- Nominal, tolerance, measured configuration은 어떻게 다른가?

실제 장비의 물리값을 설명 없는 상수로 simulation code 안에 숨기지 않는다.

## 2. Configuration layer

실제로 실행되는 simulation configuration은 다음과 같은 명시적 layer로 구성한다.

```text
project path와 active baseline
    ↓
schema default
    ↓
component catalog record
    ↓
system layout config
    ↓
scenario config
    ↓
experiment override
    ↓
validated immutable effective config
```

각 run은 완전히 resolve된 effective config와 content hash를 저장한다.

사용자 입력 물리량은 `1550 nm`, `10 mW`, `20 mm`, `5 deg`, `10 Hz`처럼 작성할 수 있다. 단위 없는 숫자는 이전 형식과의 호환성을 위해 field suffix의 canonical unit을 사용한다. Resolved config는 SI/radian 값으로 저장한다.

## 3. Parameter 분류

### Source

- Wavelength·spectrum
- Optical power
- MFD·waist·M²
- Spatial profile
- Polarization·coherence

### Optical component

- `component_ref`
- Model level
- Focal length·prescription
- Clear aperture
- Coating·transmission
- Placement와 tolerance

### Scanner

- Component·geometry reference
- Pivot과 axis
- Waveform
- Angle·frequency·timing
- Calibration과 error

### Scene·material

- Mesh reference
- Placement
- Material reference
- BRDF·BSDF·roughness parameter

### Receiver·detector

- Component·assembly reference
- Aperture·FOV
- Optical efficiency
- Detector responsivity·noise·saturation

### Numerical model

- Accuracy mode와 confidence requirement
- Model fidelity
- Sampling density
- Tolerance
- Random seed
- Backend와 dtype

## 4. Canonical value와 derived value

하나의 물리량은 하나의 canonical input source를 갖는다. Derived value를 별도로 편집하면 model이 과도하게 구속될 수 있으므로 계산해서 보고한다.

예시:

- `wavelength_m`을 입력하고 optical frequency를 계산한다.
- Source waist와 M²를 입력하고 Gaussian divergence를 계산한다.
- Scanner mechanical angle을 입력하고 reflected beam direction을 계산한다.
- Aperture diameter를 입력하고 aperture area를 계산한다.
- Radiometric quantity를 입력하고 received power를 계산한다.

사용자가 canonical value와 measured derived value를 함께 제공할 경우, 후자가 validation target인지 calibrated override인지 config에 선언해야 한다.

## 5. 부품 교체

Assembly는 product data를 scenario마다 복사하지 않고 안정적인 catalog ID를 참조한다.

```yaml
- id: collimator
  component_ref: thorlabs:TC12FC-1550
  placement_ref: placements.collimator
```

새 component의 port나 placement constraint가 호환되지 않는 경우를 제외하면 `component_ref`만 바꿔 부품을 교체한다. Compatibility validation은 다음을 보고해야 한다.

- Port type 불일치
- 유효 범위를 벗어난 wavelength
- Aperture·profile 불일치
- Mechanical envelope·collision 변화
- 누락된 model data
- 변경된 reference plane 또는 working distance

각 component-swap experiment는 다음 placement policy 중 하나를 선언한다.

- `preserve_existing_assembly`: 같은 mount·port gap을 유지하고 직접 교체 결과를 관찰한다.
- `reconnect_ports`: 새 component datum을 사용해 port-to-port placement를 다시 계산한다.
- `reoptimize_selected_parameters`: 명시적으로 선택한 placement variable만 조정한다.

초기 comparison은 `preserve_existing_assembly`를 사용한다. Automatic reoptimization을 사용자에게 알리지 않고 수행하지 않는다.

## 6. Override와 sweep 형식

Experiment는 baseline config 내부의 명시적인 path를 사용한다.

```yaml
sweeps:
  - parameter: source.wavelength_m
    values: [1310 nm, 1550 nm]

  - parameter: optical_assembly.elements[id=collimator].component_ref
    values:
      - custom:ideal_collimator_f20
      - custom:ideal_collimator_f35
```

지원할 experiment 형식:

- One-factor-at-a-time
- Cartesian parameter grid
- Pair로 지정한 named variant
- Tolerance Monte Carlo
- Calibration fit

Experiment runner는 실행 전에 run 수를 계산해야 하며 큰 Cartesian grid는 batch 실행이나 사용자 확인을 요구해야 한다.

## 7. 공정한 비교 규칙

적용 가능한 경우 variant 비교에 다음 조건을 동일하게 사용한다.

- Geometry와 coordinate frame
- Scan time·pixel
- Target sampling
- Receiver model
- Numerical precision
- Random seed·scatterer map
- Output metric

부품 교체로 reference plane, port location, aperture 또는 valid wavelength가 바뀐다면 comparison report에서 실제 물리 변화와 placement incompatibility를 구분해야 한다.

## 8. Comparison metric

초기 metric:

- Output beam radius·divergence
- Waist position
- Clipping·transmission loss
- Scan FOV와 footprint size
- Target peak·mean irradiance
- W·dBm 단위의 received aperture power
- Baseline 대비 relative·absolute change
- Material·path contribution
- Runtime과 warning 수

향후 metric:

- Detector photocurrent·SNR
- FMCW range bias·resolution
- Speckle statistics
- Tolerance distribution

## 9. Result 구성

```text
results/<experiment_id>/
├─ experiment.yaml
├─ resolved_baseline.yaml
├─ variants.csv
├─ metrics.csv
├─ comparison.html
└─ runs/
   └─ <run_id>/
      ├─ effective_config.yaml
      ├─ manifest.json
      └─ result data
```

생성된 result는 기본적으로 Git에서 제외한다.

## 10. User interface 요구사항

분석 UI는 다음 기능을 지원해야 한다.

- Scenario 복제
- 표시되는 unit과 함께 value 편집
- Drop-down에서 catalog component 선택
- Nominal·tolerance·measured provenance 표시
- Scenario 하나를 baseline으로 지정
- 두 개 이상의 variant 비교
- 선택한 parameter sweep
- Simulation 전에 잘못된 조합 표시
- 정확한 effective configuration export
- Confidence·accuracy mode와 calibration status 표시

UI edit는 command line에서 실행할 수 있는 것과 동일한 versioned configuration을 생성해야 한다. GUI가 별도의 숨겨진 project state를 유지해서는 안 된다.

## 11. Validation

- 알 수 없는 config field는 기본적으로 validation에 실패한다.
- 누락된 unit이나 모호한 STL scale은 validation에 실패한다.
- 잘못된 catalog reference는 validation에 실패한다.
- Derived value를 canonical input에서 재현할 수 있다.
- 같은 override를 두 번 적용하면 같은 config hash가 생성된다.
- Baseline과 동일한 variant의 metric delta는 0이다.
- Random seed로 제어한 comparison을 재현할 수 있다.
- 단위 포함 형식과 canonical SI 형식은 같은 물리 config hash로 resolve된다.
- Project path와 active baseline은 숨겨진 UI state 없이 resolve된다.
