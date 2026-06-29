# Measurement data·traceability contract

- 상태: 초기 구현 contract
- 작성일: 2026-06-28

## 1. 목적

상대적인 설계 비교에서 실제 장비를 calibration해 예측하는 단계로 발전하려면 measured data가 필요하다.

## 2. Directory 구성

```text
assets/measurements/
├─ source_beam_profile/
├─ component_transmission/
├─ scanner_calibration/
├─ material_brdf/
├─ receiver_response/
└─ detector_calibration/
```

각 dataset은 data file과 metadata sidecar를 포함한다.

## 3. 필수 metadata

```yaml
schema_version: 1
measurement_id: lab:source_profile_001
measurement_type: source_beam_profile
data_file: source_profile_001.csv

conditions:
  wavelength: 1550 nm
  temperature: 23 degC
  distance: 1 m

instrument:
  manufacturer: null
  model: null
  serial_number: null
  calibration_date: null

uncertainty:
  type: standard
  value: null
  confidence: null

coordinate_frame: measurement_frame
units: {}
acquired_at: null
operator: null
processing: []
source_hash: null
notes: null
```

## 4. Dataset 유형

### Source beam profile

- X·y coordinate
- Irradiance 또는 normalized intensity
- Reference plane·distance
- Total power
- Background·dark correction
- Beam-width convention
- 선택적 wavefront·phase

### Component transmission

- Wavelength
- 필요한 경우 angle·polarization
- Input·output power
- Uncertainty
- Component revision과 orientation

### Scanner calibration

- Command·time
- Measured angle 또는 hit position
- Forward·backward direction
- Temperature·frequency·load
- Fit model과 residual

### Material BRDF·BSDF

- Wavelength
- Incident·outgoing angle
- 가능한 경우 polarization
- Radiometric quantity와 normalization
- Sample preparation·roughness
- Uncertainty

### Receiver·detector response

- Aperture·optical train configuration
- Wavelength·FOV·angle
- Power·photocurrent·voltage
- Gain·bandwidth·integration time
- Dark·noise·saturation data

## 5. Import 규칙

- 누락된 unit을 추정하지 않는다.
- Raw data를 변경하지 않고 보존한다.
- 처리된 data는 processing history와 함께 별도로 저장한다.
- Coordinate orientation과 reference plane을 검증한다.
- Wavelength·angle·range를 조용히 extrapolation하지 않는다.
- Interpolation method와 validity range를 명시한다.
- Uncertainty가 누락되면 result confidence level을 낮춘다.
- Content hash를 사용해 result와 정확한 input을 연결한다.

## 6. Calibration·validation 분리

Dataset에는 다음 role 중 하나를 지정한다.

- `calibration`: parameter fitting
- `validation`: 독립적인 performance 검사
- `monitoring`: drift·repeatability 확인
- `reference`: visualization 또는 qualitative comparison

Result를 확인한 뒤 dataset의 role을 알리지 않고 바꾸지 않는다.

## 7. Comparison output

Measurement comparison은 다음을 표시한다.

- Simulation·measurement overlay
- Residual과 relative error
- Uncertainty band
- Fit·validation dataset role
- Validity range
- Calibration 전후 parameter value
- Confidence label
- 해결되지 않은 bias 또는 model mismatch
