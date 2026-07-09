# 사용자 정의 빔·스캐너·광수신 시뮬레이터

이 프로젝트는 catalog 기반 또는 사용자 정의 광학 부품을 3D 공간에 배치하고, 포인트·라인·면적 빔이 collimator 광학계와 사용자 정의 scanner를 통과해 재질이 지정된 target을 비춘 뒤 수신기로 돌아오는 광 파워 또는 coherent FMCW 신호를 계산한다.

## 프로젝트 방향

현재 v0.2 프로젝트 정의, 부품 배치 model, 물리 layer, output, 개발 단계, 검증 scenario와 미정 장비 사양은 [`docs/PROJECT_VISION.md`](docs/PROJECT_VISION.md)에서 관리한다.

물리 조건과 부품 선택은 configuration으로 관리한다. [`configs/project.yaml`](configs/project.yaml)을 열고 [`configs/baseline_1550nm.yaml`](configs/baseline_1550nm.yaml)을 기준으로 시작한 뒤, `1550 nm` 같은 단위 포함 값이나 component reference를 직접 변경한다. 여러 조건을 비교할 때는 [`configs/experiments/component_swap.example.yaml`](configs/experiments/component_swap.example.yaml) 같은 experiment를 사용한다.

합의된 임시 초기값은 [`docs/specs/INITIAL_BASELINE.md`](docs/specs/INITIAL_BASELINE.md)에 있다. FreeCAD/STL asset 준비 방법은 [`docs/specs/COORDINATES_AND_PLACEMENT.md`](docs/specs/COORDINATES_AND_PLACEMENT.md)와 [`assets/README.md`](assets/README.md)를 따른다.

파장, 광원, 광학 부품, 배치, scanner, STL geometry, 재질, 수신기 설정, output과 비교 experiment를 변경하는 자세한 방법은 [`docs/USER_MANUAL.md`](docs/USER_MANUAL.md)를 참고한다.

정확도 mode는 `relative_design`, `absolute_radiometric`, `coherent_fmcw`로 구분한다. JSON validation contract는 [`schemas/`](schemas/)에 있으며, 측정 calibration·validation data는 [`assets/measurements/`](assets/measurements/)에 둔다.

## Phase 1·2 빠른 시작

Phase 0.1의 검증 기반 위에 NumPy/float64 Gaussian Beam Engine을 구현했다. 현재 point·elliptical·line Gaussian의 자유공간 전파, M², q-parameter, second moment, power-normalized irradiance와 PNG 시각화를 지원한다.

Phase 2의 vertical slice로 source에서 ideal thin-lens collimator를 지나 scanner mirror에서 정지 반사되고, rectangle-plane target footprint와 첫 Lambertian receiver return까지 계산한다. `lidarsim optical-train`은 free-space propagation, thin-lens ABCD transform, centered circular aperture clipping, static flat-mirror reflection, mirror aperture clipping, catalog transmission/reflectivity, target footprint, receiver aperture power와 link budget을 YAML/PNG로 저장한다. Scanner time dynamics, STL hit detection, BRDF, detector noise와 coherent FMCW는 아직 후속 Phase 범위다.

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
lidarsim validate configs/project.yaml
lidarsim placement configs/project.yaml
lidarsim report configs/project.yaml
lidarsim view configs/project.yaml
lidarsim review configs/project.yaml
lidarsim beam configs/project.yaml
lidarsim optical-train configs/project.yaml
python -m pytest -q
```

`validate`는 단위가 포함된 물리량을 SI/radian으로 변환하고, 알 수 없는 field, 음수 크기, wavelength validity 위반, 잘못된 catalog·port reference와 resolve할 수 없는 placement를 거부하며 재현 가능한 물리 configuration SHA-256을 출력한다. `placement`는 active scenario의 component·port world position, optical axis와 interface를 계산한다.

`report`는 run manifest, confidence, model purpose, hardware readiness, energy ledger와 convergence 상태를 schema-validated YAML로 저장한다. `view`는 full 3D scene, X-Z assembly detail, mirror, 설정된 scan limit, receiver FOV와 return guide를 PNG로 렌더링한다. `review`는 이 그림과 지원 output·경고·수치 검사를 self-contained HTML 한 파일로 묶는다. Scan/FOV/return 선은 설정값 기반 기하학 가이드이며 아직 전파·수신광 계산 결과가 아니다.

`beam`은 active source에서 첫 downstream element까지 기본 자유공간 전파를 계산한다. 결과는 덮어쓰지 않도록 `results/phase1/<timestamp>_<scenario>_<hash>/` 아래에 full report, compact summary와 PNG로 저장된다. `--z-max-m "100 mm"`처럼 단위를 포함해 범위를 바꿀 수 있다. Line-beam 예제는 `lidarsim beam configs/line_beam_project.example.yaml`로 실행한다. Phase 1은 downstream lens·aperture·mirror를 아직 적용하지 않는다.

`optical-train`은 Phase 2 조각으로 collimator 전후와 scanner mirror 반사 후의 `BeamState`, aperture clipping loss, component transmission, mirror reflectivity, rectangle-plane target footprint와 Lambertian receiver return을 계산한다. 결과는 `results/phase2/<timestamp>_<scenario>_<hash>/` 아래에 `optical_train_report.yaml`과 `optical_train.png`로 저장된다. 현재 scanner mirror는 default static pose로만 반사하며 시간 구동 scanner motion은 아직 적용하지 않는다. 같은 명령은 짧게 `lidarsim train configs/project.yaml`로도 실행할 수 있다.

Phase 1 결과는 numerical check가 통과해도 실제 측정으로 calibration되지 않았다면 전체 상태를 `warning`, hardware readiness를 `analytical_only`로 표시한다. Fiber MFD의 정의와 catalog nominal override 여부도 configuration에 명시해야 한다.

실제 STL 또는 measurement sidecar를 추가한 뒤에는 다음 명령으로 독립 검증할 수 있다.

```powershell
lidarsim inspect-mesh assets/meshes/my_target.stl.yaml
lidarsim inspect-measurement assets/measurements/my_data.measurement.yaml
```

## 여러 컴퓨터에서 작업하기

프로젝트 파일은 비공개 Git remote로 동기화한다. 어느 컴퓨터에서든 작업을 시작하기 전에 `AGENTS.md`와 `HANDOFF.md`를 읽는다. 전체 설정·인계 절차는 [`docs/MULTI_PC_WORKFLOW.md`](docs/MULTI_PC_WORKFLOW.md)에 있다.

컴퓨터별 가상환경, credential, 생성된 simulation 결과와 Codex 상태는 의도적으로 version control에서 제외한다.

가져온 coherent FMCW LiDAR 원본 문서는 [`docs/original/coherent-fmcw-lidar-sim-docs/`](docs/original/coherent-fmcw-lidar-sim-docs/)에 변경 없이 보존한다.

## 최종적으로 포함할 기능

- M²를 포함한 Gaussian beam propagation
- ABCD matrix 기반 optical system modeling
- lens·aperture·mirror·scanner model
- scanner dynamics와 시간에 따른 beam steering
- STL/CAD 기반 scene visibility
- 재질별 reflection
- Rough surface scatterer sampling
- Coherent speckle field 합산
- FMCW beat signal 생성
- FFT/CZT range processing
- Range·intensity·speckle·point-cloud visualization
- Backend abstraction을 통한 선택적 GPU 가속

이 프로젝트는 순수 ray tracing engine이 아니다.

Ray tracing은 다음 용도로 사용한다.

1. Visibility
2. Occlusion
3. Scanner steering geometry
4. Mirror reflection geometry
5. STL hit detection
6. 보이는 surface patch 선택

LiDAR 신호는 surface scatterer의 **coherent electric field 합산**으로 생성한다.

핵심 흐름:

```text
Scanner motion
    ↓
time-dependent BeamState
    ↓
moving beam footprint on target
    ↓
fixed rough scatterer map
    ↓
changing coherent field sum
    ↓
speckle decorrelation
    ↓
FMCW beat signal per pixel
    ↓
batch FFT
    ↓
range/intensity/speckle image
```

## 개발 원칙

물리적으로 검증된 CPU 기준 model을 먼저 만든다. 정확성이 확립된 뒤 GPU 가속을 추가한다.

권장 순서:

```text
FMCW single target
→ Gaussian beam + M²
→ lens/ABCD/aperture
→ rough surface speckle
→ receiver aperture
→ scanner dynamics
→ scanner-driven speckle decorrelation
→ backend abstraction
→ CuPy batch FFT
→ STL visible patch
→ material model
→ car/mirror/retroreflector scene
→ full-frame GPU acceleration
```

## 중요 규칙

- STL triangle 하나를 optical scatterer 하나로 취급하지 않는다.
- STL triangle은 geometry와 normal의 기준일 뿐이다.
- Optical scatterer는 보이는 surface patch 위에 별도로 sampling한다.
- Speckle이 필요할 때 intensity를 먼저 합산하지 않는다.
- 올바른 speckle 계산:

```text
E_rx = Σ A_i exp(jφ_i)
P_rx = |E_rx|²
```

- 잘못된 speckle 계산:

```text
P_rx = Σ P_i
```

- Power와 field amplitude는 구분한다.

```text
P ∝ |E|²
E ∝ sqrt(P)
```
