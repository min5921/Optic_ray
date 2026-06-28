# Project Handoff

Last updated: 2026-06-28 (Asia/Seoul)

## Current State

- The coherent FMCW LiDAR design documents have been imported into the project root.
- Multi-computer Git, Codex, line-ending, secret, and generated-output conventions are configured.
- GitHub remote `origin` is connected to `https://github.com/min5921/Optic_ray.git`, and `main` is synchronized.
- No simulator source code has been implemented yet.
- The active implementation target is Phase 1: FMCW single-target CPU reference.
- The Python virtual environment and dependencies have not been installed or verified yet.

## Decisions to Preserve

- Physics and development constraints in `CODEX_MASTER_PROMPT.md` and `AGENTS.md` are authoritative.
- CPU correctness and analytical validation come before optional GPU acceleration.
- Project state moves between computers through Git; credentials and machine-local Codex state do not.
- Conversation history may be opened with the same OpenAI account, but this file remains the durable source of continuation context.

## Best Next Action

Create the local Python virtual environment, install the base dependencies, and then implement only Phase 1 from `TASKS.md`.

## Verification

- Documentation structure reviewed.
- Git safety files and multi-computer workflow added.
- Local `main` is configured to track `origin/main` on GitHub.
- Simulator tests: not available yet because Phase 1 has not been implemented.

## Session Update Template

When ending a future session, replace the current-state sections above and record:

- What changed
- Important decisions and assumptions
- Tests run and their results
- Known issues or uncommitted work
- The single best next action
