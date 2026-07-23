# AGENTS.md

이 파일은 모든 컴퓨터에서 사람과 코딩 에이전트가 함께 지켜야 할 작업 규칙을 정의한다.

## 매 세션 시작 시

1. 현재 상태와 다음 작업을 확인하기 위해 `HANDOFF.md`를 읽는다.
2. `docs/PROJECT_VISION.md`를 읽고 현재 활성 단계의 범위 안에서 작업한다.
3. 현재 검수 문제와 실제 착수 순서는 `docs/specs/IMPLEMENTATION_AUDIT_2026-07-15.md`에서 확인한다.
4. `docs/original/coherent-fmcw-lidar-sim-docs/` 아래의 파일은 보존된 물리·구현 참고 자료로 사용한다.
5. 편집 전에 `git status --short --branch`를 실행하고 기존 변경을 확인한다.
6. 현재 작업과 관계없는 변경을 덮어쓰거나 버리지 않는다.

## 프로젝트 목표

사용자가 정의한 포인트·라인·면적 빔이 collimator 광학계와 사용자 정의 scanner를 통과하고, 재질이 지정된 target과 상호작용한 뒤, 수신기로 돌아오는 광 파워 또는 coherent FMCW 신호를 계산하는 Python simulator를 구축한다.

## 반드시 지켜야 할 물리 규칙

- Speckle은 `E_rx = sum(A_i * exp(1j * phi_i))`로 계산한 뒤 `P_rx = abs(E_rx) ** 2`로 구한다.
- Coherent field 합산을 scatterer power의 합으로 대체하지 않는다.
- Field amplitude와 optical power를 서로 다른 물리량으로 유지한다.
- STL triangle은 geometry와 normal의 기준으로만 사용하고 optical scatterer로 취급하지 않는다.
- Scan position이 바뀌어도 고정된 surface scatterer map을 재사용하며 pixel마다 phase를 새로 생성하지 않는다.
- 내부 길이는 SI 단위, 내부 각도는 radian을 사용한다.
- CPU 기준 검증에는 `complex128`을 사용한다. 낮은 precision은 명시적으로 검증된 GPU 경로에서만 선택적으로 허용한다.
- 모든 stochastic model은 seed를 입력받아 재현할 수 있어야 한다.

## 개발 순서와 품질

- `docs/PROJECT_VISION.md`의 단계 순서를 따른다. 현재 목표는 `Phase 2-S0 → Phase 2-S1 → UI-S → Phase 2.4-R1 → Phase 4.1-M1 STL closest-hit → R2 → R3 → R4` 순서이며, 각 Gate는 `docs/specs/IMPLEMENTATION_AUDIT_2026-07-15.md`를 따른다.
- GPU 가속을 추가하기 전에 올바른 NumPy/CPU 기준 구현을 확립한다.
- 선택 사항인 GPU package는 기본 runtime 경로에서 제외한다.
- 동작을 변경할 때마다 test를 추가하거나 갱신한다. 복잡한 scene보다 단순한 analytical case를 먼저 검증한다.
- `src/lidarsim/` 아래에 작고 type이 명확하며 문서화된 module을 우선한다.
- 생성 결과, 가상환경, credential, 컴퓨터별 Codex 상태는 Git에 추가하지 않는다.

## 매 세션 종료 시

1. 변경과 관련된 test를 실행하고 명령과 결과를 `HANDOFF.md`에 기록한다.
2. 완료되고 검증된 작업만 `docs/PROJECT_VISION.md`의 진행 상태에 반영한다.
3. `HANDOFF.md`에 현재 상태, 결정 사항, 변경 파일, 가장 좋은 다음 작업 하나를 기록한다.
4. `git diff`와 `git status --short --branch`를 확인한다.
5. 사용자가 요청했거나 세션 범위에 Git 동기화가 명시된 경우에만 commit과 push를 수행한다.

## 여러 컴퓨터 간 협업

- 한 번에 한 컴퓨터만 `main`에서 작업한다.
- 세션을 시작할 때 fetch 후 fast-forward 방식으로 동기화한다.
- 컴퓨터를 바꾸기 전에는 깨끗한 상태의 commit을 push한다.
- 두 컴퓨터에서 병렬 작업해야 한다면 feature branch를 사용한다.
- 공유 branch에는 force-push하지 않는다.
- 정확한 명령은 `docs/MULTI_PC_WORKFLOW.md`를 따른다.
