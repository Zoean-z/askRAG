# Project Status

## Current Goal
- Package the project for portfolio delivery around two high-signal entry points: a strong README first screen and a clickable demo website.
- Keep the deployment path display-first: same-image packaging for OpenViking, so the demo stays easy to run and consistent.

## Current Memory Files
- `AGENTS.md`
- `.project-loop/PLAN.md`
- `PROJECT_STATUS.md`
- `PROJECT_PLAN.md`
- `progress.md`
- `data/loop_state.json`

## Current State
- The immediate focus is presentation and reproducibility rather than product expansion.
- The README first screen direction is already set: one-sentence value proposition, a 30-second GIF stored in the repo, and clear buttons for demo, local run, and architecture/details.
- The demo direction is fixed: a small set of pre-recorded scenarios, with outputs captured from real local runs instead of hand-written mock answers.
- Memory should be shown through visible behavior changes: before/after comparison, a memory-updated cue, and traceable source references.
- The task-memory demo should emphasize task progress continuity, not a generic prompt effect.
- OpenViking is still the main runtime dependency for memory; for Docker/demo purposes, the preferred approach is to bundle it into the same image first.
- Work has not started on the final demo implementation yet; the current phase is still planning the exact capture and deployment path.

## Suggested Next Step
- Finalize the README first-screen GIF script and the demo page structure, then continue with the 4-5 fixed scenarios and the same-image Docker packaging plan.
