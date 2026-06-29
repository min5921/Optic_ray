# 프로젝트 인계 문서

마지막 갱신: 2026-06-29 (Asia/Seoul)

## 현재 상태

- 현재 프로젝트 방향은 `docs/PROJECT_VISION.md` Draft v0.2에 정의되어 있다.
- 원본 coherent FMCW LiDAR 자료는 `docs/original/coherent-fmcw-lidar-sim-docs/`에 보존되어 있다.
- 여러 컴퓨터에서 사용할 Git·Codex·line ending·secret·생성 output 규칙이 설정되어 있다.
- GitHub remote `origin`은 `https://github.com/min5921/Optic_ray.git`에 연결되어 있으며 `main`이 동기화되어 있다.
- Phase 0가 완료되어 configuration, coordinate, placement, asset, result contract와 최소 viewer가 `src/lidarsim/`에 구현되어 있다.
- 프로젝트의 중심 범위는 catalog 기반 또는 사용자 정의 광학 부품의 3D 배치, 포인트·라인·면적 빔, collimator 광학계, 사용자 정의 scanner, target interaction과 receiver return 분석이다.
- Draft v0.2에는 model fidelity contract, commercial component catalog, optical/CAD import, coordinate frame, rigid transform, optical port, placement constraint, structured result, visualization과 tolerance analysis가 포함된다.
- Phase 0~5의 임시 초기값은 `docs/specs/INITIAL_BASELINE.md`에 정리되어 있으며 모든 값은 configuration으로 교체할 수 있다.
- `configs/baseline_1550nm.yaml`과 wavelength·collimator 교체 experiment 예제가 초기 configuration workflow를 정의한다.
- `configs/project.yaml`은 catalog, asset, measurement, scenario, experiment, baseline, result, 표시 단위와 UI 설정을 모은다.
- 사용자가 입력하는 물리량은 `1550 nm`, `10 mW`, `20 mm`, `5 deg`, `10 Hz`처럼 단위를 포함할 수 있다.
- FreeCAD source와 STL mesh directory, STL sidecar metadata, 초기 ideal component·material catalog record가 준비되어 있다.
- Draft JSON Schema contract는 project, scenario, experiment, component, material, STL metadata와 measurement metadata를 다룬다.
- Accuracy·calibration, UX, energy·convergence와 measurement data contract 및 measurement asset template가 준비되어 있다.
- `docs/USER_MANUAL.md`는 향후 사용자가 변경할 수 있는 조건, 부품 교체, FreeCAD/STL 절차, experiment 비교와 CLI workflow를 설명한다.
- `lidarsim validate`는 project·scenario·experiment·catalog YAML을 읽고 JSON Schema를 검증하며, 단위 포함 값을 SI/radian으로 변환하고, 잘못된 component·material·port·scanner reference를 거부한다.
- `RigidTransform`, right-handed optical port frame과 absolute·port-to-port assembly resolver가 구현되어 있다. `lidarsim placement`로 active scenario의 world position·axis를 확인하거나 YAML report로 저장할 수 있다.
- Binary·ASCII STL parser와 asset registry가 구현되어 raw·SI bounds, topology, normal, degenerate triangle, content hash, material, placement와 scanner metadata를 검증한다.
- Measurement loader는 metadata schema, condition unit, data column unit, referenced file과 declared SHA-256을 검증한다. Example template은 active asset scan에서 제외한다.
- `lidarsim inspect-mesh`와 `lidarsim inspect-measurement`로 개별 asset을 검사하고 YAML report를 저장할 수 있다.
- `lidarsim report`는 schema-validated run manifest, accuracy·confidence, energy ledger, convergence와 placement report를 생성한다. 계산하지 않은 beam·radiometry 값은 `not_evaluated`로 표시한다.
- `lidarsim view`는 component origin, port axis, optical path, target plane, receiver와 STL bounds를 full 3D scene 및 X-Z detail PNG로 렌더링한다.
- Resolved project state는 재귀적으로 변경 불가능하며 안정적인 물리 configuration SHA-256을 갖는다. 표시 단위와 UI preference는 이 hash를 바꾸지 않는다.
- Local `.venv`는 `pyproject.toml`에서 설치했으며, deprecation·user warning을 error로 처리해도 자동 test 41개가 통과한다.
- 다음 활성 목표는 Phase 1 Beam Engine이다.

## 유지할 결정 사항

- `docs/PROJECT_VISION.md`가 현재 범위와 개발 순서를 정의하며 원본 문서는 물리 참고 자료로만 사용한다.
- Coherent FMCW와 speckle layer를 추가하기 전에 radiometric received-power 경로를 검증한다.
- 초기 accuracy mode는 `relative_design`이다. `absolute_radiometric`에는 calibrated input·path·material·receiver data가 필요하고, `coherent_fmcw`에는 phase·coherence 요구사항이 추가된다.
- Wavelength, component, scanner, target, receiver 또는 material 값은 simulation logic에 hard-code하지 않고 scenario와 experiment에서 제공한다.
- 초기 사용자 geometry 교환 형식은 STL이다. STL unit, role, material, placement, scanner pivot과 axis는 YAML sidecar metadata에 명시한다.
- Lens STL은 mechanical·visual geometry일 뿐이며 optical behavior는 ideal, catalog, prescription 또는 measured model에서 가져온다.
- 선택적 GPU 가속보다 CPU 정확성과 analytical validation을 먼저 확보한다.
- 컴퓨터 간 project state는 Git으로 이동하며 credential과 컴퓨터별 Codex 상태는 이동하지 않는다.
- 같은 OpenAI 계정에서 대화 기록을 열 수 있지만, 이 파일을 영구적인 작업 연속성의 기준으로 사용한다.
- 프로젝트에서 새로 작성하거나 수정하는 Markdown 문서는 한글을 기본으로 한다. 보존 원본과 code·명령·고유 identifier는 번역하지 않는다.

## 가장 좋은 다음 작업

Phase 1의 첫 vertical slice로 immutable `BeamState`, circular Gaussian point beam, power normalization과 free-space analytical propagation을 NumPy·float64로 구현한다. Beam radius, Rayleigh range와 divergence를 closed-form reference와 비교하고 PNG profile·radius plot을 생성한다.

## 검증 기록

- `docs/PROJECT_VISION.md`를 검토하고 optical component placement와 commercial·custom optical system input을 포함한 Draft v0.2로 확장했다.
- Configuration 기반 조건 변경, 부품 교체, 합의된 초기값과 FreeCAD/STL workflow를 문서화했다.
- 사용자 configuration·교체 manual을 추가하고 프로젝트 진입 문서에서 연결했다.
- Baseline·experiment YAML과 ideal component·material catalog record를 실행 가능한 validator가 읽는다.
- JSON Schema validation은 최신 `referencing.Registry` API를 사용하며 unit conversion은 Pint를 사용한다.
- 원본 문서는 `docs/original/coherent-fmcw-lidar-sim-docs/`에 보존되어 있다.
- Git 안전 파일과 여러 컴퓨터 작업 절차를 추가했다.
- Local `main`은 GitHub의 `origin/main`을 추적한다.
- `python -m pytest -q`: 41개 통과.
- `python -W error::DeprecationWarning -W error::UserWarning -m pytest -q`: 41개 통과.
- `lidarsim validate configs/project.yaml`: 통과. Scenario 1개, component 4개, material 1개, experiment 1개를 resolve했다.
- `lidarsim placement configs/project.yaml`: 통과. Source origin `[0, 0, -0.1]` m, collimator origin `[0, 0, -0.08]` m와 두 port의 world optical axis `+z`를 확인했다.
- Binary·ASCII STL audit, closed·open topology, normal rejection, active mesh·measurement discovery와 inspection CLI test가 통과했다.
- Canonical SI scenario를 저장하고 재로드했을 때 config hash와 collimator world placement가 동일함을 확인했다.
- `lidarsim report configs/project.yaml`: schema validation 통과. Confidence는 `comparative`, energy ledger는 `not_evaluated`, convergence는 Phase 1 physics가 없어 `warning`으로 정확히 표시된다.
- `lidarsim view configs/project.yaml`: headless PNG 생성과 시각 검수를 완료했다. Full 3D scene과 X-Z assembly detail에 baseline placement가 표시된다.
- 현재 revision의 resolved physical config SHA-256: `b479192169edc61b65b7cc77638cb021a2c4f691803056e1634fec70f069f259`.

## 세션 갱신 형식

향후 세션을 종료할 때 현재 상태 section을 교체하고 다음을 기록한다.

- 변경 내용
- 중요한 결정과 가정
- 실행한 test와 결과
- 알려진 문제 또는 commit되지 않은 작업
- 가장 좋은 다음 작업 하나
