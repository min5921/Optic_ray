# 여러 컴퓨터 작업 절차

프로젝트 파일은 Git으로 관리하고 Codex 대화는 같은 OpenAI 계정으로 이용한다. 기존 대화를 열 수 없거나 새 thread에서 시작할 때는 `HANDOFF.md`를 영구적인 인계 문서로 사용한다.

## 이 컴퓨터에서 한 번만 설정하기

GitHub 또는 GitLab에 비어 있는 **비공개** repository를 만든다. README를 자동 생성하지 말고 다음을 실행한다.

```powershell
git remote add origin <PRIVATE_REPOSITORY_URL>
git push -u origin main
```

Password, API key, login token, `.env`, 가상환경, 사용자 계정의 `.codex` directory는 repository에 넣지 않는다. 비밀 정보는 password manager에 보관하고 각 컴퓨터에서 로컬 `.env`를 다시 만든다.

## 다른 컴퓨터 설정하기

```powershell
git clone <PRIVATE_REPOSITORY_URL> Optic_ray_project
Set-Location Optic_ray_project
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

복제한 folder를 Codex에서 연다. 기존 대화를 사용할 수 있으면 다시 열고, 그렇지 않다면 다음 요청으로 시작한다.

```text
AGENTS.md, HANDOFF.md, docs/PROJECT_VISION.md를 읽고 HANDOFF.md의 가장 좋은 다음 작업부터 이어서 진행해줘.
```

## 작업 세션 시작

한 번에 한 컴퓨터만 `main`에서 작업한다.

```powershell
git switch main
git pull --ff-only
git status --short --branch
```

파일을 변경하기 전에 `HANDOFF.md`를 읽는다. Worktree가 깨끗하지 않다면 기존 변경의 의미를 확인하고 보존한다.

## 작업 세션 종료

관련 test를 실행하고 `HANDOFF.md`를 갱신한 뒤 동기화한다.

```powershell
git status --short --branch
git diff
git add -A
git commit -m "완료한 작업을 설명하는 메시지"
git push
```

다른 컴퓨터로 옮기기 전에 `git status --short --branch`가 깨끗한지 확인한다.

## 병렬 작업

두 컴퓨터에서 동시에 작업해야 한다면 컴퓨터별 branch를 사용하고 pull request로 merge한다. 같은 branch를 동시에 수정하거나 `main`에 force-push하지 않는다.

## 복구 규칙

- `git pull --ff-only`가 실패하면 merge나 rebase를 수행하기 전에 local·remote commit을 확인한다.
- Secret이 commit되었다면 나중에 파일만 삭제하지 말고 즉시 폐기하거나 교체한다.
- 생성 data가 Git에 넣기 너무 크다면 외부 storage에 보관하고 위치와 재생성 명령을 `HANDOFF.md`에 기록한다.
