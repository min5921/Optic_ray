# 초기 simulation baseline

- 상태: 초기 default 승인
- 작성일: 2026-06-28
- 목적: 실제 장비 사양을 확보하기 전 Phase 0~5 analytical validation
- 중요: 이 값은 simulation reference이며 어떤 commercial product의 실제 사양을 의미하지 않는다.

## 1. Modeling 범위

첫 구현은 native Python CPU model을 사용하며 Zemax, CODE V 또는 OpticStudio가 필요하지 않다.

포함 범위:

- Transmit path 하나
- Gaussian point beam과 elliptical Gaussian line-beam preset
- Ideal thin-lens fiber collimator
- Absolute·port-to-port component placement
- One-axis flat-mirror scanner
- Flat diffuse target
- Virtual monostatic circular receiver aperture
- Receiver aperture에 도달하는 optical power
- Matplotlib validation plot과 PyVista 3D layout viewer
- YAML sidecar metadata를 가진 FreeCAD-exported STL geometry

후속 범위:

- Area top-hat diffraction
- 전체 CAD constraint solver
- 일반적인 Zemax·CODE V import
- Beamsplitter와 multiple optical path
- Transparent BSDF와 ghost reflection
- Detector photocurrent·noise·SNR
- Coherent FMCW와 speckle
- GPU acceleration

## 2. Coordinate·placement baseline

- 오른손 world coordinate system
- `+x`: nominal target을 향하는 전방
- `+y`: 좌측
- `+z`: 상방
- 내부 길이: meter
- 내부 각도: radian
- Column vector
- Active rotation
- Transform 이름: `T_destination_from_source`
- 내부 quaternion 순서: `[w, x, y, z]`
- Optical-port local `+z`: nominal propagation direction
- 내부 placement dtype: `float64`

자세한 contract는 [`COORDINATES_AND_PLACEMENT.md`](COORDINATES_AND_PLACEMENT.md)에 있다.

## 3. Source baseline

### Point-beam reference

| Parameter | 초기값 |
|---|---:|
| Source type | Fiber Gaussian reference |
| Wavelength | 1550 nm |
| Optical power | 10 mW |
| Fiber mode-field diameter | 10 µm |
| Waist radius | 5 µm |
| M² | 1.0 |
| Polarization | 지정하지 않은 scalar |
| Spectral model | Single wavelength |

### Line-beam reference

첫 line beam은 reference plane에서 정의한 numerical elliptical-Gaussian preset이다. Powell lens 또는 특정 commercial line generator의 실제 model을 의미하지 않는다.

| Parameter | 초기값 |
|---|---:|
| Optical power | 10 mW |
| Long-axis 1/e² radius | 3.0 mm |
| Short-axis 1/e² radius | 0.25 mm |
| M², long·short axis | 1.0 / 1.0 |
| Orientation | Local +x transverse axis |

Fresnel 또는 measured-profile model을 사용할 수 있을 때까지 area-beam propagation은 후속 단계로 미룬다.

## 4. Ideal collimator baseline

| Parameter | 초기값 |
|---|---:|
| Model level | Level 1, paraxial specification |
| Lens type | Ideal thin lens |
| Effective focal length | 20 mm |
| Clear-aperture diameter | 10 mm |
| Power transmission | 1.0 |
| Source-waist placement | Front focal plane |
| Design wavelength | 1550 nm |

Point-beam reference에서 lens 부근의 예상 collimated 1/e² radius는 다음과 같다.

```text
w_out ≈ wavelength × focal_length / (pi × w_source)
      ≈ 1.97 mm
```

예상 full 1/e² diameter는 약 3.95 mm다. 이 값은 ideal model의 analytical validation 기준이다.

## 5. Scanner baseline

| Parameter | 초기값 |
|---|---:|
| Scanner type | One-axis ideal flat mirror |
| Mirror size | 20 mm × 20 mm |
| Pivot | Mirror center |
| Rotation axis | World +y |
| Mechanical angle | ±5 deg |
| Motion | 10 Hz triangle wave |
| Samples per line | 101 |
| Reflectivity | 1.0 |
| Dynamic lag·jitter | 사용하지 않음 |

Reference placement:

- Source와 collimator가 incident beam을 world `+z` 방향으로 보낸다.
- Scanner pivot은 world `[0, 0, 0]` m에 있다.
- Zero-angle mirror normal은 `[-sqrt(0.5), 0, sqrt(0.5)]`다.
- Zero-angle reflected beam은 world `+x` 방향으로 진행한다.
- Reference pose 부근에서 `+y` axis에 대한 scanner rotation은 대략 두 배의 optical scan-angle 변화를 만든다.

## 6. Target baseline

| Parameter | 초기값 |
|---|---:|
| Geometry | Flat rectangular plane |
| Plane center | `[10, 0, 0]` m |
| Plane normal | `[-1, 0, 0]` |
| Size | 4 m × 4 m |
| Material | Ideal Lambertian diffuse |
| Hemispherical reflectivity | 0.20 |
| Occlusion | Analytical case에서는 사용하지 않음 |

Plane은 10 m 거리의 nominal ±10 deg optical scan을 포함할 만큼 충분히 크다.

## 7. Receiver baseline

| Parameter | 초기값 |
|---|---:|
| Architecture | Virtual monostatic receiver |
| Aperture center | `[0, 0, 0]` m |
| Aperture normal | World `+x` |
| Aperture diameter | 25 mm |
| Optical efficiency | 0.80 |
| FOV | Full angle 25 deg |
| Detector model | 후속 단계 |
| Primary result | Receiver aperture의 optical power |

Virtual co-location을 사용해 첫 radiometric validation에서는 beamsplitter와 reverse scanner path를 model하지 않는다. 실제 장비 사양이 결정되면 physical transmit·receive assembly로 교체한다.

## 8. Numerical·validation baseline

| 항목 | 초기 target |
|---|---:|
| Geometry dtype | float64 |
| 추가 예정인 coherent dtype | complex128 |
| Transform position error | < 1e-9 m |
| Unit-vector norm error | < 1e-12 |
| Port angular alignment error | < 1e-9 rad |
| Gaussian radius relative error | < 0.1% |
| Beam-power normalization error | < 0.1% |
| Analytical radiometric power error | < 1% |
| Random seed | stochastic model 도입 시 0 |

이 값은 software-validation tolerance다. 실제 product accuracy는 catalog, CAD, material, alignment와 measurement uncertainty의 영향을 받는다.

## 9. 초기 performance baseline

- CPU·NumPy reference implementation
- Scan line 하나
- Scan sample 101개
- Target plane 하나
- Material 하나
- Radiometric MVP에서는 surface scatterer cloud를 사용하지 않음
- Static plot과 interactive 3D layout 하나로 result 표시

## 10. Override policy

모든 초기값은 version이 관리되는 configuration 파일에서 교체할 수 있어야 한다. 실제 장비 data를 확보하면 다음 절차를 따른다.

1. 이 baseline을 regression example로 보존한다.
2. 별도의 hardware configuration을 만든다.
3. 교체하는 모든 값의 source를 기록한다.
4. Measured 또는 catalog value를 문서화되지 않은 assumption으로 덮어쓰지 않는다.
