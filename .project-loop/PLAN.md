# Working Plan

## Current Goal
- Turn the project into a portfolio-ready README-first showcase with one polished first screen, a short GIF, and clear run/deploy guidance.
- Do not build a standalone demo website; keep the demo experience inside the README itself.
- For the deployment guidance shown in the README, prefer packaging OpenViking as a same-image dependency so the project is easy to run and consistent across machines.

## Active Checklist
- [ ] Finalize the README first-screen copy: one-sentence value proposition, short GIF caption, and clear run/deploy entry links.
- [ ] Define how memory is shown as a visible before/after change, with a subtle "memory updated" cue and traceable source references.
- [ ] Define one task-memory demo path: task setup -> document summary -> follow-up question -> task progress recap.
- [ ] Define the README-only media plan: GIF capture scope, file location, and how it will be referenced from the first screen.
- [ ] Define the same-image Docker packaging guidance for OpenViking, including the minimum volume list and configuration paths.

## Decisions
- Default to a Chinese README as the main entry point; keep English as supporting content.
- Prioritize "easy to understand and easy to run" over rate limiting, account systems, or paid online APIs.
- Build the showcase from locally captured real outputs embedded in the README, not handwritten fake answers.
- Mark showcased outputs clearly as "for display only; captured from real local runs."
- Showcase memory with three visible behaviors: before/after comparison, a memory-updated cue, and traceable sources.
- Show task memory as "task progress continuation" rather than as a generic system prompt effect.
- Keep the README first screen as a fast entry point, with deeper run/architecture details lower in the document.
- For display-oriented Docker, prefer bundling OpenViking into the same image first; split services later only if needed.

## Blockers
- The GIF recording script and final capture scope are not frozen yet.
- The exact capture/cleanup/freeze rules for "real run result snapshots" are still not finalized.
- The same-image Docker layout still needs a clear volume list and path map.
- We still need to decide whether the repo should keep planning files like `AGENTS.md` and `.project-loop/PLAN.md` in the published GitHub history.

## Next Step
- Lock the README first-screen GIF script and the exact first-screen copy, then finalize the Docker/run guidance that will appear in the README.
