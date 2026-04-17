# Working Plan

## Current Goal
- Turn the project into a portfolio-ready demo with two primary entry points: a strong README first screen and a clickable demo website.
- For the demo deployment path, prefer packaging OpenViking as a same-image dependency so the showcase is easy to run and consistent across machines.

## Active Checklist
- [x] Define the README first-screen structure: one-sentence value proposition, a 30-second GIF, and short entry buttons.
- [ ] Define 4-5 fixed demo scenarios covering document summary, document Q&A, durable memory, optional web search, and knowledge-base management.
- [ ] Define how memory is shown as a visible before/after change, with a subtle "memory updated" cue and traceable source references.
- [ ] Define one task-memory demo path: task setup -> document summary -> follow-up question -> task progress recap.
- [ ] Define the demo website implementation approach, prioritizing zero API cost and stable playback over live inference.
- [ ] Define the GitHub Pages / static hosting approach so the demo has a directly clickable link.
- [ ] Define the same-image Docker packaging approach for OpenViking, including the minimum volume list and configuration paths.

## Decisions
- Default to a Chinese README as the main entry point; keep English as supporting content.
- Prioritize "easy to understand, easy to click, easy to run" over rate limiting, account systems, or paid online APIs.
- Build the demo from fixed scenarios and locally captured real outputs, not handwritten fake answers.
- Mark demo outputs clearly as "for display only; captured from real local runs."
- Showcase memory with three visible behaviors: before/after comparison, a memory-updated cue, and traceable sources.
- Show task memory as "task progress continuation" rather than as a generic system prompt effect.
- Keep the README first screen as a fast entry point, with deeper run/architecture details lower in the document.
- For display-oriented Docker, prefer bundling OpenViking into the same image first; split services later only if needed.

## Blockers
- The GIF recording script and final capture scope are not frozen yet.
- The demo site hosting choice is not fully finalized yet: static preview page, GitHub Pages, or a repo subpath.
- The exact capture/cleanup/freeze rules for "real run result snapshots" are still not finalized.
- The same-image Docker layout still needs a clear volume list and path map.
- We still need to decide whether the repo should keep planning files like `AGENTS.md` and `.project-loop/PLAN.md` in the published GitHub history.

## Next Step
- Lock the README first-screen GIF script and the demo page structure, then continue with the 4-5 fixed scenarios and the deployment plan.
