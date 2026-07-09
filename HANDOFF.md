# 프로젝트 인계 문서

마지막 갱신: 2026-07-09 (Asia/Seoul)

## 현재 상태

- 현재 프로젝트 방향은 `docs/PROJECT_VISION.md` Draft v0.2에 정의되어 있다.
- 원본 coherent FMCW LiDAR 자료는 `docs/original/coherent-fmcw-lidar-sim-docs/`에 보존되어 있다.
- 여러 컴퓨터에서 사용할 Git·Codex·line ending·secret·생성 output 규칙이 설정되어 있다.
- GitHub remote `origin`은 `https://github.com/min5921/Optic_ray.git`에 연결되어 있으며 `main`이 동기화되어 있다.
- Phase 0·0.1과 Phase 1이 완료되어 configuration, coordinate, placement, asset, 검토용 viewer/HTML와 Gaussian Beam Engine이 `src/lidarsim/`에 구현되어 있다.
- Phase 2.1~2.3 vertical slice가 진행되어 source→ideal thin-lens collimator→static scanner mirror reflection→rectangle-plane target footprint→Lambertian virtual receiver return까지의 ABCD optical train, aperture clipping, component transmission/reflectivity, power ledger, target footprint, link budget와 PNG 시각화가 구현되어 있다.
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
- `lidarsim validate`는 project·scenario·experiment·catalog YAML을 읽고 JSON Schema를 검증하며, 단위 포함 값을 SI/radian으로 변환하고, 음수 물리량, wavelength validity 위반과 잘못된 component·material·port·scanner reference를 거부한다.
- `RigidTransform`, right-handed optical port frame과 absolute·port-to-port assembly resolver가 구현되어 있다. `lidarsim placement`로 active scenario의 world position·axis를 확인하거나 YAML report로 저장할 수 있다.
- Binary·ASCII STL parser와 asset registry가 구현되어 raw·SI bounds, topology, normal, degenerate triangle, content hash, material, placement와 scanner metadata를 검증한다.
- Measurement loader는 metadata schema, condition unit, data column unit, referenced file과 declared SHA-256을 검증한다. Example template은 active asset scan에서 제외한다.
- `lidarsim inspect-mesh`와 `lidarsim inspect-measurement`로 개별 asset을 검사하고 YAML report를 저장할 수 있다.
- `lidarsim report`는 schema-validated run manifest, accuracy·confidence, energy ledger, convergence와 placement report를 생성한다. 계산하지 않은 beam·radiometry 값은 `not_evaluated`로 표시한다.
- Component port에는 `interface_type`과 `reference_plane`이 있고 source 운전값은 scenario가 소유한다. Baseline은 `analytical_regression`, receiver는 `virtual_monostatic/virtual_aperture`로 명시되어 실제 장비 예측과 구분된다.
- `lidarsim view`는 component origin, port axis, optical path, mirror normal, declared scan limit, target plane, receiver FOV, return guide와 STL bounds를 full 3D scene 및 X-Z detail PNG로 렌더링한다.
- `lidarsim review`는 placement PNG, hardware readiness, component/port, output 지원 상태, convergence와 경고를 self-contained HTML로 생성한다.
- `lidarsim beam`은 active source를 불변 `BeamState`로 만들고 circular·elliptical·line Gaussian의 M² 기반 자유공간 radius, q-parameter, second moment와 power-normalized irradiance를 full report·compact summary·PNG로 생성한다.
- `lidarsim optical-train` 또는 `lidarsim train`은 active source에서 ideal thin-lens collimator를 지나 scanner mirror default pose에서 정지 반사되고, rectangle-plane target과 Lambertian virtual receiver까지의 element별 `BeamState`, aperture clipping, catalog transmission/reflectivity, power ledger, target footprint, receiver return, link budget, 내부 일관성 check와 radius/power PNG를 생성한다.
- Fiber MFD definition과 Gaussian approximation, catalog nominal match/explicit override, small-angle paraxial proxy, confidence·calibration·provenance를 검증·보고한다.
- Power audit은 analytical tail truncation, base/refined grid quadrature와 grid convergence를 분리하며 second-moment 비교는 internal consistency로만 표시한다.
- CLI distance는 `20 mm` 같은 단위 포함 값을 받고 기본 결과는 timestamp run directory에 저장해 덮어쓰지 않는다.
- `configs/line_beam_project.example.yaml`은 3.0 mm × 0.25 mm numerical elliptical-Gaussian line preset을 제공하며 Powell lens나 상용 제품 model이 아니다.
- Resolved project state는 재귀적으로 변경 불가능하며 안정적인 물리 configuration SHA-256을 갖는다. 표시 단위와 UI preference는 이 hash를 바꾸지 않는다.
- Local `.venv`는 `pyproject.toml`에서 설치했으며, deprecation·user warning을 error로 처리해도 자동 test 91개가 통과한다.
- 사용자 친화적인 로컬 simulation dashboard와 SolidWorks-like Optical Assembly Workspace 개발 방향은 `docs/UI_SIMULATION_DASHBOARD.md`에 분리해 정리했다.
- UI MVP 0의 첫 vertical slice로 `ViewportScene` data contract, source/collimator/scanner mirror/target/receiver 표시 data, local frame, port axis, mirror normal, reflected ray, target plane, receiver FOV, beam path, target hit ray, footprint overlay와 headless Matplotlib 3D workspace PNG renderer가 구현되었다.
- `lidarsim workspace configs/project.yaml --output results/ui_workspace.png --write-scene results/ui_workspace_scene.yaml`로 현재 Phase 2.3 static simulation을 optical assembly workspace용 PNG와 YAML scene으로 확인할 수 있다.
- UI MVP 0의 read-only dashboard 조각으로 `lidarsim dashboard configs/project.yaml --output results/ui_dashboard.html` 명령이 구현되었다. 추가 dependency 없이 Phase 2 report YAML, `ViewportScene` YAML, workspace PNG, optical train PNG와 self-contained dashboard HTML을 생성한다.
- 다음 활성 목표는 numeric placement editor 조각이다. 선택 component의 position/orientation 또는 port placement 값을 안전하게 수정해 variant config로 저장하고, validate/workspace/dashboard로 재현되게 만든다. 그 다음 Phase 3 scanner command angle physics를 구현해 UI에 연결한다.

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

Numeric placement editor 조각을 구현한다. 추천 범위는 CLI 또는 UI helper로 선택 component의 translation/orientation/axial gap/transverse offset/angular misalignment를 수정해 baseline을 덮어쓰지 않는 variant config를 저장하고, 그 variant가 `lidarsim validate`, `lidarsim workspace`, `lidarsim dashboard`로 재현되는지 확인하는 것이다.

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
- Phase 0.1에서 물리·cross-field validation, source ownership, port interface, readiness report와 HTML review를 추가했다.
- `python -W error::DeprecationWarning -W error::UserWarning -m pytest -q`: 55개 통과.
- `lidarsim review configs/project.yaml --output results/phase0_1_review.html --dpi 140`: HTML과 placement PNG 생성 및 시각 검수 통과. 설정 기반 ±10° optical scan guide, 25° full receiver FOV와 return guide를 확인했다.
- Phase 1에서 immutable `BeamState`, Gaussian/M²/q/second-moment free-space propagation, normalized irradiance, beam report schema, CLI와 point/line PNG를 구현했다.
- `python -W error::DeprecationWarning -W error::UserWarning -m pytest -q`: 73개 통과.
- `lidarsim beam configs/project.yaml`: 20 mm plane에서 circular beam radius `1.97352763 mm`, power integral relative error `2.429e-15`, second-moment check `pass`.
- `lidarsim beam configs/line_beam_project.example.yaml`: 20 mm plane에서 line beam radius `3.0000018 mm × 0.253096651 mm`, power/second-moment check `pass`.
- Commit 전 realism/UX 재검수에서 MFD assumption, paraxial validity, confidence/provenance, 독립 convergence 의미, CLI unit과 plot 가독성 문제를 보강했다.
- Point baseline numerical check는 통과하지만 paraxial proxy와 uncalibrated analytical model 때문에 overall `warning`, hardware readiness `analytical_only`로 표시된다.
- 현재 revision의 resolved physical config SHA-256: `3e9fc0408e8a8aa4f3a1f83c47b9aeebc863d08133ef3a6ab0676cfcb9586c73`.
- Phase 1 checkpoint commit `3ac98b3` (`Implement Phase 1 Gaussian beam engine`)를 `origin/main`에 push했다.
- Phase 2 first vertical slice에서 `ABCDMatrix`, `apply_abcd_to_beam`, circular aperture clipping, transmitter train propagation, `phase2_optical_train_report.schema.json`, `lidarsim optical-train`, `render_optical_train_view`와 regression test를 추가했다.
- `python -W error::DeprecationWarning -W error::UserWarning -m pytest -q`: 80개 통과.
- `lidarsim validate configs/project.yaml`: 통과. 기존 small-angle paraxial, virtual receiver, unsupported downstream output, analytical regression warning을 확인했다.
- `lidarsim optical-train configs/project.yaml --output results/phase2_optical_train_report.yaml --plot results/phase2_optical_train.png --dpi 140`: 통과. Scanner origin에서 radius `1.9735783 mm × 1.9735783 mm`, final power `9.99997341 mW`, total transmission `0.999997341`, clipping loss `2.6589e-08 W`, q/energy/aperture check `pass`, overall `warning`.
- Phase 2 first slice checkpoint 당시에는 ideal centered thin lens와 circular aperture만 지원했고 mirror reflection은 아직 계산하지 않았다. x/y waist 위치가 분리되는 astigmatic post-lens beam은 현재 `BeamState` contract로 정확히 표현할 수 없어 명시적으로 거부한다.
- Phase 2 checkpoint commit `ff32a6d` (`Implement Phase 2 optical train slice`)를 `origin/main`에 push했다.
- Phase 2 mirror slice에서 ideal flat mirror reflection, rectangular mirror aperture clipping, mirror reflectivity ledger와 static mirror report를 추가했다.
- `python -W error::DeprecationWarning -W error::UserWarning -m pytest -q`: 81개 통과.
- `lidarsim optical-train configs/project.yaml --output results/phase2_optical_train_report.yaml --plot results/phase2_optical_train.png --dpi 140`: 통과. Final plane은 `scan_mirror.reflected`, reflected direction은 거의 `+x`, scanner mirror incidence angle은 `45 deg`, mirror aperture transmission은 `0.9999999999992263`, q/energy/aperture check `pass`, unsupported downstream element `0`.
- Phase 2.1~2.3 extension에서 `src/lidarsim/scene/`과 `src/lidarsim/receiver/`를 추가해 rectangle-plane target intersection, projected Gaussian footprint, target power estimate, Lambertian small-footprint receiver aperture power와 link budget을 통합했다.
- `python -m pytest -q`: 91개 통과.
- `python -W error::DeprecationWarning -W error::UserWarning -m pytest -q`: 91개 통과.
- `lidarsim validate configs/project.yaml`: 통과. 현재 output warning은 scanner time dynamics가 아직 없는 `scan_path`만 남는다.
- `lidarsim optical-train configs/project.yaml`: 통과. Final plane은 `scan_mirror.reflected`, target hit count `1`, target power `0.00999997341 W`, receiver power `2.49999335e-09 W`, link loss `66.02059991327963 dB`, q/energy/aperture/target/receiver check `pass`, unsupported downstream element `0`.
- 현재 Phase 2 한계: aperture 뒤 diffraction/truncated profile shape, mirror edge scattering, polarization, Fresnel/coating/dispersion, aberration, decenter/tilt tolerance, vendor black-box execution, STL hit detection, visibility/occlusion, non-Lambertian BRDF/BSDF, detector noise, coherent FMCW와 time-dependent scanner motion은 아직 계산하지 않는다.
- `docs/UI_SIMULATION_DASHBOARD.md`를 추가해 UI 최종 목표를 단순 dashboard가 아닌 SolidWorks-like Optical Assembly Workspace로 정리했다. 진행 규칙은 얇은 workspace UI 골격을 먼저 만들고, 이후 물리 기능을 하나씩 추가할 때마다 UI에 연결하는 방식이다.
- 문서 전용 변경이므로 자동 test는 실행하지 않았고 `git diff --check`로 형식만 확인한다.
- UI MVP 0 첫 vertical slice에서 `src/lidarsim/ui/assembly/viewport_data.py`, `src/lidarsim/visualization/workspace.py`, `lidarsim workspace` CLI, viewport scene YAML 저장, 2패널 workspace PNG renderer와 UI workspace test를 추가했다.
- 추가 검수에서 target/receiver component local frame이 물리 direction과 맞도록 정렬하고 right-handed frame test를 추가했다.
- `python -m pytest tests/test_ui_workspace.py tests/test_cli.py -q`: 19개 통과.
- `python -m pytest -q`: 96개 통과.
- `python -W error::DeprecationWarning -W error::UserWarning -m pytest -q`: 96개 통과.
- `lidarsim validate configs/project.yaml`: 통과. 기존 small-angle paraxial, virtual receiver, `scan_path` 미구현, analytical regression warning을 확인했다.
- `lidarsim workspace configs/project.yaml --output results/ui_workspace.png --write-scene results/ui_workspace_scene.yaml --dpi 140`: 통과. Components 5개, ports 3개, guides 36개, rays 3개, footprints 1개를 생성했고 2패널 workspace PNG를 시각 검수했다.
- `git diff --check`: 통과.
- UI MVP 0 read-only dashboard 조각에서 `src/lidarsim/ui/dashboard.py`, `lidarsim dashboard` CLI와 dashboard CLI test를 추가했다.
- `lidarsim dashboard configs/project.yaml --output results/ui_dashboard.html --dpi 140`: 통과. Dashboard HTML, Phase 2 report YAML, `ViewportScene` YAML, workspace PNG, optical train PNG를 생성했다.
- `python -m pytest tests/test_cli.py tests/test_ui_workspace.py -q`: 20개 통과.
- `python -m pytest -q`: 97개 통과.
- `python -W error::DeprecationWarning -W error::UserWarning -m pytest -q`: 97개 통과.

## 세션 갱신 형식

향후 세션을 종료할 때 현재 상태 section을 교체하고 다음을 기록한다.

- 변경 내용
- 중요한 결정과 가정
- 실행한 test와 결과
- 알려진 문제 또는 commit되지 않은 작업
- 가장 좋은 다음 작업 하나
