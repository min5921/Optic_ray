# Energy accounting·numerical convergence contract

- 상태: 초기 구현 contract
- 작성일: 2026-06-28

## 1. 목적

Simulator는 optical power가 어디로 이동하거나 손실되는지, 그리고 numerical resolution을 바꿔도 결과가 안정적인지를 보여야 한다.

## 2. Power ledger

각 optical path는 다음 ledger를 유지한다.

```text
source power
- source/coupling loss
- aperture clipping
- lens/window/filter loss
- mirror/scanner loss
= target incident power
- absorption/transmission/out-of-path scattering
= modeled reflected/scattered power
× receiver geometric collection
× receiver optical efficiency
= receiver-aperture 또는 detector power
```

각 항목에 다음을 기록한다.

- Component·surface·path ID
- Input·output power
- W·dB 단위 loss
- Model·data source
- Validity·warning
- Numerical residual

## 3. Energy conservation

Energy-conserving model에서는 다음 관계를 만족해야 한다.

```text
reflected + transmitted + absorbed <= incident + numerical_tolerance
```

BRDF·BSDF lobe는 normalize하거나 empirical·non-conserving임을 명시한다. Clipping과 occlusion을 이중으로 계산하지 않는다.

## 4. Radiometric convention

다음 물리량을 구분한다.

- Radiant power: W
- Irradiance: W/m²
- Radiance: W/(m² sr)
- Radiant intensity: W/sr
- BRDF: 1/sr
- Field amplitude: 선택한 normalization에서 sqrt(W)에 비례

Incidence cosine을 surface irradiance에 이미 포함했는지 link-budget 구현에 명시해 중복 적용을 막는다.

## 5. Convergence 차원

해당하는 다음 차원에 대해 convergence test를 수행한다.

- STL tessellation·triangle size
- Beam-profile grid resolution
- Footprint quadrature·patch 수
- Ray 수
- Surface scatterer 수
- Time·scan sampling
- Chirp sample rate와 FFT length
- Wavelength·angular sampling
- Monte Carlo sample 수
- Batch size·precision·backend

## 6. Convergence 절차

```text
resolution N으로 실행
refined resolution 2N으로 실행
선택한 metric 비교
error target을 만족하거나 limit에 도달할 때까지 반복
```

Metric 예시:

- Beam radius·divergence
- Clipping loss
- Footprint area·peak irradiance
- Received power
- Scan hit position
- FFT peak·range
- Speckle statistics

## 7. 초기 numerical target

Ideal analytical validation에는 다음 target을 사용한다.

- Transform position error: `< 1e-9 m`
- Unit-vector norm error: `< 1e-12`
- Port angular alignment error: `< 1e-9 rad`
- Gaussian beam-radius relative error: `< 0.1%`
- Normalized power-integral error: `< 0.1%`
- Analytical radiometric-power error: `< 1%`
- 동일 config comparison delta: metric tolerance 안에서 numerical zero

이 값은 software target이며 실제 장비 accuracy를 보장하지 않는다.

## 8. Mesh 전용 검사

- Raw·scaled bound를 expected bound와 비교한다.
- Open·non-manifold edge를 검출한다.
- Degenerate triangle을 보고한다.
- Face-normal orientation을 검증한다.
- 두 tessellation level에서 return metric을 비교한다.
- Mesh facet이 주요 error가 될 경우 ideal mirror·lens에는 analytic optical plane을 사용한다.
- 별도 validation이 없다면 STL은 주로 target·mechanical geometry에 사용한다.

## 9. Sampling과 aliasing

- Scanner sampling은 motion과 pixel timing을 분해할 수 있어야 한다.
- Footprint sampling은 beam의 가장 짧은 dimension을 분해할 수 있어야 한다.
- FMCW sample rate는 선택한 beat-frequency range를 만족해야 한다.
- FFT window·zero-padding을 실제 physical resolution처럼 해석하지 않는다.
- Random scatterer density가 안정적인 statistics를 만드는지 검사한다.
- 공정한 비교가 필요한 parameter sweep은 일관된 sampling을 유지한다.

## 10. Precision과 backend 검사

- `float64/complex128` CPU result를 reference로 사용한다.
- 낮은 precision은 metric delta를 보고한다.
- CPU·GPU peak index와 normalized spectrum을 비교한다.
- Batch size 변화가 tolerance보다 큰 result 변화를 만들지 않아야 한다.
- Deterministic mode와 nondeterministic operation을 보고한다.

## 11. Audit output

모든 run은 다음 정보를 생성한다.

- Power ledger
- Conservation residual
- 선택한 convergence 상태
- Sampling 요약
- Precision·backend 요약
- 해결되지 않은 convergence warning
- Confidence에 미치는 영향
