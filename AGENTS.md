# AGENTS.md

This file defines the shared working rules for humans and coding agents on every computer.

## Start of Every Session

1. Read `HANDOFF.md` for the current state and next action.
2. Read `docs/PROJECT_VISION.md` and keep work within the active phase.
3. Use the files under `docs/original/coherent-fmcw-lidar-sim-docs/` as preserved physics and implementation references.
4. Run `git status --short --branch` and inspect existing changes before editing.
5. Do not overwrite or discard changes that are not part of the current task.

## Project Goal

Build a Python simulator for user-defined point, line, and area beams passing through collimator optics and custom scanners, interacting with material-assigned targets, and returning optical power or coherent FMCW signals to a receiver.

## Non-Negotiable Physics Rules

- Compute speckle as `E_rx = sum(A_i * exp(1j * phi_i))`, then `P_rx = abs(E_rx) ** 2`.
- Never replace coherent field summation with a sum of scatterer powers.
- Keep field amplitude and optical power as separate quantities.
- Treat STL triangles as geometry and normal references, not as optical scatterers.
- Reuse a fixed surface scatterer map across scan positions; do not regenerate phases per pixel.
- Use SI units internally and radians for internal angles.
- Use `complex128` for CPU reference validation. Lower precision is optional only for an explicitly tested GPU path.
- Every stochastic model must accept a seed and be reproducible.

## Development Order and Quality

- Follow the phase order in `docs/PROJECT_VISION.md`; requirements confirmation and Phase 0 are the current targets.
- Establish a correct NumPy/CPU reference before adding GPU acceleration.
- Keep optional GPU packages out of the base runtime path.
- Add or update tests with each behavior change. Validate simple analytical cases before complex scenes.
- Prefer small, typed, documented modules under `src/lidarsim/`.
- Do not add generated results, virtual environments, credentials, or machine-local Codex state to Git.

## End of Every Session

1. Run the tests relevant to the changes and record the command/result in `HANDOFF.md`.
2. Update progress in `docs/PROJECT_VISION.md` only for work that is complete and verified.
3. Update `HANDOFF.md` with the current state, decisions, changed files, and the single best next action.
4. Review `git diff` and `git status --short --branch`.
5. Commit and push only when the user asks or the session explicitly includes Git synchronization.

## Multi-Computer Coordination

- Use one active computer on `main` at a time.
- At session start, fetch and fast-forward before editing.
- At session end, leave a clean, pushed commit before switching computers.
- Use a feature branch if two computers must work in parallel.
- Never force-push shared branches.
- Follow `docs/MULTI_PC_WORKFLOW.md` for exact commands.
