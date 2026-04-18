# Project Status

## Current Goal
- Package the project for portfolio delivery around one high-signal entry point: a polished README first screen.
- Keep the deployment guidance display-first inside the README, with same-image packaging for OpenViking so the project stays easy to run and consistent.

## Current Memory Files
- `AGENTS.md`
- `.project-loop/PLAN.md`
- `PROJECT_STATUS.md`
- `PROJECT_PLAN.md`
- `progress.md`
- `data/loop_state.json`

## Current State
- The immediate focus is presentation and reproducibility rather than product expansion.
- The README has been rewritten into the requested five-part structure and is now the primary showcase surface.
- The standalone demo website is no longer a goal.
- The README now centers on a one-sentence description, a Mermaid architecture diagram, core design decisions, RFC links, and quick start guidance.
- The `app/` tree is already reasonably split by responsibility; further classification is a later cleanup item, not the current priority.
- Memory should be shown through visible behavior changes: before/after comparison, a memory-updated cue, and traceable source references.
- The task-memory demo should emphasize task progress continuity, not a generic prompt effect.
- OpenViking is still the main runtime dependency for memory; for Docker/demo purposes, the preferred approach is to bundle it into the same image first.
- Work has not started on the final README media polish yet; the current phase is still tightening the first-screen presentation and the quick-start wording.

## Suggested Next Step
- Verify the rendered README on GitHub, then tighten the GIF caption and quick-start text if needed.
