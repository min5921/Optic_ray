# 정확도·신뢰도·Calibration contract

- 상태: 초기 구현 contract
- 작성일: 2026-06-28

## 1. 목적

수치적으로 정밀한 결과가 실제 장비를 정확하게 예측한다는 뜻은 아니다. 모든 결과에는 그 결과가 정당하게 나타낼 수 있는 범위를 명시해야 한다.

## 2. 정확도 mode

### `relative_design`

목적:

- Wavelength, component, placement, scanner, target 또는 receiver variant를 비교한다.
- 설계 대안의 순위를 정한다.
- Sensitivity와 clipping 위험을 찾는다.

필수 data:

- 내부적으로 일관된 nominal parameter
- 모든 비교에 동일한 sampling과 seed
- 명시적인 가정

이 mode가 프로젝트의 초기 mode다. Calibration된 절대 receiver power를 보장하지 않는다.

### `absolute_radiometric`

목적:

- Receiver aperture 또는 detector에 도달하는 optical power를 uncertainty와 함께 예측한다.

추가 필수 data:

- Calibration된 source power·profile
- Component transmission·reflectivity
- Alignment·placement uncertainty
- Wavelength·angle에 따른 material BRDF/BSDF
- Receiver aperture·optical efficiency calibration
- 필요한 경우 atmosphere·path model
- Measurement traceability

### `coherent_fmcw`

목적:

- Coherent field, speckle, beat waveform, spectrum, range와 선택적 velocity를 예측한다.

추가 필수 data:

- Phase가 일관된 optical path
- 고정된 scatterer·roughness model
- Laser coherence·linewidth·phase-noise data
- Chirp rate, linearity, timing과 sample clock
- LO·mixer·detector model
- Polarization·coherent efficiency 가정

## 3. Uncertainty 분류

다음 항목을 서로 구분해 추적한다.

- `numerical_error`: floating-point, discretization, mesh, quadrature와 solver tolerance
- `model_form_error`: paraxial, Gaussian, BRDF, thin-lens, frozen-scanner 등 model approximation
- `input_uncertainty`: catalog tolerance와 알 수 없는 parameter
- `placement_uncertainty`: decenter, tilt, gap, pivot과 calibration error
- `measurement_uncertainty`: instrument calibration, noise와 repeatability
- `environmental_uncertainty`: temperature, atmosphere와 vibration

결합 가정을 명시하지 않는 한 이 항목들을 하나의 숫자로 합치지 않는다.

## 4. 신뢰도 표시

모든 report와 주요 result에 다음 정보를 표시한다.

```yaml
accuracy_mode: relative_design
confidence_level: comparative
calibration_status: uncalibrated
model_level: paraxial_specification
material_data: assumed_lambertian
validity:
  wavelength: 1550 nm
  range: 10 m
warnings: []
```

허용되는 confidence label:

- `illustrative`: 이상화된 설명용 결과
- `comparative`: 상대적인 variant 순위 비교에 적합
- `engineering_estimate`: catalog·tolerance data로 뒷받침되는 공학적 추정
- `calibrated`: 명시된 범위의 측정값으로 fitting하고 validation한 결과
- `out_of_validity`: 진단 목적으로 생성했지만 신뢰할 수 없는 결과

## 5. Calibration workflow

```text
nominal config
→ measurement metadata·data import
→ unit, coordinate, wavelength 확인
→ calibration 대상 parameter 선택
→ calibration dataset으로 fitting
→ calibrated parameter set 고정
→ 독립 dataset으로 validation
→ residual과 validity range 기록
```

Calibration 규칙:

- 별도 표시 없이 같은 dataset으로 fitting과 validation을 동시에 수행하지 않는다.
- Nominal, fitted, measured value를 구분해 보존한다.
- Fitted parameter를 물리적으로 가능한 범위로 제한한다.
- Objective function, optimizer 설정과 random seed를 저장한다.
- Parameter correlation과 identifiability warning을 보고한다.
- 알려진 model mismatch를 숨기기 위해 calibration을 사용하지 않는다.

## 6. 비교 규칙

부품 또는 조건을 비교할 때 다음을 지킨다.

- 변경하지 않은 input은 동일하게 유지한다.
- Target sampling과 random scatterer map을 유지한다.
- Drop-in placement와 reoptimized placement를 구분한다.
- Metric의 absolute·relative change를 함께 보고한다.
- Compatibility와 validity warning을 표시한다.
- 가능한 경우 uncertainty band를 표시한다.

## 7. 승인 기준

### Relative-design release

- Analytical beam·placement·energy test가 통과한다.
- 동일한 config에서 동일한 hash와 result가 생성된다.
- 부품 교체가 선언된 comparison policy를 유지한다.
- Numerical convergence를 입증한다.
- Result confidence가 화면에 표시된다.

### Absolute-radiometric release

- Calibration data와 metadata가 존재한다.
- Link-budget audit가 선언된 tolerance 안에서 닫힌다.
- 독립 validation residual을 보고한다.
- 측정한 wavelength·angle·range 밖으로 extrapolation할 때 warning을 표시한다.
- Receiver power uncertainty를 보고한다.

### Coherent-FMCW release

- Range와 phase convention을 검증한다.
- Coherent·incoherent contribution을 암묵적으로 섞지 않는다.
- 고정된 scatterer identity를 재현할 수 있다.
- FFT·range와 phase-noise test가 통과한다.
- Regression을 위한 CPU reference를 유지한다.
