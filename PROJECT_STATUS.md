# Project Status

## Current Goal
- Reduce end-to-end chat latency safely, with priority on the streaming path and the most obvious serial bottlenecks.

## Current Memory Files
- `AGENTS.md`
- `.project-loop/PLAN.md`
- `PROJECT_STATUS.md`
- `PROJECT_PLAN.md`
- `progress.md`
- `data/loop_state.json`

## Current State
- The repository goal has shifted from web-failure wording to performance diagnosis and safe latency reduction.
- `suggestion.md` provides a useful hypothesis list, but it was written against an older commit and needs validation against the current code.
- The streaming graph path now runs the preplan trio through a shared parallel helper instead of manually nesting the three nodes in sequence.
- `/ask/stream` now emits lightweight diagnostic markers at request start and completion so real latency can be measured from logs.
- OpenViking memory reads still depend on synchronous CLI subprocess calls and multi-query serial search, so they remain a likely latency contributor.
- Direct web search and retrieval web steps still include multiple model and tool calls, but they should be optimized only after real timing data is collected.
- Local compile and relevant unit tests pass, but live request verification is still pending because the local backend process is not currently running.

## Suggested Next Step
- Start the local service, run one real slow `/ask/stream` request, and confirm the new preplan and request-level timing diagnostics before moving on to OpenViking caching.
