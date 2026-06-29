# Multi-Computer Workflow

Use Git for project files and the same OpenAI account for Codex conversations. `HANDOFF.md` is the durable bridge when a conversation is unavailable or a new thread is started.

## One-Time Setup on This Computer

Create an empty **private** repository on GitHub or GitLab. Do not initialize it with a README, then run:

```powershell
git remote add origin <PRIVATE_REPOSITORY_URL>
git push -u origin main
```

Do not put passwords, API keys, login tokens, `.env` files, virtual environments, or the user-level `.codex` directory in the repository. Store secrets in a password manager and recreate local `.env` files on each computer.

## Set Up Another Computer

```powershell
git clone <PRIVATE_REPOSITORY_URL> Optic_ray_project
Set-Location Optic_ray_project
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Open the cloned folder in Codex. Reopen the existing conversation if it is available, or begin with:

```text
Read AGENTS.md, HANDOFF.md, and docs/PROJECT_VISION.md, then continue from the best next action in HANDOFF.md.
```

## Start a Work Session

Use one active computer on `main` at a time:

```powershell
git switch main
git pull --ff-only
git status --short --branch
```

Read `HANDOFF.md` before making changes. If the worktree is not clean, understand and preserve the existing changes before continuing.

## End a Work Session

Run the relevant tests, update `TASKS.md` and `HANDOFF.md`, then synchronize:

```powershell
git status --short --branch
git diff
git add -A
git commit -m "Describe the completed work"
git push
```

Confirm that `git status --short --branch` is clean before moving to another computer.

## Parallel Work

If two computers must work at the same time, use a separate branch on each computer and merge through a pull request. Do not edit the same branch concurrently and do not force-push `main`.

## Recovery Rules

- If `git pull --ff-only` fails, stop and inspect the local and remote commits before merging or rebasing.
- If a secret is committed, revoke or rotate it immediately; deleting the file in a later commit is not enough.
- If generated data is too large for Git, keep it in external storage and document its location and reproduction command in `HANDOFF.md`.
